from __future__ import annotations

import os
from pathlib import Path

_DAYDREAMEDU_ROOT_ENV = "DAYDREAMEDU_ROOT"
_GOODNOTES_ROOT_ENV = "GOODNOTES_ROOT"

_LOCAL_DAYDREAMEDU_ROOT_FILE = Path(__file__).resolve().parents[1] / "local_daydreamedu_root.txt"
_LOCAL_GOODNOTES_ROOT_FILE = Path(__file__).resolve().parents[1] / "local_goodnotes_root.txt"


def _resolve_path_from_env(env_var: str) -> Path | None:
    env = os.environ.get(env_var, "").strip()
    if not env:
        return None
    p = Path(env).expanduser().resolve()
    return p if p.is_dir() else None


def _resolve_first_path_from_file(config_file: Path) -> Path | None:
    if not config_file.is_file():
        return None
    text = config_file.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = Path(line).expanduser().resolve()
        return p if p.is_dir() else None
    return None


def resolve_daydreamedu_root() -> Path | None:
    """Return configured DaydreamEdu root.

    Resolution order:
    1. DAYDREAMEDU_ROOT env var
    2. ai_study_buddy/local_daydreamedu_root.txt
    """
    return _resolve_path_from_env(_DAYDREAMEDU_ROOT_ENV) or _resolve_first_path_from_file(_LOCAL_DAYDREAMEDU_ROOT_FILE)


def resolve_goodnotes_root() -> Path | None:
    """Return configured/discoverable GoodNotes root.

    Resolution order:
    1. GOODNOTES_ROOT env var
    2. ai_study_buddy/local_goodnotes_root.txt
    3. Sibling discovery: <DaydreamEdu parent>/GoodNotes
    """
    direct = _resolve_path_from_env(_GOODNOTES_ROOT_ENV) or _resolve_first_path_from_file(_LOCAL_GOODNOTES_ROOT_FILE)
    if direct is not None:
        return direct

    dd = resolve_daydreamedu_root()
    if dd is None:
        return None
    sibling = (dd.parent / "GoodNotes").resolve()
    return sibling if sibling.is_dir() else None
