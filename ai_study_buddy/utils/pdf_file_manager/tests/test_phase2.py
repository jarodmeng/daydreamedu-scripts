# Phase 2 confidence tests. See TESTING.md § Phase 2.
# Uses the DaydreamEdu fixture (copy to temp dir for scan/compress tests).

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

_tests_dir = Path(__file__).resolve().parent
_util_dir = _tests_dir.parent
if str(_util_dir) not in sys.path:
    sys.path.insert(0, str(_util_dir))

from pdf_file_manager import (
    PdfFileManager,
    Student,
    ScanRoot,
    PdfFile,
    AlreadyRegisteredError,
    NotFoundError,
    ConfigError,
)

FIXTURE_ROOT = _tests_dir / "fixtures" / "daydreamedu_fixture"


def _fixture_has_pdfs() -> bool:
    if not FIXTURE_ROOT.is_dir():
        return False
    pdfs = list(FIXTURE_ROOT.rglob("*.pdf"))
    return len(pdfs) >= 1


def test_2_1_add_student_then_list_students():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        s = mgr.add_student("w", "Winston", email="w@x.com")
        assert s.id == "w" and s.name == "Winston" and s.email == "w@x.com"
        lst = mgr.list_students()
        assert len(lst) == 1
        assert lst[0].id == "w" and lst[0].email == "w@x.com"
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_2_2_list_students_empty_at_first():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        assert mgr.list_students() == []
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_2_3_add_scan_root_then_list_scan_roots():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        r = mgr.add_scan_root("/tmp/foo", student_id="w")
        roots = mgr.list_scan_roots()
        assert len(roots) == 1
        assert roots[0].path.endswith("foo") or "foo" in roots[0].path
        assert roots[0].student_id == "w"
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_2_4_remove_scan_root():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr.add_scan_root("/tmp/foo", student_id="w")
        mgr.remove_scan_root("/tmp/foo")
        assert mgr.list_scan_roots() == []
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_2_5_register_file_creates_row_and_log():
    if not _fixture_has_pdfs():
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


def test_2_6_register_file_missing_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        with pytest.raises(FileNotFoundError):
            mgr.register_file("/nonexistent/file.pdf")
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_2_7_register_file_duplicate_path():
    if not _fixture_has_pdfs():
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


def test_2_8_register_file_infers_file_type_raw():
    if not _fixture_has_pdfs():
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


def test_2_9_register_file_accepts_optional_args():
    if not _fixture_has_pdfs():
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


def test_2_10_compress_and_register_with_unregistered_path():
    if not _fixture_has_pdfs():
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


def test_2_11_compress_and_register_already_main_raises():
    if not _fixture_has_pdfs():
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


def test_2_12_scan_dry_run_does_not_write():
    if not _fixture_has_pdfs():
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


def test_2_13_scan_without_dry_run_registers_and_compresses():
    if not _fixture_has_pdfs():
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


def test_2_14_scan_with_no_roots_raises():
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
