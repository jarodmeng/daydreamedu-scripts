"""Tests for marking amendment obsolescence comparison helpers."""

from __future__ import annotations

from ai_study_buddy.learning_db.analysis.marking_amendment_obsolescence import (
    _audit_amendment_payload,
    field_values_equal,
)


def test_field_values_equal_marks_and_text():
    assert field_values_equal("earned_marks", 1, 1.0)
    assert field_values_equal("student_answer", "  hello ", "hello")
    assert not field_values_equal("outcome", "wrong", "correct")


def test_audit_amendment_payload_marks_obsolete_and_active_fields():
    amendment_payload = {
        "question_amendments": [
            {
                "result_id": "Q1",
                "fields": {"outcome": "wrong", "earned_marks": 0},
            }
        ],
        "question_page_map_amendments": [],
        "summary_overrides": {},
    }
    marking_payload = {
        "question_results": [
            {"result_id": "Q1", "outcome": "wrong", "earned_marks": 0, "max_marks": 1},
        ],
        "context": {"question_page_map": []},
        "summary": {},
    }
    items = _audit_amendment_payload(
        amendment_id="a1",
        amendment_path="marking_amendments/demo.json",
        marking_result_path="marking_results/demo.json",
        student_id="emma",
        subject_context="singapore_primary_math",
        amendment_payload=amendment_payload,
        marking_payload=marking_payload,
    )
    by_key = {(item.field_key): item.status for item in items}
    assert by_key["outcome"] == "obsolete"
    assert by_key["earned_marks"] == "obsolete"

    marking_payload["question_results"][0]["outcome"] = "correct"
    items = _audit_amendment_payload(
        amendment_id="a1",
        amendment_path="marking_amendments/demo.json",
        marking_result_path="marking_results/demo.json",
        student_id="emma",
        subject_context="singapore_primary_math",
        amendment_payload=amendment_payload,
        marking_payload=marking_payload,
    )
    by_key = {(item.field_key): item.status for item in items}
    assert by_key["outcome"] == "active"
    assert by_key["earned_marks"] == "obsolete"
