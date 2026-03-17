from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.common.logging import configure_logging
from scripts.common.models import BATCH_LIMITS, PendingUpload
from scripts.common.supabase_client import SupabaseClient, utc_now_iso
from scripts.common.telegram_client import TelegramClient


@dataclass
class DeliveryGroup:
    reel_id: str
    sequence_index: int
    file_path: str
    platforms: list[str] = field(default_factory=list)
    items: list[PendingUpload] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send the next pending reel batch to Telegram.")
    parser.add_argument("--workspace", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--platforms",
        default="instagram,youtube,tiktok",
        help="Comma-separated platforms to deliver to Telegram (default: instagram,youtube,tiktok)",
    )
    return parser.parse_args()


def _selected_platforms(raw: str) -> list[str]:
    allowed = {"instagram", "youtube", "tiktok"}
    platforms = [entry.strip() for entry in raw.split(",") if entry.strip()]
    if not platforms:
        raise ValueError("At least one Telegram platform must be selected")
    unknown = [entry for entry in platforms if entry not in allowed]
    if unknown:
        raise ValueError(f"Unsupported Telegram platforms: {', '.join(unknown)}")
    return platforms


def _merge_batches(per_platform: dict[str, list[PendingUpload]], platforms: list[str]) -> list[DeliveryGroup]:
    by_reel: dict[str, DeliveryGroup] = {}
    for platform in platforms:
        for item in per_platform[platform]:
            group = by_reel.setdefault(
                item.reel_id,
                DeliveryGroup(
                    reel_id=item.reel_id,
                    sequence_index=item.sequence_index,
                    file_path=item.file_path,
                ),
            )
            group.platforms.append(platform)
            group.items.append(item)
    return sorted(by_reel.values(), key=lambda entry: entry.sequence_index)


def _summary_text(
    per_platform: dict[str, list[PendingUpload]],
    merged: list[DeliveryGroup],
    platforms: list[str],
) -> str:
    lines = [
        "Serevona daily batch",
        "",
        f"Unique reels: {len(merged)}",
        "",
        "Platforms:",
    ]
    for platform in platforms:
        label = "TikTok" if platform == "tiktok" else platform.title()
        lines.append(f"{label}: {len(per_platform[platform])}")
    lines.extend(
        [
            "",
        "Queue:",
        ]
    )
    for group in merged:
        lines.append(
            f"{group.sequence_index}. {Path(group.file_path).name} -> {', '.join(group.platforms)}"
        )
    return "\n".join(lines)


def _video_caption(group: DeliveryGroup) -> str:
    return f"Sequence {group.sequence_index}\nPlatforms: {', '.join(group.platforms)}"


def main() -> int:
    args = parse_args()
    configure_logging()
    workspace = args.workspace.resolve()
    client = SupabaseClient(workspace)
    telegram = TelegramClient(workspace)
    platforms = _selected_platforms(args.platforms)

    per_platform = {
        platform: client.select_next_pending(platform, BATCH_LIMITS[platform]) for platform in platforms
    }
    merged = _merge_batches(per_platform, platforms)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "summary": _summary_text(per_platform, merged, platforms),
                    "deliveries": [
                        {
                            "sequence_index": group.sequence_index,
                            "file_path": group.file_path,
                            "platforms": group.platforms,
                        }
                        for group in merged
                    ],
                },
                indent=2,
            )
        )
        return 0

    telegram.send_message(_summary_text(per_platform, merged, platforms))
    for group in merged:
        video_bytes = client.download_video(group.file_path)
        telegram.send_video(video_bytes, Path(group.file_path).name, _video_caption(group))

    posted_at = utc_now_iso()
    for platform, batch in per_platform.items():
        for item in batch:
            client.update_status(item.reel_id, platform, "posted", posted_at=posted_at)

    print(f"telegram: delivered {len(merged)} unique reels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
