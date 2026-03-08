# scan_for_new_files. See TESTING.md § Phase 2 (scan_for_new_files).

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
from pdf_file_manager import PdfFileManager, ConfigError


def test_scan_dry_run_does_not_write():
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        root = str(tmpdir)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_scan_root(root)
            results = mgr.scan_for_new_files(dry_run=True)
            conn = sqlite3.connect(db_path)
            count = conn.execute("SELECT COUNT(*) FROM pdf_files").fetchone()[0]
            assert count == 0
            conn.close()
            assert len(results) >= 1
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_scan_without_dry_run_registers_and_compresses():
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        root = str(tmpdir)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_student("w", "W")
            mgr.add_scan_root(root, student_id="w")
            results = mgr.scan_for_new_files(dry_run=False, min_savings_pct=0)
            conn = sqlite3.connect(db_path)
            count = conn.execute("SELECT COUNT(*) FROM pdf_files WHERE file_type = 'main'").fetchone()[0]
            assert count >= 1
            if results:
                assert results[0].file.student_id == "w"
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_scan_with_no_roots_raises():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        with pytest.raises(ConfigError):
            mgr.scan_for_new_files()
        err = None
        try:
            mgr.scan_for_new_files()
        except ConfigError as e:
            err = e
        assert err is not None
        assert "root" in str(err).lower() or "config" in str(err).lower()
    finally:
        Path(tmp).unlink(missing_ok=True)
