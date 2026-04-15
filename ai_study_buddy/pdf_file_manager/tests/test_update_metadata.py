# update_metadata. See TESTING.md § Phase 3 (update_metadata).

import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

from .conftest import FIXTURE_ROOT, fixture_has_pdfs


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


def test_update_metadata_invalid_file_type_raises():
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
                mgr.update_metadata(reg.id, file_type="bogus")
            assert "file_type" in str(exc_info.value).lower()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_update_metadata_file_type_syncs_invariant_fields_to_raw():
    """TESTING.md § 3.12b: unknown main + linked raw; one call promotes main and syncs doc_type/subject to raw."""
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        assert len(pdfs) >= 2
        main_disk = tmpdir / "plain_main.pdf"
        raw_disk = tmpdir / "_raw_plain_main.pdf"
        shutil.copy2(pdfs[0], main_disk)
        shutil.copy2(pdfs[1], raw_disk)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            main_reg = mgr.register_file(main_disk, file_type="unknown")
            raw_reg = mgr.register_file(raw_disk, file_type="raw")
            mgr.link_files(main_reg.id, raw_reg.id, "raw_source")
            assert mgr.get_file(main_reg.id).file_type == "unknown"

            mgr.update_metadata(
                main_reg.id,
                file_type="main",
                doc_type="exam",
                subject="english",
            )
            main = mgr.get_file(main_reg.id)
            raw = mgr.get_file(raw_reg.id)
            assert main is not None and raw is not None
            assert main.file_type == "main"
            assert main.doc_type == "exam" and main.subject == "english"
            assert raw.doc_type == "exam" and raw.subject == "english"
        finally:
            Path(db_path).unlink(missing_ok=True)
