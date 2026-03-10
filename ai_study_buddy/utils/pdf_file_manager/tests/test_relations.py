# get_related_files, link_files, unlink_files, link_to_template, unlink_template, get_template, get_completions. See TESTING.md § Phase 4 (relations).

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))
from conftest import FIXTURE_ROOT, fixture_has_pdfs
from pdf_file_manager import PdfFileManager, NotFoundError


def test_get_related_files_after_compress():
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
            related = mgr.get_related_files(result.main_file_id)
            assert len(related) >= 1
            assert any(r[1] in ("raw_source", "main_version") for r in related)
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_link_files_creates_relation_and_has_raw():
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
            main_result = mgr.compress_and_register(pdfs[0], min_savings_pct=0)
            main_id = main_result.main_file_id
            raw_id = main_result.raw_archive_id
            if raw_id is None:
                pytest.skip("Compression did not produce raw archive")
            mgr.unlink_files(main_id, raw_id)
            main_file = mgr.get_file(main_id)
            assert main_file is not None and not main_file.has_raw
            mgr.link_files(main_id, raw_id, "raw_source")
            related = mgr.get_related_files(main_id)
            assert len(related) >= 1
            assert mgr.get_file(main_id).has_raw
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_unlink_files_removes_relation():
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
            main_id, raw_id = result.main_file_id, result.raw_archive_id
            if raw_id is None:
                pytest.skip("Compression did not produce raw archive")
            mgr.unlink_files(main_id, raw_id)
            assert len(mgr.get_related_files(main_id)) == 0
            assert not mgr.get_file(main_id).has_raw
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_link_to_template_and_get_template():
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
            mgr.update_metadata(m1, is_template=True)
            mgr.update_metadata(m2, is_template=False)
            mgr.link_to_template(m2, m1)
            tpl = mgr.get_template(m2)
            assert tpl is not None and tpl.id == m1
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_get_completions():
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
            mgr.update_metadata(m1, is_template=True)
            mgr.update_metadata(m2, is_template=False)
            mgr.link_to_template(m2, m1)
            completions = mgr.get_completions(m1)
            assert len(completions) == 1 and completions[0].id == m2
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_unlink_template():
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
            mgr.update_metadata(m1, is_template=True)
            mgr.update_metadata(m2, is_template=False)
            mgr.link_to_template(m2, m1)
            mgr.unlink_template(m2)
            assert mgr.get_template(m2) is None
            assert len(mgr.get_completions(m1)) == 0
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_link_to_template_validation():
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
            mgr.update_metadata(m1, is_template=True)
            mgr.update_metadata(m2, is_template=False)
            mgr.link_to_template(m2, m1)
            with pytest.raises(ValueError):
                mgr.link_to_template(m2, m1)
            mgr.unlink_template(m2)
            mgr.update_metadata(m1, is_template=False)
            with pytest.raises(ValueError):
                mgr.link_to_template(m2, m1)
            mgr.update_metadata(m1, is_template=True)
            mgr.update_metadata(m2, is_template=True)
            with pytest.raises(ValueError):
                mgr.link_to_template(m2, m1)
        finally:
            Path(db_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# link_template_by_paths (Proposal 4)
# ---------------------------------------------------------------------------

def test_link_template_by_paths_success():
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
            p1 = mgr.get_file(m1).path
            p2 = mgr.get_file(m2).path
            rel = mgr.link_template_by_paths(p2, p1, inherit_metadata=True)
            assert rel.relation_type == "template_for"
            assert mgr.get_template(m2) is not None and mgr.get_template(m2).id == m1
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_link_template_by_paths_template_missing_raises():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f2:
            completed_path = f2.name
        try:
            with pytest.raises(NotFoundError) as exc:
                mgr.link_template_by_paths(completed_path, "/nonexistent/template.pdf")
            assert "Template" in str(exc.value) or "template" in str(exc.value).lower()
        finally:
            Path(completed_path).unlink(missing_ok=True)
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_link_template_by_paths_already_linked_raises():
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
            p1 = mgr.get_file(m1).path
            p2 = mgr.get_file(m2).path
            mgr.link_template_by_paths(p2, p1)
            with pytest.raises(ValueError) as exc:
                mgr.link_template_by_paths(p2, p1)
            assert "already linked" in str(exc.value).lower()
        finally:
            Path(db_path).unlink(missing_ok=True)
