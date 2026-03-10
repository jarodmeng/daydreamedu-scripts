# Students and scan roots (config). See TESTING.md § Phase 2 (students, scan roots).

import sys
import tempfile
from pathlib import Path

import pytest

_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))
from pdf_file_manager import PdfFileManager


def test_add_student_then_list_students():
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


def test_list_students_empty_at_first():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        assert mgr.list_students() == []
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_add_scan_root_then_list_scan_roots():
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


def test_remove_scan_root():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr.add_scan_root("/tmp/foo", student_id="w")
        mgr.remove_scan_root("/tmp/foo")
        assert mgr.list_scan_roots() == []
    finally:
        Path(tmp).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# ensure_student / ensure_scan_root (Proposal 1)
# ---------------------------------------------------------------------------

def test_ensure_student_creates_when_missing():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        s = mgr.ensure_student("w", "Winston", email="w@x.com")
        assert s.id == "w" and s.name == "Winston" and s.email == "w@x.com"
        assert mgr.get_student("w") is not None
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_ensure_student_idempotent_returns_existing():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr.add_student("w", "Winston", email="w@x.com")
        s = mgr.ensure_student("w", "Other", email="other@x.com")
        assert s.id == "w" and s.name == "Winston" and s.email == "w@x.com"
        assert len(mgr.list_students()) == 1
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_ensure_scan_root_creates_when_missing():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        r = mgr.ensure_scan_root("/tmp/foo", student_id="w")
        assert r.path.endswith("foo") or "foo" in r.path
        assert r.student_id == "w"
        assert len(mgr.list_scan_roots()) == 1
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_ensure_scan_root_idempotent_returns_existing():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr.add_scan_root("/tmp/foo", student_id="w")
        r = mgr.ensure_scan_root("/tmp/foo", student_id=None)
        assert r.path.endswith("foo") or "foo" in r.path
        assert r.student_id == "w"  # unchanged
        assert len(mgr.list_scan_roots()) == 1
    finally:
        Path(tmp).unlink(missing_ok=True)
