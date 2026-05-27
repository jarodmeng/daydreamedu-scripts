#!/usr/bin/env python3
"""Apply drive_modified completion dates for d_root book completions (proposal 17 §4.3).

Uses filesystem mtime on the registered PDF path (Google Drive sync on macOS).

Usage::

  python3 -m ai_study_buddy.pdf_file_manager.scripts.apply_completion_date_drive_modified
  python3 -m ai_study_buddy.pdf_file_manager.scripts.apply_completion_date_drive_modified --dry-run
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def repo_root() -> Path:
    return SCRIPT_DIR.parent.parent.parent


def default_db_path() -> Path:
    return repo_root() / "ai_study_buddy" / "db" / "pdf_registry.db"


@dataclass
class ApplyDriveModifiedReport:
    processed: int = 0
    written: int = 0
    skipped_existing: int = 0
    skipped_manual: int = 0
    skipped_no_mtime: int = 0
    skipped_not_book: int = 0
    failed: int = 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(default_db_path()))
    parser.add_argument("--student-id", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--force-manual", action="store_true")
    parser.add_argument("--undated-only", action="store_true", default=True)
    parser.add_argument(
        "--include-already-dated",
        action="store_true",
        help="Allow --force overwrite without requiring undated-only",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    undated_only = args.undated_only and not args.include_already_dated

    from ai_study_buddy.pdf_file_manager.completion_date.drive_modified import (
        DRIVE_MODIFIED_CONFIDENCE,
        DRIVE_MODIFIED_SOURCE,
        infer_completion_date_from_drive_modified,
    )
    from ai_study_buddy.pdf_file_manager.completion_date.page1 import list_d_root_page1_cohort
    from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

    mgr = PdfFileManager(db_path=Path(args.db))
    cohort = list_d_root_page1_cohort(
        mgr,
        student_ids=args.student_id or None,
        doc_types=frozenset({"book"}),
    )
    report = ApplyDriveModifiedReport()

    for pdf in cohort:
        report.processed += 1
        existing = mgr.get_completion_date(pdf.id)
        if existing is not None:
            if existing.source == "manual" and not args.force_manual:
                report.skipped_manual += 1
                continue
            if undated_only or not args.force:
                report.skipped_existing += 1
                continue

        inferred = infer_completion_date_from_drive_modified(
            pdf.path, doc_type=pdf.doc_type
        )
        if inferred is None:
            report.skipped_no_mtime += 1
            continue

        if args.dry_run:
            report.written += 1
            continue

        mgr.set_completion_date(
            pdf.id,
            inferred.completion_date,
            source=DRIVE_MODIFIED_SOURCE,
            confidence=DRIVE_MODIFIED_CONFIDENCE,
            source_detail=inferred.source_detail,
        )
        report.written += 1

    if args.json:
        print(asdict(report))
    else:
        print(
            f"processed={report.processed} written={report.written} "
            f"no_mtime={report.skipped_no_mtime} skipped_existing={report.skipped_existing}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
