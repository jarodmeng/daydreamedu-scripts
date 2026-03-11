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
from pdf_file_manager import PdfFileManager, ConfigError, CompressResult


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


def test_scan_c_prefix_registers_without_compressing():
    """When scan finds a _c_*.pdf file, it registers as main only (no compress, no _raw_ created)."""
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        src = pdfs[0]
        c_name = "_c_" + src.name
        c_path = tmpdir / c_name
        shutil.copy2(src, c_path)
        root = str(tmpdir)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_scan_root(root)
            results = mgr.scan_for_new_files(dry_run=False)
            conn = sqlite3.connect(db_path)
            main_rows = conn.execute(
                "SELECT id, name, path, has_raw FROM pdf_files WHERE file_type = 'main'"
            ).fetchall()
            conn.close()
            assert len(main_rows) >= 1
            c_main = [r for r in main_rows if r[1].startswith("_c_")]
            assert len(c_main) >= 1
            assert c_main[0][3] == 0
            assert c_path.exists()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_scan_drive_c_prefix_registers_without_compressing():
    """When scan finds a c_*.pdf file, it registers as main only for GoodNotes/Drive compatibility."""
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        src = pdfs[0]
        c_path = tmpdir / ("c_" + src.name)
        shutil.copy2(src, c_path)
        root = str(tmpdir)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_scan_root(root)
            results = mgr.scan_for_new_files(dry_run=False)
            conn = sqlite3.connect(db_path)
            main_rows = conn.execute(
                "SELECT id, name, path, has_raw FROM pdf_files WHERE file_type = 'main'"
            ).fetchall()
            conn.close()
            assert len(main_rows) >= 1
            c_main = [r for r in main_rows if Path(r[2]).name.startswith("c_")]
            assert len(c_main) >= 1
            assert c_main[0][3] == 0
            assert c_path.exists()
            assert all(result.raw_archive is None for result in results if result.file.path == str(c_path.resolve()))
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_scan_for_new_files_goodnotes_uses_preserve_input(monkeypatch):
    """scan_for_new_files should treat GoodNotes paths as preserve_input=True (no rename/move of originals)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        goodnotes_root = tmpdir / "GoodNotes" / "Singapore Primary Math" / "winston.ry.meng@gmail.com" / "P6" / "Exam"
        goodnotes_root.mkdir(parents=True, exist_ok=True)
        pdf_path = goodnotes_root / "P6 WA1 practice paper 1 (empty) (attempt).pdf"
        pdf_path.write_bytes(b"pdf")
        db_path = tmpdir / "registry.db"
        mgr = PdfFileManager(db_path=str(db_path))

        calls: dict = {}

        def _spy(file_id_or_path, *args, **kwargs):
            # Record kwargs and short-circuit before real compression so we
            # don't need a valid PDF for this behavioural test.
            calls["kwargs"] = kwargs.copy()
            # Minimal result: pretend we created a main id; we won't look it up.
            return CompressResult(main_file_id="dummy", compressed=False, raw_archive_id=None)

        # Avoid update_metadata trying to resolve the dummy id in the DB.
        monkeypatch.setattr(mgr, "compress_and_register", _spy)
        monkeypatch.setattr(mgr, "update_metadata", lambda *a, **k: None)

        results = mgr.scan_for_new_files(roots=[goodnotes_root], min_savings_pct=0)
        assert isinstance(results, list)
        # Original GoodNotes file should still exist at the same path
        assert pdf_path.exists()
        # compress_and_register should have been called with preserve_input=True
        assert calls.get("kwargs", {}).get("preserve_input") is True


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
