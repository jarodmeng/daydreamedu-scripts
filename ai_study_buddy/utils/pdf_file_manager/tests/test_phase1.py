# Phase 1 confidence tests. See TESTING.md § Phase 1.

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

# Ensure we can import pdf_file_manager from the parent directory
_tests_dir = Path(__file__).resolve().parent
_util_dir = _tests_dir.parent
if str(_util_dir) not in sys.path:
    sys.path.insert(0, str(_util_dir))

from pdf_file_manager import PdfFileManager

EXPECTED_TABLES = [
    "file_group_members",
    "file_groups",
    "file_relations",
    "operation_log",
    "pdf_files",
    "scan_roots",
    "students",
]

OPERATION_LOG_COLUMNS = {
    "id",
    "operation",
    "file_id",
    "group_id",
    "performed_at",
    "performed_by",
    "before_state",
    "after_state",
    "notes",
}

PDF_FILES_COLUMNS = {
    "id",
    "name",
    "path",
    "file_type",
    "doc_type",
    "student_id",
    "subject",
    "is_template",
    "size_bytes",
    "page_count",
    "has_raw",
    "metadata",
    "added_at",
    "updated_at",
    "notes",
}


def test_1_schema_exists_after_init():
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


def test_2_schema_shape_operation_log():
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


def test_3_schema_shape_pdf_files():
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


def test_4_custom_db_path():
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


def test_5_default_db_path():
    """PdfFileManager() creates DB at default location (env override so we don't touch real registry)."""
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


def test_6_operation_log_write():
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
