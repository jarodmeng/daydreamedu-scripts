from __future__ import annotations

from pathlib import Path
import sys

_tests_dir = Path(__file__).resolve().parent
_pkg_dir = _tests_dir.parent
if str(_pkg_dir.parent) not in sys.path:
    sys.path.insert(0, str(_pkg_dir.parent))
