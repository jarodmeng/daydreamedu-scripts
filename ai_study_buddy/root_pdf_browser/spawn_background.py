#!/usr/bin/env python3
"""Start `root_pdf_browser.serve` detached so the parent exits immediately (e.g. Cursor agent shell)."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _default_log_path() -> Path:
    return Path(tempfile.gettempdir()) / "root-pdf-browser.log"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start Root PDF browser in the background; parent exits immediately.",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Append server stdout/stderr here (default: <temp>/root-pdf-browser.log).",
    )
    known, forwarded = parser.parse_known_args()
    log_path = known.log or _default_log_path()

    cmd = [sys.executable, "-m", "ai_study_buddy.root_pdf_browser.serve", *forwarded]
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "ab") as logf:
            proc = subprocess.Popen(
                cmd,
                cwd=str(_REPO_ROOT),
                stdout=logf,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except OSError as exc:
        print(f"Failed to spawn server: {exc}", file=sys.stderr)
        return 1

    port = 8770
    for i, a in enumerate(forwarded):
        if a == "--port" and i + 1 < len(forwarded):
            try:
                port = int(forwarded[i + 1])
            except ValueError:
                pass

    url = f"http://127.0.0.1:{port}/"
    print(f"Root PDF browser started in background (PID {proc.pid}).")
    print(f"URL: {url}")
    print(f"Log: {log_path.resolve()}")
    print(f"Stop: kill {proc.pid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
