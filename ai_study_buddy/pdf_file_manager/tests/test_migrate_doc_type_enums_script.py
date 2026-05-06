import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


def _create_old_schema_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            added_at TEXT NOT NULL
        );
        CREATE TABLE pdf_files (
            id             TEXT PRIMARY KEY,
            name           TEXT NOT NULL,
            path           TEXT NOT NULL UNIQUE,
            file_type      TEXT NOT NULL DEFAULT 'unknown'
                           CHECK(file_type IN ('main', 'raw', 'unknown')),
            doc_type       TEXT NOT NULL DEFAULT 'unknown'
                           CHECK(doc_type IN ('exam', 'worksheet', 'book', 'book_exercise', 'activity', 'practice', 'notes', 'unknown')),
            student_id     TEXT,
            subject        TEXT,
            is_template    BOOLEAN NOT NULL DEFAULT 0,
            size_bytes     INTEGER,
            page_count     INTEGER,
            has_raw        BOOLEAN NOT NULL DEFAULT 0,
            metadata       TEXT,
            added_at       TEXT NOT NULL,
            updated_at     TEXT NOT NULL,
            notes          TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO pdf_files (id, name, path, file_type, doc_type, added_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("f1", "a.pdf", "/tmp/a.pdf", "main", "worksheet", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO pdf_files (id, name, path, file_type, doc_type, added_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("f2", "b.pdf", "/tmp/b.pdf", "main", "notes", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()


def test_migrate_doc_type_enums_rewrites_worksheet_and_notes():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "registry.db"
        _create_old_schema_db(db_path)

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "ai_study_buddy.pdf_file_manager.scripts.migrate_doc_type_enums",
                "--db",
                str(db_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT id, doc_type FROM pdf_files ORDER BY id").fetchall()
        conn.close()
        assert rows == [("f1", "exercise"), ("f2", "note")]

