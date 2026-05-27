#!/usr/bin/env python3
"""Apply page-1 agent inspection JSON to file_completion_dates (Phase 2).

Reads ``<work_dir>/results/*.json``, a JSONL file, or a single JSON object.
Does **not** run visual inspection.

Usage::

  python3 -m ai_study_buddy.pdf_file_manager.scripts.apply_completion_date_page1_results \\
    --work-dir ai_study_buddy/pdf_file_manager/.completion_date_page1
  python3 -m ai_study_buddy.pdf_file_manager.scripts.apply_completion_date_page1_results \\
    --results path/to/results.ndjson --force
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def repo_root() -> Path:
    return SCRIPT_DIR.parent.parent.parent


def default_db_path() -> Path:
    return repo_root() / "ai_study_buddy" / "db" / "pdf_registry.db"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(default_db_path()), help="Path to pdf_registry.db")
    parser.add_argument(
        "--work-dir",
        default="",
        help="Batch work dir; results read from <work-dir>/results unless --results set",
    )
    parser.add_argument(
        "--results",
        default="",
        help="Results directory, .jsonl, or single .json (default: <work-dir>/results)",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing completion_date rows")
    parser.add_argument("--force-manual", action="store_true", help="Overwrite source=manual rows")
    parser.add_argument("--dry-run", action="store_true", help="Validate only; do not write registry rows")
    parser.add_argument("--json", action="store_true", help="Print report JSON")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"error: registry database not found: {db_path}", file=sys.stderr)
        return 2

    from ai_study_buddy.pdf_file_manager.completion_date.page1 import (
        apply_page1_results_from_path,
        default_page1_work_dir,
    )
    from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

    work_dir = Path(args.work_dir) if args.work_dir else default_page1_work_dir()
    results_path = Path(args.results) if args.results else work_dir / "results"
    if not results_path.exists():
        print(f"error: results path not found: {results_path}", file=sys.stderr)
        return 2

    mgr = PdfFileManager(db_path=db_path)
    report = apply_page1_results_from_path(
        mgr,
        results_path,
        force=args.force,
        force_manual=args.force_manual,
        dry_run=args.dry_run,
    )

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(f"Results: {results_path.resolve()}")
        print(f"Processed: {report.processed}")
        print(f"Written: {report.written}")
        print(f"Skipped (existing): {report.skipped_existing}")
        print(f"Skipped (manual): {report.skipped_manual}")
        print(f"Skipped (no date in JSON): {report.skipped_no_date}")
        print(f"Failed (parse/validation): {report.failed}")
        if args.dry_run:
            print("(dry-run: registry not updated)")
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
