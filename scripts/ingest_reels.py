from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.common.hashing import sha256_file
from scripts.common.logging import configure_logging
from scripts.common.models import IngestionCandidate
from scripts.common.supabase_client import SupabaseClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest local MP4 reels into Supabase Storage and Postgres.")
    parser.add_argument("--batch", required=True, help="Batch name such as batch_001")
    parser.add_argument("--input", required=True, type=Path, help="Folder containing exported MP4 reels")
    parser.add_argument("--workspace", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _file_sort_key(path: Path) -> tuple[int, str]:
    stem = path.stem
    if stem.isdigit():
        return (0, f"{int(stem):09d}")
    return (1, stem.lower())


def main() -> None:
    args = parse_args()
    configure_logging()
    workspace = args.workspace.resolve()
    client = SupabaseClient(workspace)

    files = sorted(
        (path for path in args.input.resolve().iterdir() if path.is_file() and path.suffix.lower() == ".mp4"),
        key=_file_sort_key,
    )
    if not files:
        raise SystemExit(f"No MP4 files found in {args.input}")

    next_sequence = client.get_max_sequence_index() + 1
    for offset, file_path in enumerate(files):
        content_hash = sha256_file(file_path)
        if client.reel_exists_by_hash(content_hash):
            logging.info("skip duplicate content_hash=%s file=%s", content_hash, file_path.name)
            continue

        candidate = IngestionCandidate(
            local_path=file_path,
            sequence_index=next_sequence + offset,
            batch_name=args.batch,
            storage_path=f"{args.batch}/{file_path.name}",
            content_hash=content_hash,
        )
        logging.info("ingest sequence=%s file=%s storage=%s", candidate.sequence_index, file_path.name, candidate.storage_path)
        if args.dry_run:
            continue

        client.upload_video(candidate.local_path, candidate.storage_path)
        reel_row = client.insert_reel(candidate)
        client.insert_default_platform_statuses(reel_row["id"])


if __name__ == "__main__":
    main()
