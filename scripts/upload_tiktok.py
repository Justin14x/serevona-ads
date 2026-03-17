from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.upload_platform import main


if __name__ == "__main__":
    raise SystemExit(main("tiktok"))
