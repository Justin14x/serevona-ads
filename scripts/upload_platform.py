from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.common.logging import configure_logging
from scripts.common.models import BATCH_LIMITS
from scripts.common.supabase_client import SupabaseClient, utc_now_iso


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run or stub uploader for a single platform queue.")
    parser.add_argument("--workspace", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main(platform: str) -> int:
    args = parse_args()
    configure_logging()
    client = SupabaseClient(args.workspace.resolve())
    limit = args.limit or BATCH_LIMITS[platform]
    batch = client.select_next_pending(platform, limit)
    if args.dry_run:
        print(
            json.dumps(
                [
                    {
                        "platform": item.platform,
                        "reel_id": item.reel_id,
                        "sequence_index": item.sequence_index,
                        "file_path": item.file_path,
                    }
                    for item in batch
                ],
                indent=2,
            )
        )
        return 0

    for item in batch:
        client.update_status(item.reel_id, platform, "queued")
        client.update_status(
            item.reel_id,
            platform,
            "uploaded",
            uploaded_at=utc_now_iso(),
            platform_post_id=f"stub_{platform}_{item.sequence_index:03d}",
        )
    print(f"{platform}: uploaded {len(batch)} reels in stub mode")
    return 0
