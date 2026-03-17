from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

from .canva_client import build_canva_client
from .canva_oauth import (
    DEFAULT_SCOPES,
    TokenStore,
    complete_authorization,
    fetch_capabilities,
    fetch_brand_template_dataset,
    get_valid_access_token,
    start_authorization,
)
from .captions import metadata_for_plan
from .env import load_dotenv
from .models import RenderedAsset, RuntimeSettings
from .planner import build_daily_plan
from .storage import (
    append_run_history,
    append_usage_records,
    load_hooks,
    load_platforms,
    load_subtitles,
    load_template_map,
    load_usage_log,
    utc_now_iso,
    write_json,
)
from .uploaders import build_uploaders
from .xlsx_inputs import build_plans_from_spreadsheet, import_spreadsheet_creatives


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Serevona daily short-form video batches.")
    parser.add_argument("--workspace", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--run-id", default=f"{datetime.now().date().isoformat()}_daily")
    parser.add_argument("--same-pair-cooldown-days", default=7, type=int)
    parser.add_argument("--image-cooldown-days", default=3, type=int)
    parser.add_argument("--sample", action="store_true", help="Allow placeholder image inventory for local dry runs.")
    parser.add_argument("--force", action="store_true", help="Re-render assets even if output files already exist.")
    parser.add_argument("--live-canva", action="store_true", help="Use live Canva mode instead of local mock rendering.")
    parser.add_argument("--live-uploads", action="store_true", help="Reserved for future uploader integrations.")
    parser.add_argument("--xlsx-source", type=Path, help="Read Canva field rows and embedded images from an .xlsx workbook.")
    parser.add_argument("--canva-auth-start", action="store_true", help="Create a Canva OAuth URL and save a local PKCE session.")
    parser.add_argument("--canva-auth-finish", action="store_true", help="Wait for or complete a Canva OAuth callback and save tokens.")
    parser.add_argument("--canva-auth-code", help="Authorization code returned by Canva.")
    parser.add_argument("--canva-auth-state", help="State value returned by Canva.")
    parser.add_argument(
        "--canva-scopes",
        nargs="+",
        default=DEFAULT_SCOPES,
        help="Scopes to request during Canva OAuth. Defaults to the project's MVP Canva scopes.",
    )
    parser.add_argument("--canva-check-capabilities", action="store_true", help="Call Canva's capabilities endpoint with the saved token.")
    parser.add_argument("--canva-check-template", action="store_true", help="Fetch the configured Canva Brand Template dataset.")
    return parser.parse_args()


def build_settings(args: argparse.Namespace) -> RuntimeSettings:
    workspace = args.workspace.resolve()
    load_dotenv(workspace)
    return RuntimeSettings(
        workspace=workspace,
        config_dir=workspace / "config",
        assets_dir=workspace / "assets",
        outputs_dir=workspace / "outputs",
        state_dir=workspace / "state",
        run_id=args.run_id,
        canva_mode="live" if args.live_canva or os.getenv("CANVA_MODE") == "live" else "mock",
        same_pair_cooldown_days=args.same_pair_cooldown_days,
        image_cooldown_days=args.image_cooldown_days,
        dry_run_uploads=not args.live_uploads,
        sample=args.sample,
        force=args.force,
        xlsx_source=args.xlsx_source.resolve() if args.xlsx_source else None,
    )


def execute_batch(settings: RuntimeSettings) -> dict:
    platforms = load_platforms(settings.config_dir)
    template_map = load_template_map(settings.config_dir)
    if settings.xlsx_source is not None:
        creatives = import_spreadsheet_creatives(settings.xlsx_source, settings.workspace, template_map)
        plans = build_plans_from_spreadsheet(settings, platforms, creatives)
    else:
        hooks = load_hooks(settings.config_dir)
        subtitles = load_subtitles(settings.config_dir)
        usage_log = load_usage_log(settings.state_dir)
        plans = build_daily_plan(settings, hooks, subtitles, platforms, usage_log)
    canva_client = build_canva_client(settings, template_map)
    uploaders = build_uploaders(dry_run=settings.dry_run_uploads)

    generated: list[RenderedAsset] = []
    failed: list[dict] = []
    for plan in plans:
        try:
            export_path, thumbnail_path = canva_client.render_asset(
                plan=plan,
                template_map=template_map,
                outputs_dir=settings.outputs_dir,
                force=settings.force,
            )
            rendered = RenderedAsset(plan=plan, export_path=export_path, thumbnail_path=thumbnail_path)
            uploader = uploaders[plan.platform]
            upload_result = uploader.upload_draft(export_path, plan.caption, metadata_for_plan(plan))
            rendered.upload_status[plan.platform] = upload_result["status"]
            rendered.upload_refs[plan.platform] = upload_result
            generated.append(rendered)
        except Exception as exc:  # noqa: BLE001
            failed.append(
                {
                    "asset_id": plan.asset_id,
                    "platform": plan.platform,
                    "error": str(exc),
                }
            )

    summary = {
        "run_id": settings.run_id,
        "created_at": utc_now_iso(),
        "generated_count": len(generated),
        "failed_count": len(failed),
        "assets": [
            {
                "run_id": asset.plan.run_id,
                "asset_id": asset.plan.asset_id,
                "platforms": [asset.plan.platform],
                "image_id": asset.plan.image_id,
                "hook_id": asset.plan.hook.id,
                "subtitle_id": asset.plan.subtitle.id,
                "header_text": asset.plan.hook.text,
                "subtitle_text": asset.plan.subtitle.text,
                "caption": asset.plan.caption,
                "export_path": str(asset.export_path.relative_to(settings.workspace)),
                "thumbnail_path": str(asset.thumbnail_path.relative_to(settings.workspace)),
                "upload_status": asset.upload_status,
                "upload_refs": asset.upload_refs,
                "created_at": utc_now_iso(),
            }
            for asset in generated
        ],
        "failed": failed,
    }
    write_json(settings.outputs_dir / f"{settings.run_id}_summary.json", summary)
    append_run_history(settings.state_dir, summary)
    append_usage_records(settings.state_dir, summary["assets"])
    return summary


def handle_canva_auth(args: argparse.Namespace) -> int:
    workspace = args.workspace.resolve()
    load_dotenv(workspace)
    state_dir = workspace / "state"

    if args.canva_auth_start:
        url = start_authorization(state_dir=state_dir, scopes=args.canva_scopes)
        print("Open this URL in your browser and approve the Canva integration:\n")
        print(url)
        print("\nThen run: python3 -m src.main --canva-auth-finish")
        return 0

    if args.canva_auth_finish:
        tokens = complete_authorization(
            state_dir=state_dir,
            code=args.canva_auth_code,
            state=args.canva_auth_state,
        )
        print("Canva OAuth complete.")
        print(f"Token type: {tokens.get('token_type', 'unknown')}")
        print(f"Scopes: {tokens.get('scope', '')}")
        print(f"Expires in: {tokens.get('expires_in', 'unknown')} seconds")
        return 0

    if args.canva_check_capabilities:
        token_store = TokenStore(state_dir)
        payload = fetch_capabilities(get_valid_access_token(token_store))
        print(payload)
        return 0

    if args.canva_check_template:
        template_map = load_template_map(workspace / "config")
        token_store = TokenStore(state_dir)
        payload = fetch_brand_template_dataset(
            access_token=get_valid_access_token(token_store),
            brand_template_id=os.getenv("CANVA_TEMPLATE_ID", template_map.template_id).strip(),
        )
        print(payload)
        return 0

    return 1


def main() -> None:
    args = parse_args()
    if args.canva_auth_start or args.canva_auth_finish or args.canva_check_capabilities or args.canva_check_template:
        raise SystemExit(handle_canva_auth(args))
    settings = build_settings(args)
    summary = execute_batch(settings)
    print(
        f"Run {summary['run_id']}: generated={summary['generated_count']} "
        f"failed={summary['failed_count']}"
    )


if __name__ == "__main__":
    main()
