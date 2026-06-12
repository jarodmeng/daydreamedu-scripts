#!/usr/bin/env python3
"""Report completion mains missing a template link (no ``completed_from`` edge).

Completion mains are ``pdf_files`` rows with ``file_type='main'`` and
``is_template=0``. A template link exists when there is a ``file_relations`` row
with ``relation_type='completed_from'`` and ``source_id`` equal to the
completion's ``id``.

By default, ``doc_type`` values ``activity`` and ``note`` are excluded so the
report targets exam / exercise / book completions only (see L4 framework).
``composition`` completions are always excluded: they do not require a template
link (proposal 18). GoodNotes WIP completions under a ``Not completed`` path
segment are also excluded by default (same convention as GoodNotes leaf-registry
reports).

Usage::

  python3 -m ai_study_buddy.pdf_file_manager.scripts.completion_template_link_gap_report
  python3 -m ai_study_buddy.pdf_file_manager.scripts.completion_template_link_gap_report --include-activity-note
  python3 -m ai_study_buddy.pdf_file_manager.scripts.completion_template_link_gap_report --db /path/to/pdf_registry.db
  python3 -m ai_study_buddy.pdf_file_manager.scripts.completion_template_link_gap_report --json

Exit code: ``0`` when there are zero gap rows under the chosen filters; ``1``
when at least one completion is still missing a template link.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def repo_root() -> Path:
    return SCRIPT_DIR.parent.parent.parent


def default_db_path() -> Path:
    return repo_root() / "ai_study_buddy" / "db" / "pdf_registry.db"


# Compositions are standalone writing samples; never require completed_from.
_ALWAYS_EXCLUDED_DOC_TYPES = ("composition",)
_OPTIONAL_EXCLUDED_DOC_TYPES = ("activity", "note")


def _doc_type_filter_sql(include_activity_note: bool) -> str:
    excluded = list(_ALWAYS_EXCLUDED_DOC_TYPES)
    if not include_activity_note:
        excluded.extend(_OPTIONAL_EXCLUDED_DOC_TYPES)
    quoted = ", ".join(f"'{value}'" for value in excluded)
    return f"f.doc_type NOT IN ({quoted})"


def _path_has_not_completed_segment_sql() -> str:
    """SQL truth value: ``f.path`` has a ``Not completed`` segment (case-insensitive)."""
    normalized = "LOWER(REPLACE(f.path, '\\\\', '/'))"
    return f"INSTR({normalized}, '/not completed/') > 0"


def _scope_filter_sql(*, include_activity_note: bool, exclude_not_completed: bool) -> str:
    clauses = [_doc_type_filter_sql(include_activity_note)]
    if exclude_not_completed:
        clauses.append(f"NOT ({_path_has_not_completed_segment_sql()})")
    return " AND ".join(clauses)


def build_report(
    db_path: Path,
    *,
    include_activity_note: bool,
    exclude_not_completed: bool = True,
) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    scope_clause = _scope_filter_sql(
        include_activity_note=include_activity_note,
        exclude_not_completed=exclude_not_completed,
    )

    cur.execute(
        f"""
        SELECT COUNT(*) AS n
        FROM pdf_files f
        WHERE f.file_type = 'main' AND f.is_template = 0 AND ({scope_clause})
        """
    )
    completion_total = int(cur.fetchone()["n"])

    cur.execute(
        f"""
        SELECT COUNT(*) AS n
        FROM pdf_files f
        WHERE f.file_type = 'main' AND f.is_template = 0 AND ({scope_clause})
          AND EXISTS (
            SELECT 1 FROM file_relations r
            WHERE r.source_id = f.id AND r.relation_type = 'completed_from'
          )
        """
    )
    with_template = int(cur.fetchone()["n"])

    cur.execute(
        f"""
        SELECT
          CASE
            WHEN INSTR(f.path, '/GoodNotes/') > 0 THEN 'g_root'
            WHEN INSTR(f.path, '/DaydreamEdu/') > 0 THEN 'd_root'
            ELSE '(unknown)'
          END AS file_root,
          f.doc_type,
          COALESCE(s.name, '(no student)') AS student_name,
          COALESCE(json_extract(f.metadata, '$.grade_or_scope'), '(no grade)') AS grade,
          COALESCE(f.subject, '(no subject)') AS subject,
          COUNT(*) AS cnt
        FROM pdf_files f
        LEFT JOIN students s ON s.id = f.student_id
        WHERE f.file_type = 'main' AND f.is_template = 0 AND ({scope_clause})
          AND NOT EXISTS (
            SELECT 1 FROM file_relations r
            WHERE r.source_id = f.id AND r.relation_type = 'completed_from'
          )
        GROUP BY file_root, f.doc_type, student_name, grade, subject
        ORDER BY cnt DESC, file_root, f.doc_type, student_name, grade, subject
        """
    )
    gap_rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    without_template = sum(r["cnt"] for r in gap_rows)
    assert completion_total == with_template + without_template, (
        completion_total,
        with_template,
        without_template,
    )

    return {
        "registry_db": str(db_path.resolve()),
        "filters": {
            "include_activity_note": include_activity_note,
            "exclude_not_completed": exclude_not_completed,
        },
        "summary": {
            "completion_mains": completion_total,
            "with_template": with_template,
            "without_template": without_template,
            "gap_buckets": len(gap_rows),
        },
        "gaps": gap_rows,
    }


def _print_human(report: dict) -> None:
    filt = report["filters"]
    summ = report["summary"]
    gaps = report["gaps"]
    print(f"Registry: {report['registry_db']}")
    filter_bits = []
    if filt["include_activity_note"]:
        filter_bits.append("all completion doc_types except composition")
    else:
        filter_bits.append("doc_type NOT IN (activity, note, composition)")
    if filt.get("exclude_not_completed", True):
        filter_bits.append("exclude Not completed path segment")
    print("Filter: " + "; ".join(filter_bits))
    print()
    print(
        f"Completion mains: {summ['completion_mains']}  "
        f"with template: {summ['with_template']}  "
        f"without template: {summ['without_template']}  "
        f"gap buckets: {summ['gap_buckets']}"
    )
    print()
    if not gaps:
        print("No completions missing a template link under this filter.")
        return

    print(f"{'cnt':>4}  {'root':<8}  {'doc_type':<10}  {'student':<24}  {'grade':<10}  subject")
    print("-" * 96)
    for r in gaps:
        name = (r["student_name"] or "")[:24]
        print(
            f"{r['cnt']:4d}  {r['file_root']:<8}  {r['doc_type']:<10}  "
            f"{name:<24}  {r['grade']!s:<10}  {r['subject']}"
        )
    print("-" * 96)
    print(f"{summ['without_template']:4d}  (total without template)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List completion mains missing a template (completed_from) link."
    )
    parser.add_argument("--db", default=str(default_db_path()), help="Path to pdf_registry.db")
    parser.add_argument(
        "--include-activity-note",
        action="store_true",
        help="Include activity and note doc_types (default excludes them).",
    )
    parser.add_argument(
        "--include-not-completed",
        action="store_true",
        help="Include completions under a Not completed path segment (default excludes WIP).",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"error: registry database not found: {db_path}", flush=True)
        return 2

    report = build_report(
        db_path,
        include_activity_note=args.include_activity_note,
        exclude_not_completed=not args.include_not_completed,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)

    return 0 if report["summary"]["without_template"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
