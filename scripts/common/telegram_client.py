from __future__ import annotations

import os
import time
from pathlib import Path

import requests

from src.env import load_dotenv


class TelegramClient:
    def __init__(self, workspace: Path) -> None:
        load_dotenv(workspace)
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not self.token or not self.chat_id:
            raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, text: str) -> dict:
        return self._post_with_retry(
            "sendMessage",
            data={"chat_id": self.chat_id, "text": text},
            timeout=120,
        )

    def send_video(self, video_bytes: bytes, filename: str, caption: str | None = None) -> dict:
        return self._post_with_retry(
            "sendVideo",
            data={"chat_id": self.chat_id, "caption": caption or ""},
            files={"video": (filename, video_bytes, "video/mp4")},
            timeout=300,
        )

    def _post_with_retry(self, method: str, **kwargs) -> dict:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{self.base_url}/{method}",
                    **kwargs,
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout as exc:
                last_error = exc
                if attempt == 2:
                    break
                time.sleep(2 * (attempt + 1))
        assert last_error is not None
        raise last_error
