from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import requests


AUTHORIZE_URL = "https://www.canva.com/api/oauth/authorize"
TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
CAPABILITIES_URL = "https://api.canva.com/rest/v1/users/me/capabilities"
BRAND_TEMPLATE_DATASET_URL = "https://api.canva.com/rest/v1/brand-templates/{brand_template_id}/dataset"

DEFAULT_SCOPES = [
    "asset:read",
    "asset:write",
    "brandtemplate:content:read",
    "brandtemplate:meta:read",
    "design:content:read",
    "design:content:write",
    "design:meta:read",
    "profile:read",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _base64url_sha256(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _build_basic_auth(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


@dataclass(frozen=True)
class OAuthSession:
    state: str
    code_verifier: str
    redirect_uri: str
    scopes: list[str]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "code_verifier": self.code_verifier,
            "redirect_uri": self.redirect_uri,
            "scopes": self.scopes,
            "created_at": self.created_at,
        }


class TokenStore:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.session_path = state_dir / "canva_oauth_session.json"
        self.token_path = state_dir / "canva_tokens.json"

    def save_session(self, session: OAuthSession) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.session_path.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")

    def load_session(self) -> OAuthSession:
        if not self.session_path.exists():
            raise RuntimeError("No pending Canva OAuth session found. Start with --canva-auth-start.")
        payload = json.loads(self.session_path.read_text(encoding="utf-8"))
        return OAuthSession(
            state=payload["state"],
            code_verifier=payload["code_verifier"],
            redirect_uri=payload["redirect_uri"],
            scopes=list(payload["scopes"]),
            created_at=payload["created_at"],
        )

    def clear_session(self) -> None:
        if self.session_path.exists():
            self.session_path.unlink()

    def save_tokens(self, payload: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_tokens(self) -> dict[str, Any]:
        if not self.token_path.exists():
            raise RuntimeError("No Canva tokens found. Run --canva-auth-start and complete the callback first.")
        return json.loads(self.token_path.read_text(encoding="utf-8"))


def create_oauth_session(redirect_uri: str, scopes: list[str]) -> OAuthSession:
    code_verifier = secrets.token_urlsafe(72)
    state = secrets.token_urlsafe(48)
    return OAuthSession(
        state=state,
        code_verifier=code_verifier,
        redirect_uri=redirect_uri,
        scopes=scopes,
        created_at=_utc_now().replace(microsecond=0).isoformat(),
    )


def build_authorization_url(client_id: str, session: OAuthSession) -> str:
    scope_value = quote(" ".join(session.scopes), safe="")
    redirect_value = quote(session.redirect_uri, safe="")
    state_value = quote(session.state, safe="")
    code_challenge = _base64url_sha256(session.code_verifier)
    return (
        f"{AUTHORIZE_URL}?code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&scope={scope_value}"
        f"&response_type=code"
        f"&client_id={quote(client_id, safe='')}"
        f"&state={state_value}"
        f"&redirect_uri={redirect_value}"
    )


def exchange_code_for_tokens(code: str, session: OAuthSession) -> dict[str, Any]:
    client_id = _require_env("CANVA_CLIENT_ID")
    client_secret = _require_env("CANVA_CLIENT_SECRET")
    response = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {_build_basic_auth(client_id, client_secret)}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": session.code_verifier,
            "redirect_uri": session.redirect_uri,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    payload["created_at"] = _utc_now().replace(microsecond=0).isoformat()
    payload["redirect_uri"] = session.redirect_uri
    return payload


def refresh_access_token(token_store: TokenStore) -> dict[str, Any]:
    tokens = token_store.load_tokens()
    client_id = _require_env("CANVA_CLIENT_ID")
    client_secret = _require_env("CANVA_CLIENT_SECRET")
    refresh_token = tokens.get("refresh_token", "").strip()
    if not refresh_token:
        raise RuntimeError("Saved Canva tokens do not include a refresh token")
    response = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {_build_basic_auth(client_id, client_secret)}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    payload["created_at"] = _utc_now().replace(microsecond=0).isoformat()
    payload["redirect_uri"] = tokens.get("redirect_uri")
    token_store.save_tokens(payload)
    return payload


def get_valid_access_token(token_store: TokenStore) -> str:
    tokens = token_store.load_tokens()
    created_at = _parse_iso(tokens.get("created_at"))
    expires_in = int(tokens.get("expires_in", 0))
    if not created_at or not expires_in:
        refreshed = refresh_access_token(token_store)
        return refreshed["access_token"]

    expiry = created_at + timedelta(seconds=expires_in)
    if _utc_now() >= expiry - timedelta(minutes=5):
        refreshed = refresh_access_token(token_store)
        return refreshed["access_token"]
    return tokens["access_token"]


def fetch_capabilities(access_token: str) -> dict[str, Any]:
    response = requests.get(
        CAPABILITIES_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_brand_template_dataset(access_token: str, brand_template_id: str) -> dict[str, Any]:
    response = requests.get(
        BRAND_TEMPLATE_DATASET_URL.format(brand_template_id=brand_template_id),
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


class _CallbackHandler(BaseHTTPRequestHandler):
    server_version = "SerevonaCanvaOAuth/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != self.server.callback_path:
            self.send_error(404, "Unknown callback path")
            return
        query = parse_qs(parsed.query)
        self.server.oauth_result = {
            "code": query.get("code", [None])[0],
            "state": query.get("state", [None])[0],
            "error": query.get("error", [None])[0],
            "error_description": query.get("error_description", [None])[0],
        }
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            (
                "<html><body><h1>Canva authorization received</h1>"
                "<p>You can close this tab and return to the terminal.</p></body></html>"
            ).encode("utf-8")
        )

    def log_message(self, format: str, *args: object) -> None:
        del format, args


class _OAuthServer(HTTPServer):
    def __init__(self, server_address: tuple[str, int], handler: type[_CallbackHandler], callback_path: str) -> None:
        super().__init__(server_address, handler)
        self.callback_path = callback_path
        self.oauth_result: dict[str, Any] | None = None


def wait_for_callback(redirect_uri: str, timeout_seconds: int) -> dict[str, Any]:
    parsed = urlparse(redirect_uri)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Local callback waiting only supports http://127.0.0.1 or http://localhost redirect URIs")
    if parsed.port is None:
        raise RuntimeError("Redirect URI must include a port")

    server = _OAuthServer((parsed.hostname, parsed.port), _CallbackHandler, parsed.path or "/")
    server.timeout = 1

    def _serve() -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline and server.oauth_result is None:
            server.handle_request()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    thread.join(timeout_seconds + 1)
    server.server_close()
    if server.oauth_result is None:
        raise TimeoutError(f"Timed out waiting for Canva OAuth callback after {timeout_seconds} seconds")
    return server.oauth_result


def start_authorization(state_dir: Path, scopes: list[str]) -> str:
    client_id = _require_env("CANVA_CLIENT_ID")
    redirect_uri = _require_env("CANVA_REDIRECT_URI")
    token_store = TokenStore(state_dir)
    session = create_oauth_session(redirect_uri=redirect_uri, scopes=scopes)
    token_store.save_session(session)
    return build_authorization_url(client_id, session)


def complete_authorization(state_dir: Path, code: str | None = None, state: str | None = None) -> dict[str, Any]:
    token_store = TokenStore(state_dir)
    session = token_store.load_session()

    if code is None:
        callback = wait_for_callback(session.redirect_uri, timeout_seconds=180)
        if callback.get("error"):
            raise RuntimeError(
                f"Canva authorization failed: {callback['error']} {callback.get('error_description') or ''}".strip()
            )
        code = callback.get("code")
        state = callback.get("state")

    if not code:
        raise RuntimeError("No authorization code received from Canva")
    if state and state != session.state:
        raise RuntimeError("OAuth state mismatch. Stop and start the authorization flow again.")

    tokens = exchange_code_for_tokens(code=code, session=session)
    token_store.save_tokens(tokens)
    token_store.clear_session()
    return tokens
