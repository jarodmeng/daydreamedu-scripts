# get_operation_log. See TESTING.md § Phase 5 (audit).

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))
from pdf_file_manager import PdfFileManager


def test_get_operation_log_no_filters_returns_all_ordered():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        (tmpdir / "dummy.pdf").write_bytes(b"%PDF-1.0\n")
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.register_file(tmpdir / "dummy.pdf")
            mgr.create_file_group("G", group_type="collection")
            log = mgr.get_operation_log()
            assert isinstance(log, list)
            assert len(log) >= 2
            for i in range(len(log) - 1):
                assert log[i].performed_at <= log[i + 1].performed_at
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_get_operation_log_filter_by_file_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        pdf_path = tmpdir / "dummy.pdf"
        pdf_path.write_bytes(b"%PDF-1.0\n")
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            reg = mgr.register_file(pdf_path)
            log_file = mgr.get_operation_log(file_id=reg.id)
            assert len(log_file) >= 1
            for entry in log_file:
                assert entry.file_id == reg.id
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_get_operation_log_filter_by_operation():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        mgr = PdfFileManager(db_path=db_path)
        mgr.add_student("w", "W")
        mgr.create_file_group("G", group_type="exam")
        log_register = mgr.get_operation_log(operation="group_create")
        assert len(log_register) >= 1
        for entry in log_register:
            assert entry.operation == "group_create"
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_get_operation_log_filter_by_group_id():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        mgr = PdfFileManager(db_path=db_path)
        g = mgr.create_file_group("MyGroup", group_type="collection")
        log = mgr.get_operation_log(group_id=g.id)
        assert len(log) >= 1
        for entry in log:
            assert entry.group_id == g.id
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_get_operation_log_log_id_returns_one_or_empty():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        mgr = PdfFileManager(db_path=db_path)
        mgr.create_file_group("G", group_type="collection")
        log = mgr.get_operation_log()
        assert len(log) >= 1
        first_id = log[0].id
        one = mgr.get_operation_log(log_id=first_id)
        assert len(one) == 1
        assert one[0].id == first_id
        empty = mgr.get_operation_log(log_id="00000000-0000-0000-0000-000000000000")
        assert len(empty) == 0
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_get_operation_log_since_filter():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        mgr = PdfFileManager(db_path=db_path)
        mgr.create_file_group("G", group_type="collection")
        log = mgr.get_operation_log()
        assert len(log) >= 1
        since = log[0].performed_at
        log_since = mgr.get_operation_log(since=since)
        assert len(log_since) >= 1
        for entry in log_since:
            assert entry.performed_at >= since
        log_since_future = mgr.get_operation_log(since="2099-01-01T00:00:00Z")
        assert len(log_since_future) == 0
    finally:
        Path(db_path).unlink(missing_ok=True)
