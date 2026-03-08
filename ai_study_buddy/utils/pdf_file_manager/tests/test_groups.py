# File group CRUD, suggest_groups, open_file_group. See TESTING.md § Phase 4 (groups).

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))
from conftest import FIXTURE_ROOT, fixture_has_pdfs
from pdf_file_manager import PdfFileManager, ConfigError


def test_create_file_group_and_get_file_group():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        mgr = PdfFileManager(db_path=db_path)
        g = mgr.create_file_group("Test", group_type="exam")
        got = mgr.get_file_group(g.id)
        assert got.id == g.id and got.label == "Test" and len(got.members) == 0
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_add_to_file_group_and_list_file_groups():
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
            m1 = mgr.compress_and_register(pdfs[0], min_savings_pct=0).main_file_id
            m2 = mgr.compress_and_register(pdfs[1], min_savings_pct=0).main_file_id
            g = mgr.create_file_group("Exams", group_type="exam")
            mgr.add_to_file_group(g.id, m1)
            mgr.add_to_file_group(g.id, m2)
            got = mgr.get_file_group(g.id)
            assert len(got.members) == 2
            assert any(gr.id == g.id for gr in mgr.list_file_groups())
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_add_to_file_group_with_raw_raises():
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
            raw_id = result.raw_archive_id
            if raw_id is None:
                pytest.skip("Compression did not produce raw archive")
            g = mgr.create_file_group("G", group_type="collection")
            with pytest.raises(ValueError):
                mgr.add_to_file_group(g.id, raw_id)
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_remove_from_file_group():
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
            m1 = mgr.compress_and_register(pdfs[0], min_savings_pct=0).main_file_id
            g = mgr.create_file_group("G", group_type="collection")
            mgr.add_to_file_group(g.id, m1)
            mgr.remove_from_file_group(g.id, m1)
            got = mgr.get_file_group(g.id)
            assert len(got.members) == 0
            assert mgr.get_file(m1) is not None
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_set_file_group_anchor_and_get_file_group_membership():
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
            m1 = mgr.compress_and_register(pdfs[0], min_savings_pct=0).main_file_id
            g = mgr.create_file_group("G", group_type="exam")
            mgr.add_to_file_group(g.id, m1)
            mgr.set_file_group_anchor(g.id, m1)
            got = mgr.get_file_group(g.id)
            assert got.anchor_id == m1
            membership = mgr.get_file_group_membership(m1)
            assert any(m.id == g.id for m in membership)
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_delete_file_group():
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
            m1 = mgr.compress_and_register(pdfs[0], min_savings_pct=0).main_file_id
            g = mgr.create_file_group("G", group_type="collection")
            mgr.add_to_file_group(g.id, m1)
            mgr.delete_file_group(g.id)
            with pytest.raises(Exception):
                mgr.get_file_group(g.id)
            assert mgr.get_file(m1) is not None
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_suggest_groups_returns_candidates():
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
            mgr.add_student("w", "W")
            main_ids = []
            for p in pdfs[:2]:
                result = mgr.compress_and_register(p, min_savings_pct=0)
                main_ids.append(result.main_file_id)
            for fid in main_ids:
                mgr.update_metadata(fid, doc_type="exam", student_id="w", subject="science", metadata={"exam_date": "2025-11-12"})
            suggestions = mgr.suggest_groups()
            assert len(suggestions) >= 1
            assert any(len(s.candidate_files) >= 2 for s in suggestions)
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_suggest_groups_unclassified_excluded():
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
            mgr.register_file(pdfs[0], doc_type="unknown")
            mgr.register_file(pdfs[1], doc_type="exam", student_id="w", subject="science", metadata={"exam_date": "2025-11-12"})
            suggestions = mgr.suggest_groups()
            for s in suggestions:
                for c in s.candidate_files:
                    assert c.doc_type == "exam"
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_open_file_group_no_anchor_raises():
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
            m1 = mgr.compress_and_register(pdfs[0], min_savings_pct=0).main_file_id
            g = mgr.create_file_group("G", group_type="exam")
            mgr.add_to_file_group(g.id, m1)
            with pytest.raises(ConfigError):
                mgr.open_file_group(g.id)
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_open_file_group_with_anchor():
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
            m1 = mgr.compress_and_register(pdfs[0], min_savings_pct=0).main_file_id
            g = mgr.create_file_group("G", group_type="exam")
            mgr.add_to_file_group(g.id, m1)
            mgr.set_file_group_anchor(g.id, m1)
            with patch("pdf_file_manager.subprocess.run"):
                mgr.open_file_group(g.id)
        finally:
            Path(db_path).unlink(missing_ok=True)
