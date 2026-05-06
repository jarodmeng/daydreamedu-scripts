from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from ai_study_buddy.learning_db.core.connection import default_context_root, default_db_path, get_connection
from ai_study_buddy.learning_db.core.migrate import apply_migrations


@dataclass
class ValidationReport:
    source_count: int
    db_count: int
    unresolved: int


def _count_source(context_root: Path, folder: str) -> int:
    target = context_root / folder
    if not target.exists():
        return 0
    return len(list(target.rglob("*.json")))


def run_validation(db_path: Path, context_root: Path) -> dict[str, ValidationReport]:
    apply_migrations(db_path=db_path)
    conn = get_connection(db_path)
    try:
        result = {
            "marking_result": ValidationReport(
                source_count=_count_source(context_root, "marking_results"),
                db_count=int(conn.execute("SELECT COUNT(*) AS c FROM marking_artifacts").fetchone()["c"]),
                unresolved=0,
            ),
            "marking_amendment": ValidationReport(
                source_count=_count_source(context_root, "marking_amendments"),
                db_count=int(conn.execute("SELECT COUNT(*) AS c FROM marking_amendments").fetchone()["c"]),
                unresolved=int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM marking_amendments ma
                        LEFT JOIN marking_artifacts a ON a.artifact_id = ma.artifact_id
                        WHERE a.artifact_id IS NULL
                        """
                    ).fetchone()["c"]
                ),
            ),
            "student_review_state": ValidationReport(
                source_count=_count_source(context_root, "student_review_states"),
                db_count=int(conn.execute("SELECT COUNT(*) AS c FROM student_review_states").fetchone()["c"]),
                unresolved=int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM student_review_states rs
                        LEFT JOIN marking_artifacts a ON a.artifact_id = rs.artifact_id
                        WHERE a.artifact_id IS NULL
                        """
                    ).fetchone()["c"]
                ),
            ),
        }
        return result
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate study_buddy.db structural import health (counts, FKs, quarantine). "
            "Optional --reader-parity runs find_marking_artifacts_for_attempt FS vs DB-only parity."
        )
    )
    parser.add_argument("--db-path", help="Optional DB path override.")
    parser.add_argument("--context-root", help="Optional context root override.")
    parser.add_argument(
        "--reader-parity",
        action="store_true",
        help=(
            "After structural checks, compare filesystem vs strict-DB marking lookup for each "
            "non-template main file with student_id (requires pdf registry and imported context JSON)."
        ),
    )
    parser.add_argument(
        "--parity-limit",
        type=int,
        metavar="N",
        help="With --reader-parity, only check the first N completion files (after sort by path).",
    )
    parser.add_argument(
        "--pdf-registry",
        dest="pdf_registry",
        help="Path to pdf_registry SQLite DB (default: PDF_REGISTRY_PATH or pdf_file_manager default).",
    )
    parser.add_argument(
        "--quarantine-history",
        action="store_true",
        help=(
            "Include resolved import_quarantine counts (cleared retries). Default output only mentions "
            "open/ignored rows that still need attention."
        ),
    )
    args = parser.parse_args()

    db_path = Path(args.db_path).expanduser().resolve() if args.db_path else default_db_path()
    context_root = Path(args.context_root).expanduser().resolve() if args.context_root else default_context_root()
    report = run_validation(db_path=db_path, context_root=context_root)

    print("Validation report:")
    for family, item in report.items():
        print(
            f"- {family}: source_json={item.source_count} db_rows={item.db_count} unresolved_fk={item.unresolved}"
        )

    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT status, COUNT(*) AS c
            FROM import_quarantine
            GROUP BY status
            ORDER BY status
            """
        ).fetchall()
        by_status = {str(r["status"]): int(r["c"]) for r in rows}
        if args.quarantine_history and by_status:
            print("- import_quarantine_by_status:", by_status)
        else:
            open_n = by_status.get("open", 0)
            ignored_n = by_status.get("ignored", 0)
            if open_n or ignored_n:
                print(f"- import_quarantine_needing_attention: open={open_n} ignored={ignored_n}")
    finally:
        conn.close()

    exit_code = 0
    if args.reader_parity:
        from ai_study_buddy.learning_db.cli.reader_parity import print_reader_parity_report, run_reader_parity

        pdf_reg = Path(args.pdf_registry).expanduser().resolve() if args.pdf_registry else None
        rp = run_reader_parity(
            study_buddy_db_path=db_path,
            context_root=context_root,
            pdf_registry_path=pdf_reg,
            limit=args.parity_limit,
        )
        print_reader_parity_report(rp)
        if rp.mismatch_count or rp.errors:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

