"""Unified completion-date inference CLI (proposal 17 Phase 3 integration).

Usage (from repo root or ai_study_buddy/):

    python3 -m ai_study_buddy.pdf_file_manager.scripts.infer_completion_dates \\
        --root d_root --doc-type exam --dry-run

See proposal 17 §4 for method semantics and ordering.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def _parse_methods(values: Iterable[str] | None) -> frozenset[str] | None:
    if values is None:
        return None
    items = {v.strip() for v in values if v.strip()}
    return frozenset(items) if items else None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Infer completion_date for a cohort of files (proposal 17)."
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        help="Path to pdf_registry.db (defaults to PdfFileManager default).",
    )
    parser.add_argument(
        "--file-id",
        dest="file_ids",
        action="append",
        help="Limit inference to a specific file_id (may be repeated).",
    )
    parser.add_argument(
        "--student-id",
        dest="student_id",
        help="Restrict cohort to a single student_id.",
    )
    parser.add_argument(
        "--root",
        choices=["d_root", "g_root"],
        help="Restrict cohort to d_root or g_root based on registry path.",
    )
    parser.add_argument(
        "--doc-type",
        dest="doc_types",
        action="append",
        help="Restrict cohort to one or more doc_type values (may be repeated).",
    )
    parser.add_argument(
        "--method",
        dest="methods",
        action="append",
        choices=[
            "handwritten_page1",
            "goodnotes_last_modified",
            "goodnotes_updated_at",
            "filename_term",
            "drive_modified",
            "manual",
        ],
        help="Limit inference to specific methods (may be repeated). Defaults to all.",
    )
    parser.add_argument(
        "--work-dir",
        dest="work_dir",
        help="Override page-1 work dir (defaults to completion_date/page1 DEFAULT_WORK_DIR_NAME).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Walk cohort and report counts without writing any file_completion_dates rows.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting non-manual completion_date rows.",
    )
    parser.add_argument(
        "--force-manual",
        action="store_true",
        help="Allow overwriting source=manual rows (use with care).",
    )
    return parser


def main(args: list[str] | None = None) -> int:
    parser = build_arg_parser()
    ns = parser.parse_args(args=args)

    mgr_kwargs = {}
    if ns.db_path:
        mgr_kwargs["db_path"] = Path(ns.db_path)
    mgr = PdfFileManager(**mgr_kwargs)

    methods = _parse_methods(ns.methods)
    work_dir = Path(ns.work_dir) if ns.work_dir else None

    report = mgr.infer_completion_dates(
        file_ids=ns.file_ids,
        student_id=ns.student_id,
        root=ns.root,
        doc_types=ns.doc_types,
        methods=methods,
        work_dir=work_dir,
        dry_run=ns.dry_run,
        force=ns.force,
        force_manual=ns.force_manual,
    )

    print("completion_date inference report")
    print("--------------------------------")
    print(f"processed       : {report.processed}")
    print(f"written         : {report.written}")
    print(f"skipped_existing: {report.skipped_existing}")
    print(f"skipped_manual  : {report.skipped_manual}")
    print(f"skipped_no_cached_result: {report.skipped_no_cached_result}")
    print(f"skipped_no_date : {report.skipped_no_date}")
    print(f"failed          : {report.failed}")
    print(f"still_undated   : {report.still_undated}")

    if ns.dry_run:
        print("\nNote: dry-run mode; no registry rows were written.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

