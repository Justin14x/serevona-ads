from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.common.logging import configure_logging
from scripts.common.models import BATCH_LIMITS
from scripts.common.supabase_client import SupabaseClient, utc_now_iso
from scripts.common.youtube_client import YoutubeClient
from scripts.common.youtube_schedule import (
    YOUTUBE_DESCRIPTION,
    YOUTUBE_TITLE,
    next_publish_slots,
    youtube_publish_at_iso,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload the next 5 pending YouTube reels and schedule them public.")
    parser.add_argument("--workspace", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging()
    workspace = args.workspace.resolve()
    client = SupabaseClient(workspace)
    batch = client.select_next_pending("youtube", BATCH_LIMITS["youtube"])
    slots = next_publish_slots(len(batch))

    if args.dry_run:
        print(
            json.dumps(
                [
                    {
                        "platform": item.platform,
                        "reel_id": item.reel_id,
                        "sequence_index": item.sequence_index,
                        "file_path": item.file_path,
                        "title": YOUTUBE_TITLE,
                        "publish_at": youtube_publish_at_iso(slot),
                    }
                    for item, slot in zip(batch, slots)
                ],
                indent=2,
            )
        )
        return 0

    youtube = YoutubeClient(workspace)
    uploaded = 0
    failures = 0
    for item, slot in zip(batch, slots):
        client.update_status(item.reel_id, "youtube", "queued")
        try:
            video_id = youtube.upload_video(
                client.download_video(item.file_path),
                filename=Path(item.file_path).name,
                title=YOUTUBE_TITLE,
                description=YOUTUBE_DESCRIPTION,
                publish_at=youtube_publish_at_iso(slot),
            )
            client.update_status(
                item.reel_id,
                "youtube",
                "uploaded",
                uploaded_at=utc_now_iso(),
                platform_post_id=video_id,
                error_message=None,
            )
            uploaded += 1
        except Exception as exc:
            client.update_status(
                item.reel_id,
                "youtube",
                "failed",
                error_message=str(exc),
                increment_attempt=True,
            )
            failures += 1

    print(f"youtube: uploaded={uploaded} failed={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
