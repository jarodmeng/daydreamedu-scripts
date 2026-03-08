# update_metadata. See TESTING.md § Phase 3 (update_metadata).

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


def test_update_metadata_updates_single_fields():
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            reg = mgr.register_file(pdfs[0])
            updated = mgr.update_metadata(reg.id, doc_type="exam", subject="science")
            assert updated.doc_type == "exam" and updated.subject == "science"
            got = mgr.get_file(reg.id)
            assert got is not None and got.doc_type == "exam" and got.subject == "science"
            conn = sqlite3.connect(db_path)
            log = conn.execute("SELECT operation FROM operation_log WHERE operation = 'update_metadata'").fetchall()
            assert len(log) >= 1
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_update_metadata_merges_metadata_dict():
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            reg = mgr.register_file(pdfs[0], metadata={"a": 1})
            updated = mgr.update_metadata(reg.id, metadata={"b": 2})
            assert updated.metadata is not None
            assert updated.metadata.get("a") == 1 and updated.metadata.get("b") == 2
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_update_metadata_invalid_subject_raises():
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            reg = mgr.register_file(pdfs[0])
            with pytest.raises(ValueError) as exc_info:
                mgr.update_metadata(reg.id, subject="invalid")
            assert "subject" in str(exc_info.value).lower() or "english" in str(exc_info.value).lower()
        finally:
            Path(db_path).unlink(missing_ok=True)
