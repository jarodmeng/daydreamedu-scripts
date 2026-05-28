"""Report DB<->context path drift for marking artifact families.

This checker is read-only and intended for recurring health checks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ai_study_buddy.learning_db.core.connection import default_context_root, default_db_path, get_connection


def _exists_rel(context_root: Path, rel_path: str | None) -> bool:
    if not rel_path:
        return False
    return (context_root / rel_path).resolve(strict=False).exists()


def _sample(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return rows[: max(limit, 0)]


def build_report(*, db_path: Path, context_root: Path, sample_limit: int = 5) -> dict[str, Any]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT artifact_id, artifact_path, marking_asset, is_deleted
            FROM marking_artifacts
            """
        ).fetchall()
        missing_artifact_path = [
            {"artifact_id": r["artifact_id"], "artifact_path": r["artifact_path"]}
            for r in rows
            if int(r["is_deleted"]) == 0 and not _exists_rel(context_root, str(r["artifact_path"]))
        ]
        missing_marking_asset = [
            {"artifact_id": r["artifact_id"], "marking_asset": r["marking_asset"]}
            for r in rows
            if int(r["is_deleted"]) == 0 and r["marking_asset"] and not _exists_rel(context_root, str(r["marking_asset"]))
        ]

        review_rows = conn.execute(
            """
            SELECT review_state_id, review_state_path, marking_result_path, is_deleted
            FROM student_review_states
            """
        ).fetchall()
        missing_review_state_path = [
            {"review_state_id": r["review_state_id"], "review_state_path": r["review_state_path"]}
            for r in review_rows
            if int(r["is_deleted"]) == 0 and not _exists_rel(context_root, str(r["review_state_path"]))
        ]
        missing_review_marking_result_path = [
            {"review_state_id": r["review_state_id"], "marking_result_path": r["marking_result_path"]}
            for r in review_rows
            if int(r["is_deleted"]) == 0 and not _exists_rel(context_root, str(r["marking_result_path"]))
        ]

        amend_rows = conn.execute(
            """
            SELECT amendment_id, amendment_path, marking_result_path, is_deleted
            FROM marking_amendments
            """
        ).fetchall()
        missing_amendment_path = [
            {"amendment_id": r["amendment_id"], "amendment_path": r["amendment_path"]}
            for r in amend_rows
            if int(r["is_deleted"]) == 0 and not _exists_rel(context_root, str(r["amendment_path"]))
        ]
        missing_amend_marking_result_path = [
            {"amendment_id": r["amendment_id"], "marking_result_path": r["marking_result_path"]}
            for r in amend_rows
            if int(r["is_deleted"]) == 0 and not _exists_rel(context_root, str(r["marking_result_path"]))
        ]

        artifact_paths = {
            str(r["artifact_path"])
            for r in conn.execute("SELECT artifact_path FROM marking_artifacts").fetchall()
        }
        review_not_in_marking_artifacts = [
            {"review_state_id": r["review_state_id"], "marking_result_path": r["marking_result_path"]}
            for r in conn.execute(
                """
                SELECT review_state_id, marking_result_path
                FROM student_review_states
                WHERE is_deleted = 0
                """
            ).fetchall()
            if str(r["marking_result_path"]) not in artifact_paths
        ]
        amend_not_in_marking_artifacts = [
            {"amendment_id": r["amendment_id"], "marking_result_path": r["marking_result_path"]}
            for r in conn.execute(
                """
                SELECT amendment_id, marking_result_path
                FROM marking_amendments
                WHERE is_deleted = 0
                """
            ).fetchall()
            if str(r["marking_result_path"]) not in artifact_paths
        ]

        identity_rows = conn.execute(
            """
            SELECT map_id, artifact_family, source_path
            FROM import_identity_map
            WHERE artifact_family IN ('marking_result', 'marking_amendment', 'student_review_state')
            """
        ).fetchall()
        identity_source_path_base_missing = []
        for r in identity_rows:
            source_path = str(r["source_path"])
            base = source_path.split("::", 1)[0]
            if not _exists_rel(context_root, base):
                identity_source_path_base_missing.append(
                    {"map_id": r["map_id"], "artifact_family": r["artifact_family"], "source_path": source_path}
                )

        checks = {
            "marking_artifacts_missing_artifact_path": missing_artifact_path,
            "marking_artifacts_missing_marking_asset": missing_marking_asset,
            "student_review_states_missing_review_state_path": missing_review_state_path,
            "student_review_states_missing_marking_result_path": missing_review_marking_result_path,
            "marking_amendments_missing_amendment_path": missing_amendment_path,
            "marking_amendments_missing_marking_result_path": missing_amend_marking_result_path,
            "student_review_states_marking_result_path_not_in_marking_artifacts": review_not_in_marking_artifacts,
            "marking_amendments_marking_result_path_not_in_marking_artifacts": amend_not_in_marking_artifacts,
            "import_identity_map_source_path_base_missing": identity_source_path_base_missing,
        }
        counts = {key: len(value) for key, value in checks.items()}
        total_issues = sum(counts.values())
        return {
            "db_path": str(db_path.resolve()),
            "context_root": str(context_root.resolve()),
            "total_issues": total_issues,
            "counts": counts,
            "samples": {key: _sample(value, sample_limit) for key, value in checks.items()},
        }
    finally:
        conn.close()


def _print_human(report: dict[str, Any]) -> None:
    print(f"DB: {report['db_path']}")
    print(f"Context: {report['context_root']}")
    print(f"Total issues: {report['total_issues']}")
    print("\nCounts:")
    for key, value in report["counts"].items():
        print(f"- {key}: {value}")

    print("\nSamples:")
    for key, rows in report["samples"].items():
        if not rows:
            continue
        print(f"- {key}:")
        for row in rows:
            parts = ", ".join(f"{k}={v}" for k, v in row.items())
            print(f"  - {parts}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Report DB/context drift for marking artifacts.")
    parser.add_argument("--db-path", type=Path, default=None, help="Path to study_buddy.db.")
    parser.add_argument("--context-root", type=Path, default=None, help="Path to context root.")
    parser.add_argument("--sample-limit", type=int, default=5, help="Sample rows per check in output.")
    parser.add_argument("--json", action="store_true", help="Emit report as JSON.")
    parser.add_argument(
        "--fail-on-any",
        action="store_true",
        help="Return exit code 1 if any drift issue count is non-zero.",
    )
    args = parser.parse_args()

    db_path = args.db_path or default_db_path()
    context_root = args.context_root or default_context_root()
    report = build_report(
        db_path=Path(db_path).expanduser().resolve(),
        context_root=Path(context_root).expanduser().resolve(),
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
