"""Tests for student_file_browser.filters."""

from ai_study_buddy.student_file_browser.filters import filter_criteria_from_query


def test_filter_criteria_from_query_defaults() -> None:
    c = filter_criteria_from_query({})
    assert c.scope == "completion"
    assert c.subject == "all"
    assert c.is_registered is None


def test_filter_criteria_from_query_is_registered() -> None:
    c = filter_criteria_from_query({"is_registered": ["false"]})
    assert c.is_registered == "false"


def test_filter_criteria_from_query_workflow() -> None:
    c = filter_criteria_from_query(
        {
            "has_template": ["true"],
            "has_marking": ["false"],
            "review_status": ["in_progress"],
        }
    )
    assert c.has_template == "true"
    assert c.has_marking == "false"
    assert c.review_status == "in_progress"
