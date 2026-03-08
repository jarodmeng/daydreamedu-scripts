# get_file, find_files. See TESTING.md § Phase 3 (read).

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))
from conftest import FIXTURE_ROOT, fixture_has_pdfs
from pdf_file_manager import PdfFileManager


def test_get_file_by_id_returns_pdffile():
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
            registered = mgr.register_file(path)
            out = mgr.get_file(registered.id)
            assert out is not None
            assert out.id == registered.id
            assert out.path == registered.path
            assert out.name == registered.name
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_get_file_unknown_id_returns_none():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        out = mgr.get_file("00000000-0000-0000-0000-000000000000")
        assert out is None
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_find_files_no_filters_returns_all():
    if not fixture_has_pdfs():
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


def test_find_files_file_type_filter():
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
            mgr.register_file(pdfs[0])
            mgr.compress_and_register(pdfs[1], min_savings_pct=0)
            main_only = mgr.find_files(file_type="main")
            assert len(main_only) >= 1
            assert all(f.file_type == "main" for f in main_only)
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_find_files_doc_type_filter():
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
            mgr.register_file(pdfs[0], doc_type="exam")
            mgr.register_file(pdfs[1], doc_type="worksheet")
            exam = mgr.find_files(doc_type="exam")
            assert len(exam) == 1 and exam[0].doc_type == "exam"
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_find_files_student_id_filter():
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
            mgr.add_student("w", "W")
            mgr.add_student("x", "X")
            mgr.register_file(pdfs[0], student_id="w")
            mgr.register_file(pdfs[1], student_id="x")
            w_files = mgr.find_files(student_id="w")
            assert len(w_files) == 1 and w_files[0].student_id == "w"
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_find_files_subject_filter():
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
            mgr.register_file(pdfs[0], subject="math")
            mgr.register_file(pdfs[1], subject="science")
            math_files = mgr.find_files(subject="math")
            assert len(math_files) == 1 and math_files[0].subject == "math"
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_find_files_query_name_substring():
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
            mgr.register_file(pdfs[0])
            name_substring = "Science"
            found = mgr.find_files(query=name_substring)
            assert len(found) >= 1
            assert name_substring.lower() in found[0].name.lower()
            empty = mgr.find_files(query="nonexistentxyzz")
            assert len(empty) == 0
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_find_files_is_template_and_has_raw():
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
            mgr.register_file(pdfs[0], is_template=True)
            mgr.compress_and_register(pdfs[1], min_savings_pct=0)
            templates = mgr.find_files(is_template=True)
            assert len(templates) >= 1 and all(f.is_template for f in templates)
            with_raw = mgr.find_files(has_raw=True)
            assert len(with_raw) >= 1 and all(f.has_raw for f in with_raw)
        finally:
            Path(db_path).unlink(missing_ok=True)
