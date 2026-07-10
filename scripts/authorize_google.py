#!/usr/bin/env python
"""One-time (or re-)authorization for Google Sheets + Drive.

Run this from the repo root when the API reports that Google credentials are
missing or expired:

    python scripts/authorize_google.py

It opens a browser, asks for both the Sheets and Drive scopes, and writes the
token to `data/credentials/token.json` (gitignored). The servers themselves
never do this — they refuse rather than block on a browser prompt.

Prerequisite: an OAuth *client* file at `data/credentials/credentials.json`
(Google Cloud Console -> APIs & Services -> Credentials -> OAuth client ID,
type "Desktop app"). Override paths with GOOGLE_CREDENTIALS_PATH /
GOOGLE_TOKEN_PATH if yours live elsewhere.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.google_auth import (  # noqa: E402
    CREDENTIALS_FILE,
    SCOPES,
    TOKEN_FILE,
    GoogleAuthError,
    get_credentials,
)


def main() -> int:
    print("Authorizing Google access for:")
    for scope in SCOPES:
        print(f"  - {scope}")
    print(f"\nOAuth client: {CREDENTIALS_FILE}")
    print(f"Token target: {TOKEN_FILE}\n")

    try:
        creds = get_credentials(interactive=True)
    except GoogleAuthError as exc:
        print(f"Authorization failed: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 — surface anything the flow throws
        print(f"Authorization failed: {exc}")
        return 1

    print("Authorized. Token saved.")
    print(f"  valid:  {creds.valid}")
    print(f"  scopes: {', '.join(creds.scopes or [])}")
    print("\nSheets export and Drive upload can now run from the app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
