from __future__ import annotations

_FULL_SCOPE_MARKERS = (
    "full paper",
    "full booklet",
    "all questions",
    "whole worksheet",
    "booklet a + booklet b",
    "booklet a, booklet b, and paper 2",
    "all statistics mcqs on this completion",
    "including subparts",
)


def infer_is_partial_from_raw_text(raw_text: str | None) -> bool:
    """Infer whether marking scope is partial from free-text question selection notes."""
    if not isinstance(raw_text, str):
        return False
    normalized = " ".join(raw_text.strip().lower().split())
    if not normalized:
        return False
    if any(marker in normalized for marker in _FULL_SCOPE_MARKERS):
        return False
    if "disqualified" in normalized and "partial" not in normalized:
        return False
    if "partial" in normalized:
        return True
    if "only" in normalized:
        return True
    return False
