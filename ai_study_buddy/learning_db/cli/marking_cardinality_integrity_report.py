"""Cardinality integrity report for marking context artifacts.

Checks:
1) template file -> at most 1 file_question_info run
2) completion file -> at most 1 active marking family artifact
   (marking_results / marking_assets / learning_reports / marking_amendments / student_review_states)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _sample(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return items[: max(limit, 0)]


def build_report(*, pdf_registry_db: Path, study_buddy_db: Path, context_root: Path, sample_limit: int = 5) -> dict[str, Any]:
    pr = _connect(pdf_registry_db)
    ld = _connect(study_buddy_db)
    try:
        template_ids = {
            str(r["id"])
            for r in pr.execute(
                "SELECT id FROM pdf_files WHERE file_type='main' AND is_template=1"
            ).fetchall()
        }
        completion_ids = {
            str(r["id"])
            for r in pr.execute(
                "SELECT id FROM pdf_files WHERE file_type='main' AND is_template=0"
            ).fetchall()
        }

        # Rule 1: template -> file_question_info (DB)
        fqi_db_counts: dict[str, int] = defaultdict(int)
        if "file_question_info_runs" in {
            str(r["name"])
            for r in ld.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }:
            for r in ld.execute("SELECT primary_file_id FROM file_question_info_runs WHERE is_deleted=0").fetchall():
                file_id = r["primary_file_id"]
                if file_id:
                    fqi_db_counts[str(file_id)] += 1

        fqi_db_violations = [
            {"template_file_id": file_id, "count": count}
            for file_id, count in fqi_db_counts.items()
            if file_id in template_ids and count > 1
        ]

        # Rule 1: template -> file_question_info (on disk by payload)
        fqi_disk_counts: dict[str, int] = defaultdict(int)
        fqi_root = context_root / "file_question_info"
        if fqi_root.exists():
            for p in fqi_root.rglob("question_sections.json"):
                try:
                    payload = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                files = ((payload.get("input_context") or {}).get("files") or []) if isinstance(payload, dict) else []
                if files and isinstance(files[0], dict):
                    file_id = files[0].get("file_id")
                    if file_id:
                        fqi_disk_counts[str(file_id)] += 1

        fqi_disk_violations = [
            {"template_file_id": file_id, "count": count}
            for file_id, count in fqi_disk_counts.items()
            if file_id in template_ids and count > 1
        ]

        # Completion-side checks (DB first)
        marking_result_db_counts: dict[str, int] = defaultdict(int)
        marking_asset_db_distinct: dict[str, set[str]] = defaultdict(set)
        for r in ld.execute(
            "SELECT attempt_file_id, marking_asset FROM marking_artifacts WHERE is_deleted=0"
        ).fetchall():
            completion_id = r["attempt_file_id"]
            if not completion_id:
                continue
            completion_id = str(completion_id)
            marking_result_db_counts[completion_id] += 1
            if r["marking_asset"]:
                marking_asset_db_distinct[completion_id].add(str(r["marking_asset"]))

        marking_amendment_db_counts: dict[str, int] = defaultdict(int)
        for r in ld.execute(
            "SELECT attempt_file_id FROM marking_amendments WHERE is_deleted=0"
        ).fetchall():
            completion_id = r["attempt_file_id"]
            if completion_id:
                marking_amendment_db_counts[str(completion_id)] += 1

        review_state_db_counts: dict[str, int] = defaultdict(int)
        for r in ld.execute(
            "SELECT attempt_file_id FROM student_review_states WHERE is_deleted=0"
        ).fetchall():
            completion_id = r["attempt_file_id"]
            if completion_id:
                review_state_db_counts[str(completion_id)] += 1

        # Completion-side checks (on disk via payload join)
        marking_result_disk_counts: dict[str, int] = defaultdict(int)
        learning_report_disk_counts: dict[str, int] = defaultdict(int)
        marking_asset_disk_distinct: dict[str, set[str]] = defaultdict(set)

        results_root = context_root / "marking_results"
        if results_root.exists():
            for p in results_root.rglob("*.json"):
                try:
                    payload = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                context = payload.get("context") if isinstance(payload, dict) else None
                if not isinstance(context, dict):
                    continue
                completion_id = context.get("attempt_file_id")
                if not completion_id:
                    continue
                completion_id = str(completion_id)
                marking_result_disk_counts[completion_id] += 1

                # derived report path
                rel_parent = p.relative_to(results_root).parent
                report_path = context_root / "learning_reports" / rel_parent / f"{p.stem} - Marking Report.md"
                if report_path.exists():
                    learning_report_disk_counts[completion_id] += 1

                marking_asset_rel = context.get("marking_asset")
                if isinstance(marking_asset_rel, str) and marking_asset_rel.strip():
                    asset_path = context_root / marking_asset_rel
                    if asset_path.exists():
                        marking_asset_disk_distinct[completion_id].add(marking_asset_rel)

        marking_amendment_disk_counts: dict[str, int] = defaultdict(int)
        amend_root = context_root / "marking_amendments"
        if amend_root.exists():
            for p in amend_root.rglob("*.json"):
                try:
                    payload = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                completion_id = ((payload.get("context") or {}).get("attempt_file_id")) if isinstance(payload, dict) else None
                if completion_id:
                    marking_amendment_disk_counts[str(completion_id)] += 1

        review_state_disk_counts: dict[str, int] = defaultdict(int)
        review_root = context_root / "student_review_states"
        if review_root.exists():
            for p in review_root.rglob("*.json"):
                try:
                    payload = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                completion_id = ((payload.get("context") or {}).get("attempt_file_id")) if isinstance(payload, dict) else None
                if completion_id:
                    review_state_disk_counts[str(completion_id)] += 1

        # Violation builders
        def db_count_violations(counts: dict[str, int], *, family: str) -> list[dict[str, Any]]:
            return [
                {"completion_file_id": completion_id, "family": family, "count": count}
                for completion_id, count in counts.items()
                if completion_id in completion_ids and count > 1
            ]

        def disk_count_violations(counts: dict[str, int], *, family: str) -> list[dict[str, Any]]:
            return [
                {"completion_file_id": completion_id, "family": family, "count": count}
                for completion_id, count in counts.items()
                if completion_id in completion_ids and count > 1
            ]

        def distinct_violations(distinct_map: dict[str, set[str]], *, family: str) -> list[dict[str, Any]]:
            return [
                {
                    "completion_file_id": completion_id,
                    "family": family,
                    "distinct_count": len(paths),
                    "examples": sorted(paths)[:3],
                }
                for completion_id, paths in distinct_map.items()
                if completion_id in completion_ids and len(paths) > 1
            ]

        completion_db_violations = (
            db_count_violations(marking_result_db_counts, family="marking_results")
            + distinct_violations(marking_asset_db_distinct, family="marking_assets")
            + db_count_violations(marking_amendment_db_counts, family="marking_amendments")
            + db_count_violations(review_state_db_counts, family="student_review_states")
        )
        completion_disk_violations = (
            disk_count_violations(marking_result_disk_counts, family="marking_results")
            + distinct_violations(marking_asset_disk_distinct, family="marking_assets")
            + disk_count_violations(learning_report_disk_counts, family="learning_reports")
            + disk_count_violations(marking_amendment_disk_counts, family="marking_amendments")
            + disk_count_violations(review_state_disk_counts, family="student_review_states")
        )

        checks = {
            "template_file_question_info_db_cardinality": fqi_db_violations,
            "template_file_question_info_disk_cardinality": fqi_disk_violations,
            "completion_marking_family_db_cardinality": completion_db_violations,
            "completion_marking_family_disk_cardinality": completion_disk_violations,
        }
        counts = {name: len(rows) for name, rows in checks.items()}
        total_issues = sum(counts.values())
        return {
            "pdf_registry_db": str(pdf_registry_db.resolve()),
            "study_buddy_db": str(study_buddy_db.resolve()),
            "context_root": str(context_root.resolve()),
            "total_issues": total_issues,
            "counts": counts,
            "samples": {name: _sample(rows, sample_limit) for name, rows in checks.items()},
        }
    finally:
        pr.close()
        ld.close()


def _print_human(report: dict[str, Any]) -> None:
    print(f"pdf_registry_db: {report['pdf_registry_db']}")
    print(f"study_buddy_db: {report['study_buddy_db']}")
    print(f"context_root: {report['context_root']}")
    print(f"total_issues: {report['total_issues']}")
    print("\nCounts:")
    for k, v in report["counts"].items():
        print(f"- {k}: {v}")
    print("\nSamples:")
    for name, rows in report["samples"].items():
        if not rows:
            continue
        print(f"- {name}:")
        for row in rows:
            print("  - " + ", ".join(f"{k}={v}" for k, v in row.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description="Cardinality integrity report for template/completion marking artifacts.")
    parser.add_argument("--registry-db-path", type=Path, default=Path("ai_study_buddy/db/pdf_registry.db"))
    parser.add_argument("--study-db-path", type=Path, default=Path("ai_study_buddy/db/study_buddy.db"))
    parser.add_argument("--context-root", type=Path, default=Path("ai_study_buddy/context"))
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-any", action="store_true")
    args = parser.parse_args()

    report = build_report(
        pdf_registry_db=args.registry_db_path.expanduser().resolve(),
        study_buddy_db=args.study_db_path.expanduser().resolve(),
        context_root=args.context_root.expanduser().resolve(),
        sample_limit=args.sample_limit,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    if args.fail_on_any and report["total_issues"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
