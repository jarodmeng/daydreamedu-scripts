"""Tests for student_file_browser.filters."""

from ai_study_buddy.student_file_browser.filters import filter_criteria_from_query


def test_filter_criteria_from_query_defaults() -> None:
    c = filter_criteria_from_query({})
    assert c.scope == "completion"
    assert c.root_id == "all"
    assert c.subject == ()
    assert c.grade == ()
    assert c.doc_type == ()
    assert c.is_registered is None
    assert c.sort == "recent"


def test_filter_criteria_from_query_root_id() -> None:
    c = filter_criteria_from_query({"root_id": ["goodnotes"]})
    assert c.root_id == "goodnotes"


def test_filter_criteria_from_query_invalid_root_id() -> None:
    c = filter_criteria_from_query({"root_id": ["invalid"]})
    assert c.root_id == "all"


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


def test_filter_criteria_from_query_sort_name() -> None:
    c = filter_criteria_from_query({"sort": ["name"]})
    assert c.sort == "name"


def test_filter_criteria_from_query_invalid_sort() -> None:
    c = filter_criteria_from_query({"sort": ["bogus"]})
    assert c.sort == "recent"


def test_filter_criteria_from_query_multi_subject() -> None:
    c = filter_criteria_from_query({"subject": ["math", "science"]})
    assert c.subject == ("math", "science")


def test_filter_criteria_from_query_single_subject_legacy() -> None:
    c = filter_criteria_from_query({"subject": ["math"]})
    assert c.subject == ("math",)


def test_filter_criteria_from_query_subject_all_ignored() -> None:
    c = filter_criteria_from_query({"subject": ["all"]})
    assert c.subject == ()
