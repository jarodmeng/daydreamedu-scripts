# Phase 4 confidence tests. See TESTING.md § Phase 4.
# Uses the same DaydreamEdu fixture as Phase 2/3. No fixture layout change:
# raw↔main from compress_and_register; template↔completed and groups created in-test.

import shutil
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
    ConfigError,
)

FIXTURE_ROOT = _tests_dir / "fixtures" / "daydreamedu_fixture"


def _fixture_has_pdfs() -> bool:
    if not FIXTURE_ROOT.is_dir():
        return False
    pdfs = list(FIXTURE_ROOT.rglob("*.pdf"))
    return len(pdfs) >= 1


# ---------------------------------------------------------------------------
# get_related_files / link_files / unlink_files (4.1–4.3)
# ---------------------------------------------------------------------------

def test_4_1_get_related_files_after_compress():
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
            related = mgr.get_related_files(result.main_file_id)
            assert len(related) >= 1
            assert any(r[1] in ("raw_source", "main_version") for r in related)
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_4_2_link_files_creates_relation_and_has_raw():
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


def test_4_3_unlink_files_removes_relation():
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
            main_id, raw_id = result.main_file_id, result.raw_archive_id
            if raw_id is None:
                pytest.skip("Compression did not produce raw archive")
            mgr.unlink_files(main_id, raw_id)
            assert len(mgr.get_related_files(main_id)) == 0
            assert not mgr.get_file(main_id).has_raw
        finally:
            Path(db_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# link_to_template / unlink_template / get_template / get_completions (4.4–4.7)
# ---------------------------------------------------------------------------

def test_4_4_link_to_template_and_get_template():
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
            m1 = mgr.compress_and_register(pdfs[0], min_savings_pct=0).main_file_id
            m2 = mgr.compress_and_register(pdfs[1], min_savings_pct=0).main_file_id
            mgr.update_metadata(m1, is_template=True)
            mgr.update_metadata(m2, is_template=False)
            mgr.link_to_template(m2, m1)
            tpl = mgr.get_template(m2)
            assert tpl is not None and tpl.id == m1
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_4_5_get_completions():
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
            m1 = mgr.compress_and_register(pdfs[0], min_savings_pct=0).main_file_id
            m2 = mgr.compress_and_register(pdfs[1], min_savings_pct=0).main_file_id
            mgr.update_metadata(m1, is_template=True)
            mgr.update_metadata(m2, is_template=False)
            mgr.link_to_template(m2, m1)
            completions = mgr.get_completions(m1)
            assert len(completions) == 1 and completions[0].id == m2
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_4_6_unlink_template():
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


def test_4_7_link_to_template_validation():
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
# File group CRUD (4.8–4.13)
# ---------------------------------------------------------------------------

def test_4_8_create_file_group_and_get_file_group():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        mgr = PdfFileManager(db_path=db_path)
        g = mgr.create_file_group("Test", group_type="exam")
        got = mgr.get_file_group(g.id)
        assert got.id == g.id and got.label == "Test" and len(got.members) == 0
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_4_9_add_to_file_group_and_list_file_groups():
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


def test_4_10_add_to_file_group_with_raw_raises():
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
            raw_id = result.raw_archive_id
            if raw_id is None:
                pytest.skip("Compression did not produce raw archive")
            g = mgr.create_file_group("G", group_type="collection")
            with pytest.raises(ValueError):
                mgr.add_to_file_group(g.id, raw_id)
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_4_11_remove_from_file_group():
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
            m1 = mgr.compress_and_register(pdfs[0], min_savings_pct=0).main_file_id
            g = mgr.create_file_group("G", group_type="collection")
            mgr.add_to_file_group(g.id, m1)
            mgr.remove_from_file_group(g.id, m1)
            got = mgr.get_file_group(g.id)
            assert len(got.members) == 0
            assert mgr.get_file(m1) is not None
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_4_12_set_file_group_anchor_and_get_file_group_membership():
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


def test_4_13_delete_file_group():
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
            m1 = mgr.compress_and_register(pdfs[0], min_savings_pct=0).main_file_id
            g = mgr.create_file_group("G", group_type="collection")
            mgr.add_to_file_group(g.id, m1)
            mgr.delete_file_group(g.id)
            with pytest.raises(Exception):
                mgr.get_file_group(g.id)
            assert mgr.get_file(m1) is not None
        finally:
            Path(db_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# suggest_groups (4.14–4.15)
# ---------------------------------------------------------------------------

def test_4_14_suggest_groups_returns_candidates():
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


def test_4_15_suggest_groups_unclassified_excluded():
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
            mgr.register_file(pdfs[0], doc_type="unknown")
            mgr.register_file(pdfs[1], doc_type="exam", student_id="w", subject="science", metadata={"exam_date": "2025-11-12"})
            suggestions = mgr.suggest_groups()
            for s in suggestions:
                for c in s.candidate_files:
                    assert c.doc_type == "exam"
        finally:
            Path(db_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# open_file_group (4.16–4.17)
# ---------------------------------------------------------------------------

def test_4_16_open_file_group_no_anchor_raises():
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
            m1 = mgr.compress_and_register(pdfs[0], min_savings_pct=0).main_file_id
            g = mgr.create_file_group("G", group_type="exam")
            mgr.add_to_file_group(g.id, m1)
            with pytest.raises(ConfigError):
                mgr.open_file_group(g.id)
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_4_17_open_file_group_with_anchor():
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
            m1 = mgr.compress_and_register(pdfs[0], min_savings_pct=0).main_file_id
            g = mgr.create_file_group("G", group_type="exam")
            mgr.add_to_file_group(g.id, m1)
            mgr.set_file_group_anchor(g.id, m1)
            with patch("pdf_file_manager.subprocess.run"):
                mgr.open_file_group(g.id)
        finally:
            Path(db_path).unlink(missing_ok=True)
