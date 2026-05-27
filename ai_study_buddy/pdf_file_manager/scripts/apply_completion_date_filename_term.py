#!/usr/bin/env python3
"""Apply filename_term completion dates (proposal 17 §5.2).

Usage::

  python3 -m ai_study_buddy.pdf_file_manager.scripts.apply_completion_date_filename_term \\
    --work-dir ai_study_buddy/pdf_file_manager/.completion_date_page1
  python3 -m ai_study_buddy.pdf_file_manager.scripts.apply_completion_date_filename_term \\
    --file-id <uuid> --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def repo_root() -> Path:
    return SCRIPT_DIR.parent.parent.parent


def default_db_path() -> Path:
    return repo_root() / "ai_study_buddy" / "db" / "pdf_registry.db"


@dataclass
class ApplyFilenameTermReport:
    processed: int = 0
    written: int = 0
    skipped_existing: int = 0
    skipped_manual: int = 0
    skipped_no_match: int = 0
    skipped_already_dated: int = 0
    failed: int = 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(default_db_path()))
    parser.add_argument("--work-dir", default="", help="Batch dir with batch_manifest.json")
    parser.add_argument("--file-id", action="append", default=[], help="Single file (repeatable)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing completion_date rows")
    parser.add_argument("--force-manual", action="store_true")
    parser.add_argument(
        "--undated-only",
        action="store_true",
        help="Skip files that already have a completion_date row",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from ai_study_buddy.pdf_file_manager.completion_date.filename_term import (
        FILENAME_TERM_CONFIDENCE,
        FILENAME_TERM_SOURCE,
        infer_completion_date_from_filename_term,
        load_school_term_calendar,
    )
    from ai_study_buddy.pdf_file_manager.completion_date.page1 import default_page1_work_dir
    from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

    mgr = PdfFileManager(db_path=Path(args.db))
    calendar = load_school_term_calendar()
    report = ApplyFilenameTermReport()

    file_ids: list[str] = []
    if args.file_id:
        file_ids.extend(args.file_id)
    if args.work_dir:
        work_dir = Path(args.work_dir)
        manifest = json.loads((work_dir / "batch_manifest.json").read_text(encoding="utf-8"))
        for item in manifest["items"]:
            fid = item["file_id"]
            if args.file_id and fid not in args.file_id:
                continue
            if fid not in file_ids:
                file_ids.append(fid)

    if not file_ids:
        print("error: no files to process (use --work-dir or --file-id)", file=sys.stderr)
        return 2

    seen: set[str] = set()
    for file_id in file_ids:
        if file_id in seen:
            continue
        seen.add(file_id)
        report.processed += 1
        pdf = mgr.get_file(file_id)
        if pdf is None:
            report.failed += 1
            continue

        existing = mgr.get_completion_date(file_id)
        if existing is not None:
            if existing.source == "manual" and not args.force_manual:
                report.skipped_manual += 1
                continue
            if args.undated_only or not args.force:
                report.skipped_existing += 1
                continue

        title = pdf.normal_name
        inferred = infer_completion_date_from_filename_term(
            title,
            student_id=pdf.student_id,
            path=pdf.path,
            name=pdf.name,
            calendar=calendar,
        )
        if inferred is None:
            if existing is None:
                report.skipped_no_match += 1
            else:
                report.skipped_already_dated += 1
            continue

        if args.dry_run:
            report.written += 1
            continue

        mgr.set_completion_date(
            file_id,
            inferred.completion_date,
            source=FILENAME_TERM_SOURCE,
            confidence=FILENAME_TERM_CONFIDENCE,
            source_detail=inferred.source_detail,
        )
        report.written += 1

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(
            f"processed={report.processed} written={report.written} "
            f"no_match={report.skipped_no_match} skipped_existing={report.skipped_existing}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
