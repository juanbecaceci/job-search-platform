#!/usr/bin/env python3
"""Safety check: block commits containing user data or secrets.

Fails if any inspected file:
  - lives under data/ (should be gitignored; belt and suspenders)
  - is a credentials/token/db file anywhere in the tree
  - contains obvious secret patterns (private keys, OAuth client secrets)

Install as a git hook (inspects staged files):
  py scripts/check_no_secrets.py --install

Sweep the whole tracked tree instead (what CI runs):
  py scripts/check_no_secrets.py --all
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_NAMES = re.compile(
    r"(^|/)(credentials\.json|token[^/]*\.json|\.env)$|\.(db|sqlite3?|pem|key)$",
    re.IGNORECASE,
)
FORBIDDEN_DIRS = ("data/", ".tmp/", "output/", "context/")
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    re.compile(r'"client_secret"\s*:'),
    re.compile(r'"refresh_token"\s*:'),
    re.compile(r"(?i)(api[_-]?key|secret)\s*[=:]\s*['\"][A-Za-z0-9_\-]{20,}"),
]

HOOK = "#!/bin/sh\npy scripts/check_no_secrets.py || exit 1\n"


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True, check=True,
    )
    return [f for f in out.stdout.splitlines() if f.strip()]


def tracked_files() -> list[str]:
    """Every file in the tree, for `--all`."""
    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    )
    return [f for f in out.stdout.splitlines() if f.strip()]


def main() -> int:
    if "--install" in sys.argv:
        hook = Path(".git/hooks/pre-commit")
        hook.write_text(HOOK, encoding="utf-8", newline="\n")
        print(f"Installed pre-commit hook at {hook}")
        return 0

    # As a hook this checks what's staged. CI has nothing staged, so it needs
    # `--all` — otherwise the job passes without inspecting a single file.
    scan_all = "--all" in sys.argv
    files = tracked_files() if scan_all else staged_files()

    errors: list[str] = []
    for f in files:
        if any(f.startswith(d) for d in FORBIDDEN_DIRS):
            errors.append(f"{f}: files under {f.split('/')[0]}/ must never be committed")
            continue
        if FORBIDDEN_NAMES.search(f):
            errors.append(f"{f}: credential/token/database files must never be committed")
            continue
        p = Path(f)
        if p.is_file() and p.suffix.lower() not in {".png", ".jpg", ".pdf", ".docx", ".ico"}:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pat in SECRET_PATTERNS:
                if pat.search(text):
                    errors.append(f"{f}: matches secret pattern {pat.pattern!r}")
                    break

    if errors:
        label = "tracked in the repo" if scan_all else "staged"
        print(f"BLOCKED — potential secrets or user data {label}:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"check_no_secrets: {len(files)} file(s) scanned, clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
