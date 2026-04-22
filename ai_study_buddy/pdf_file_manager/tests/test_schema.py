# Schema and DB init (foundation). See TESTING.md § Phase 1.

import os
import sqlite3
import tempfile
from pathlib import Path

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

from .conftest import EXPECTED_TABLES, OPERATION_LOG_COLUMNS, PDF_FILES_COLUMNS


BOOK_ANSWER_MAPPING_COLUMNS = {
    "id", "unit_file_id", "answer_file_id", "answer_page_start", "answer_page_end",
    "starts_mid_page", "ends_mid_page", "source", "notes", "created_at", "updated_at",
}


def test_schema_exists_after_init():
    """Create manager with temp DB; assert all seven tables exist."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr._get_connection()
        conn = sqlite3.connect(tmp)
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        conn.close()
        assert tables == EXPECTED_TABLES
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_schema_shape_operation_log():
    """operation_log has required columns."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr._get_connection()
        conn = sqlite3.connect(tmp)
        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(operation_log)").fetchall()
        }
        conn.close()
        assert OPERATION_LOG_COLUMNS <= cols
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_schema_shape_pdf_files():
    """pdf_files has required columns."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr._get_connection()
        conn = sqlite3.connect(tmp)
        cols = {
            r[1] for r in conn.execute("PRAGMA table_info(pdf_files)").fetchall()
        }
        conn.close()
        assert PDF_FILES_COLUMNS <= cols
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_schema_shape_book_answer_mappings():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr._get_connection()
        conn = sqlite3.connect(tmp)
        cols = {
            r[1] for r in conn.execute("PRAGMA table_info(book_answer_mappings)").fetchall()
        }
        conn.close()
        assert BOOK_ANSWER_MAPPING_COLUMNS <= cols
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_custom_db_path():
    """Manager with custom path creates file at that path with schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr._get_connection()
        assert Path(tmp).exists()
        conn = sqlite3.connect(tmp)
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        conn.close()
        assert tables == EXPECTED_TABLES
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_default_db_path():
    """PdfFileManager() creates DB at default location (env override)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        prev = os.environ.get("PDF_REGISTRY_PATH")
        os.environ["PDF_REGISTRY_PATH"] = tmp
        try:
            mgr = PdfFileManager()
            mgr._get_connection()
            p = mgr.db_path
            assert p.exists()
            assert str(p) == str(Path(tmp).resolve())
            assert p.name.endswith(".db")
        finally:
            if prev is None:
                os.environ.pop("PDF_REGISTRY_PATH", None)
            else:
                os.environ["PDF_REGISTRY_PATH"] = prev
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_operation_log_write():
    """_log_operation inserts a row; we can read it back."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr._log_operation("test", performed_by="pytest")
        conn = sqlite3.connect(tmp)
        row = conn.execute(
            "SELECT operation, performed_by FROM operation_log"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "test"
        assert row[1] == "pytest"
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_manager_connection_enables_foreign_keys():
    """Manager connection enables FK enforcement for ON DELETE CASCADE constraints."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        conn = mgr._get_connection()
        fk_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk_on == 1
    finally:
        Path(tmp).unlink(missing_ok=True)
