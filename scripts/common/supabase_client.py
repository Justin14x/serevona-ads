from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from src.env import load_dotenv

from .models import BATCH_LIMITS, PLATFORMS, IngestionCandidate, PendingUpload


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SupabaseClient:
    def __init__(self, workspace: Path) -> None:
        load_dotenv(workspace)
        self.workspace = workspace
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.url or not self.key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        }

    def _db_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            **self._headers,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def get_max_sequence_index(self) -> int:
        response = requests.get(
            f"{self.url}/rest/v1/reels",
            headers=self._db_headers({"Range": "0-0"}),
            params={"select": "sequence_index", "order": "sequence_index.desc"},
            timeout=30,
        )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            return 0
        return int(rows[0]["sequence_index"])

    def reel_exists_by_hash(self, content_hash: str) -> bool:
        response = requests.get(
            f"{self.url}/rest/v1/reels",
            headers=self._db_headers(),
            params={"select": "id", "content_hash": f"eq.{content_hash}", "limit": "1"},
            timeout=30,
        )
        response.raise_for_status()
        return bool(response.json())

    def upload_video(self, local_path: Path, storage_path: str, upsert: bool = False) -> None:
        response = requests.post(
            f"{self.url}/storage/v1/object/reels/{storage_path}",
            headers={
                **self._headers,
                "Content-Type": "video/mp4",
                "x-upsert": "true" if upsert else "false",
            },
            data=local_path.read_bytes(),
            timeout=120,
        )
        response.raise_for_status()

    def insert_reel(self, candidate: IngestionCandidate) -> dict[str, Any]:
        response = requests.post(
            f"{self.url}/rest/v1/reels",
            headers=self._db_headers({"Prefer": "return=representation"}),
            json={
                "sequence_index": candidate.sequence_index,
                "file_path": candidate.storage_path,
                "batch_name": candidate.batch_name,
                "content_hash": candidate.content_hash,
            },
            timeout=30,
        )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            raise RuntimeError("Supabase did not return the inserted reel row")
        return rows[0]

    def insert_default_platform_statuses(self, reel_id: str) -> None:
        payload = [{"reel_id": reel_id, "platform": platform, "status": "pending"} for platform in PLATFORMS]
        response = requests.post(
            f"{self.url}/rest/v1/reel_platform_status",
            headers=self._db_headers({"Prefer": "resolution=merge-duplicates,return=representation"}),
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

    def select_next_pending(self, platform: str, limit: int | None = None) -> list[PendingUpload]:
        limit = limit or BATCH_LIMITS[platform]
        response = requests.get(
            f"{self.url}/rest/v1/reels",
            headers=self._db_headers(),
            params={
                "select": "id,sequence_index,file_path,caption,header_text,subtitle_text,reel_platform_status!inner(id,platform,status)",
                "is_active": "eq.true",
                "reel_platform_status.platform": f"eq.{platform}",
                "reel_platform_status.status": "eq.pending",
                "order": "sequence_index.asc",
                "limit": str(limit),
            },
            timeout=30,
        )
        response.raise_for_status()
        rows = response.json()
        batch: list[PendingUpload] = []
        for row in rows:
            status_row = row["reel_platform_status"][0]
            batch.append(
                PendingUpload(
                    reel_id=row["id"],
                    sequence_index=row["sequence_index"],
                    file_path=row["file_path"],
                    platform_status_id=status_row["id"],
                    platform=platform,
                    caption=row.get("caption"),
                    header_text=row.get("header_text"),
                    subtitle_text=row.get("subtitle_text"),
                )
            )
        return batch

    def update_status(
        self,
        reel_id: str,
        platform: str,
        status: str,
        *,
        uploaded_at: str | None = None,
        posted_at: str | None = None,
        platform_post_id: str | None = None,
        error_message: str | None = None,
        increment_attempt: bool = False,
    ) -> None:
        current_attempt = None
        if increment_attempt:
            current_attempt = self._get_attempt_count(reel_id, platform)
        payload: dict[str, Any] = {
            "status": status,
            "updated_at": utc_now_iso(),
            "error_message": error_message,
            "platform_post_id": platform_post_id,
        }
        if uploaded_at is not None:
            payload["uploaded_at"] = uploaded_at
        if posted_at is not None:
            payload["posted_at"] = posted_at
        if increment_attempt and current_attempt is not None:
            payload["attempt_count"] = current_attempt + 1

        response = requests.patch(
            f"{self.url}/rest/v1/reel_platform_status",
            headers=self._db_headers(),
            params={"reel_id": f"eq.{reel_id}", "platform": f"eq.{platform}"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

    def reset_status(self, reel_id: str, platform: str) -> None:
        response = requests.patch(
            f"{self.url}/rest/v1/reel_platform_status",
            headers=self._db_headers(),
            params={"reel_id": f"eq.{reel_id}", "platform": f"eq.{platform}"},
            json={
                "status": "pending",
                "uploaded_at": None,
                "posted_at": None,
                "platform_post_id": None,
                "error_message": None,
                "updated_at": utc_now_iso(),
            },
            timeout=30,
        )
        response.raise_for_status()

    def public_storage_url(self, storage_path: str) -> str:
        return f"{self.url}/storage/v1/object/public/reels/{quote(storage_path)}"

    def download_video(self, storage_path: str) -> bytes:
        response = requests.get(
            f"{self.url}/storage/v1/object/reels/{storage_path}",
            headers=self._headers,
            timeout=120,
        )
        response.raise_for_status()
        return response.content

    def _get_attempt_count(self, reel_id: str, platform: str) -> int:
        response = requests.get(
            f"{self.url}/rest/v1/reel_platform_status",
            headers=self._db_headers(),
            params={
                "select": "attempt_count",
                "reel_id": f"eq.{reel_id}",
                "platform": f"eq.{platform}",
                "limit": "1",
            },
            timeout=30,
        )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            return 0
        return int(rows[0].get("attempt_count") or 0)
