#!/usr/bin/env python3
"""Prepare Phase 2 page-1 batch: d_root cohort manifest + rendered PNGs (no vision).

Renders page 1 for every file and page 2 when the PDF has ≥2 pages. After this script, run
the Cursor agent ``completion-date-page1-inspector`` (``model: inherit``) per manifest item:
inspect ``page1_image_path`` first; if no date and ``page2_image_path`` is set, inspect page 2.
Write JSON to ``<work_dir>/results/<file_id>.json``. Then run
``apply_completion_date_page1_results``.

Usage::

  python3 -m ai_study_buddy.pdf_file_manager.scripts.prepare_completion_date_page1_batch --dry-run
  python3 -m ai_study_buddy.pdf_file_manager.scripts.prepare_completion_date_page1_batch \\
    --skip-doc-types book
  python3 -m ai_study_buddy.pdf_file_manager.scripts.prepare_completion_date_page1_batch --limit 3

Does **not** invoke any vision model.
"""

from __future__ import annotations

import argparse
import json
import sys
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
        help="Batch work directory (default: pdf_file_manager/.completion_date_page1)",
    )
    parser.add_argument(
        "--skip-doc-types",
        action="append",
        default=[],
        metavar="DOC_TYPE",
        help="Exclude doc_type values (e.g. book for priority-only pass)",
    )
    parser.add_argument(
        "--exclude-activity-note",
        action="store_true",
        help="Omit activity and note doc_types from cohort",
    )
    parser.add_argument("--dry-run", action="store_true", help="Manifest only; do not render PNGs")
    parser.add_argument("--limit", type=int, default=None, help="Max files (testing)")
    parser.add_argument("--json", action="store_true", help="Print manifest JSON to stdout")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"error: registry database not found: {db_path}", file=sys.stderr)
        return 2

    from ai_study_buddy.pdf_file_manager.completion_date.page1 import (
        default_page1_work_dir,
        manifest_path_for,
        prepare_page1_batch,
    )
    from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

    work_dir = Path(args.work_dir) if args.work_dir else default_page1_work_dir()
    mgr = PdfFileManager(db_path=db_path)
    manifest = prepare_page1_batch(
        mgr,
        work_dir,
        skip_doc_types=frozenset(args.skip_doc_types),
        include_activity_note=not args.exclude_activity_note,
        dry_run=args.dry_run,
        limit=args.limit,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "manifest_path": str(manifest_path_for(work_dir)),
                    "counts": manifest.counts,
                    "items": [item.__dict__ for item in manifest.items],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Work dir: {work_dir.resolve()}")
        print(f"Manifest: {manifest_path_for(work_dir)}")
        print(f"Total: {manifest.counts.get('total', 0)}")
        print(f"  priority (non-book): {manifest.counts.get('priority', 0)}")
        print(f"  deprioritized (book): {manifest.counts.get('deprioritized', 0)}")
        if args.dry_run:
            print("(dry-run: PNGs not rendered)")
        else:
            print("Next: Task → completion-date-page1-inspector (page 1, then page 2 if needed)")
            print("Then: apply_completion_date_page1_results --work-dir", work_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
