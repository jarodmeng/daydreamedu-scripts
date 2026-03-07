# Phase 3 confidence tests. See TESTING.md § Phase 3.
# Uses the same DaydreamEdu fixture as Phase 2: tests/fixtures/daydreamedu_fixture/
# (copied into a temp dir for tests that need PDFs on disk).

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

_tests_dir = Path(__file__).resolve().parent
_util_dir = _tests_dir.parent
if str(_util_dir) not in sys.path:
    sys.path.insert(0, str(_util_dir))

from pdf_file_manager import (
    PdfFileManager,
    PdfFile,
    AlreadyRegisteredError,
    NotFoundError,
)

# Same fixture as Phase 2
FIXTURE_ROOT = _tests_dir / "fixtures" / "daydreamedu_fixture"


def _fixture_has_pdfs() -> bool:
    if not FIXTURE_ROOT.is_dir():
        return False
    pdfs = list(FIXTURE_ROOT.rglob("*.pdf"))
    return len(pdfs) >= 1


# ---------------------------------------------------------------------------
# get_file (3.1, 3.2)
# ---------------------------------------------------------------------------

def test_3_1_get_file_by_id_returns_pdffile():
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
            registered = mgr.register_file(path)
            out = mgr.get_file(registered.id)
            assert out is not None
            assert out.id == registered.id
            assert out.path == registered.path
            assert out.name == registered.name
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_2_get_file_unknown_id_returns_none():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        out = mgr.get_file("00000000-0000-0000-0000-000000000000")
        assert out is None
    finally:
        Path(tmp).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# find_files (3.3–3.9)
# ---------------------------------------------------------------------------

def test_3_3_find_files_no_filters_returns_all():
    if not _fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        assert len(pdfs) >= 2, "Need at least 2 PDFs in fixture"
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.register_file(pdfs[0])
            mgr.register_file(pdfs[1])
            results = mgr.find_files()
            assert len(results) == 2
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_4_find_files_file_type_filter():
    if not _fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.register_file(pdfs[0])
            mgr.compress_and_register(pdfs[1], min_savings_pct=0)
            main_only = mgr.find_files(file_type="main")
            assert len(main_only) >= 1
            assert all(f.file_type == "main" for f in main_only)
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_5_find_files_doc_type_filter():
    if not _fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.register_file(pdfs[0], doc_type="exam")
            mgr.register_file(pdfs[1], doc_type="worksheet")
            exam = mgr.find_files(doc_type="exam")
            assert len(exam) == 1 and exam[0].doc_type == "exam"
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_6_find_files_student_id_filter():
    if not _fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_student("w", "W")
            mgr.add_student("x", "X")
            mgr.register_file(pdfs[0], student_id="w")
            mgr.register_file(pdfs[1], student_id="x")
            w_files = mgr.find_files(student_id="w")
            assert len(w_files) == 1 and w_files[0].student_id == "w"
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_7_find_files_subject_filter():
    if not _fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.register_file(pdfs[0], subject="math")
            mgr.register_file(pdfs[1], subject="science")
            math_files = mgr.find_files(subject="math")
            assert len(math_files) == 1 and math_files[0].subject == "math"
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_8_find_files_query_name_substring():
    if not _fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.register_file(pdfs[0])
            name_substring = "Science"  # fixture has "Primary 5 Science" etc.
            found = mgr.find_files(query=name_substring)
            assert len(found) >= 1
            assert name_substring.lower() in found[0].name.lower()
            empty = mgr.find_files(query="nonexistentxyzz")
            assert len(empty) == 0
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_9_find_files_is_template_and_has_raw():
    if not _fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.register_file(pdfs[0], is_template=True)
            mgr.compress_and_register(pdfs[1], min_savings_pct=0)
            templates = mgr.find_files(is_template=True)
            assert len(templates) >= 1 and all(f.is_template for f in templates)
            with_raw = mgr.find_files(has_raw=True)
            assert len(with_raw) >= 1 and all(f.has_raw for f in with_raw)
        finally:
            Path(db_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# update_metadata (3.10–3.12)
# ---------------------------------------------------------------------------

def test_3_10_update_metadata_updates_single_fields():
    if not _fixture_has_pdfs():
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


def test_3_11_update_metadata_merges_metadata_dict():
    if not _fixture_has_pdfs():
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


def test_3_12_update_metadata_invalid_subject_raises():
    if not _fixture_has_pdfs():
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


# ---------------------------------------------------------------------------
# rename_file / move_file (3.13–3.16)
# ---------------------------------------------------------------------------

def test_3_13_rename_file_renames_on_disk_and_in_db():
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
            reg = mgr.register_file(path)
            new_name = "newname.pdf"
            renamed = mgr.rename_file(reg.id, new_name=new_name)
            assert renamed.name == new_name
            assert Path(renamed.path).name == new_name
            assert Path(renamed.path).exists()
            conn = sqlite3.connect(db_path)
            log = conn.execute("SELECT operation FROM operation_log WHERE operation = 'rename'").fetchall()
            assert len(log) >= 1
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_14_rename_file_destination_exists_raises():
    if not _fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        assert len(pdfs) >= 2
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            r1 = mgr.register_file(pdfs[0])
            mgr.register_file(pdfs[1])
            dest_name = pdfs[1].name
            with pytest.raises(ValueError):
                mgr.rename_file(r1.id, new_name=dest_name)
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_15_move_file_moves_on_disk_and_in_db():
    if not _fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        new_dir = tmpdir / "subdir"
        new_dir.mkdir()
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            reg = mgr.register_file(pdfs[0])
            moved = mgr.move_file(reg.id, new_dir=str(new_dir))
            assert str(new_dir) in moved.path
            assert Path(moved.path).exists()
            conn = sqlite3.connect(db_path)
            log = conn.execute("SELECT operation FROM operation_log WHERE operation = 'move'").fetchall()
            assert len(log) >= 1
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_16_move_file_destination_exists_raises():
    if not _fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        subdir = tmpdir / "subdir"
        subdir.mkdir()
        clash_name = "same_name.pdf"
        in_subdir = subdir / clash_name
        shutil.copy2(pdfs[0], in_subdir)
        in_root = tmpdir / clash_name
        shutil.copy2(pdfs[0], in_root)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.register_file(in_subdir)
            r2 = mgr.register_file(in_root)
            with pytest.raises(ValueError):
                mgr.move_file(r2.id, new_dir=str(subdir))
        finally:
            Path(db_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# delete_file (3.17–3.20)
# ---------------------------------------------------------------------------

def test_3_17_delete_file_removes_file_and_row():
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
            reg = mgr.register_file(path)
            file_path = Path(reg.path)
            mgr.delete_file(reg.id)
            assert not file_path.exists()
            assert mgr.get_file(reg.id) is None
            conn = sqlite3.connect(db_path)
            log = conn.execute("SELECT before_state FROM operation_log WHERE operation = 'delete'").fetchone()
            assert log is not None
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_18_delete_file_keep_related_false_cascades_to_raw():
    if not _fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            result = mgr.compress_and_register(pdfs[0], min_savings_pct=0)
            main_id = result.main_file_id
            raw_id = result.raw_archive_id
            if raw_id is None:
                pytest.skip("Compression did not produce raw archive")
            main_path = mgr.get_file(main_id).path if mgr.get_file(main_id) else None
            raw_path = mgr.get_file(raw_id).path if mgr.get_file(raw_id) else None
            mgr.delete_file(main_id, keep_related=False)
            assert mgr.get_file(main_id) is None and mgr.get_file(raw_id) is None
            if main_path:
                assert not Path(main_path).exists()
            if raw_path:
                assert not Path(raw_path).exists()
            conn = sqlite3.connect(db_path)
            deletes = conn.execute("SELECT performed_by FROM operation_log WHERE operation = 'delete'").fetchall()
            assert len(deletes) >= 2
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_19_delete_file_keep_related_true_leaves_raw():
    if not _fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            result = mgr.compress_and_register(pdfs[0], min_savings_pct=0)
            main_id = result.main_file_id
            raw_id = result.raw_archive_id
            if raw_id is None:
                pytest.skip("Compression did not produce raw archive")
            raw_path = mgr.get_file(raw_id).path if mgr.get_file(raw_id) else None
            mgr.delete_file(main_id, keep_related=True)
            assert mgr.get_file(main_id) is None
            raw_still = mgr.get_file(raw_id)
            assert raw_still is not None
            if raw_path:
                assert Path(raw_path).exists()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_20_delete_file_already_absent_on_disk():
    if not _fixture_has_pdfs():
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
            Path(reg.path).unlink(missing_ok=True)
            mgr.delete_file(reg.id)
            assert mgr.get_file(reg.id) is None
            conn = sqlite3.connect(db_path)
            log = conn.execute("SELECT 1 FROM operation_log WHERE operation = 'delete'").fetchone()
            assert log is not None
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# open_file (3.21, 3.22)
# ---------------------------------------------------------------------------

def test_3_21_open_file_path_exists():
    """open_file with existing path does not raise. We mock subprocess so the real
    macOS 'open' is never run (avoids opening Preview and a blocking 'file not found'
    dialog when the temp dir is torn down)."""
    if not _fixture_has_pdfs():
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
            with patch("pdf_file_manager.subprocess.run") as mock_run:
                mgr.open_file(reg.id)
            mock_run.assert_called_once()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_3_22_open_file_path_missing_raises():
    if not _fixture_has_pdfs():
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
            Path(reg.path).unlink(missing_ok=True)
            with pytest.raises(FileNotFoundError):
                mgr.open_file(reg.id)
        finally:
            Path(db_path).unlink(missing_ok=True)
