#!/usr/bin/env python3
"""Validate common PDF registry integrity issues.

This is a reproducible audit for the main problems previously discovered by
ad hoc investigation:

1. files still marked with doc_type='unknown'
2. files under a registered student's email folder that are missing student_id
3. linked raw/main pairs whose invariant metadata has drifted

Usage:
  python3 ai_study_buddy/utils/pdf_file_manager/scripts/validate_pdf_registry_integrity.py
  python3 ai_study_buddy/utils/pdf_file_manager/scripts/validate_pdf_registry_integrity.py --json
  python3 ai_study_buddy/utils/pdf_file_manager/scripts/validate_pdf_registry_integrity.py --db /path/to/pdf_registry.db
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PDF_MANAGER_DIR = SCRIPT_DIR.parent
if str(PDF_MANAGER_DIR) not in sys.path:
    sys.path.insert(0, str(PDF_MANAGER_DIR))

from pdf_file_manager import PdfFileManager  # noqa: E402


INVARIANT_METADATA_KEYS = (
    "subject",
    "doc_type",
    "student_id",
    "is_template",
    "metadata.grade_or_scope",
    "metadata.content_folder",
    "metadata.chinese_variant",
)


def repo_root() -> Path:
    return SCRIPT_DIR.parent.parent.parent.parent


def default_db_path() -> Path:
    return repo_root() / "ai_study_buddy" / "db" / "pdf_registry.db"


def collect_unknown_doc_type(mgr: PdfFileManager) -> list[dict]:
    return [
        {
            "id": f.id,
            "path": f.path,
            "file_type": f.file_type,
        }
        for f in mgr.find_files(doc_type="unknown")
    ]


def collect_missing_student_id(mgr: PdfFileManager) -> list[dict]:
    items = []
    for f in mgr.find_files():
        inferred_student_id = mgr._infer_student_id_from_path(f.path)
        if inferred_student_id is not None and not f.student_id:
            items.append(
                {
                    "id": f.id,
                    "path": f.path,
                    "file_type": f.file_type,
                    "expected_student_id": inferred_student_id,
                }
            )
    return items


def collect_main_raw_metadata_drift(mgr: PdfFileManager) -> list[dict]:
    conn = mgr._get_connection()
    rows = conn.execute(
        """
        SELECT raw.id AS raw_id, raw.path AS raw_path, raw.file_type AS raw_file_type,
               raw.subject AS raw_subject, raw.doc_type AS raw_doc_type, raw.student_id AS raw_student_id,
               raw.is_template AS raw_is_template, raw.metadata AS raw_metadata,
               main.id AS main_id, main.path AS main_path, main.file_type AS main_file_type,
               main.subject AS main_subject, main.doc_type AS main_doc_type, main.student_id AS main_student_id,
               main.is_template AS main_is_template, main.metadata AS main_metadata
        FROM file_relations fr
        JOIN pdf_files raw ON raw.id = fr.source_id
        JOIN pdf_files main ON main.id = fr.target_id
        WHERE fr.relation_type = 'main_version'
          AND raw.file_type = 'raw'
          AND main.file_type = 'main'
        ORDER BY raw.path
        """
    ).fetchall()
    issues = []
    seen_raw_ids: set[str] = set()
    for row in rows:
        raw_id = row["raw_id"]
        if raw_id in seen_raw_ids:
            continue
        seen_raw_ids.add(raw_id)
        raw_meta = json.loads(row["raw_metadata"]) if row["raw_metadata"] else {}
        main_meta = json.loads(row["main_metadata"]) if row["main_metadata"] else {}
        field_diffs = []
        comparisons = {
            "subject": (row["raw_subject"], row["main_subject"]),
            "doc_type": (row["raw_doc_type"], row["main_doc_type"]),
            "student_id": (row["raw_student_id"], row["main_student_id"]),
            "is_template": (bool(row["raw_is_template"]), bool(row["main_is_template"])),
            "metadata.grade_or_scope": (raw_meta.get("grade_or_scope"), main_meta.get("grade_or_scope")),
            "metadata.content_folder": (raw_meta.get("content_folder"), main_meta.get("content_folder")),
            "metadata.chinese_variant": (raw_meta.get("chinese_variant"), main_meta.get("chinese_variant")),
        }
        for field, (raw_value, main_value) in comparisons.items():
            if raw_value != main_value:
                field_diffs.append(
                    {
                        "field": field,
                        "raw_value": raw_value,
                        "main_value": main_value,
                    }
                )
        if field_diffs:
            issues.append(
                {
                    "raw_id": row["raw_id"],
                    "raw_path": row["raw_path"],
                    "main_id": row["main_id"],
                    "main_path": row["main_path"],
                    "fields": field_diffs,
                }
            )
    return issues


def build_report(mgr: PdfFileManager) -> dict:
    unknown_doc_type = collect_unknown_doc_type(mgr)
    missing_student_id = collect_missing_student_id(mgr)
    main_raw_drift = collect_main_raw_metadata_drift(mgr)
    return {
        "db_path": str(Path(mgr.db_path).resolve()),
        "summary": {
            "unknown_doc_type": len(unknown_doc_type),
            "missing_student_id": len(missing_student_id),
            "main_raw_metadata_drift": len(main_raw_drift),
        },
        "checks": {
            "unknown_doc_type": unknown_doc_type,
            "missing_student_id": missing_student_id,
            "main_raw_metadata_drift": main_raw_drift,
        },
    }


def _print_human_report(report: dict, *, limit: int) -> None:
    print(f"DB: {report['db_path']}")
    print("Summary:")
    for key, value in report["summary"].items():
        print(f"- {key}: {value}")

    print("\nUnknown doc_type:")
    for item in report["checks"]["unknown_doc_type"][:limit]:
        print(f"- {item['path']} [{item['file_type']}]")

    print("\nMissing student_id:")
    for item in report["checks"]["missing_student_id"][:limit]:
        print(f"- {item['path']} [{item['file_type']}] expected={item['expected_student_id']}")

    print("\nMain/raw metadata drift:")
    for item in report["checks"]["main_raw_metadata_drift"][:limit]:
        field_names = ", ".join(diff["field"] for diff in item["fields"])
        print(f"- raw={item['raw_path']}")
        print(f"  main={item['main_path']}")
        print(f"  fields={field_names}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate common pdf_registry integrity issues.")
    parser.add_argument("--db", default=str(default_db_path()), help="Path to pdf_registry.db")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--limit", type=int, default=20, help="Max examples per section for human-readable output")
    args = parser.parse_args()

    mgr = PdfFileManager(db_path=args.db)
    report = build_report(mgr)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human_report(report, limit=max(args.limit, 0))

    return 1 if any(report["summary"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
