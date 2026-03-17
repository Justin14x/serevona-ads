from __future__ import annotations

import os
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
        response = requests.post(
            f"{self.base_url}/sendMessage",
            data={"chat_id": self.chat_id, "text": text},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def send_video(self, video_bytes: bytes, filename: str, caption: str | None = None) -> dict:
        response = requests.post(
            f"{self.base_url}/sendVideo",
            data={"chat_id": self.chat_id, "caption": caption or ""},
            files={"video": (filename, video_bytes, "video/mp4")},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
