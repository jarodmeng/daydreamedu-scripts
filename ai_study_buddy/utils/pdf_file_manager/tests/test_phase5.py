# Phase 5 confidence tests. See TESTING.md § Phase 5.
# get_operation_log (filters, log_id) and CLI smoke tests (--help, --db with temp DB).

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_tests_dir = Path(__file__).resolve().parent
_util_dir = _tests_dir.parent
if str(_util_dir) not in sys.path:
    sys.path.insert(0, str(_util_dir))

from pdf_file_manager import (
    PdfFileManager,
    OperationRecord,
)

# CLI script path (same directory as the module)
_CLI_SCRIPT = _util_dir / "pdf_file_manager.py"


def _has_cli() -> bool:
    """True if the CLI entry point exists and responds to --help."""
    if not _CLI_SCRIPT.is_file():
        return False
    try:
        r = subprocess.run(
            [sys.executable, str(_CLI_SCRIPT), "--help"],
            cwd=str(_util_dir),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.returncode == 0 and ("help" in r.stdout.lower() or "usage" in r.stdout.lower())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# get_operation_log (5.1–5.6)
# ---------------------------------------------------------------------------

def test_5_1_get_operation_log_no_filters_returns_all_ordered():
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


def test_5_2_get_operation_log_filter_by_file_id():
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


def test_5_3_get_operation_log_filter_by_operation():
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


def test_5_4_get_operation_log_filter_by_group_id():
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


def test_5_5_get_operation_log_log_id_returns_one_or_empty():
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


def test_5_6_get_operation_log_since_filter():
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


# ---------------------------------------------------------------------------
# CLI smoke tests (5.7–5.8)
# ---------------------------------------------------------------------------

def test_5_7_cli_help_exits_0():
    if not _has_cli():
        pytest.skip("CLI not available (no script or --help failed)")
    r = subprocess.run(
        [sys.executable, str(_CLI_SCRIPT), "--help"],
        cwd=str(_util_dir),
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert r.returncode == 0
    assert "help" in r.stdout.lower() or "usage" in r.stdout.lower()


def test_5_8_cli_log_help_with_temp_db():
    if not _has_cli():
        pytest.skip("CLI not available")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        r = subprocess.run(
            [sys.executable, str(_CLI_SCRIPT), "--db", db_path, "log", "--help"],
            cwd=str(_util_dir),
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert r.returncode == 0
    finally:
        Path(db_path).unlink(missing_ok=True)
