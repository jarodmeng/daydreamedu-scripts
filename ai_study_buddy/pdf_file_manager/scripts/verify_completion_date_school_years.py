#!/usr/bin/env python3
"""Audit completion dates against student P1 anchor + path ``Pn`` (proposal 17 §5.2).

Usage::

  python3 -m ai_study_buddy.pdf_file_manager.scripts.verify_completion_date_school_years
  python3 -m ai_study_buddy.pdf_file_manager.scripts.verify_completion_date_school_years \\
    --work-dir ai_study_buddy/pdf_file_manager/.completion_date_page1 --fix
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
    parser.add_argument("--db", default=str(default_db_path()))
    parser.add_argument(
        "--work-dir",
        default="",
        help="If set, also audit cached results/*.json under this batch dir",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Null mismatched batch results and clear registry rows",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from ai_study_buddy.pdf_file_manager.completion_date import (
        REASON_SCHOOL_YEAR_MISMATCH,
        check_completion_date_school_year,
    )
    from ai_study_buddy.pdf_file_manager.completion_date.page1 import (
        default_page1_work_dir,
    )
    from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

    mgr = PdfFileManager(db_path=Path(args.db))
    mismatches: list[dict] = []

    conn = mgr._get_connection()
    for db_row in conn.execute(
        "SELECT file_id, completion_date, source, confidence FROM file_completion_dates"
    ):
        row = mgr.get_completion_date(db_row["file_id"])
        if row is None:
            continue
        pdf = mgr.get_file(row.file_id)
        if pdf is None:
            continue
        ok, detail = check_completion_date_school_year(
            row.completion_date,
            student_id=pdf.student_id,
            path=pdf.path,
            name=pdf.name,
        )
        if not ok:
            mismatches.append(
                {
                    "file_id": row.file_id,
                    "completion_date": row.completion_date,
                    "source": row.source,
                    "confidence": row.confidence,
                    "name": pdf.name,
                    "path": pdf.path,
                    **detail,
                }
            )

    work_dir = Path(args.work_dir) if args.work_dir else None
    result_mismatches: list[dict] = []
    if work_dir is None and not args.work_dir:
        work_dir = default_page1_work_dir()
    if work_dir and work_dir.is_dir():
        results_dir = work_dir / "results"
        for path in sorted(results_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            completion_date = payload.get("completion_date")
            if not completion_date:
                continue
            file_id = payload["file_id"]
            pdf = mgr.get_file(file_id)
            if pdf is None:
                continue
            ok, detail = check_completion_date_school_year(
                completion_date,
                student_id=pdf.student_id,
                path=pdf.path,
                name=pdf.name,
            )
            if not ok:
                result_mismatches.append(
                    {
                        "file_id": file_id,
                        "completion_date": completion_date,
                        "result_path": str(path),
                        "name": pdf.name,
                        **detail,
                    }
                )
                if args.fix:
                    payload["completion_date"] = None
                    payload["confidence"] = None
                    payload["inference_model"] = None
                    sd = payload.get("source_detail") or {}
                    if not isinstance(sd, dict):
                        sd = {}
                    sd.update(
                        {
                            "timezone": "Asia/Singapore",
                            "reason": REASON_SCHOOL_YEAR_MISMATCH,
                            "note": (
                                "Rejected by school-year check: "
                                f"completion_year={detail['completion_year']} "
                                f"not in [{detail['allowed_year_min']}, "
                                f"{detail['allowed_year_max']}] for "
                                f"P{detail['primary_level']} "
                                f"(expected_school_year="
                                f"{detail['expected_school_year']})."
                            ),
                            "school_year_check": detail,
                        }
                    )
                    payload["source_detail"] = sd
                    path.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )

    if args.fix:
        for item in mismatches:
            mgr.clear_completion_date(item["file_id"])

    report = {
        "registry_mismatches": len(mismatches),
        "result_mismatches": len(result_mismatches),
        "mismatches": mismatches,
        "result_files": result_mismatches,
        "fixed": args.fix,
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"registry mismatches: {len(mismatches)}; "
            f"batch result mismatches: {len(result_mismatches)}"
        )
        for item in mismatches:
            print(
                f"  {item['completion_date']}  P{item['primary_level']} "
                f"expected {item['allowed_year_min']}–{item['allowed_year_max']}  "
                f"{item['name']}"
            )
        if args.fix and (mismatches or result_mismatches):
            print("applied --fix: cleared registry rows and nulled batch JSON")

    return 1 if mismatches or result_mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
