# CLI smoke tests. See TESTING.md § Phase 5 (CLI).

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))
_util_dir = _tests_dir.parent
_CLI_SCRIPT = _util_dir / "pdf_file_manager.py"


def _has_cli() -> bool:
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


def test_cli_help_exits_0():
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


def test_cli_log_help_with_temp_db():
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


# ---------------------------------------------------------------------------
# scan subcommand (Proposal 2)
# ---------------------------------------------------------------------------

def test_cli_scan_help():
    if not _has_cli():
        pytest.skip("CLI not available")
    r = subprocess.run(
        [sys.executable, str(_CLI_SCRIPT), "scan", "--help"],
        cwd=str(_util_dir),
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert r.returncode == 0
    assert "dry-run" in r.stdout
    assert "root" in r.stdout or "PATH" in r.stdout


def test_cli_scan_dry_run_no_roots_raises():
    if not _has_cli():
        pytest.skip("CLI not available")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        r = subprocess.run(
            [sys.executable, str(_CLI_SCRIPT), "--db", db_path, "scan", "--dry-run"],
            cwd=str(_util_dir),
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert r.returncode != 0
        assert "No scan roots" in r.stderr or "Error" in r.stderr
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_cli_scan_dry_run_with_root_empty_dir():
    if not _has_cli():
        pytest.skip("CLI not available")
    with tempfile.TemporaryDirectory() as tmpdir:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            r = subprocess.run(
                [sys.executable, str(_CLI_SCRIPT), "--db", db_path, "scan", "--dry-run", "--root", tmpdir],
                cwd=str(_util_dir),
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert r.returncode == 0
            assert "No new PDFs" in r.stdout
        finally:
            Path(db_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# coverage subcommand (Proposal 3)
# ---------------------------------------------------------------------------

def test_cli_coverage_help():
    if not _has_cli():
        pytest.skip("CLI not available")
    r = subprocess.run(
        [sys.executable, str(_CLI_SCRIPT), "coverage", "--help"],
        cwd=str(_util_dir),
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert r.returncode == 0
    assert "from-registry" in r.stdout or "registry" in r.stdout.lower()
    assert "base" in r.stdout.lower()


def test_cli_coverage_from_registry_empty_db():
    if not _has_cli():
        pytest.skip("CLI not available")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        r = subprocess.run(
            [sys.executable, str(_CLI_SCRIPT), "--db", db_path, "coverage", "--from-registry"],
            cwd=str(_util_dir),
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert r.returncode == 0
        assert "Leaf dirs: 0" in r.stdout
        assert "Scan roots: 0" in r.stdout
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_cli_coverage_base_nonexistent():
    if not _has_cli():
        pytest.skip("CLI not available")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        r = subprocess.run(
            [sys.executable, str(_CLI_SCRIPT), "--db", db_path, "coverage", "--base", "/nonexistent/path/12345"],
            cwd=str(_util_dir),
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert r.returncode != 0
        assert "not a directory" in r.stderr or "Error" in r.stderr
    finally:
        Path(db_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# link-template subcommand (Proposal 4)
# ---------------------------------------------------------------------------

def test_cli_link_template_help():
    if not _has_cli():
        pytest.skip("CLI not available")
    r = subprocess.run(
        [sys.executable, str(_CLI_SCRIPT), "link-template", "--help"],
        cwd=str(_util_dir),
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert r.returncode == 0
    assert "template" in r.stdout.lower()
    assert "completed" in r.stdout.lower()


def test_cli_link_template_missing_file_exits_nonzero():
    if not _has_cli():
        pytest.skip("CLI not available")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        r = subprocess.run(
            [sys.executable, str(_CLI_SCRIPT), "--db", db_path, "link-template", "--template", "/nonexistent/t.pdf", "--completed", "/nonexistent/c.pdf"],
            cwd=str(_util_dir),
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert r.returncode != 0
        assert "Error" in r.stderr or "not found" in r.stderr.lower()
    finally:
        Path(db_path).unlink(missing_ok=True)
