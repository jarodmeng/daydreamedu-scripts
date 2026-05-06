#!/usr/bin/env python3
"""Apply tiered retention for study_buddy timestamped backups.

Policy:
- 0..hot_days: keep raw .db files in backup directory.
- (hot_days..cold_days]: move to coldstorage/ as .zst and remove raw .db.
- > cold_days: remove backups from both hot and cold tiers.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ai_study_buddy.files.roots import resolve_daydreamedu_root


def _default_backup_dir() -> Path | None:
    env = os.environ.get("STUDY_BUDDY_DB_BACKUP_DIR", "").strip()
    if env:
        return Path(env).expanduser()

    dd = resolve_daydreamedu_root()
    if dd is None:
        return None
    return dd / "db"


def _age_days(path: Path, now_ts: float) -> float:
    return (now_ts - path.stat().st_mtime) / 86400.0


def _compress_zstd(src: Path, dest: Path, dry_run: bool) -> None:
    if dry_run:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["zstd", "-19", "--quiet", "-o", str(dest), str(src)],
        check=True,
    )


def _remove_file(path: Path, dry_run: bool) -> None:
    if not dry_run:
        path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply tiered backup retention for study_buddy backups.")
    parser.add_argument("--backups-dir", default=_default_backup_dir(), help="Backup directory path.")
    parser.add_argument("--hot-days", type=int, default=7, help="Keep raw .db backups up to this age.")
    parser.add_argument(
        "--cold-days",
        type=int,
        default=60,
        help="Keep compressed .zst backups up to this age; older backups are pruned.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned actions without writing, compressing, or deleting files.",
    )
    args = parser.parse_args()

    if args.hot_days < 0 or args.cold_days < 0 or args.hot_days >= args.cold_days:
        print("Invalid retention: require 0 <= hot-days < cold-days.", file=sys.stderr)
        return 2

    if not args.backups_dir:
        print(
            "No backup directory configured. Set STUDY_BUDDY_DB_BACKUP_DIR or pass --backups-dir.",
            file=sys.stderr,
        )
        return 1

    if not args.dry_run and not shutil.which("zstd"):
        print("zstd not found in PATH. Install zstd first (e.g. brew install zstd).", file=sys.stderr)
        return 1

    backup_dir = Path(args.backups_dir).expanduser().resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    cold_dir = backup_dir / "coldstorage"
    cold_dir.mkdir(parents=True, exist_ok=True)

    now_ts = datetime.now(timezone.utc).timestamp()

    hot_raw_files = sorted(backup_dir.glob("study_buddy_*.db"))
    cold_files = sorted(cold_dir.glob("study_buddy_*.db.zst"))

    planned_compress = 0
    planned_remove_hot = 0
    planned_remove_cold = 0
    compressed = 0
    removed_hot = 0
    removed_cold = 0

    for raw in hot_raw_files:
        age = _age_days(raw, now_ts)
        if age > args.cold_days:
            print(f"remove hot (expired): {raw}")
            planned_remove_hot += 1
            _remove_file(raw, args.dry_run)
            removed_hot += 0 if args.dry_run else 1
            continue

        if age > args.hot_days:
            cold_target = cold_dir / f"{raw.name}.zst"
            if not cold_target.exists():
                print(f"compress to cold: {raw} -> {cold_target}")
                planned_compress += 1
                _compress_zstd(raw, cold_target, args.dry_run)
                compressed += 0 if args.dry_run else 1
            print(f"remove hot (tiered): {raw}")
            planned_remove_hot += 1
            _remove_file(raw, args.dry_run)
            removed_hot += 0 if args.dry_run else 1

    for cold in cold_files:
        age = _age_days(cold, now_ts)
        if age > args.cold_days:
            print(f"remove cold (expired): {cold}")
            planned_remove_cold += 1
            _remove_file(cold, args.dry_run)
            removed_cold += 0 if args.dry_run else 1

    if args.dry_run:
        print(
            "Tiering dry run complete: "
            f"planned_compress={planned_compress}, "
            f"planned_remove_hot={planned_remove_hot}, "
            f"planned_remove_cold={planned_remove_cold}"
        )
        return 0

    print(
        "Tiering complete: "
        f"compressed={compressed}, "
        f"removed_hot={removed_hot}, "
        f"removed_cold={removed_cold}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
