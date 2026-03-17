from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.canva_oauth import OAuthSession, TokenStore, build_authorization_url, create_oauth_session


class CanvaOAuthTests(unittest.TestCase):
    def test_build_authorization_url_contains_pkce_and_scopes(self) -> None:
        session = create_oauth_session(
            redirect_uri="http://127.0.0.1:3000/oauth/callback",
            scopes=["design:content:read", "profile:read"],
        )
        url = build_authorization_url("client_123", session)
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(params["client_id"][0], "client_123")
        self.assertEqual(params["response_type"][0], "code")
        self.assertEqual(params["code_challenge_method"][0], "S256")
        self.assertEqual(params["redirect_uri"][0], "http://127.0.0.1:3000/oauth/callback")
        self.assertEqual(params["scope"][0], "design:content:read profile:read")

    def test_token_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = TokenStore(Path(tmp_dir))
            session = OAuthSession(
                state="abc",
                code_verifier="def",
                redirect_uri="http://127.0.0.1:3000/oauth/callback",
                scopes=["profile:read"],
                created_at="2026-03-15T00:00:00+00:00",
            )
            store.save_session(session)
            loaded = store.load_session()
            self.assertEqual(loaded.state, "abc")

            store.save_tokens({"access_token": "token", "refresh_token": "refresh", "expires_in": 14400})
            tokens = store.load_tokens()
            self.assertEqual(tokens["access_token"], "token")


if __name__ == "__main__":
    unittest.main()
