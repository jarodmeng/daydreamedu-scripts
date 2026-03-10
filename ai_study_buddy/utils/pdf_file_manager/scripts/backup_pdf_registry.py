#!/usr/bin/env python3
"""Copy pdf_registry.db to a cloud-synced folder (e.g. Google Drive).

Use this to back up the PDF registry without committing it to git. The DB is
already ignored via .gitignore; this script copies it to a directory that
syncs to the cloud (e.g. Google Drive on your Mac).

Usage:
  python3 ai_study_buddy/utils/pdf_file_manager/scripts/backup_pdf_registry.py
  python3 ai_study_buddy/utils/pdf_file_manager/scripts/backup_pdf_registry.py --timestamp

Backup runs only when the source DB has changed since the last backup (by mtime/size).
Use --force to copy anyway. Default backup dir: .../My Drive/DaydreamEdu/db

Each run appends one line to pdf_registry_backup.log in the backup directory (so you can
see that the script ran even when it skipped because there were no changes).
"""

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo


SINGAPORE_TZ = ZoneInfo("Asia/Singapore")


def repo_root() -> Path:
    # Script lives in ai_study_buddy/utils/pdf_file_manager/scripts/; repo root is 4 levels up.
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def default_db_path() -> Path:
    return repo_root() / "ai_study_buddy" / "db" / "pdf_registry.db"


def _last_backup_file(dest_path: Path, timestamped: bool) -> Optional[Path]:
    """Path to the most recent backup we'd compare against, or None."""
    if timestamped:
        candidates = sorted(dest_path.glob("pdf_registry_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else None
    p = dest_path / "pdf_registry.db"
    return p if p.exists() else None


def _log_event(dest_path: Path, message: str) -> None:
    """Append one line to pdf_registry_backup.log in the backup directory."""
    log_file = dest_path / "pdf_registry_backup.log"
    ts = datetime.now(SINGAPORE_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{ts} {message}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Back up pdf_registry.db to a cloud-synced directory (e.g. Google Drive)."
    )
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="Write a timestamped copy (e.g. pdf_registry_2025-03-10_14-30-00.db) so you keep history.",
    )
    default_backup_dir = os.environ.get("PDF_REGISTRY_BACKUP_DIR") or (
        Path.home() / "genrong.meng@gmail.com - Google Drive/My Drive/DaydreamEdu/db"
    )
    parser.add_argument(
        "--dest",
        default=default_backup_dir,
        help="Backup directory (default: env PDF_REGISTRY_BACKUP_DIR or DaydreamEdu/db in Google Drive).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Copy even if source is unchanged since last backup.",
    )
    args = parser.parse_args()

    src = default_db_path()
    if not src.exists():
        print(f"Source DB not found: {src}", file=sys.stderr)
        return 1

    dest_dir = args.dest
    if not dest_dir:
        print(
            "Set backup destination via PDF_REGISTRY_BACKUP_DIR or --dest.",
            file=sys.stderr,
        )
        return 1

    dest_path = Path(dest_dir).expanduser().resolve()
    dest_path.mkdir(parents=True, exist_ok=True)

    if not args.force:
        last = _last_backup_file(dest_path, args.timestamp)
        if last and last.exists():
            src_stat = src.stat()
            last_stat = last.stat()
            if src_stat.st_mtime <= last_stat.st_mtime and src_stat.st_size == last_stat.st_size:
                print("No changes since last backup, skipping.")
                _log_event(dest_path, "skipped (no changes)")
                return 0

    if args.timestamp:
        stamp = datetime.now(SINGAPORE_TZ).strftime("%Y-%m-%d_%H-%M-%S%z")
        dest_file = dest_path / f"pdf_registry_{stamp}.db"
    else:
        dest_file = dest_path / "pdf_registry.db"

    shutil.copy2(src, dest_file)
    print(f"Backed up to {dest_file}")
    _log_event(dest_path, f"backed up to {dest_file.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
