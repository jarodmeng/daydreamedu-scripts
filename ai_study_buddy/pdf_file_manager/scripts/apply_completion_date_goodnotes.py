#!/usr/bin/env python3
"""Apply Goodnotes last_modified completion dates for g_root browser cohort (§5.3).

Usage::

  python3 -m ai_study_buddy.pdf_file_manager.scripts.apply_completion_date_goodnotes --dry-run
  python3 -m ai_study_buddy.pdf_file_manager.scripts.apply_completion_date_goodnotes --force
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
class ApplyGoodnotesReport:
    processed: int = 0
    written: int = 0
    skipped_existing: int = 0
    skipped_manual: int = 0
    skipped_no_match: int = 0
    skipped_metadata_unavailable: int = 0
    by_status: dict[str, int] | None = None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(default_db_path()))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--force-manual", action="store_true")
    parser.add_argument(
        "--include-already-dated",
        action="store_true",
        help="Also process files that already have completion_date (use with --force)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    undated_only = not args.include_already_dated

    from ai_study_buddy.pdf_file_manager.completion_date.goodnotes import (
        infer_completion_date_from_goodnotes_match,
        list_g_root_browser_cohort_files,
    )
    from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

    mgr = PdfFileManager(db_path=Path(args.db))
    cohort = list_g_root_browser_cohort_files(mgr)
    report = ApplyGoodnotesReport(by_status={})

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

        match = mgr.get_goodnotes_document_timestamps_for_file(pdf.id)
        assert report.by_status is not None
        report.by_status[match.status] = report.by_status.get(match.status, 0) + 1

        if match.status == "metadata_unavailable":
            report.skipped_metadata_unavailable += 1
            continue

        inferred = infer_completion_date_from_goodnotes_match(match)
        if inferred is None:
            report.skipped_no_match += 1
            continue

        if args.dry_run:
            report.written += 1
            continue

        mgr.set_completion_date(
            pdf.id,
            inferred.completion_date,
            source=inferred.source,
            confidence=inferred.confidence,
            source_detail=inferred.source_detail,
        )
        report.written += 1

    if args.json:
        print(asdict(report))
    else:
        print(
            f"cohort={report.processed} written={report.written} "
            f"no_match={report.skipped_no_match} "
            f"metadata_unavailable={report.skipped_metadata_unavailable} "
            f"skipped_existing={report.skipped_existing}"
        )
        if report.by_status:
            print("match_status:", dict(sorted(report.by_status.items())))

    return 0


if __name__ == "__main__":
    sys.exit(main())
