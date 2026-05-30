import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def _create_pre_composition_schema_db(db_path: Path) -> None:
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
            doc_type       TEXT NOT NULL DEFAULT 'exam'
                           CHECK(doc_type IN ('exam', 'exercise', 'book', 'activity', 'note')),
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
        "INSERT INTO pdf_files (id, name, path, file_type, doc_type, added_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("f1", "a.pdf", "/tmp/a.pdf", "main", "activity", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()


def test_migrate_add_composition_doc_type_dry_run_leaves_db_unchanged():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "registry.db"
        _create_pre_composition_schema_db(db_path)

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "ai_study_buddy.pdf_file_manager.scripts.migrate_add_composition_doc_type",
                "--db",
                str(db_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
        assert "dry-run" in proc.stdout.lower()

        conn = sqlite3.connect(str(db_path))
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='pdf_files'"
        ).fetchone()[0]
        conn.close()
        assert "'composition'" not in sql


def test_migrate_add_composition_doc_type_execute_extends_check():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "registry.db"
        _create_pre_composition_schema_db(db_path)

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "ai_study_buddy.pdf_file_manager.scripts.migrate_add_composition_doc_type",
                "--db",
                str(db_path),
                "--execute",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr

        conn = sqlite3.connect(str(db_path))
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='pdf_files'"
        ).fetchone()[0]
        row = conn.execute("SELECT doc_type FROM pdf_files WHERE id='f1'").fetchone()
        conn.close()
        assert "'composition'" in sql
        assert row[0] == "activity"


def test_pdf_file_manager_open_auto_migrates_composition_check():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "registry.db"
        _create_pre_composition_schema_db(db_path)

        PdfFileManager(db_path=str(db_path))._get_connection()

        conn = sqlite3.connect(str(db_path))
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='pdf_files'"
        ).fetchone()[0]
        conn.close()
        assert "'composition'" in sql


def test_register_file_accepts_composition_doc_type():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        pdf_path = tmpdir_path / "essay.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")
        mgr = PdfFileManager(db_path=str(tmpdir_path / "registry.db"))
        registered = mgr.register_file(
            pdf_path,
            file_type="main",
            doc_type="composition",
            subject="english",
        )
        assert registered.doc_type == "composition"
