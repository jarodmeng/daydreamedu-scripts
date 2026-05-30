"""Audit marking amendments against base marking results for obsolete overrides."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ai_study_buddy.learning_db.analysis.marking_amendment_obsolescence import (
    AuditReport,
    Source,
    build_report,
)
from ai_study_buddy.learning_db.core.connection import default_context_root, default_db_path


def _print_human(report: AuditReport, *, sample_limit: int) -> None:
    data = report.to_dict(sample_limit=sample_limit)
    print(f"Source: {report.source}")
    if report.db_path:
        print(f"DB: {report.db_path}")
    if report.context_root:
        print(f"Context: {report.context_root}")
    if report.source == "both":
        print(f"DB vs JSON status mismatches: {report.db_json_mismatch_count}")
    print()

    counts = data["counts"]
    total = counts["total_field_items"]
    print(f"Total amended field items: {total}")
    for status in ("obsolete", "active", "missing_row", "error"):
        count = counts.get(status, 0)
        if count:
            pct = 100 * count / total if total else 0
            print(f"  {status:12s} {count:4d} ({pct:.1f}%)")
    print()

    print("By kind:")
    for kind, count in sorted(report.kind_counts.items()):
        kind_items = [item for item in report.items if item.kind == kind]
        obs = sum(1 for item in kind_items if item.status == "obsolete")
        act = sum(1 for item in kind_items if item.status == "active")
        print(f"  {kind:16s} total={count:4d}  obsolete={obs:4d}  active={act:4d}")
    print()

    print("Amendment file rollup:")
    rollup = data["amendment_file_rollup"]
    print(f"  fully obsolete:      {rollup['fully_obsolete']}")
    print(f"  partially obsolete:  {rollup['partially_obsolete']}")
    print(f"  no obsolete items:   {rollup['no_obsolete_items']}")
    print()

    print("By field (question_field):")
    field_counts: Counter[tuple[str, str]] = Counter()
    for item in report.items:
        if item.kind != "question_field" or item.status not in {"obsolete", "active"}:
            continue
        field_counts[(item.field_key, item.status)] += 1
    for (field_key, status), count in sorted(field_counts.items(), key=lambda x: (-x[1], x[0][0], x[0][1])):
        print(f"  {field_key:25s} {status:10s} {count}")

    print()
    print("By student/subject (question_field):")
    ss: Counter[tuple[str | None, str | None, str]] = Counter()
    for item in report.items:
        if item.kind != "question_field" or item.status not in {"obsolete", "active"}:
            continue
        ss[(item.student_id, item.subject_context, item.status)] += 1
    keys = sorted(set(k[:2] for k in ss))
    for student_id, subject_context in keys:
        obs = ss[(student_id, subject_context, "obsolete")]
        act = ss[(student_id, subject_context, "active")]
        tot = obs + act
        if not tot:
            continue
        pct = 100 * obs / tot
        print(f"  {student_id or '?':8s} {subject_context or '?':30s} obsolete={obs:3d} active={act:3d} ({pct:.0f}% obsolete)")

    samples = data["samples"]
    if samples["fully_obsolete_amendment_paths"]:
        print()
        print("Sample fully obsolete amendment paths:")
        for path in samples["fully_obsolete_amendment_paths"]:
            print(f"  - {path}")
    if samples["partially_obsolete_amendment_paths"]:
        print()
        print("Sample partially obsolete amendment paths:")
        for path in samples["partially_obsolete_amendment_paths"]:
            print(f"  - {path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit marking amendments for obsolete overrides (base marking result already matches)."
    )
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--context-root", type=Path, default=None)
    parser.add_argument(
        "--source",
        choices=("db", "json", "both"),
        default="db",
        help="Compare amendments to base marking results from DB rows, JSON files, or both (default: db).",
    )
    parser.add_argument("--sample-limit", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="Emit full report as JSON.")
    parser.add_argument(
        "--list-prune-candidates",
        action="store_true",
        help="Print fully/partially obsolete amendment paths suitable for prune review.",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path or default_db_path()).expanduser().resolve()
    context_root = Path(args.context_root or default_context_root()).expanduser().resolve()
    source: Source = args.source

    report = build_report(source=source, db_path=db_path, context_root=context_root)

    if args.json:
        print(json.dumps(report.to_dict(sample_limit=args.sample_limit), ensure_ascii=False, indent=2))
    else:
        _print_human(report, sample_limit=args.sample_limit)

    if args.list_prune_candidates:
        print()
        print("=== Prune candidates ===")
        print("Fully obsolete amendment files:")
        for path in report.fully_obsolete_amendment_paths():
            count = len(report.items_by_amendment_path()[path])
            print(f"  delete_file: {path} ({count} obsolete field items)")
        print()
        print("Partially obsolete amendment files:")
        for path in report.partially_obsolete_amendment_paths():
            group = report.items_by_amendment_path()[path]
            obs = sum(1 for item in group if item.status == "obsolete")
            act = sum(1 for item in group if item.status == "active")
            print(f"  edit_file: {path} ({obs} obsolete / {act} active field items)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
