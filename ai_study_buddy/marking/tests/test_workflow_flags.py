"""Tests for marking.review.workflow_flags."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_study_buddy.marking.review.workflow_flags import (
    completion_workflow_flags,
    load_completion_marking_context,
)


def _completion() -> MagicMock:
    c = MagicMock()
    c.id = "file-1"
    c.subject = "math"
    c.student_id = "winston"
    return c


@patch("ai_study_buddy.marking.review.workflow_flags.find_marking_artifacts_for_attempt")
def test_completion_workflow_flags_unmarked(mock_find) -> None:
    mock_find.return_value = []
    pfm = MagicMock()
    review_repo = MagicMock()
    flags = completion_workflow_flags(
        _completion(),
        context_root=Path("/ctx"),
        manager=pfm,
        review_repo=review_repo,
    )
    assert flags.has_marking is False
    assert flags.review_status == "not_started"


@patch("ai_study_buddy.marking.review.workflow_flags.find_marking_artifacts_for_attempt")
@patch("ai_study_buddy.marking.review.workflow_flags.read_marking_result_payload")
def test_load_completion_marking_context_marked(mock_read, mock_find) -> None:
    ref = MagicMock()
    json_path = MagicMock()
    json_path.stem = "artifact_stem"
    json_path.relative_to.return_value = Path("marking_results/artifact_stem.json")
    ref.marking_result_json = json_path
    mock_find.return_value = [ref]
    mock_read.return_value = {
        "context": {"student_id": "winston", "subject_context": "singapore_primary_math"},
        "summary": {"earned_marks": 1, "total_marks": 2},
    }
    review_repo = MagicMock()
    review_repo.load_review_state.return_value = {"review_status": "in_progress"}
    review_repo.load_raw_amendment.return_value = None

    ctx = load_completion_marking_context(
        _completion(),
        context_root=Path("/ctx"),
        manager=MagicMock(),
        review_repo=review_repo,
    )
    assert ctx.has_marking is True
    assert ctx.review_status == "in_progress"
    assert ctx.has_marking_amendment is False
