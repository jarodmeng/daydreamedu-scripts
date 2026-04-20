"""Singapore (SGT) wall time for marking artifacts.

All persisted ``created_at`` / ``updated_at`` timestamps on ``marking_result.v1``
JSON and the ``__YYYYMMDD_HHMMSS`` attempt basename suffix use **Asia/Singapore**
local civil time with an explicit ``+08:00`` offset in ISO-8601 strings.

Callers may construct artifacts with UTC (``Z``) or other offsets; the canonical
writer normalizes to SGT before persisting.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

MARKING_TIMEZONE = ZoneInfo("Asia/Singapore")


def _parse_to_aware(value: str | datetime) -> datetime:
    """Parse to a timezone-aware datetime (naive strings treated as UTC)."""
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def format_basename_timestamp(value: str | datetime) -> str:
    """``YYYYMMDD_HHMMSS`` in Singapore local time for ``<attempt_basename>`` suffix."""
    dt = _parse_to_aware(value).astimezone(MARKING_TIMEZONE)
    return dt.strftime("%Y%m%d_%H%M%S")


def to_marking_iso(value: str | datetime) -> str:
    """Normalize any parseable instant to ISO-8601 string with ``+08:00`` offset."""
    dt = _parse_to_aware(value).astimezone(MARKING_TIMEZONE)
    return dt.replace(microsecond=0).isoformat()


def now_marking_iso() -> str:
    """Current time as Singapore marking timestamp (no microseconds)."""
    return to_marking_iso(datetime.now(MARKING_TIMEZONE))
