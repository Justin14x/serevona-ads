from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.common.logging import configure_logging
from scripts.common.models import BATCH_LIMITS
from scripts.common.supabase_client import SupabaseClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select the next sequential pending reels per platform.")
    parser.add_argument("--workspace", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--platform", choices=["instagram", "tiktok", "youtube"], help="Optional single-platform selection")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging()
    client = SupabaseClient(args.workspace.resolve())
    platforms = [args.platform] if args.platform else ["instagram", "youtube", "tiktok"]
    selection = {
        platform: [
            {
                "reel_id": item.reel_id,
                "sequence_index": item.sequence_index,
                "file_path": item.file_path,
            }
            for item in client.select_next_pending(platform, BATCH_LIMITS[platform])
        ]
        for platform in platforms
    }
    print(json.dumps(selection, indent=2))


if __name__ == "__main__":
    main()
