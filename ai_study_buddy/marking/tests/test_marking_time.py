from __future__ import annotations

from datetime import datetime, timezone

from ai_study_buddy.marking.core.marking_time import (
    format_basename_timestamp,
    now_marking_iso,
    to_marking_iso,
)


def test_to_marking_iso_normalizes_z_to_plus08():
    assert to_marking_iso("2026-04-15T10:30:25Z") == "2026-04-15T18:30:25+08:00"


def test_format_basename_timestamp_matches_sgt_wall_clock():
    assert format_basename_timestamp("2026-04-15T10:30:25Z") == "20260415_183025"
    assert format_basename_timestamp("2026-04-15T18:30:25+08:00") == "20260415_183025"


def test_to_marking_iso_accepts_aware_datetime():
    dt = datetime(2026, 4, 15, 10, 30, 25, tzinfo=timezone.utc)
    assert to_marking_iso(dt) == "2026-04-15T18:30:25+08:00"


def test_now_marking_iso_ends_with_offset():
    assert now_marking_iso().endswith("+08:00")
