"""Runtime toggles for `study_buddy.db` read/write integration (Proposal L4)."""

from __future__ import annotations

import os


def _truthy(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    v = raw.strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    return default


def learning_db_reads_enabled() -> bool:
    """When True, marking/review code may read from `study_buddy.db`. Default True."""
    return _truthy("LEARNING_DB_ENABLE_READS", True)


def learning_db_read_fallback_filesystem() -> bool:
    """When True, if DB misses a lookup, fall back to context JSON scans. Default False after cutover."""
    return _truthy("LEARNING_DB_READ_FALLBACK_FILESYSTEM", False)


def learning_db_dual_write_enabled() -> bool:
    """When True, canonical JSON snapshots also upsert rows in ``study_buddy.db``. Default True."""
    return _truthy("LEARNING_DB_ENABLE_DUAL_WRITE", True)


def learning_db_strict_dual_write() -> bool:
    """When True, filesystem snapshot rollback is attempted after failed DB projection; caller sees an exception."""
    return _truthy("LEARNING_DB_STRICT_DUAL_WRITE", False)


def learning_db_json_export_enabled() -> bool:
    """When True (default during compatibility phase), repositories still emit JSON under ``context/`` alongside DB writes."""
    return _truthy("LEARNING_DB_ENABLE_JSON_EXPORT", True)
