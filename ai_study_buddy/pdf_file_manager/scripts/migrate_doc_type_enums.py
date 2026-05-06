"""
One-shot migration for pdf_files.doc_type enums:

- worksheet -> exercise
- notes -> note
- assert no remaining rows in {worksheet, notes, book_exercise, practice, unknown}

Uses PdfFileManager for connection handling but runs direct SQL for efficiency and
to avoid changing doc_type semantics in the main API.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


REMOVED_VALUES = {"worksheet", "notes", "book_exercise", "practice", "unknown"}
RENAME_MAP = {"worksheet": "exercise", "notes": "note"}


def _count_doc_types(mgr: PdfFileManager) -> Counter[str]:
    conn = mgr._get_connection()  # internal, but intentional for migration
    rows = conn.execute("SELECT doc_type, COUNT(*) AS c FROM pdf_files GROUP BY doc_type").fetchall()
    return Counter({row["doc_type"]: row["c"] for row in rows})


def migrate(doc_types_only: bool = False, dry_run: bool = False) -> int:
    mgr = PdfFileManager()
    conn = mgr._get_connection()

    before = _count_doc_types(mgr)
    print("Before migration doc_type counts:")
    for k in sorted(before):
        print(f"- {k}: {before[k]}")

    if before.get("unknown", 0):
        print("\nFound rows with doc_type='unknown' that must be resolved before enforcing canonical enums.")
        rows = conn.execute("SELECT id, path FROM pdf_files WHERE doc_type = 'unknown'").fetchall()
        for row in rows:
            inferred = mgr._infer_from_path(Path(row["path"]))  # type: ignore[attr-defined]
            inferred_type = (inferred or {}).get("doc_type")
            # Map canonical inference back to old enum vocabulary for pre-rebuild UPDATEs.
            if inferred_type == "exercise":
                target_old = "worksheet"
            elif inferred_type == "note":
                target_old = "notes"
            else:
                target_old = inferred_type
            # Fallback for paths with no usable inference (e.g. old Trash backups): treat as 'exam'.
            if target_old is None:
                target_old = "exam"
            print(f"- {row['id']} -> {row['path']} | inferred={inferred_type!r} -> old_enum={target_old!r}")
            if target_old not in {"exam", "worksheet", "book", "activity", "notes"}:
                print("  ERROR: Could not resolve a safe pre-migration doc_type within old enum set; aborting.")
                return 1
            if not dry_run:
                conn.execute(
                    "UPDATE pdf_files SET doc_type = ? WHERE id = ?",
                    (target_old, row["id"]),
                )
        if not dry_run:
            conn.commit()
            before = _count_doc_types(mgr)
            print("\nAfter resolving 'unknown' rows:")
            for k in sorted(before):
                print(f"- {k}: {before[k]}")

    if doc_types_only:
        return 0

    # When not dry-run, rebuild pdf_files with the canonical CHECK constraint and
    # inline CASE mapping for legacy doc_type values, mirroring PdfFileManager._rebuild_pdf_files_table.
    if not dry_run:
        print("\nRebuilding pdf_files table with canonical doc_type CHECK and mapped values...")
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(
            """
            BEGIN;
            CREATE TABLE pdf_files_new (
                id             TEXT PRIMARY KEY,
                name           TEXT NOT NULL,
                path           TEXT NOT NULL UNIQUE,
                file_type      TEXT NOT NULL DEFAULT 'unknown'
                               CHECK(file_type IN ('main', 'raw', 'unknown')),
                doc_type       TEXT NOT NULL
                               CHECK(doc_type IN ('exam', 'exercise', 'book', 'activity', 'note')),
                student_id     TEXT REFERENCES students(id),
                subject        TEXT
                               CHECK(subject IN ('english', 'math', 'science', 'chinese')),
                is_template    BOOLEAN NOT NULL DEFAULT 0,
                size_bytes     INTEGER,
                page_count     INTEGER,
                has_raw        BOOLEAN NOT NULL DEFAULT 0,
                metadata       TEXT,
                added_at       TEXT NOT NULL,
                updated_at     TEXT NOT NULL,
                notes          TEXT
            );
            INSERT INTO pdf_files_new (
                id, name, path, file_type, doc_type, student_id, subject, is_template,
                size_bytes, page_count, has_raw, metadata, added_at, updated_at, notes
            )
            SELECT
                id,
                name,
                path,
                file_type,
                CASE doc_type
                    WHEN 'worksheet' THEN 'exercise'
                    WHEN 'notes' THEN 'note'
                    ELSE doc_type
                END AS doc_type,
                student_id,
                subject,
                is_template,
                size_bytes,
                page_count,
                has_raw,
                metadata,
                added_at,
                updated_at,
                notes
            FROM pdf_files;
            DROP TABLE pdf_files;
            ALTER TABLE pdf_files_new RENAME TO pdf_files;
            COMMIT;
            """
        )
        conn.execute("PRAGMA foreign_keys = ON")

    after = _count_doc_types(mgr)
    print("\nAfter migration doc_type counts:")
    for k in sorted(after):
        print(f"- {k}: {after[k]}")

    remaining_removed = {k: after.get(k, 0) for k in REMOVED_VALUES if after.get(k, 0)}
    if remaining_removed:
        print("\nERROR: Remaining rows in removed/legacy doc_type values:")
        for k, v in remaining_removed.items():
            print(f"- {k}: {v}")
        return 1

    print("\nMigration completed successfully.")
    if dry_run:
        print("NOTE: dry-run enabled; no changes were written.")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Migrate pdf_files.doc_type enums to canonical set.")
    parser.add_argument(
        "--db",
        type=Path,
        help="Optional explicit registry DB path (defaults to PDF_REGISTRY_PATH or repo default).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned rewrites and counts without modifying the registry.",
    )
    args = parser.parse_args(argv)
    if args.db:
        # Support targeted migrations in tests and one-off runs.
        import os

        os.environ["PDF_REGISTRY_PATH"] = str(args.db)
    code = migrate(dry_run=args.dry_run)
    raise SystemExit(code)


if __name__ == "__main__":
    main()

