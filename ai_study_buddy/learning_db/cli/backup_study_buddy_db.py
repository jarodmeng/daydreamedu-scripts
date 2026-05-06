#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_study_buddy.files.roots import resolve_daydreamedu_root
from ai_study_buddy.learning_db.core.connection import default_db_path

SINGAPORE_TZ = ZoneInfo("Asia/Singapore")


def _default_backup_dir() -> Path | None:
    env = os.environ.get("STUDY_BUDDY_DB_BACKUP_DIR", "").strip()
    if env:
        return Path(env).expanduser()
    dd = resolve_daydreamedu_root()
    if dd is None:
        return None
    return dd / "db"


def _last_backup_file(dest_path: Path, timestamped: bool) -> Path | None:
    if timestamped:
        candidates = sorted(dest_path.glob("study_buddy_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else None
    p = dest_path / "study_buddy.db"
    return p if p.exists() else None


def _log_event(dest_path: Path, message: str) -> None:
    ts = datetime.now(SINGAPORE_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")
    with (dest_path / "study_buddy_backup.log").open("a", encoding="utf-8") as f:
        f.write(f"{ts} {message}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up study_buddy.db to cloud-synced storage.")
    parser.add_argument("--timestamp", action="store_true", help="Create timestamped backup file.")
    parser.add_argument("--force", action="store_true", help="Back up even when unchanged.")
    parser.add_argument("--dest", default=_default_backup_dir(), help="Backup destination directory.")
    args = parser.parse_args()

    src = default_db_path()
    if not src.exists():
        print(f"Source DB not found: {src}")
        return 1
    if not args.dest:
        print("Set STUDY_BUDDY_DB_BACKUP_DIR or pass --dest.")
        return 1

    dest = Path(args.dest).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    if not args.force:
        last = _last_backup_file(dest, args.timestamp)
        if last and last.exists():
            src_stat = src.stat()
            last_stat = last.stat()
            if src_stat.st_mtime <= last_stat.st_mtime and src_stat.st_size == last_stat.st_size:
                print("No changes since last backup, skipping.")
                _log_event(dest, "skipped (no changes)")
                return 0

    if args.timestamp:
        stamp = datetime.now(SINGAPORE_TZ).strftime("%Y-%m-%d_%H-%M-%S%z")
        dest_file = dest / f"study_buddy_{stamp}.db"
    else:
        dest_file = dest / "study_buddy.db"
    shutil.copy2(src, dest_file)
    _log_event(dest, f"backed up to {dest_file.name}")
    print(f"Backed up to {dest_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

