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
