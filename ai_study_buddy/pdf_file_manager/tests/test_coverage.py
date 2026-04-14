# find_leaf_dirs, report_coverage, coverage CLI (Proposal 3).

import sys
import tempfile
from pathlib import Path

import pytest

_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))
from conftest import _util_dir
if str(_util_dir) not in sys.path:
    sys.path.insert(0, str(_util_dir))

from pdf_file_manager import PdfFileManager, CoverageReport


def test_find_leaf_dirs_empty_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        leafs = PdfFileManager.find_leaf_dirs(tmpdir)
        assert len(leafs) == 1 and leafs[0].resolve() == tmpdir.resolve()


def test_find_leaf_dirs_dir_with_only_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        (tmpdir / "a.txt").write_text("x")
        leafs = PdfFileManager.find_leaf_dirs(tmpdir)
        assert len(leafs) == 1 and leafs[0].resolve() == tmpdir.resolve()


def test_find_leaf_dirs_one_subdir_no_grandchildren():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        sub = tmpdir / "sub"
        sub.mkdir()
        (sub / "f.txt").write_text("x")
        leafs = PdfFileManager.find_leaf_dirs(tmpdir)
        assert len(leafs) == 1 and leafs[0].resolve() == sub.resolve()


def test_find_leaf_dirs_nested_returns_only_leaves():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        (tmpdir / "a.txt").write_text("x")
        sub1 = tmpdir / "sub1"
        sub1.mkdir()
        (sub1 / "f.txt").write_text("x")
        sub2 = tmpdir / "sub2"
        sub2.mkdir()
        deep = sub2 / "deep"
        deep.mkdir()
        (deep / "g.txt").write_text("y")
        leafs = PdfFileManager.find_leaf_dirs(tmpdir)
        assert len(leafs) == 2
        resolved = {p.resolve() for p in leafs}
        assert resolved == {sub1.resolve(), deep.resolve()}


def test_find_leaf_dirs_nonexistent_returns_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent = Path(tmpdir) / "nonexistent"
        assert not nonexistent.exists()
        leafs = PdfFileManager.find_leaf_dirs(nonexistent)
        assert leafs == []


def test_report_coverage_empty_db_from_registry():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        report = mgr.report_coverage(from_registry=True)
        assert report.leaf_dirs == set()
        assert report.scan_roots == set()
        assert report.leaf_not_in_roots == set()
        assert report.roots_without_leaf_pdfs == set()
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_report_coverage_empty_db_with_base():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            mgr = PdfFileManager(db_path=tmp)
            report = mgr.report_coverage(base_path=tmpdir, from_registry=False)
            assert report.scan_roots == set()
            assert str(tmpdir.resolve()) in report.leaf_dirs
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_report_coverage_from_registry_leaf_not_in_roots():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            pdf_path = tmpdir / "doc.pdf"
            pdf_path.write_bytes(b"%PDF-1.0\n")
            mgr = PdfFileManager(db_path=tmp)
            mgr.register_file(pdf_path)
            report = mgr.report_coverage(from_registry=True)
            assert len(report.leaf_dirs) == 1
            parent_str = str(tmpdir.resolve())
            assert parent_str in report.leaf_dirs
            assert report.scan_roots == set()
            assert report.leaf_not_in_roots == {parent_str}
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_report_coverage_registry_derived_paths_no_raw_sql():
    """Integration: list paths from registry and compare to scan_roots using only public API."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            pdf_path = tmpdir / "a.pdf"
            pdf_path.write_bytes(b"%PDF-1.0\n")
            mgr = PdfFileManager(db_path=tmp)
            mgr.register_file(pdf_path)
            mgr.add_scan_root(str(tmpdir), student_id=None)
            report = mgr.report_coverage(from_registry=True)
            parent_str = str(tmpdir.resolve())
            assert parent_str in report.leaf_dirs
            assert parent_str in report.scan_roots
            assert parent_str not in report.leaf_not_in_roots
    finally:
        Path(tmp).unlink(missing_ok=True)
