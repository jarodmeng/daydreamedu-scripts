#!/usr/bin/env python3
"""Build a template-level FQI detector queue from registry + study DB coverage gaps."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from fqi_detector_marking_reference import (
    build_template_marking_reference,
    default_priority_filters,
    parse_student_grade_filters,
    remaining_p1_p5_filters,
)

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
_DEFAULT_CONTEXT_ROOT = _REPO_ROOT / "ai_study_buddy" / "context"


def _repo_root() -> Path:
    return _REPO_ROOT


def _default_registry_db() -> Path:
    return _repo_root() / "ai_study_buddy" / "db" / "pdf_registry.db"


def _default_study_db() -> Path:
    return _repo_root() / "ai_study_buddy" / "db" / "study_buddy.db"


def _extract_grade(path: str) -> str:
    match = re.search(r"/((P[1-6])|PSLE)/", path.replace("\\", "/"), flags=re.IGNORECASE)
    if not match:
        return "UNKNOWN"
    return match.group(1).upper()


def _select_detector(*, subject: str, metadata_raw: str | None) -> str:
    lowered = (subject or "").strip().lower()
    if lowered == "english":
        return "english-paper-2-question-section-detector"
    if lowered == "science":
        return "science-question-section-detector"
    if lowered == "math":
        return "math-question-section-detector"
    if lowered == "chinese":
        chinese_variant = None
        if metadata_raw:
            try:
                payload = json.loads(metadata_raw)
                if isinstance(payload, dict):
                    value = payload.get("chinese_variant")
                    if isinstance(value, str):
                        chinese_variant = value.strip().lower()
            except Exception:
                chinese_variant = None
        if chinese_variant == "higher":
            return "higher-chinese-paper-2-question-section-detector"
        return "chinese-paper-2-question-section-detector"
    return "math-question-section-detector"


def build_queue(
    *,
    registry_db: Path,
    study_db: Path,
    include_student_grade_filters: list[tuple[str, set[str]]],
    context_root: Path | None = None,
    attach_marking_reference: bool = True,
) -> dict[str, Any]:
    sconn = sqlite3.connect(str(study_db))
    sconn.row_factory = sqlite3.Row
    rconn = sqlite3.connect(str(registry_db))
    rconn.row_factory = sqlite3.Row
    try:
        marked_completion_ids = {
            str(row["attempt_file_id"])
            for row in sconn.execute(
                "SELECT DISTINCT attempt_file_id FROM marking_artifacts WHERE is_deleted=0 AND attempt_file_id IS NOT NULL"
            )
        }
        templates_with_fqi = {
            str(row["primary_file_id"])
            for row in sconn.execute(
                "SELECT DISTINCT primary_file_id FROM file_question_info_runs WHERE is_deleted=0 AND primary_file_id IS NOT NULL"
            )
        }
        if not marked_completion_ids:
            return {
                "summary": {
                    "marked_completion_total": 0,
                    "prioritized_completion_total": 0,
                    "prioritized_template_total": 0,
                    "filters": [
                        {"student_name": student, "grades": sorted(list(grades))}
                        for student, grades in include_student_grade_filters
                    ],
                },
                "items": [],
            }

        completion_placeholders = ",".join("?" for _ in marked_completion_ids)
        relation_rows = rconn.execute(
            f"""
            SELECT fr.source_id AS completion_id, fr.target_id AS template_id
            FROM file_relations fr
            JOIN pdf_files completion ON completion.id = fr.source_id
            JOIN pdf_files template ON template.id = fr.target_id
            WHERE fr.relation_type='completed_from'
              AND completion.is_template=0
              AND template.is_template=1
              AND fr.source_id IN ({completion_placeholders})
            """,
            tuple(marked_completion_ids),
        ).fetchall()
        completion_to_template = {
            str(row["completion_id"]): str(row["template_id"])
            for row in relation_rows
            if row["completion_id"] is not None and row["template_id"] is not None
        }
        gap_completion_ids = [
            completion_id
            for completion_id, template_id in completion_to_template.items()
            if template_id not in templates_with_fqi
        ]

        if not gap_completion_ids:
            return {
                "summary": {
                    "marked_completion_total": len(marked_completion_ids),
                    "prioritized_completion_total": 0,
                    "prioritized_template_total": 0,
                    "filters": [
                        {"student_name": student, "grades": sorted(list(grades))}
                        for student, grades in include_student_grade_filters
                    ],
                },
                "items": [],
            }

        gap_placeholders = ",".join("?" for _ in gap_completion_ids)
        completion_rows = rconn.execute(
            f"""
            SELECT id, path, subject, doc_type, student_id
            FROM pdf_files
            WHERE id IN ({gap_placeholders})
            """,
            tuple(gap_completion_ids),
        ).fetchall()
        completion_by_id = {str(row["id"]): row for row in completion_rows}

        students = {
            str(row["id"]): str(row["name"] or row["id"])
            for row in rconn.execute("SELECT id, name FROM students").fetchall()
        }

        def include_completion(row: sqlite3.Row) -> bool:
            student_name = students.get(str(row["student_id"]), str(row["student_id"]))
            grade = _extract_grade(str(row["path"] or ""))
            for wanted_student, wanted_grades in include_student_grade_filters:
                if student_name == wanted_student and grade in wanted_grades:
                    return True
            return False

        prioritized_completion_ids: list[str] = []
        for completion_id in gap_completion_ids:
            row = completion_by_id.get(completion_id)
            if row is None:
                continue
            if include_completion(row):
                prioritized_completion_ids.append(completion_id)

        if not prioritized_completion_ids:
            return {
                "summary": {
                    "marked_completion_total": len(marked_completion_ids),
                    "prioritized_completion_total": 0,
                    "prioritized_template_total": 0,
                    "filters": [
                        {"student_name": student, "grades": sorted(list(grades))}
                        for student, grades in include_student_grade_filters
                    ],
                },
                "items": [],
            }

        prioritized_template_ids = sorted(
            {completion_to_template[completion_id] for completion_id in prioritized_completion_ids}
        )
        template_placeholders = ",".join("?" for _ in prioritized_template_ids)
        template_rows = rconn.execute(
            f"""
            SELECT id, path, subject, doc_type, metadata
            FROM pdf_files
            WHERE id IN ({template_placeholders})
            """,
            tuple(prioritized_template_ids),
        ).fetchall()
        template_by_id = {str(row["id"]): row for row in template_rows}

        completions_by_template: dict[str, list[str]] = defaultdict(list)
        for completion_id in prioritized_completion_ids:
            template_id = completion_to_template[completion_id]
            completions_by_template[template_id].append(completion_id)

        items: list[dict[str, Any]] = []
        for index, template_id in enumerate(prioritized_template_ids, start=1):
            template = template_by_id.get(template_id)
            if template is None:
                continue
            linked_completion_ids = sorted(completions_by_template.get(template_id, []))
            linked_completion_rows = [
                completion_by_id[completion_id]
                for completion_id in linked_completion_ids
                if completion_id in completion_by_id
            ]
            detector = _select_detector(
                subject=str(template["subject"] or ""),
                metadata_raw=str(template["metadata"]) if template["metadata"] is not None else None,
            )
            item: dict[str, Any] = {
                "ord": index,
                "template_file_id": template_id,
                "template_path": str(template["path"] or ""),
                "template_subject": str(template["subject"] or "").lower(),
                "template_doc_type": str(template["doc_type"] or "").lower(),
                "template_grade": _extract_grade(str(template["path"] or "")),
                "detector": detector,
                "linked_completion_count": len(linked_completion_rows),
                "linked_completion_file_ids": linked_completion_ids,
                "linked_completion_paths": [str(row["path"] or "") for row in linked_completion_rows],
                "linked_student_names": sorted(
                    {
                        students.get(str(row["student_id"]), str(row["student_id"]))
                        for row in linked_completion_rows
                        if row["student_id"] is not None
                    }
                ),
                "status": "pending_detection",
            }
            if attach_marking_reference:
                item["marking_reference"] = build_template_marking_reference(
                    sconn,
                    template_file_id=template_id,
                    linked_completion_file_ids=linked_completion_ids,
                    context_root=context_root or _DEFAULT_CONTEXT_ROOT,
                )
            items.append(item)

        detector_counts: dict[str, int] = defaultdict(int)
        for item in items:
            detector_counts[str(item["detector"])] += 1

        return {
            "summary": {
                "marked_completion_total": len(marked_completion_ids),
                "templates_with_fqi_total": len(templates_with_fqi),
                "gap_completion_total": len(gap_completion_ids),
                "prioritized_completion_total": len(prioritized_completion_ids),
                "prioritized_template_total": len(items),
                "detector_counts": dict(sorted(detector_counts.items())),
                "attach_marking_reference": attach_marking_reference,
                "filters": [
                    {"student_name": student, "grades": sorted(list(grades))}
                    for student, grades in include_student_grade_filters
                ],
            },
            "items": items,
        }
    finally:
        sconn.close()
        rconn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a template detector queue for prioritized completion coverage gaps "
            "(marked completions whose linked templates lack file_question_info)."
        )
    )
    parser.add_argument(
        "--registry-db",
        type=Path,
        default=_default_registry_db(),
        help="Path to pdf_registry.db",
    )
    parser.add_argument(
        "--study-db",
        type=Path,
        default=_default_study_db(),
        help="Path to study_buddy.db",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_SCRIPT_DIR / "queues" / "priority_template_fqi_detector_queue.json",
        help="Output JSON queue path",
    )
    parser.add_argument(
        "--context-root",
        type=Path,
        default=_DEFAULT_CONTEXT_ROOT,
        help="Context root for marking_result relative paths in marking_reference",
    )
    parser.add_argument(
        "--student-grade",
        action="append",
        default=[],
        metavar="NAME:GRADE[,GRADE...]",
        help="Repeatable student+grade filter (e.g. 'Abigail Meng:P1'). Overrides --filter-set.",
    )
    parser.add_argument(
        "--filter-set",
        choices=("default", "remaining-fqi-p1-p5"),
        default="default",
        help="Preset filters when --student-grade is not passed (default: Winston P6/PSLE + Emma P4)",
    )
    parser.add_argument(
        "--no-marking-reference",
        action="store_true",
        help="Omit marking_reference on queue items (detector prompt will lack prior question_page_map)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.student_grade:
        filters = parse_student_grade_filters(args.student_grade)
    elif args.filter_set == "remaining-fqi-p1-p5":
        filters = remaining_p1_p5_filters()
    else:
        filters = default_priority_filters()
    payload = build_queue(
        registry_db=args.registry_db.expanduser().resolve(),
        study_db=args.study_db.expanduser().resolve(),
        include_student_grade_filters=filters,
        context_root=args.context_root.expanduser().resolve(),
        attach_marking_reference=not args.no_marking_reference,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(args.output))
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
