# rename_file, move_file, delete_file, open_file. See TESTING.md § Phase 3 (file ops).

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))
from conftest import FIXTURE_ROOT, fixture_has_pdfs
from pdf_file_manager import PdfFileManager


def test_rename_file_renames_on_disk_and_in_db():
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


def test_rename_file_destination_exists_raises():
    if not fixture_has_pdfs():
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


def test_move_file_moves_on_disk_and_in_db():
    if not fixture_has_pdfs():
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


def test_move_file_destination_exists_raises():
    if not fixture_has_pdfs():
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


def test_delete_file_removes_file_and_row():
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


def test_delete_file_keep_related_false_cascades_to_raw():
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


def test_delete_file_keep_related_true_leaves_raw():
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


def test_delete_file_already_absent_on_disk():
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
            Path(reg.path).unlink(missing_ok=True)
            mgr.delete_file(reg.id)
            assert mgr.get_file(reg.id) is None
            conn = sqlite3.connect(db_path)
            log = conn.execute("SELECT 1 FROM operation_log WHERE operation = 'delete'").fetchone()
            assert log is not None
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_open_file_path_exists():
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
            with patch("pdf_file_manager.subprocess.run") as mock_run:
                mgr.open_file(reg.id)
            mock_run.assert_called_once()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_open_file_path_missing_raises():
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
            Path(reg.path).unlink(missing_ok=True)
            with pytest.raises(FileNotFoundError):
                mgr.open_file(reg.id)
        finally:
            Path(db_path).unlink(missing_ok=True)
