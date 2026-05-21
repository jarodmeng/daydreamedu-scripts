"""Tests for files.completion_enrichment."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_study_buddy.files.completion_enrichment import (
    _marking_score_from_summary,
    enrich_registered_completion,
)


def test_marking_score_from_summary_computes_percentage() -> None:
    earned, total, pct = _marking_score_from_summary({"earned_marks": 1, "total_marks": 2})
    assert earned == 1
    assert total == 2
    assert pct == 50.0


def test_marking_score_from_summary_uses_existing_percentage() -> None:
    earned, total, pct = _marking_score_from_summary(
        {"earned_marks": 3, "total_marks": 4, "percentage": 75.0}
    )
    assert earned == 3
    assert total == 4
    assert pct == 75.0


@patch("ai_study_buddy.marking.review.workflow_flags.load_completion_marking_context")
def test_enrich_registered_completion_exposes_score(mock_load) -> None:
    mock_load.return_value = MagicMock(
        has_marking=True,
        has_marking_amendment=False,
        review_status="completed",
        resolved_summary={"earned_marks": 8, "total_marks": 10, "percentage": 80.0},
    )
    completion = MagicMock()
    out = enrich_registered_completion(
        completion,
        context_root=Path("/ctx"),
        pfm=MagicMock(),
        review_repo=MagicMock(),
    )
    assert out.marking_earned_marks == 8
    assert out.marking_total_marks == 10
    assert out.marking_percentage == 80.0


@patch("ai_study_buddy.marking.review.workflow_flags.load_completion_marking_context")
def test_enrich_registered_completion_unmarked_has_no_score(mock_load) -> None:
    mock_load.return_value = MagicMock(
        has_marking=False,
        has_marking_amendment=False,
        review_status="not_started",
        resolved_summary=None,
    )
    out = enrich_registered_completion(
        MagicMock(),
        context_root=Path("/ctx"),
        pfm=MagicMock(),
        review_repo=MagicMock(),
    )
    assert out.marking_earned_marks is None
    assert out.marking_total_marks is None
    assert out.marking_percentage is None
