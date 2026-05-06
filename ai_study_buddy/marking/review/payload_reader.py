from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_marking_result_payload(*, marking_result_json: Path, context_root: Path) -> dict[str, Any] | None:
    """Read a marking result through the configured DB-first compatibility path."""

    rel_path = _relative_to_context(marking_result_json, context_root)

    try:
        from ai_study_buddy.learning_db.core.config import (
            learning_db_read_fallback_filesystem,
            learning_db_reads_enabled,
        )
        from ai_study_buddy.learning_db.read.read_documents import fetch_marking_artifact_raw_json
    except ImportError:
        return _read_json_payload(marking_result_json)

    if learning_db_reads_enabled():
        if rel_path is not None:
            raw = fetch_marking_artifact_raw_json(rel_path)
            if raw is not None:
                return raw
        if not learning_db_read_fallback_filesystem():
            return None

    return _read_json_payload(marking_result_json)


def _relative_to_context(path: Path, context_root: Path) -> str | None:
    try:
        return path.resolve(strict=False).relative_to(context_root.resolve(strict=False)).as_posix()
    except ValueError:
        try:
            return path.relative_to(context_root).as_posix()
        except ValueError:
            return None


def _read_json_payload(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None
