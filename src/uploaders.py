from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class DraftUploader(Protocol):
    platform: str

    def upload_draft(self, asset_path: Path, caption: str, metadata: dict[str, str]) -> dict[str, str]:
        ...


@dataclass
class DryRunUploader:
    platform: str

    def upload_draft(self, asset_path: Path, caption: str, metadata: dict[str, str]) -> dict[str, str]:
        return {
            "status": "draft_uploaded",
            "draft_id": f"dryrun_{self.platform}_{metadata['asset_id']}",
            "asset_path": str(asset_path),
            "caption": caption,
        }


def build_uploaders(dry_run: bool = True) -> dict[str, DraftUploader]:
    # All adapters are dry-run until official draft flows are confirmed.
    return {
        "instagram": DryRunUploader("instagram"),
        "tiktok": DryRunUploader("tiktok"),
        "youtube": DryRunUploader("youtube"),
    }
