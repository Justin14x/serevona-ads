from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


PLATFORMS = ("instagram", "tiktok", "youtube")
BATCH_LIMITS = {"instagram": 5, "youtube": 5, "tiktok": 2}


@dataclass(frozen=True)
class ReelRecord:
    id: str
    sequence_index: int
    file_path: str
    batch_name: str | None = None
    header_text: str | None = None
    subtitle_text: str | None = None
    caption: str | None = None
    content_hash: str | None = None


@dataclass(frozen=True)
class PlatformStatusRecord:
    id: str
    reel_id: str
    platform: str
    status: str
    attempt_count: int = 0
    uploaded_at: datetime | None = None
    posted_at: datetime | None = None
    platform_post_id: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class PendingUpload:
    reel_id: str
    sequence_index: int
    file_path: str
    platform_status_id: str
    platform: str
    caption: str | None = None
    header_text: str | None = None
    subtitle_text: str | None = None


@dataclass(frozen=True)
class IngestionCandidate:
    local_path: Path
    sequence_index: int
    batch_name: str
    storage_path: str
    content_hash: str
