from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.env import load_dotenv


class EnvYoutubeTests(unittest.TestCase):
    def test_load_dotenv_reads_youtube_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / ".env").write_text(
                "YOUTUBE_CLIENT_ID=abc\nYOUTUBE_CLIENT_SECRET=def\n",
                encoding="utf-8",
            )
            load_dotenv(workspace)
            import os

            self.assertEqual(os.getenv("YOUTUBE_CLIENT_ID"), "abc")
            self.assertEqual(os.getenv("YOUTUBE_CLIENT_SECRET"), "def")


if __name__ == "__main__":
    unittest.main()
