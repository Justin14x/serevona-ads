from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from google_auth_oauthlib.flow import InstalledAppFlow

from src.env import load_dotenv


YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a YouTube refresh token for the configured OAuth client.")
    parser.add_argument("--workspace", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--port", default=8765, type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace = args.workspace.resolve()
    load_dotenv(workspace)

    client_id = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise SystemExit("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET are required in .env")

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [f"http://127.0.0.1:{args.port}/"],
            }
        },
        scopes=YOUTUBE_SCOPES,
    )

    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=args.port,
        authorization_prompt_message="Open this URL in your browser to authorize YouTube upload access:\n{url}",
        success_message="YouTube authorization received. Return to the terminal.",
        open_browser=False,
        access_type="offline",
        prompt="consent",
    )

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "scopes": list(credentials.scopes or []),
    }
    token_path = workspace / "state" / "youtube_oauth.json"
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("YouTube OAuth complete.")
    print(f"Refresh token saved to {token_path}")


if __name__ == "__main__":
    main()
