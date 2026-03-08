# compress_and_register. See TESTING.md § Phase 2 (compress_and_register).

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
from pdf_file_manager import PdfFileManager


def test_compress_and_register_with_unregistered_path():
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
            result = mgr.compress_and_register(path, min_savings_pct=0)
            conn = sqlite3.connect(db_path)
            main_rows = conn.execute("SELECT file_type, has_raw FROM pdf_files WHERE file_type = 'main'").fetchall()
            assert len(main_rows) >= 1
            log_register = conn.execute("SELECT 1 FROM operation_log WHERE operation = 'register'").fetchall()
            log_compress = conn.execute("SELECT 1 FROM operation_log WHERE operation = 'compress'").fetchall()
            assert len(log_register) >= 1 and len(log_compress) >= 1
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_compress_and_register_already_main_raises():
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
            mgr.compress_and_register(path, min_savings_pct=0)
            with pytest.raises(ValueError):
                mgr.compress_and_register(path)
        finally:
            Path(db_path).unlink(missing_ok=True)
