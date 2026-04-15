from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from ai_study_buddy.marking.core.artifact_paths import (
    build_attempt_basename,
    build_learning_report_path,
    build_marking_artifact_path,
    normalize_attempt_stem,
)
from ai_study_buddy.marking.core.artifact_schema import (
    MarkingArtifactValidationError,
    SCHEMA_PATH,
    compute_percentage,
    load_marking_result_schema,
    validate_marking_artifact_dict,
)
from ai_study_buddy.marking.core.artifact_writer import write_marking_artifact
from ai_study_buddy.marking.workflows.edit_human_notes import update_human_notes
from ai_study_buddy.marking.core.models import (
    ArtifactQuestionResult,
    ArtifactSummary,
    Diagnosis,
    GenerationMeta,
    MarkingArtifact,
    MarkingArtifactContext,
    QuestionSelection,
    ReviewMeta,
)
from ai_study_buddy.marking.workflows.report_renderer import render_learning_report_from_json


def _sample_artifact() -> MarkingArtifact:
    return MarkingArtifact(
        schema_version="marking_result.v1",
        created_at="2026-04-15T10:30:25Z",
        updated_at="2026-04-15T10:30:25Z",
        context=MarkingArtifactContext(
            student_id="winston",
            student_name="Winston",
            subject_context="singapore_primary_science",
            attempt_file_id="attempt_123",
            attempt_file_path="/tmp/c_Science Practice Primary 5 and 6 - 17 Interactions.pdf",
            template_file_id="template_456",
            template_file_path="/tmp/_c_Science Practice Primary 5 and 6 - 17 Interactions.pdf",
            book_group_id="book_789",
            book_label="Science Practice Primary 5 and 6",
            unit_file_id="template_456",
            unit_file_path="/tmp/_c_Science Practice Primary 5 and 6 - 17 Interactions.pdf",
            unit_label="17 Interactions",
            answer_file_id="answer_321",
            answer_file_path="/tmp/_c_Science Practice Primary 5 and 6 - 26 Answers.pdf",
            answer_page_start=22,
            answer_page_end=24,
            starts_mid_page=False,
            ends_mid_page=True,
            answer_mapping_source="manual_verified",
            answer_mapping_notes="page 24 top only",
            question_selection=QuestionSelection(raw_text="Q1-10"),
        ),
        summary=ArtifactSummary(
            total_marks=4,
            earned_marks=3,
            percentage=75.0,
            overall_assessment="Mostly correct with one conceptual miss.",
            human_note=None,
        ),
        question_results=(
            ArtifactQuestionResult(
                result_id="Q1",
                max_marks=2,
                earned_marks=2,
                outcome="correct",
                student_answer="(2)",
                correct_answer="(2)",
                skill_tags=("forces", "fair_test"),
                diagnosis=Diagnosis(),
            ),
            ArtifactQuestionResult(
                result_id="Q2",
                max_marks=2,
                earned_marks=1,
                outcome="partial",
                student_answer="downward force only",
                correct_answer="downward gravitational force and upward air resistance",
                feedback="Need both forces.",
                error_tags=("incomplete_explanation",),
                skill_tags=("forces", "effects_of_force"),
                diagnosis=Diagnosis(
                    mistake_type="incomplete_explanation",
                    reasoning="Final answer mentions only one of two visible forces.",
                    confidence="high",
                ),
            ),
        ),
        review_meta=ReviewMeta(),
        generation=GenerationMeta(
            produced_by="test",
            mode="manual_visual_with_ai_assist",
            notes="test fixture",
        ),
    )


def test_schema_file_exists_and_loads():
    assert SCHEMA_PATH.is_file()
    schema = load_marking_result_schema()
    assert schema["title"] == "marking_result.v1"


def test_normalize_attempt_stem_strips_known_prefixes():
    assert normalize_attempt_stem("c_example.pdf") == "example"
    assert normalize_attempt_stem("_c_example.pdf") == "example"
    assert normalize_attempt_stem("_raw_example.pdf") == "example"


def test_build_attempt_basename_uses_timestamp_suffix():
    assert build_attempt_basename("_c_p4.math.wa1.6.pdf", marked_at="2026-04-15T10:30:25Z") == "p4.math.wa1.6__20260415_103025"


def test_artifact_paths_use_student_and_subject_context():
    artifact = _sample_artifact()
    json_path = build_marking_artifact_path(artifact, context_root="/tmp/context")
    report_path = build_learning_report_path(artifact, context_root="/tmp/context")
    assert str(json_path).endswith("/marking_results/winston/singapore_primary_science/Science Practice Primary 5 and 6 - 17 Interactions__20260415_103025.json")
    assert str(report_path).endswith("/learning_reports/winston/singapore_primary_science/Science Practice Primary 5 and 6 - 17 Interactions__20260415_103025 - Marking Report.md")


def test_validate_marking_artifact_dict_accepts_valid_payload():
    validate_marking_artifact_dict(_sample_artifact().to_dict())


def test_validate_marking_artifact_dict_rejects_inconsistent_totals():
    payload = _sample_artifact().to_dict()
    payload["summary"]["earned_marks"] = 99
    with pytest.raises(MarkingArtifactValidationError):
        validate_marking_artifact_dict(payload)


def test_validate_marking_artifact_dict_supports_disqualified_excluded_rows():
    artifact = _sample_artifact()
    disqualified = ArtifactQuestionResult(
        result_id="QX",
        max_marks=2,
        earned_marks=0,
        outcome="disqualified",
        student_answer="612.5",
        correct_answer=None,
        scoring_status="excluded_disqualified",
        feedback="Question stem mismatch with mapped answer key.",
        diagnosis=Diagnosis(
            mistake_type=None,
            reasoning="Disqualified item; student error diagnosis not applicable.",
            confidence="high",
        ),
    )
    updated = replace(
        artifact,
        question_results=artifact.question_results + (disqualified,),
        summary=replace(
            artifact.summary,
            total_marks=4,
            earned_marks=3,
            percentage=75.0,
        ),
    )
    validate_marking_artifact_dict(updated.to_dict())


def test_compute_percentage_rounds_to_two_decimals():
    assert compute_percentage(1, 3) == 33.33


def test_write_marking_artifact_writes_json(tmp_path):
    artifact = _sample_artifact()
    written = write_marking_artifact(artifact, context_root=tmp_path)
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "marking_result.v1"


def test_render_learning_report_from_json_is_idempotent(tmp_path):
    artifact = _sample_artifact()
    json_path = write_marking_artifact(artifact, context_root=tmp_path)
    first = render_learning_report_from_json(json_path, context_root=tmp_path)
    second = render_learning_report_from_json(json_path, context_root=tmp_path)
    assert first == second
    text = first.read_text(encoding="utf-8")
    assert "## Marking Table" in text
    assert "Q2" in text


def test_update_human_notes_updates_review_meta(tmp_path):
    artifact = _sample_artifact()
    json_path = write_marking_artifact(artifact, context_root=tmp_path)
    update_human_notes(
        json_path,
        summary_note="Parent reviewed this attempt.",
        result_id="Q2",
        question_note="Needs to mention both forces.",
        updated_by="jarod",
    )
    payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    assert payload["summary"]["human_note"] == "Parent reviewed this attempt."
    assert payload["question_results"][1]["human_note"] == "Needs to mention both forces."
    assert payload["review_meta"]["updated_by"] == "jarod"
