"""Basename heuristics for proposal 18 Activity → Composition migration selection."""

from __future__ import annotations

import re

COMPOSITION_BASENAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"composition", re.IGNORECASE),
    re.compile(r"作文"),
    re.compile(r"paper\s*1", re.IGNORECASE),
    re.compile(r"试卷一"),
    re.compile(r"situational\s*writing", re.IGNORECASE),
    re.compile(r"continuous\s*writing", re.IGNORECASE),
)


def is_composition_basename(name: str) -> bool:
    """True when *name* matches migration heuristics (filename only, not path inference)."""
    return any(p.search(name) for p in COMPOSITION_BASENAME_PATTERNS)
