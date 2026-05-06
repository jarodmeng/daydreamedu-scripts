from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
import json

import pytest

from ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3 import (
    aggregate_phase2_section_rows,
    build_phase2_retry_targets,
    build_phase2_section_inputs,
    build_phase3_question_inputs,
    execute_phase2_section_runtime,
    execute_phase3_question_runtime,
    finalize_phase_e_artifact,
    V3_MODE_BOOK_PRACTICE,
    V3_MODE_EMBEDDED_ANSWER,
    V3_MODE_REDO_PRACTICE,
    V3_MODE_TEACHER_ANNOTATED,
    V3ModeSignals,
    V3InputRequest,
    V3WorkflowError,
    build_context_resolution_debug_record,
    prepare_finalize_rows,
    require_template_link_for_v3,
    require_no_user_asset_contradiction,
    resolve_question_sections_authority,
    resolve_attempt_input_to_pdf_file,
    resolve_redo_practice_reference,
    resolve_v3_marking_context,
    resolve_v3_mode,
    write_phase2_execution_trace,
    write_context_resolution_debug_artifact,
    plan_phase2_batches,
    plan_phase3_batches,
)
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
from ai_study_buddy.marking.core.artifact_schema import SCHEMA_VERSION
from ai_study_buddy.marking.core.artifact_writer import write_marking_artifact
from ai_study_buddy.marking.core.marking_time import now_marking_iso
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.marking.file_question_info.errors import QuestionSectionsNotFoundError
from ai_study_buddy.marking.file_question_info.errors import QuestionSectionsValidationError
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
from ai_study_buddy.marking.workflows.v3_helpers import (
    build_authoritative_marks_by_question,
    build_generation_telemetry,
    find_human_note_policy_violations,
    find_language_violations,
    merge_phase2_phase3_rows,
    normalize_outcome,
    reconcile_teacher_tally,
    select_phase3_question_ids,
)


def _question_sections_payload() -> dict:
    return {
        "schema_version": "math-v1.2",
        "created_at": "2026-01-01T00:00:00+08:00",
        "updated_at": "2026-01-01T00:00:00+08:00",
        "input_context": {
            "files": [
                {
                    "path": "/tmp/mock.pdf",
                    "file_id": "11111111-2222-4333-8444-555555555555",
                    "role": "question_booklet",
                    "notes": "",
                }
            ],
            "hints": "",
            "notes": "",
        },
        "debug": {"generation_model": "pytest", "confidence": "high", "notes": ""},
        "sections": [
            {
                "question_type": "SAQ",
                "questions_page_range": {"start_page": 1, "end_page": 2, "start_mid_page": False, "end_mid_page": False},
                "question_info": [
                    {"question_index": "Q1", "question_mark": 2, "start_page": 1},
                    {"question_index": "Q2", "question_mark": 3, "start_page": 2},
                ],
                "debug": {"matched_header_text": "", "matched_instruction_text": "", "notes": ""},
            }
        ],
    }

def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n% mock\n")
    return path


def test_normalize_outcome_legacy_incorrect():
    assert normalize_outcome("incorrect") == "wrong"
    assert normalize_outcome("correct") == "correct"


def test_select_phase3_question_ids_on_low_confidence_and_non_correct():
    rows = [
        {"question_id": "Q1", "outcome": "correct", "confidence": {"grading": "high"}},
        {"question_id": "Q2", "outcome": "wrong", "confidence": {"grading": "high"}},
        {"question_id": "Q3", "outcome": "correct", "confidence": {"grading": "low"}},
    ]
    assert select_phase3_question_ids(rows) == ("Q2", "Q3")


def test_find_language_violations_han_detection():
    rows = [{"question_id": "Q1", "student_answer": "答案", "correct_answer": "x", "diagnosis": {"reasoning": "ok"}}]
    assert find_language_violations(rows, english_required=True) == ("Q1",)
    assert find_language_violations(rows, english_required=False) == ()


def test_find_human_note_policy_violations():
    rows = [{"question_id": "Q1", "human_note": "teacher note", "human_note_source": "none", "human_note_is_verbatim": False}]
    violations = find_human_note_policy_violations(rows)
    assert len(violations) == 2
    assert violations[0]["question_id"] == "Q1"


def test_build_authoritative_marks_by_question():
    marks = build_authoritative_marks_by_question(_question_sections_payload())
    assert marks == {"Q1": 2.0, "Q2": 3.0}


def test_merge_phase2_phase3_rows_uses_authoritative_marks():
    phase2 = [
        {"question_id": "Q1", "outcome": "correct", "earned_marks": 1, "max_marks": 99},
        {"question_id": "Q2", "outcome": "wrong", "earned_marks": 0, "max_marks": 99},
    ]
    phase3 = [{"question_id": "Q2", "outcome": "incorrect", "earned_marks": 2, "max_marks": 7}]
    merged = merge_phase2_phase3_rows(phase2, phase3, authoritative_marks={"Q1": 2.0, "Q2": 3.0})
    assert len(merged.merged_rows) == 2
    assert merged.phase3_applied_question_ids == ("Q2",)
    assert merged.merged_rows[0]["max_marks"] == 2.0
    assert merged.merged_rows[1]["max_marks"] == 3.0
    assert merged.merged_rows[1]["outcome"] == "wrong"


def test_build_generation_telemetry():
    telemetry = build_generation_telemetry(phase2_subagents=3, deep_dive_count=4, total_duration_seconds=8.7)
    assert telemetry["fast_pass_count"] == 3
    assert telemetry["deep_dive_count"] == 4
    assert telemetry["phase2_task_subagents"] is True


def test_reconcile_teacher_tally():
    rows = [{"max_marks": 2, "earned_marks": 1}, {"max_marks": 3, "earned_marks": 3}]
    out = reconcile_teacher_tally(rows, teacher_total_marks=5, teacher_earned_marks=4)
    assert out["computed_total_marks"] == 5.0
    assert out["computed_earned_marks"] == 4.0
    assert out["qc_passed"] is True
    bad = reconcile_teacher_tally(rows, teacher_total_marks=6, teacher_earned_marks=4)
    assert bad["qc_passed"] is False


def test_resolve_v3_mode():
    assert resolve_v3_mode(V3ModeSignals()) == V3_MODE_BOOK_PRACTICE
    assert resolve_v3_mode(V3ModeSignals(embedded_answer_requested=True)) == V3_MODE_EMBEDDED_ANSWER
    assert resolve_v3_mode(V3ModeSignals(redo_practice_requested=True)) == V3_MODE_REDO_PRACTICE
    assert resolve_v3_mode(V3ModeSignals(has_mapped_answer_range=False)) == V3_MODE_TEACHER_ANNOTATED
    with pytest.raises(V3WorkflowError, match="requires linked template"):
        resolve_v3_mode(V3ModeSignals(has_linked_template=False))
    with pytest.raises(V3WorkflowError, match="Ambiguous mode"):
        resolve_v3_mode(V3ModeSignals(redo_practice_requested=True, embedded_answer_requested=True))


def test_require_no_user_asset_contradiction():
    require_no_user_asset_contradiction(has_contradiction=False)
    with pytest.raises(V3WorkflowError, match="contradicts"):
        require_no_user_asset_contradiction(has_contradiction=True)


def test_prepare_finalize_rows_applies_qc():
    payload = _question_sections_payload()
    phase2 = [
        {
            "question_id": "Q1",
            "outcome": "correct",
            "earned_marks": 2,
            "student_answer": "答案",
            "correct_answer": "A",
            "diagnosis": {"reasoning": "ok"},
            "human_note": "teacher note",
            "human_note_source": "none",
            "human_note_is_verbatim": False,
            "confidence": {"grading": "high"},
        }
    ]
    phase3 = []
    result = prepare_finalize_rows(
        question_sections_payload=payload,
        phase2_rows=phase2,
        phase3_rows=phase3,
        english_required=True,
    )
    assert result.phase3_question_ids == ()
    assert result.language_violations == ("Q1",)
    assert len(result.human_note_violations) == 2
    assert result.merged_rows[0]["max_marks"] == 2.0


def test_resolve_attempt_input_registers_path_when_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        mgr = PdfFileManager(db_path=str(base / "registry.db"))
        pdf = _touch(base / "GoodNotes" / "Math" / "_c_sample.pdf")
        out = resolve_attempt_input_to_pdf_file(
            manager=mgr,
            request=V3InputRequest(attempt_file_id_or_path=str(pdf)),
        )
        assert out.path == str(pdf.resolve())
        again = resolve_attempt_input_to_pdf_file(
            manager=mgr,
            request=V3InputRequest(attempt_file_id_or_path=out.id),
        )
        assert again.id == out.id


def test_resolve_attempt_input_student_plus_filename():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        mgr = PdfFileManager(db_path=str(base / "registry.db"))
        mgr.add_student("emma", "Emma", email="emma@example.com")
        pdf = _touch(base / "GoodNotes" / "Math" / "emma@example.com" / "_c_p6.math.wa1.2 (attempt).pdf")
        reg = mgr.register_file(pdf, file_type="main", is_template=False, doc_type="exam", student_id="emma")
        out = resolve_attempt_input_to_pdf_file(
            manager=mgr,
            request=V3InputRequest(student_name="Emma", file_name=reg.name),
        )
        assert out.id == reg.id


def test_resolve_v3_marking_context_from_input_request():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        mgr = PdfFileManager(db_path=str(base / "registry.db"))
        attempt_path = _touch(base / "GoodNotes" / "Math" / "_c_p6.math.wa1.2 (attempt).pdf")
        template_path = _touch(base / "DaydreamEdu" / "Math" / "_c_p6.math.wa1.2.pdf")
        answer_path = _touch(base / "DaydreamEdu" / "Math" / "_c_p6.math.wa1.ans.pdf")

        attempt = mgr.register_file(attempt_path, file_type="main", is_template=False, doc_type="exam")
        template = mgr.register_file(template_path, file_type="main", is_template=True, doc_type="book")
        answer = mgr.register_file(answer_path, file_type="main", is_template=False, doc_type="book")
        mgr.link_to_template(attempt.id, template.id)
        group = mgr.create_file_group("P6 Math WA1", group_type="book")
        mgr.add_to_file_group(group.id, template.id)
        mgr.add_to_file_group(group.id, answer.id)
        mgr.set_book_answer_mapping(
            template.id,
            answer.id,
            answer_page_start=11,
            answer_page_end=13,
            source="unit_mapping",
        )

        context = resolve_v3_marking_context(
            manager=mgr,
            request=V3InputRequest(attempt_file_id_or_path=attempt.id),
        )
        assert context.attempt_file_id == attempt.id
        assert context.template_file_id == template.id
        assert context.answer_file_id == answer.id


def test_write_context_resolution_debug_artifact():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        mgr = PdfFileManager(db_path=str(base / "registry.db"))
        attempt_path = _touch(base / "GoodNotes" / "Math" / "_c_p6.math.wa1.2 (attempt).pdf")
        template_path = _touch(base / "DaydreamEdu" / "Math" / "_c_p6.math.wa1.2.pdf")
        answer_path = _touch(base / "DaydreamEdu" / "Math" / "_c_p6.math.wa1.ans.pdf")
        attempt = mgr.register_file(attempt_path, file_type="main", is_template=False, doc_type="exam")
        template = mgr.register_file(template_path, file_type="main", is_template=True, doc_type="book")
        answer = mgr.register_file(answer_path, file_type="main", is_template=False, doc_type="book")
        mgr.link_to_template(attempt.id, template.id)
        group = mgr.create_file_group("P6 Math WA1", group_type="book")
        mgr.add_to_file_group(group.id, template.id)
        mgr.add_to_file_group(group.id, answer.id)
        mgr.set_book_answer_mapping(template.id, answer.id, answer_page_start=11, answer_page_end=13, source="unit_mapping")

        request = V3InputRequest(attempt_file_id_or_path=attempt.id)
        context = resolve_v3_marking_context(manager=mgr, request=request)
        record = build_context_resolution_debug_record(request=request, context=context)
        out = write_context_resolution_debug_artifact(bundle_root=base / "bundle", record=record)
        assert out.name == "context_resolution_provenance.json"
        text = out.read_text(encoding="utf-8")
        assert "\"attempt_input\"" in text
        assert attempt.id in text


def test_phase_c_template_link_required():
    with pytest.raises(V3WorkflowError, match="requires linked template"):
        require_template_link_for_v3(template_file=None)


def test_phase_c_lookup_reused(monkeypatch):
    payload = _question_sections_payload()

    def _fake_lookup(*, template_file, detect_divergence=True):
        _ = template_file
        _ = detect_divergence
        return {
            "payload": payload,
            "source_kind": "filesystem",
        }

    monkeypatch.setattr(
        "ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3.resolve_question_sections_for_template_file",
        _fake_lookup,
    )
    authority = resolve_question_sections_authority(template_file=object())
    assert authority.source.startswith("lookup:")
    assert len(authority.sections) == 1
    assert len(authority.questions) == 2
    assert "Q1" in authority.question_page_map


def test_phase_c_detector_fallback_in_memory_payload(monkeypatch):
    payload = _question_sections_payload()

    def _fake_lookup(*, template_file, detect_divergence=True):
        _ = template_file
        _ = detect_divergence
        raise QuestionSectionsNotFoundError("not found")

    monkeypatch.setattr(
        "ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3.resolve_question_sections_for_template_file",
        _fake_lookup,
    )
    authority = resolve_question_sections_authority(
        template_file=object(),
        detector_fallback=lambda _tpl: payload,
    )
    assert authority.source == "detector-fallback:in-memory"
    assert len(authority.questions) == 2


def test_phase_c_detector_fallback_missing_and_no_fallback_raises(monkeypatch):
    def _fake_lookup(*, template_file, detect_divergence=True):
        _ = template_file
        _ = detect_divergence
        raise QuestionSectionsNotFoundError("not found")

    monkeypatch.setattr(
        "ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3.resolve_question_sections_for_template_file",
        _fake_lookup,
    )
    with pytest.raises(V3WorkflowError, match="detector fallback orchestration required"):
        resolve_question_sections_authority(template_file=object())


def test_phase_c_detector_fallback_invalid_payload_hard_fails(monkeypatch):
    def _fake_lookup(*, template_file, detect_divergence=True):
        _ = template_file
        _ = detect_divergence
        raise QuestionSectionsNotFoundError("not found")

    monkeypatch.setattr(
        "ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3.resolve_question_sections_for_template_file",
        _fake_lookup,
    )
    bad_payload = {"schema_version": "math-v1.2", "input_context": {"files": []}}
    with pytest.raises(QuestionSectionsValidationError):
        resolve_question_sections_authority(
            template_file=object(),
            detector_fallback=lambda _tpl: bad_payload,
        )


def test_phase_d_build_section_inputs_and_page_filtering(monkeypatch):
    payload = _question_sections_payload()

    def _fake_lookup(*, template_file, detect_divergence=True):
        _ = template_file
        _ = detect_divergence
        raise QuestionSectionsNotFoundError("not found")

    monkeypatch.setattr(
        "ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3.resolve_question_sections_for_template_file",
        _fake_lookup,
    )
    authority = resolve_question_sections_authority(
        template_file=object(),
        detector_fallback=lambda _tpl: payload,
    )
    section_inputs = build_phase2_section_inputs(authority)
    assert len(section_inputs) == 1
    s0 = section_inputs[0]
    assert s0.question_ids == ("Q1", "Q2")
    # only section-scoped ranges included
    assert s0.page_numbers == (1, 2)


def test_phase_d_plan_batches_concurrency_cap(monkeypatch):
    payload = _question_sections_payload()
    payload["sections"] = [
        {
            "question_type": "SAQ",
            "questions_page_range": {"start_page": 1, "end_page": 1, "start_mid_page": False, "end_mid_page": False},
            "question_info": [{"question_index": "Q1", "question_mark": 1, "start_page": 1}],
            "debug": {"matched_header_text": "", "matched_instruction_text": "", "notes": ""},
        },
        {
            "question_type": "SAQ",
            "questions_page_range": {"start_page": 2, "end_page": 2, "start_mid_page": False, "end_mid_page": False},
            "question_info": [{"question_index": "Q2", "question_mark": 1, "start_page": 2}],
            "debug": {"matched_header_text": "", "matched_instruction_text": "", "notes": ""},
        },
        {
            "question_type": "SAQ",
            "questions_page_range": {"start_page": 3, "end_page": 3, "start_mid_page": False, "end_mid_page": False},
            "question_info": [{"question_index": "Q3", "question_mark": 1, "start_page": 3}],
            "debug": {"matched_header_text": "", "matched_instruction_text": "", "notes": ""},
        },
    ]
    def _fake_lookup(*, template_file, detect_divergence=True):
        _ = template_file
        _ = detect_divergence
        raise QuestionSectionsNotFoundError("not found")

    monkeypatch.setattr(
        "ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3.resolve_question_sections_for_template_file",
        _fake_lookup,
    )
    authority = resolve_question_sections_authority(template_file=object(), detector_fallback=lambda _tpl: payload)
    section_inputs = build_phase2_section_inputs(authority)
    batches = plan_phase2_batches(section_inputs, max_concurrency=2)
    assert len(batches) == 2
    assert len(batches[0]) == 2
    assert len(batches[1]) == 1


def test_phase_d_aggregate_rows_order_and_section_guard(monkeypatch):
    def _fake_lookup(*, template_file, detect_divergence=True):
        _ = template_file
        _ = detect_divergence
        raise QuestionSectionsNotFoundError("not found")

    monkeypatch.setattr(
        "ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3.resolve_question_sections_for_template_file",
        _fake_lookup,
    )
    authority = resolve_question_sections_authority(template_file=object(), detector_fallback=lambda _tpl: _question_sections_payload())
    # out of order input rows by section should still return authority order Q1,Q2
    section_rows = {
        0: [
            {"question_id": "Q2", "outcome": "wrong"},
            {"question_id": "Q1", "outcome": "correct"},
        ]
    }
    out = aggregate_phase2_section_rows(section_rows, authority=authority)
    assert [r["question_id"] for r in out] == ["Q1", "Q2"]

    with pytest.raises(V3WorkflowError, match="out-of-section"):
        aggregate_phase2_section_rows({1: [{"question_id": "Q1"}]}, authority=authority)


def test_phase_d_build_retry_targets_from_qc():
    rows = [
        {
            "question_id": "Q1",
            "student_answer": "答案",
            "correct_answer": "A",
            "diagnosis": {"reasoning": "ok"},
            "human_note": None,
            "human_note_source": "none",
        },
        {
            "question_id": "Q2",
            "student_answer": "A",
            "correct_answer": "A",
            "diagnosis": {"reasoning": "ok"},
            "human_note": "teacher note",
            "human_note_source": "none",
            "human_note_is_verbatim": False,
        },
    ]
    targets = build_phase2_retry_targets(rows, english_required=True)
    assert targets == ("Q1", "Q2")


def test_phase_d_runtime_execution_success_and_trace(monkeypatch, tmp_path):
    payload = _question_sections_payload()

    def _fake_lookup(*, template_file, detect_divergence=True):
        _ = template_file
        _ = detect_divergence
        raise QuestionSectionsNotFoundError("not found")

    monkeypatch.setattr(
        "ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3.resolve_question_sections_for_template_file",
        _fake_lookup,
    )
    authority = resolve_question_sections_authority(template_file=object(), detector_fallback=lambda _tpl: payload)
    section_inputs = build_phase2_section_inputs(authority)

    def _worker(section_input):
        return [
            {
                "question_id": qid,
                "outcome": "correct",
                "student_answer": "A",
                "correct_answer": "A",
                "diagnosis": {"reasoning": "ok"},
                "human_note": None,
                "human_note_source": "none",
            }
            for qid in section_input.question_ids
        ]

    summary = execute_phase2_section_runtime(
        section_inputs=section_inputs,
        authority=authority,
        worker=_worker,
        bundle_root=tmp_path / "bundle",
        english_required=True,
        max_concurrency=5,
        max_retries=1,
    )
    assert len(summary.aggregated_rows) == 2
    assert summary.retry_targets == ()
    assert summary.trace_path.is_file()


def test_phase_d_runtime_retries_failed_section_then_succeeds(monkeypatch, tmp_path):
    payload = _question_sections_payload()

    def _fake_lookup(*, template_file, detect_divergence=True):
        _ = template_file
        _ = detect_divergence
        raise QuestionSectionsNotFoundError("not found")

    monkeypatch.setattr(
        "ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3.resolve_question_sections_for_template_file",
        _fake_lookup,
    )
    authority = resolve_question_sections_authority(template_file=object(), detector_fallback=lambda _tpl: payload)
    section_inputs = build_phase2_section_inputs(authority)
    calls = {"count": 0}

    def _worker(section_input):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient failure")
        return [{"question_id": qid, "outcome": "correct"} for qid in section_input.question_ids]

    summary = execute_phase2_section_runtime(
        section_inputs=section_inputs,
        authority=authority,
        worker=_worker,
        bundle_root=tmp_path / "bundle",
        english_required=False,
        max_retries=1,
    )
    assert calls["count"] == 2
    assert summary.section_results[0].attempts == 2


def test_phase_d_runtime_raises_after_retry_exhaustion(monkeypatch, tmp_path):
    payload = _question_sections_payload()

    def _fake_lookup(*, template_file, detect_divergence=True):
        _ = template_file
        _ = detect_divergence
        raise QuestionSectionsNotFoundError("not found")

    monkeypatch.setattr(
        "ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3.resolve_question_sections_for_template_file",
        _fake_lookup,
    )
    authority = resolve_question_sections_authority(template_file=object(), detector_fallback=lambda _tpl: payload)
    section_inputs = build_phase2_section_inputs(authority)

    def _worker(_section_input):
        raise RuntimeError("persistent failure")

    with pytest.raises(V3WorkflowError, match="failed after retries"):
        execute_phase2_section_runtime(
            section_inputs=section_inputs,
            authority=authority,
            worker=_worker,
            bundle_root=tmp_path / "bundle",
            english_required=False,
            max_retries=1,
        )


def _build_context_with_mapping(tmp_path: Path):
    mgr = PdfFileManager(db_path=str(tmp_path / "registry.db"))
    attempt_path = _touch(tmp_path / "GoodNotes" / "Math" / "_c_p6.math.wa1.2 (attempt).pdf")
    template_path = _touch(tmp_path / "DaydreamEdu" / "Math" / "_c_p6.math.wa1.2.pdf")
    answer_path = _touch(tmp_path / "DaydreamEdu" / "Math" / "_c_p6.math.wa1.ans.pdf")
    attempt = mgr.register_file(attempt_path, file_type="main", is_template=False, doc_type="exam")
    template = mgr.register_file(template_path, file_type="main", is_template=True, doc_type="book")
    answer = mgr.register_file(answer_path, file_type="main", is_template=False, doc_type="book")
    mgr.link_to_template(attempt.id, template.id)
    group = mgr.create_file_group("P6 Math WA1", group_type="book")
    mgr.add_to_file_group(group.id, template.id)
    mgr.add_to_file_group(group.id, answer.id)
    mgr.set_book_answer_mapping(template.id, answer.id, answer_page_start=11, answer_page_end=13, source="unit_mapping")
    context = resolve_v3_marking_context(manager=mgr, request=V3InputRequest(attempt_file_id_or_path=attempt.id))
    return mgr, context


def test_phase_e_runtime_and_finalize(monkeypatch, tmp_path):
    payload = _question_sections_payload()

    def _fake_lookup(*, template_file, detect_divergence=True):
        _ = template_file
        _ = detect_divergence
        raise QuestionSectionsNotFoundError("not found")

    monkeypatch.setattr(
        "ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3.resolve_question_sections_for_template_file",
        _fake_lookup,
    )
    authority = resolve_question_sections_authority(template_file=object(), detector_fallback=lambda _tpl: payload)
    phase2_rows = [
        {"question_id": "Q1", "outcome": "wrong", "confidence": {"grading": "low"}, "earned_marks": 0, "max_marks": 2},
        {"question_id": "Q2", "outcome": "correct", "confidence": {"grading": "high"}, "earned_marks": 3, "max_marks": 3},
    ]
    qinputs = build_phase3_question_inputs(authority=authority, phase2_rows=phase2_rows)
    assert len(qinputs) == 1
    batches = plan_phase3_batches(qinputs, max_concurrency=5)
    assert len(batches) == 1

    def _worker(qinput):
        return {
            "question_id": qinput.question_id,
            "outcome": "partial",
            "earned_marks": 1,
            "student_answer": "A",
            "correct_answer": "B",
            "diagnosis": {"reasoning": "fix"},
            "human_note": None,
        }

    p3 = execute_phase3_question_runtime(
        question_inputs=qinputs,
        worker=_worker,
        bundle_root=tmp_path / "bundle",
        max_retries=1,
    )
    assert len(p3.remediated_rows) == 1
    assert p3.trace_path.is_file()

    _, context = _build_context_with_mapping(tmp_path / "ctx")
    merged_rows = [
        {
            "question_id": "Q1",
            "result_id": "Q1",
            "outcome": "partial",
            "earned_marks": 1,
            "max_marks": 2,
            "student_answer": "A",
            "correct_answer": "B",
            "diagnosis": {"reasoning": "fix", "mistake_type": None, "confidence": "low"},
            "attempt_page_start": 1,
        },
        {
            "question_id": "Q2",
            "result_id": "Q2",
            "outcome": "correct",
            "earned_marks": 3,
            "max_marks": 3,
            "student_answer": "C",
            "correct_answer": "C",
            "diagnosis": {"reasoning": "ok", "mistake_type": None, "confidence": "high"},
            "attempt_page_start": 2,
        },
    ]
    out = finalize_phase_e_artifact(
        context=context,
        merged_rows=merged_rows,
        mode="book-practice",
        bundle_root=tmp_path / "bundle",
        context_root=tmp_path / "context",
        deep_dive_count=1,
        phase2_subagents=1,
    )
    assert out.artifact_path.is_file()
    assert out.debug_trace_path.is_file()


def test_phase_e_finalize_infers_subject_context_from_context_path(tmp_path):
    _, context = _build_context_with_mapping(tmp_path / "ctx_science")
    context = replace(
        context,
        attempt_file_path=str(Path(context.attempt_file_path).with_name("_c_p6.science.wa1.2 (attempt).pdf")),
    )
    merged_rows = [
        {
            "question_id": "Q1",
            "result_id": "Q1",
            "outcome": "correct",
            "earned_marks": 1,
            "max_marks": 1,
            "student_answer": "A",
            "correct_answer": "A",
            "diagnosis": {"reasoning": None, "mistake_type": None, "confidence": "high"},
            "attempt_page_start": 1,
        }
    ]
    out = finalize_phase_e_artifact(
        context=context,
        merged_rows=merged_rows,
        mode="book-practice",
        bundle_root=tmp_path / "bundle",
        context_root=tmp_path / "context",
        deep_dive_count=0,
        phase2_subagents=1,
    )
    payload = json.loads(out.artifact_path.read_text(encoding="utf-8"))
    assert payload["context"]["subject_context"] == "singapore_primary_science"


def test_phase_e_runtime_retry_exhaustion_raises(monkeypatch, tmp_path):
    payload = _question_sections_payload()

    def _fake_lookup(*, template_file, detect_divergence=True):
        _ = template_file
        _ = detect_divergence
        raise QuestionSectionsNotFoundError("not found")

    monkeypatch.setattr(
        "ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3.resolve_question_sections_for_template_file",
        _fake_lookup,
    )
    authority = resolve_question_sections_authority(template_file=object(), detector_fallback=lambda _tpl: payload)
    phase2_rows = [{"question_id": "Q1", "outcome": "wrong", "confidence": {"grading": "low"}}]
    qinputs = build_phase3_question_inputs(authority=authority, phase2_rows=phase2_rows)

    def _worker(_qinput):
        raise RuntimeError("boom")

    with pytest.raises(V3WorkflowError, match="Phase 3 runtime failed after retries"):
        execute_phase3_question_runtime(
            question_inputs=qinputs,
            worker=_worker,
            bundle_root=tmp_path / "bundle",
            max_retries=1,
        )


def _mk_artifact(*, context, created_at: str, run_mode: str, earned: float) -> MarkingArtifact:
    artifact_context = MarkingArtifactContext.from_marking_context(
        context,
        subject_context="singapore_primary_math",
        resolved_at=created_at,
    )
    return MarkingArtifact(
        schema_version=SCHEMA_VERSION,
        created_at=created_at,
        updated_at=created_at,
        context=artifact_context,
        summary=ArtifactSummary(
            total_marks=2,
            earned_marks=earned,
            percentage=100.0 if earned >= 2 else 50.0,
            overall_assessment="ok",
            human_note=None,
        ),
        question_results=(
            ArtifactQuestionResult(
                result_id="Q1",
                max_marks=2,
                earned_marks=earned,
                outcome="correct" if earned >= 2 else "partial",
                student_answer="A",
                correct_answer="A",
                scoring_status="counted",
                error_tags=(),
                skill_tags=(),
                diagnosis=Diagnosis(mistake_type=None, reasoning=None, confidence=None),
                human_note=None,
            ),
        ),
        review_meta=ReviewMeta(updated_at=created_at, updated_by="pytest"),
        generation=GenerationMeta(produced_by="pytest", mode=run_mode, notes=None, telemetry=None),
    )


def test_resolve_redo_practice_reference_uses_first_marking_result_and_loads_amendment():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        context_root = (base / "context").resolve()
        mgr = PdfFileManager(db_path=str(base / "registry.db"))
        attempt_path = _touch(base / "GoodNotes" / "Math" / "emma@example.com" / "_c_p6.math.wa1.2 (attempt).pdf")
        template_path = _touch(base / "DaydreamEdu" / "Math" / "_c_p6.math.wa1.2.pdf")
        answer_path = _touch(base / "DaydreamEdu" / "Math" / "_c_p6.math.wa1.ans.pdf")

        mgr.add_student("emma", "Emma", email="emma@example.com")
        attempt = mgr.register_file(attempt_path, file_type="main", is_template=False, doc_type="exam", student_id="emma")
        template = mgr.register_file(template_path, file_type="main", is_template=True, doc_type="book")
        answer = mgr.register_file(answer_path, file_type="main", is_template=False, doc_type="book")
        mgr.link_to_template(attempt.id, template.id)
        group = mgr.create_file_group("P6 Math WA1", group_type="book")
        mgr.add_to_file_group(group.id, template.id)
        mgr.add_to_file_group(group.id, answer.id)
        mgr.set_book_answer_mapping(template.id, answer.id, answer_page_start=11, answer_page_end=13, source="unit_mapping")

        ctx = resolve_v3_marking_context(
            manager=mgr,
            request=V3InputRequest(attempt_file_id_or_path=attempt.id),
        )
        t1 = now_marking_iso()
        first_artifact = _mk_artifact(context=ctx, created_at=t1, run_mode="book-practice", earned=1)
        first_path = write_marking_artifact(first_artifact, context_root=context_root)

        t2 = now_marking_iso()
        second_artifact = _mk_artifact(context=ctx, created_at=t2, run_mode="book-practice", earned=2)
        write_marking_artifact(second_artifact, context_root=context_root)

        repo = StudentReviewRepository(context_root=context_root)
        repo.save_amendment(
            student_id="emma",
            subject_context="singapore_primary_math",
            artifact_stem=Path(first_path).stem,
            payload={"schema_version": "marking_amendment.v1", "question_overrides": []},
        )

        ref = resolve_redo_practice_reference(
            manager=mgr,
            attempt_file_id_or_path=attempt.id,
            context_root=context_root,
        )
        assert Path(ref.marking_result_path).stem == Path(first_path).stem
        assert ref.amendment_payload is not None
        assert ref.amendment_payload.get("schema_version") == "marking_amendment.v1"
