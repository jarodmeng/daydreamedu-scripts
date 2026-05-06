"""
One-off helper: clean up stale registry rows for missing-on-disk files
and their linked counterparts when *both* sides are missing on disk.

Algorithm:

1. Run validate_pdf_registry_integrity in JSON mode to get missing_on_disk_files.
2. For each missing file:
   - Confirm its path is absent on disk.
   - Fetch related files via get_related_files(...) (raw/main + template/completion).
   - If **all** related files are also missing on disk:
     - Mark this file id and all related file ids for deletion.
3. In real mode, call delete_file(...) on each unique id.

Usage (from repo root):

    python3 -m ai_study_buddy.pdf_file_manager.scripts._cleanup_missing_files_and_links --dry-run
    python3 -m ai_study_buddy.pdf_file_manager.scripts._cleanup_missing_files_and_links
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def load_missing_on_disk(db_path: Path | None = None) -> list[dict]:
    args = [
        sys.executable,
        "-m",
        "ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity",
        "--json",
    ]
    if db_path is not None:
        args += ["--db", str(db_path)]
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"validator failed with code {proc.returncode}: {proc.stderr}")
    payload = json.loads(proc.stdout)
    return payload.get("checks", {}).get("missing_on_disk_files", [])


def collect_ids_to_delete(dry_run: bool, db_path: Path | None = None) -> set[str]:
    mgr = PdfFileManager(db_path=str(db_path) if db_path is not None else None)
    missing_items = load_missing_on_disk(db_path)
    ids_to_delete: set[str] = set()

    print(f"Found {len(missing_items)} missing-on-disk registry entries.")
    for item in missing_items:
        file_id = item["id"]
        path = Path(item["path"])
        if path.exists():
            # Race condition or manual restore; skip.
            print(f"- SKIP (restored on disk): {file_id} -> {path}")
            continue
        try:
            f = mgr.get_file(file_id)
        except Exception as exc:  # NotFoundError or others
            print(f"- SKIP (get_file failed): {file_id} ({exc})")
            continue
        if f is None:
            print(f"- SKIP (no longer in registry): {file_id}")
            continue

        related = mgr.get_related_files(file_id)
        all_related_missing = True
        related_ids: set[str] = set()
        for rf, rel_type in related:
            related_ids.add(rf.id)
            if Path(rf.path).exists():
                all_related_missing = False
                print(f"- KEEP (linked file still exists): {file_id} -> {rf.id} [{rel_type}] {rf.path}")
        if not related:
            # No related files; safe to delete this single stale row.
            print(f"- CANDIDATE (no relations): {file_id} -> {path}")
            ids_to_delete.add(file_id)
            continue
        if not all_related_missing:
            # Mixed case; do not delete anything in this relation set.
            continue

        # All related files are also missing on disk; delete the whole mini-cluster.
        print(f"- CANDIDATE CLUSTER: {file_id} + {len(related_ids)} related (all missing on disk)")
        ids_to_delete.add(file_id)
        ids_to_delete.update(related_ids)

    print(f"\nTotal unique ids to delete: {len(ids_to_delete)}")
    return ids_to_delete


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Clean up stale missing-on-disk files and fully-missing linked clusters.")
    parser.add_argument(
        "--db",
        type=Path,
        help="Optional explicit path to pdf_registry.db (defaults to package default).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which ids would be deleted without mutating the registry.",
    )
    args = parser.parse_args(argv)

    ids_to_delete = collect_ids_to_delete(dry_run=args.dry_run, db_path=args.db)
    if args.dry_run:
        print("\nDry-run complete; no deletions performed.")
        raise SystemExit(0)

    mgr = PdfFileManager(db_path=str(args.db) if args.db is not None else None)
    for file_id in sorted(ids_to_delete):
        try:
            print(f"Deleting file_id={file_id}")
            mgr.delete_file(file_id)
        except Exception as exc:
            print(f"ERROR: delete_file({file_id}) failed: {exc}")
    print("Cleanup complete.")


if __name__ == "__main__":
    main()

