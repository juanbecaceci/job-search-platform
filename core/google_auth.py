"""Shared Google OAuth credential loading for the Sheets and Drive tools.

Two things this fixes over the per-tool auth it replaces:

1. **Never opens a browser from a server.** `get_credentials(interactive=False)`
   raises `GoogleAuthError` with an actionable message instead of calling
   `flow.run_local_server()`. A job handler that pops an OAuth window would hang
   the request thread until it timed out, on a machine nobody is looking at.
2. **One token for both scopes.** Sheets export and Drive upload used to want
   separate tokens (`token.json` / `token_drive.json`, the latter written to the
   repo root — hard rule #1). Authorizing once for both means the user does the
   browser dance a single time, and everything lives under `data/credentials/`.

Run `python scripts/authorize_google.py` once to mint or refresh the token.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv("data/credentials/.env")
load_dotenv()

# Both scopes, always — a token minted for only one of them can't serve the
# other, and re-prompting mid-job is exactly what this module exists to avoid.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_PATH", "data/credentials/credentials.json")
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_PATH", "data/credentials/token.json")

_REAUTH_HINT = (
    "Run `python scripts/authorize_google.py` once to (re-)authorize "
    "Google access; it opens a browser and stores the token under "
    "data/credentials/."
)


class GoogleAuthError(RuntimeError):
    """Credentials are missing, expired, or lack the scopes we need."""


def _has_scopes(creds: Credentials) -> bool:
    granted = set(creds.scopes or [])
    return all(scope in granted for scope in SCOPES)


def get_credentials(interactive: bool = False) -> Credentials:
    """Load usable credentials.

    With `interactive=False` (the default, and what servers must use) this only
    ever reads the token file and silently refreshes it. Anything else — no
    token, a dead refresh token, missing scopes — raises `GoogleAuthError`.
    """
    token_path = Path(TOKEN_FILE)
    creds: Credentials | None = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except ValueError as exc:
            raise GoogleAuthError(f"Token file is unreadable ({exc}). {_REAUTH_HINT}") from exc

    if creds and creds.valid and _has_scopes(creds):
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            if _has_scopes(creds):
                token_path.write_text(creds.to_json())
                return creds
        except Exception as exc:  # noqa: BLE001 — any refresh failure means re-auth
            if not interactive:
                raise GoogleAuthError(
                    f"Google authorization expired or was revoked ({exc}). {_REAUTH_HINT}"
                ) from exc

    if creds and not _has_scopes(creds) and not interactive:
        raise GoogleAuthError(
            "The stored Google token is missing required scopes "
            f"(needs Sheets + Drive). {_REAUTH_HINT}"
        )

    if not interactive:
        raise GoogleAuthError(f"No usable Google credentials. {_REAUTH_HINT}")

    # Interactive path — only ever reached from scripts/authorize_google.py.
    if not Path(CREDENTIALS_FILE).exists():
        raise GoogleAuthError(
            f"OAuth client file not found at {CREDENTIALS_FILE}. Download it from the "
            "Google Cloud Console and save it there."
        )
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    return creds
