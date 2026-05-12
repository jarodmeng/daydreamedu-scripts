from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from jsonschema import Draft202012Validator

from ai_study_buddy.learning_db.core.connection import get_connection
from ai_study_buddy.learning_db.core.migrate import apply_migrations
from ai_study_buddy.marking.core.artifact_paths import (
    build_attempt_basename,
    build_learning_report_path,
    build_marking_artifact_path,
    build_marking_run_paths,
)
from ai_study_buddy.marking.core.artifact_schema import (
    AMENDMENT_SCHEMA_PATH,
    MarkingArtifactValidationError,
    SCHEMA_PATH,
    SCHEMA_VERSION,
    UnsupportedSchemaVersionError,
    compute_percentage,
    load_marking_amendment_schema,
    load_marking_result_schema,
    validate_marking_artifact_dict,
)
from ai_study_buddy.marking.core.artifact_writer import write_marking_artifact
from ai_study_buddy.marking.core.path_privacy import (
    resolve_marking_artifact_paths,
    sanitize_marking_artifact_paths,
)
from ai_study_buddy.marking.workflows.edit_human_notes import update_human_notes
from ai_study_buddy.marking.core.models import (
    ArtifactQuestionResult,
    ArtifactSummary,
    ContextResolution,
    Diagnosis,
    GenerationMeta,
    MarkingArtifact,
    MarkingArtifactContext,
    QuestionPageMapEntry,
    QuestionSelection,
    ReviewMeta,
)
from ai_study_buddy.marking.workflows.report_renderer import render_learning_report_from_json
from ai_study_buddy.pdf_file_manager.pdf_file_manager import normalize_pdf_display_name


def _sample_artifact() -> MarkingArtifact:
    return MarkingArtifact(
        schema_version="marking_result.v1.6",
        created_at="2026-04-15T18:30:25+08:00",
        updated_at="2026-04-15T18:30:25+08:00",
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
            unit_label="Science Practice Primary 5 and 6 - 17 Interactions",
            answer_file_id="answer_321",
            answer_file_path="/tmp/_c_Science Practice Primary 5 and 6 - 26 Answers.pdf",
            answer_page_start=22,
            answer_page_end=24,
            starts_mid_page=False,
            ends_mid_page=True,
            answer_mapping_source="manual_verified",
            answer_mapping_notes="page 24 top only",
            is_partial=False,
            question_page_map=(
                QuestionPageMapEntry(
                    result_id="Q1",
                    attempt_page_start=1,
                    confidence="high",
                    source="manual_visual",
                    evidence_image="attempt/attempt-page-01.png",
                    note=None,
                ),
            ),
            question_selection=QuestionSelection(raw_text="Q1-10"),
            context_resolution=ContextResolution(
                method="resolve_marking_context",
                resolver_version="1",
                resolved_at="2026-04-15T18:30:25+08:00",
                mode="standard_mapped_answer",
                invariants={"unit_label_normalized": True, "mode_explicit": True},
            ),
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


def _sample_amendment_payload() -> dict:
    return {
        "schema_version": "marking_amendment.v1",
        "context": {
            "student_id": "winston",
            "subject_context": "singapore_primary_science",
            "attempt_file_id": "attempt_123",
            "marking_result_path": "marking_results/winston/singapore_primary_science/sample.json",
        },
        "summary_overrides": {
            "human_note": "Checked by reviewer.",
        },
        "question_amendments": [
            {
                "result_id": "Q2",
                "fields": {
                    "earned_marks": 2,
                    "outcome": "correct",
                    "skill_tags": ["forces", "effects_of_force"],
                },
                "reviewer_reason": "AI under-awarded this row.",
                "updated_at": "2026-04-26T12:00:00Z",
                "updated_by": "review_workspace_ui",
            }
        ],
        "question_page_map_amendments": [
            {
                "result_id": "Q2",
                "attempt_page_start": 1,
                "confidence": "high",
                "updated_at": "2026-04-26T12:00:00Z",
                "updated_by": "review_workspace_ui",
            }
        ],
        "review_meta": {
            "updated_at": "2026-04-26T12:00:00Z",
            "updated_by": "review_workspace_ui",
        },
    }


def test_schema_file_exists_and_loads():
    assert SCHEMA_PATH.is_file()
    schema = load_marking_result_schema(SCHEMA_VERSION)
    assert schema["title"] == "marking_result.v1.6"


def _schema_fixture(name: str) -> dict:
    path = Path(__file__).resolve().parent / "fixtures" / "marking_result_v1_5" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_fixture_valid_payload_passes_schema_and_python_validator():
    payload = _schema_fixture("valid_minimal.json")
    schema = load_marking_result_schema(payload["schema_version"])
    assert list(Draft202012Validator(schema).iter_errors(payload)) == []
    validate_marking_artifact_dict(payload)


def test_schema_fixture_extra_top_level_field_fails_schema_and_python_validator():
    payload = _schema_fixture("invalid_extra_top_level.json")
    schema = load_marking_result_schema(payload["schema_version"])
    schema_errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert schema_errors
    with pytest.raises(MarkingArtifactValidationError, match="Additional properties are not allowed"):
        validate_marking_artifact_dict(payload)


def test_schema_fixture_schema_valid_but_python_totals_check_fails():
    payload = _schema_fixture("valid_schema_but_bad_totals.json")
    schema = load_marking_result_schema(payload["schema_version"])
    assert list(Draft202012Validator(schema).iter_errors(payload)) == []
    with pytest.raises(MarkingArtifactValidationError, match="summary.total_marks must equal sum"):
        validate_marking_artifact_dict(payload)


def test_validate_marking_artifact_dict_accepts_generation_telemetry():
    payload = _schema_fixture("valid_minimal.json")
    payload["generation"]["telemetry"] = {
        "fast_pass_count": 10,
        "deep_dive_count": 2,
        "total_duration_seconds": 30.5,
        "manual_corrections": 1,
    }
    validate_marking_artifact_dict(payload)


def test_validate_marking_artifact_dict_accepts_generation_telemetry_null():
    payload = _sample_artifact().to_dict()
    payload["generation"]["telemetry"] = None
    validate_marking_artifact_dict(payload)


def test_validate_marking_artifact_dict_accepts_generation_telemetry_arbitrary_object():
    payload = _sample_artifact().to_dict()
    payload["generation"]["telemetry"] = {
        "worker_durations_seconds": {"phase1": 1.2, "phase2": 4.8},
        "debug_flags": ["partial_credit_override"],
        "llm_model": "gpt-5.4",
    }
    validate_marking_artifact_dict(payload)


def test_amendment_schema_file_exists_and_loads():
    assert AMENDMENT_SCHEMA_PATH.is_file()
    schema = load_marking_amendment_schema()
    assert schema["title"] == "marking_amendment.v1"


def test_marking_amendment_schema_accepts_valid_payload():
    schema = load_marking_amendment_schema()
    errors = list(Draft202012Validator(schema).iter_errors(_sample_amendment_payload()))
    assert errors == []


def test_marking_amendment_schema_rejects_unsupported_question_field():
    schema = load_marking_amendment_schema()
    payload = _sample_amendment_payload()
    payload["question_amendments"][0]["fields"]["scoring_status"] = "counted"
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert any(error.validator in {"propertyNames", "additionalProperties"} for error in errors)


def test_normalize_pdf_display_name_strips_known_prefixes():
    assert normalize_pdf_display_name("c_example.pdf") == "example"
    assert normalize_pdf_display_name("_c_example.pdf") == "example"
    assert normalize_pdf_display_name("_raw_example.pdf") == "example"


def test_build_attempt_basename_uses_timestamp_suffix():
    # Basename uses Singapore wall time; 10:30 UTC == 18:30 SGT
    assert build_attempt_basename("_c_p4.math.wa1.6.pdf", marked_at="2026-04-15T10:30:25Z") == "p4.math.wa1.6__20260415_183025"
    assert build_attempt_basename("_c_p4.math.wa1.6.pdf", marked_at="2026-04-15T18:30:25+08:00") == "p4.math.wa1.6__20260415_183025"


def test_build_marking_run_paths_uses_single_timestamp_for_json_and_bundle():
    artifact_json, marking_asset_rel, bundle_root = build_marking_run_paths(
        attempt_file_path="/tmp/c_Science Practice Primary 5 and 6 - 17 Interactions.pdf",
        student_id="winston",
        student_name="Winston",
        subject_context="singapore_primary_science",
        marked_at="2026-04-15T18:30:25+08:00",
        context_root="/tmp/context",
    )
    assert str(artifact_json).endswith(
        "/marking_results/winston/singapore_primary_science/Science Practice Primary 5 and 6 - 17 Interactions__20260415_183025.json"
    )
    assert (
        marking_asset_rel
        == "marking_assets/winston/singapore_primary_science/Science Practice Primary 5 and 6 - 17 Interactions__20260415_183025"
    )
    assert str(bundle_root).endswith(
        "/marking_assets/winston/singapore_primary_science/Science Practice Primary 5 and 6 - 17 Interactions__20260415_183025"
    )


def test_artifact_paths_use_student_and_subject_context():
    artifact = _sample_artifact()
    json_path = build_marking_artifact_path(artifact, context_root="/tmp/context")
    report_path = build_learning_report_path(artifact, context_root="/tmp/context")
    assert str(json_path).endswith("/marking_results/winston/singapore_primary_science/Science Practice Primary 5 and 6 - 17 Interactions__20260415_183025.json")
    assert str(report_path).endswith("/learning_reports/winston/singapore_primary_science/Science Practice Primary 5 and 6 - 17 Interactions__20260415_183025 - Marking Report.md")


def test_validate_marking_artifact_dict_accepts_valid_payload():
    validate_marking_artifact_dict(_sample_artifact().to_dict())


def test_validate_marking_artifact_dict_v16_requires_context_resolution():
    payload = _sample_artifact().to_dict()
    payload["context"].pop("context_resolution", None)
    with pytest.raises(MarkingArtifactValidationError, match="context_resolution"):
        validate_marking_artifact_dict(payload)


def test_load_marking_result_schema_rejects_unsupported_version():
    with pytest.raises(UnsupportedSchemaVersionError, match="unsupported schema_version"):
        load_marking_result_schema("marking_result.v1.3")


def test_validate_marking_artifact_dict_rejects_missing_schema_version():
    payload = _schema_fixture("valid_minimal.json")
    payload.pop("schema_version")
    with pytest.raises(UnsupportedSchemaVersionError, match="unsupported schema_version: None"):
        validate_marking_artifact_dict(payload)


def test_validate_marking_artifact_dict_rejects_legacy_schema_version_fixture():
    payload = _schema_fixture("invalid_unknown_version.json")
    with pytest.raises(UnsupportedSchemaVersionError, match="unsupported schema_version: marking_result.v1.3"):
        validate_marking_artifact_dict(payload)


def test_validate_marking_artifact_dict_accepts_half_marks():
    half = MarkingArtifact(
        schema_version="marking_result.v1.6",
        created_at="2026-04-21T12:00:00+08:00",
        updated_at="2026-04-21T12:00:00+08:00",
        context=replace(_sample_artifact().context, question_page_map=()),
        summary=ArtifactSummary(
            total_marks=3.0,
            earned_marks=2.5,
            percentage=compute_percentage(2.5, 3.0),
            overall_assessment="ok",
            human_note=None,
        ),
        question_results=(
            ArtifactQuestionResult(
                result_id="Q1",
                max_marks=2,
                earned_marks=1.5,
                outcome="partial",
                student_answer="a",
                correct_answer="b",
                skill_tags=("x",),
                diagnosis=Diagnosis(),
            ),
            ArtifactQuestionResult(
                result_id="Q2",
                max_marks=1,
                earned_marks=1,
                outcome="correct",
                student_answer="c",
                correct_answer="c",
                skill_tags=("y",),
                diagnosis=Diagnosis(),
            ),
        ),
        review_meta=ReviewMeta(),
        generation=GenerationMeta(produced_by="test", mode="unit_test", notes=None),
    )
    validate_marking_artifact_dict(half.to_dict())


def test_validate_marking_artifact_dict_rejects_duplicate_question_page_map_result_ids():
    payload = _sample_artifact().to_dict()
    payload["context"]["question_page_map"] = [
        {
            "result_id": "Q1",
            "attempt_page_start": 1,
            "confidence": "high",
            "source": "manual_visual",
        },
        {
            "result_id": "Q1",
            "attempt_page_start": 2,
            "confidence": "medium",
            "source": "manual_visual",
        },
    ]
    with pytest.raises(MarkingArtifactValidationError, match="duplicate context.question_page_map result_id"):
        validate_marking_artifact_dict(payload)


def test_validate_marking_artifact_dict_rejects_unknown_question_page_map_result_id():
    payload = _sample_artifact().to_dict()
    payload["context"]["question_page_map"] = [
        {
            "result_id": "Q999",
            "attempt_page_start": 1,
            "confidence": "high",
            "source": "manual_visual",
        }
    ]
    with pytest.raises(MarkingArtifactValidationError, match="must match question_results"):
        validate_marking_artifact_dict(payload)


def test_validate_marking_artifact_dict_rejects_invalid_question_page_map_page_number():
    payload = _sample_artifact().to_dict()
    payload["context"]["question_page_map"] = [
        {
            "result_id": "Q1",
            "attempt_page_start": 0,
            "confidence": "high",
            "source": "manual_visual",
        }
    ]
    with pytest.raises(MarkingArtifactValidationError, match="attempt_page_start must be int >= 1"):
        validate_marking_artifact_dict(payload)


def test_validate_marking_artifact_dict_rejects_invalid_question_page_map_enums():
    payload = _sample_artifact().to_dict()
    payload["context"]["question_page_map"] = [
        {
            "result_id": "Q1",
            "attempt_page_start": 1,
            "confidence": "certain",
            "source": "manual",
        }
    ]
    with pytest.raises(MarkingArtifactValidationError, match="confidence must be high\\|medium\\|low"):
        validate_marking_artifact_dict(payload)


def test_validate_marking_artifact_dict_rejects_inconsistent_totals():
    payload = _sample_artifact().to_dict()
    payload["summary"]["earned_marks"] = 99
    with pytest.raises(MarkingArtifactValidationError):
        validate_marking_artifact_dict(payload)


def test_validate_marking_artifact_dict_rejects_unexpected_top_level_fields():
    payload = _sample_artifact().to_dict()
    payload["unexpected"] = True
    with pytest.raises(MarkingArtifactValidationError, match="Additional properties are not allowed"):
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
    assert payload["schema_version"] == "marking_result.v1.6"
    assert payload["context"]["template_attempt_group_id"] == "winston::template_456"
    assert payload["context"]["attempt_sequence"] == 1
    assert payload["context"]["marking_asset"].startswith("marking_assets/winston/singapore_primary_science/")
    assert payload["context"]["is_partial"] is False
    assert payload["context"]["question_page_map"][0]["result_id"] == "Q1"
    bundle_root = tmp_path / payload["context"]["marking_asset"]
    assert bundle_root.is_dir()
    assert (bundle_root / "attempt").is_dir()
    assert (bundle_root / "crops").is_dir()
    assert payload["created_at"].endswith("+08:00")
    assert payload["updated_at"].endswith("+08:00")


def test_write_marking_artifact_accepts_matching_marking_asset(tmp_path):
    artifact = _sample_artifact()
    resolved_bundle = (
        "marking_assets/winston/singapore_primary_science/"
        "Science Practice Primary 5 and 6 - 17 Interactions__20260415_183025"
    )
    updated = replace(
        artifact,
        context=replace(
            artifact.context,
            marking_asset=resolved_bundle,
        ),
    )
    written = write_marking_artifact(updated, context_root=tmp_path)
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["context"]["marking_asset"] == resolved_bundle
    bundle_root = tmp_path / resolved_bundle
    assert bundle_root.is_dir()
    assert (bundle_root / "attempt").is_dir()
    assert (bundle_root / "crops").is_dir()


def test_write_marking_artifact_rejects_mismatched_resolved_marking_asset(tmp_path):
    artifact = _sample_artifact()
    updated = replace(
        artifact,
        context=replace(
            artifact.context,
            marking_asset="marking_assets/winston/singapore_primary_science/prebuilt_bundle__20260415_172147",
        ),
    )
    with pytest.raises(ValueError, match="context.marking_asset must match canonical artifact-derived path"):
        write_marking_artifact(updated, context_root=tmp_path)


def test_write_marking_artifact_rejects_latest_alias(tmp_path):
    artifact = _sample_artifact()
    with pytest.raises(ValueError, match='schema_version must be explicit; "latest" is not supported'):
        write_marking_artifact(artifact, context_root=tmp_path, schema_version="latest")


def test_write_marking_artifact_allows_unit_label_drift_from_path(tmp_path):
    artifact = _sample_artifact()
    drifted = replace(
        artifact,
        context=replace(
            artifact.context,
            unit_label="17 Interactions",
        ),
    )
    written = write_marking_artifact(drifted, context_root=tmp_path)
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["context"]["unit_label"] == "17 Interactions"


def test_write_marking_artifact_context_contract_passes_with_matching_unit_label(tmp_path):
    artifact = _sample_artifact()
    written = write_marking_artifact(artifact, context_root=tmp_path)
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "marking_result.v1.6"


def test_write_marking_artifact_rejects_blank_unit_label(tmp_path):
    artifact = _sample_artifact()
    bad = replace(
        artifact,
        context=replace(
            artifact.context,
            unit_label="   ",
        ),
    )
    with pytest.raises(ValueError, match="context.unit_label must be non-empty string"):
        write_marking_artifact(bad, context_root=tmp_path)


def test_write_marking_artifact_rejects_manual_context_without_resolution_provenance(tmp_path):
    artifact = _sample_artifact()
    manual_context = replace(
        artifact,
        context=replace(
            artifact.context,
            context_resolution=None,
        ),
    )
    with pytest.raises(ValueError, match="context.context_resolution is required"):
        write_marking_artifact(manual_context, context_root=tmp_path)


def test_write_marking_artifact_rejects_empty_subject_context_in_writer_gate(tmp_path):
    artifact = _sample_artifact()
    bad = replace(
        artifact,
        context=replace(
            artifact.context,
            subject_context="",
        ),
    )
    with pytest.raises(ValueError, match="context.subject_context must be non-empty string"):
        write_marking_artifact(bad, context_root=tmp_path)


def test_write_marking_artifact_rejects_empty_attempt_file_path_in_writer_gate(tmp_path):
    artifact = _sample_artifact()
    bad = replace(
        artifact,
        context=replace(
            artifact.context,
            attempt_file_path="",
        ),
    )
    with pytest.raises(ValueError, match="context.attempt_file_path must be non-empty string"):
        write_marking_artifact(bad, context_root=tmp_path)


def test_write_marking_artifact_rejects_embedded_override_mode_incoherence_in_writer_gate(tmp_path):
    artifact = _sample_artifact()
    bad = replace(
        artifact,
        context=replace(
            artifact.context,
            context_resolution=replace(artifact.context.context_resolution, mode="embedded_answer_override"),
            answer_file_id="different_answer_id",
        ),
    )
    with pytest.raises(ValueError, match="embedded_answer_override requires answer_file_id == template_file_id"):
        write_marking_artifact(bad, context_root=tmp_path)


def test_write_marking_artifact_increments_attempt_sequence_for_same_template(tmp_path):
    first = _sample_artifact()
    second = replace(
        _sample_artifact(),
        created_at="2026-04-15T18:31:25+08:00",
        updated_at="2026-04-15T18:31:25+08:00",
    )
    first_path = write_marking_artifact(first, context_root=tmp_path)
    second_path = write_marking_artifact(second, context_root=tmp_path)

    first_payload = json.loads(first_path.read_text(encoding="utf-8"))
    second_payload = json.loads(second_path.read_text(encoding="utf-8"))
    assert first_payload["context"]["attempt_sequence"] == 1
    assert second_payload["context"]["attempt_sequence"] == 2
    assert (
        second_payload["context"]["template_attempt_group_id"]
        == first_payload["context"]["template_attempt_group_id"]
    )


def test_write_marking_artifact_infers_is_partial_from_scope_text(tmp_path):
    artifact = _sample_artifact()
    partial_context = replace(
        artifact.context,
        is_partial=None,
        question_selection=QuestionSelection(raw_text="Partial marking: Q1-Q6 on page 1 only."),
    )
    partial_artifact = replace(artifact, context=partial_context)
    path = write_marking_artifact(partial_artifact, context_root=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["context"]["is_partial"] is True


def test_render_learning_report_from_json_is_idempotent(tmp_path):
    artifact = _sample_artifact()
    json_path = write_marking_artifact(artifact, context_root=tmp_path)
    first = render_learning_report_from_json(json_path, context_root=tmp_path)
    second = render_learning_report_from_json(json_path, context_root=tmp_path)
    assert first == second
    text = first.read_text(encoding="utf-8")
    assert "## Marking Table" in text
    assert "Q2" in text
    assert "Attempt #1" in text
    assert "Marking asset folder:" in text


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
    assert payload["review_meta"]["updated_at"].endswith("+08:00")
    assert payload["updated_at"].endswith("+08:00")


def test_write_marking_artifact_sanitizes_context_paths(tmp_path):
    artifact = _sample_artifact()
    updated = replace(
        artifact,
            context=replace(
                artifact.context,
                attempt_file_path="/Users/me/Library/CloudStorage/GoogleDrive-owner@example.com/My Drive/GoodNotes/Singapore Primary Science/winston.ry.meng@gmail.com/P6/Book/c_test.pdf",
                template_file_path="/Users/me/Library/CloudStorage/GoogleDrive-owner@example.com/My Drive/DaydreamEdu/Singapore Primary Science/P6/Book/_c_test.pdf",
                unit_file_path="/Users/me/Library/CloudStorage/GoogleDrive-owner@example.com/My Drive/DaydreamEdu/Singapore Primary Science/P6/Book/_c_test.pdf",
                unit_label="test",
                answer_file_path="/Users/me/Library/CloudStorage/GoogleDrive-owner@example.com/My Drive/DaydreamEdu/Singapore Primary Science/P6/Book/_c_answers.pdf",
            ),
        )
    written = write_marking_artifact(updated, context_root=tmp_path)
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["context"]["attempt_file_path"].startswith("GOODNOTES_ROOT/")
    assert "<student_email>" in payload["context"]["attempt_file_path"]
    assert payload["context"]["template_file_path"].startswith("DAYDREAMEDU_ROOT/")
    assert "@example.com" not in payload["context"]["attempt_file_path"]


def test_resolve_marking_artifact_paths_expands_placeholders(monkeypatch):
    payload = _sample_artifact().to_dict()
    payload["context"]["student_id"] = "winston"
    payload["context"]["attempt_file_path"] = (
        "GOODNOTES_ROOT/Singapore Primary Science/<student_email>/P6/Book/c_test.pdf"
    )
    payload["context"]["template_file_path"] = "DAYDREAMEDU_ROOT/Singapore Primary Science/P6/Book/_c_test.pdf"

    from ai_study_buddy.marking.core import path_privacy

    monkeypatch.setattr(path_privacy, "resolve_goodnotes_root", lambda: Path("/tmp/GoodNotes"))
    monkeypatch.setattr(path_privacy, "resolve_daydreamedu_root", lambda: Path("/tmp/DaydreamEdu"))
    monkeypatch.setattr(path_privacy, "_resolve_student_email", lambda student_id: "winston.ry.meng@gmail.com")

    resolved = resolve_marking_artifact_paths(payload)
    assert resolved["context"]["attempt_file_path"] == (
        "/tmp/GoodNotes/Singapore Primary Science/winston.ry.meng@gmail.com/P6/Book/c_test.pdf"
    )
    assert resolved["context"]["template_file_path"] == (
        "/tmp/DaydreamEdu/Singapore Primary Science/P6/Book/_c_test.pdf"
    )


def test_sanitize_marking_artifact_paths_scrubs_emails():
    payload = _sample_artifact().to_dict()
    payload["context"]["attempt_file_path"] = (
        "/Users/me/Library/CloudStorage/GoogleDrive-owner@example.com/My Drive/GoodNotes/"
        "Singapore Primary Science/winston.ry.meng@gmail.com/P6/Book/c_test.pdf"
    )
    sanitized = sanitize_marking_artifact_paths(payload)
    assert sanitized["context"]["attempt_file_path"] == (
        "GOODNOTES_ROOT/Singapore Primary Science/<student_email>/P6/Book/c_test.pdf"
    )


def test_write_marking_artifact_json_write_failure_logs_and_keeps_db_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_DUAL_WRITE", "1")
    monkeypatch.setenv("LEARNING_DB_STRICT_DUAL_WRITE", "0")
    monkeypatch.setenv("LEARNING_DB_ENABLE_JSON_EXPORT", "1")
    db_path = tmp_path / "study_buddy.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    apply_migrations(db_path=db_path)

    artifact = _sample_artifact()
    with patch.object(Path, "write_text", side_effect=OSError("simulated_json_write_failure")):
        with pytest.raises(OSError, match="simulated_json_write_failure"):
            write_marking_artifact(artifact, context_root=tmp_path)

    conn = get_connection(db_path)
    try:
        artifacts = int(conn.execute("SELECT COUNT(*) AS c FROM marking_artifacts").fetchone()["c"])
        failed_logs = int(
            conn.execute(
                """
                SELECT COUNT(*) AS c FROM operation_log
                WHERE operation_type='marking_artifact_write' AND status='failed'
                """
            ).fetchone()["c"]
        )
        assert artifacts == 0
        assert failed_logs >= 1
    finally:
        conn.close()
