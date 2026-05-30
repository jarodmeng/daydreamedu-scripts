"""
One-shot migration: extend pdf_files.doc_type CHECK to include 'composition'.

No row rewrites — existing values stay until Activity→Composition file migration (proposal 18).

Uses PdfFileManager for connection handling; rebuild mirrors _rebuild_pdf_files_table().
"""

from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from pathlib import Path

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def _pdf_files_table_sql(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'pdf_files'"
    ).fetchone()
    return (row[0] or "") if row else ""


def _count_doc_types(mgr: PdfFileManager) -> Counter[str]:
    conn = mgr._get_connection()
    rows = conn.execute("SELECT doc_type, COUNT(*) AS c FROM pdf_files GROUP BY doc_type").fetchall()
    return Counter({row["doc_type"]: row["c"] for row in rows})


def _check_includes_composition(table_sql: str) -> bool:
    return "'composition'" in table_sql


def _registry_db_path(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    import os

    env = os.environ.get("PDF_REGISTRY_PATH", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    from ai_study_buddy.pdf_file_manager.pdf_file_manager import _default_db_path

    return _default_db_path()


def migrate(*, db_path: Path | None = None, dry_run: bool = True) -> int:
    resolved = _registry_db_path(db_path)

    conn = sqlite3.connect(str(resolved))
    conn.row_factory = sqlite3.Row
    table_sql = _pdf_files_table_sql(conn)
    already_ok = _check_includes_composition(table_sql)
    before_rows = conn.execute("SELECT doc_type, COUNT(*) AS c FROM pdf_files GROUP BY doc_type").fetchall()
    before = Counter({row["doc_type"]: row["c"] for row in before_rows})
    conn.close()

    print("Current doc_type counts:")
    for k in sorted(before):
        print(f"- {k}: {before[k]}")

    if already_ok:
        print("\nCHECK constraint already includes 'composition'; nothing to do.")
        return 0

    print("\nCHECK constraint missing 'composition'; will rebuild pdf_files table.")
    if dry_run:
        print("NOTE: dry-run enabled; no changes were written.")
        return 0

    print("Rebuilding pdf_files table with extended doc_type CHECK...")
    mgr = PdfFileManager(db_path=str(resolved))
    mgr._get_connection()
    if not _check_includes_composition(_pdf_files_table_sql(mgr._get_connection())):
        mgr._rebuild_pdf_files_table()  # type: ignore[attr-defined]

    after = _count_doc_types(mgr)
    if not _check_includes_composition(_pdf_files_table_sql(mgr._get_connection())):
        print("ERROR: rebuild did not add 'composition' to CHECK constraint.")
        return 1

    print("\nAfter migration doc_type counts:")
    for k in sorted(after):
        print(f"- {k}: {after[k]}")
    if before != after:
        print("ERROR: row counts changed unexpectedly during schema-only migration.")
        return 1

    print("\nMigration completed successfully.")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Extend pdf_files.doc_type CHECK to include composition (proposal 18)."
    )
    parser.add_argument(
        "--db",
        type=Path,
        help="Optional explicit registry DB path (defaults to PDF_REGISTRY_PATH or repo default).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply rebuild (default is dry-run).",
    )
    args = parser.parse_args(argv)
    if args.db:
        import os

        os.environ["PDF_REGISTRY_PATH"] = str(args.db)
    code = migrate(db_path=args.db, dry_run=not args.execute)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
