from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

from src.env import load_dotenv


class YoutubeClient:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        load_dotenv(workspace)
        self.token_path = workspace / "state" / "youtube_oauth.json"
        self.client_id = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
        self.refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN", "").strip()
        if (not self.client_id or not self.client_secret or not self.refresh_token) and not self.token_path.exists():
            raise RuntimeError(
                "YouTube OAuth credentials are missing. Set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN or run `python3 scripts/youtube_oauth.py` first."
            )

    def upload_video(
        self,
        video_bytes: bytes,
        *,
        filename: str,
        title: str,
        description: str,
        publish_at: str,
        category_id: str = "22",
    ) -> str:
        youtube = self._build_service()
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": publish_at,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = self._build_media(video_bytes)
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response: dict[str, Any] | None = None
        while response is None:
            _, response = request.next_chunk()

        video_id = response.get("id")
        if not video_id:
            raise RuntimeError(f"YouTube upload for {filename} did not return a video ID")
        return str(video_id)

    def _build_service(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        payload = self._load_payload()
        credentials = Credentials(
            token=None,
            refresh_token=payload["refresh_token"],
            token_uri=payload["token_uri"],
            client_id=payload["client_id"],
            client_secret=payload["client_secret"],
            scopes=payload.get("scopes") or ["https://www.googleapis.com/auth/youtube.upload"],
        )
        credentials.refresh(Request())
        return build("youtube", "v3", credentials=credentials, cache_discovery=False)

    def _build_media(self, video_bytes: bytes):
        from googleapiclient.http import MediaIoBaseUpload

        return MediaIoBaseUpload(
            io.BytesIO(video_bytes),
            mimetype="video/mp4",
            resumable=True,
        )

    def _load_payload(self) -> dict[str, Any]:
        if self.client_id and self.client_secret and self.refresh_token:
            return {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": ["https://www.googleapis.com/auth/youtube.upload"],
            }
        return json.loads(self.token_path.read_text(encoding="utf-8"))
