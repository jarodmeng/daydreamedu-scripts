# register_file. See TESTING.md § Phase 2 (register_file).

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))
from conftest import FIXTURE_ROOT, fixture_has_pdfs
from pdf_file_manager import PdfFileManager, AlreadyRegisteredError


def test_register_file_creates_row_and_log():
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present (copy from real drive)")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        assert pdfs, "Fixture has no PDFs"
        path = pdfs[0]
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.register_file(path)
            conn = sqlite3.connect(db_path)
            rows = conn.execute("SELECT * FROM pdf_files WHERE path = ?", (str(path.resolve()),)).fetchall()
            assert len(rows) == 1
            assert rows[0][3] == "unknown"
            log = conn.execute("SELECT operation FROM operation_log WHERE operation = 'register'").fetchall()
            assert len(log) >= 1
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_register_file_missing_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        with pytest.raises(FileNotFoundError):
            mgr.register_file("/nonexistent/file.pdf")
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_register_file_duplicate_path():
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        path = pdfs[0]
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.register_file(path)
            with pytest.raises(AlreadyRegisteredError):
                mgr.register_file(path)
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_register_file_infers_file_type_raw():
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        src = pdfs[0]
        raw_path = src.parent / ("_raw_" + src.name)
        shutil.copy2(src, raw_path)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.register_file(raw_path)
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT file_type FROM pdf_files WHERE path = ?", (str(raw_path.resolve()),)).fetchone()
            assert row[0] == "raw"
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_register_file_infers_file_type_main_for_c_prefix():
    """Files with _c_ prefix are inferred as file_type='main' (compressed, no compress step)."""
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        src = pdfs[0]
        c_path = src.parent / ("_c_" + src.name)
        shutil.copy2(src, c_path)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.register_file(c_path)
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT file_type FROM pdf_files WHERE path = ?", (str(c_path.resolve()),)).fetchone()
            assert row[0] == "main"
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_register_file_infers_file_type_main_for_drive_c_prefix():
    """Files with c_ prefix are inferred as file_type='main' for GoodNotes/Drive compatibility."""
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        src = pdfs[0]
        c_path = src.parent / ("c_" + src.name)
        shutil.copy2(src, c_path)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.register_file(c_path)
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT file_type FROM pdf_files WHERE path = ?", (str(c_path.resolve()),)).fetchone()
            assert row[0] == "main"
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_register_file_accepts_optional_args():
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        path = pdfs[0]
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_student("w", "W")
            mgr.register_file(path, doc_type="exam", student_id="w", subject="math")
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT doc_type, student_id, subject FROM pdf_files WHERE path = ?", (str(path.resolve()),)).fetchone()
            assert row[0] == "exam" and row[1] == "w" and row[2] == "math"
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)
