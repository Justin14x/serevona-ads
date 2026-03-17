from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.common.logging import configure_logging
from scripts.common.supabase_client import SupabaseClient, utc_now_iso


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update or reset a platform status for a reel.")
    parser.add_argument("--workspace", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--reel-id", required=True)
    parser.add_argument("--platform", required=True, choices=["instagram", "tiktok", "youtube"])
    parser.add_argument("--status", choices=["pending", "queued", "uploaded", "posted", "failed", "skipped"])
    parser.add_argument("--error-message")
    parser.add_argument("--platform-post-id")
    parser.add_argument("--reset", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging()
    client = SupabaseClient(args.workspace.resolve())
    if args.reset:
        client.reset_status(args.reel_id, args.platform)
        return
    if not args.status:
        raise SystemExit("--status is required unless --reset is used")
    client.update_status(
        args.reel_id,
        args.platform,
        args.status,
        uploaded_at=utc_now_iso() if args.status == "uploaded" else None,
        posted_at=utc_now_iso() if args.status == "posted" else None,
        platform_post_id=args.platform_post_id,
        error_message=args.error_message,
        increment_attempt=args.status == "failed",
    )


if __name__ == "__main__":
    main()
