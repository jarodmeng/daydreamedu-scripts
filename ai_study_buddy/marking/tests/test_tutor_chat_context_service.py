from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_study_buddy.marking.review import api_routes
import ai_study_buddy.marking.review.tutor_chat_context_service as tutor_chat_context_service
from ai_study_buddy.marking.review.tutor_chat_context_service import (
    build_context_bundle_from_detail,
    format_labeled_review_notes,
    load_pedagogy_refs,
    render_context_bundle_prompt,
)
from ai_study_buddy.marking.review.tutor_chat_stale import (
    build_context_snapshot,
    compute_stale_context,
    fingerprint_resolved_question_row,
)
from ai_study_buddy.review_workspace.backend import app as review_workspace_backend


def _detail_fixture() -> dict:
    return {
        "attempt": {
            "attempt_id": "attempt-1",
            "student_id": "emma",
            "title": "Science WA",
            "subject_context": "singapore_primary_science",
            "book_label": "Book A",
            "collection_kind": "book",
        },
        "marking_status": "marked",
        "marking_result": {
            "artifact_path": "marking_results/emma/singapore_primary_science/sample.json",
            "context": {"unit_label": "Unit 1", "is_partial": False},
            "summary": {
                "earned_marks": 3,
                "total_marks": 4,
                "percentage": 75.0,
                "overall_assessment": "ok",
                "human_note": None,
            },
            "question_results": [
                {
                    "result_id": "Q1",
                    "outcome": "correct",
                    "earned_marks": 2,
                    "max_marks": 2,
                    "student_answer": "roots",
                    "correct_answer": "roots",
                    "skill_tags": ["plants"],
                    "diagnosis": {},
                    "human_note": "Good.",
                    "attempt_page_start": 1,
                },
                {
                    "result_id": "Q2",
                    "outcome": "partial",
                    "earned_marks": 1,
                    "max_marks": 2,
                    "student_answer": "stem",
                    "correct_answer": "stem and leaves",
                    "skill_tags": ["plants"],
                    "diagnosis": {"mistake_type": "incomplete", "reasoning": "Missing leaves."},
                    "human_note": None,
                    "attempt_page_start": 2,
                },
            ],
        },
        "amendment_state": {
            "review_meta": {"updated_at": "2026-06-01T00:00:00Z", "updated_by": "parent"},
            "question_amendments": [
                {
                    "result_id": "Q2",
                    "fields": {"outcome": "wrong"},
                    "reviewer_reason": "Checked script.",
                }
            ],
        },
        "review_state": {
            "review_status": "in_progress",
            "question_reviews": [
                {
                    "result_id": "Q2",
                    "review_status": "reviewed",
                    "note_text": "[misreading] misread the diagram",
                    "author_role": "student",
                    "updated_at": "2026-06-02T10:00:00Z",
                },
                {
                    "result_id": "Q1",
                    "review_status": "not_reviewed",
                    "note_text": "",
                },
            ],
            "attempt_notes": [{"note_text": "Need more practice on diagrams", "author_role": "student"}],
            "student_subject_notes": [{"note_text": "Science is improving", "author_role": "student"}],
        },
        "viewer": {
            "marking_asset": "marking_assets/emma/singapore_primary_science/sample",
            "attempt_images": [
                {"name": "page-01.png", "page_num": 1, "url": "/review-workspace-static/marking_assets/emma/singapore_primary_science/sample/attempt/page-01.png"},
                {"name": "page-02.png", "page_num": 2, "url": "/review-workspace-static/marking_assets/emma/singapore_primary_science/sample/attempt/page-02.png"},
            ],
        },
    }


def test_fingerprint_changes_when_resolved_row_changes():
    row = {"result_id": "Q1", "outcome": "correct", "earned_marks": 2}
    first = fingerprint_resolved_question_row(row)
    row["outcome"] = "wrong"
    second = fingerprint_resolved_question_row(row)
    assert first != second


def test_stale_context_detects_amendment_and_review_drift():
    snapshot = build_context_snapshot(
        marking_result_path="marking_results/emma/singapore_primary_science/sample.json",
        amendment_state={"review_meta": {"updated_at": "2026-06-01T00:00:00Z"}},
        review_state_updated_at="2026-06-02T10:00:00Z",
        resolved_question_row={"result_id": "Q2", "outcome": "partial"},
    )
    live = build_context_snapshot(
        marking_result_path="marking_results/emma/singapore_primary_science/sample.json",
        amendment_state={"review_meta": {"updated_at": "2026-06-03T00:00:00Z"}},
        review_state_updated_at="2026-06-02T10:00:00Z",
        resolved_question_row={"result_id": "Q2", "outcome": "partial"},
    )
    stale = compute_stale_context(snapshot=snapshot, live_snapshot=live)
    assert stale == {"marking": True, "review_notes": False}

    live_review = {**live, "review_state_updated_at": "2026-06-04T00:00:00Z"}
    stale = compute_stale_context(snapshot=snapshot, live_snapshot=live_review)
    assert stale == {"marking": True, "review_notes": True}


def test_format_labeled_review_notes_orders_active_question_first():
    detail = _detail_fixture()
    blocks = format_labeled_review_notes(
        detail["review_state"],
        active_result_id="Q2",
        subject_context="singapore_primary_science",
    )
    assert blocks[0].startswith("[QUESTION — Q2]")
    assert any(block.startswith("[QUESTION — Q1]") for block in blocks) is False
    assert any(block.startswith("[ATTEMPT]") for block in blocks)
    assert any(block.startswith("[STUDENT_SUBJECT — singapore_primary_science]") for block in blocks)
    assert "[misreading]" in blocks[0]


def test_build_context_bundle_from_detail_includes_amendments_and_snapshot(tmp_path: Path):
  # create page png for resolver
    page_dir = tmp_path / "marking_assets/emma/singapore_primary_science/sample/attempt"
    page_dir.mkdir(parents=True)
    (page_dir / "page-02.png").write_bytes(b"png")

    detail = _detail_fixture()
    bundle = build_context_bundle_from_detail(
        detail=detail,
        result_id="Q2",
        context_root=tmp_path,
        review_state_updated_at="2026-06-02T10:00:00Z",
    )

    assert bundle["result_id"] == "Q2"
    assert bundle["question"]["result_id"] == "Q2"
    assert bundle["amendments"]["result_id"] == "Q2"
    assert bundle["page"]["page_num"] == 2
    assert bundle["page"]["absolute_path"] is not None
    assert bundle["context_snapshot"]["review_state_updated_at"] == "2026-06-02T10:00:00Z"
    assert "resolved_question_fingerprint" in bundle["context_snapshot"]
    assert "[QUESTION — Q2]" in bundle["review_notes_labeled"][0]
    prompt = bundle["prompt_text"]
    assert "Socratic tutor" in prompt
    assert "Base marking (AI grader output — challengeable)" in prompt
    assert "Human amendments (authoritative overrides)" in prompt
    assert "may be wrong" in prompt
    assert "Active question (resolved marking)" not in prompt


def test_render_context_bundle_prompt_without_amendments_omits_human_override_section():
    bundle = {
        "attempt_meta": {"student_id": "emma"},
        "question": {"result_id": "Q1", "outcome": "wrong"},
        "amendments": None,
        "review_notes_labeled": [],
        "attempt_summary": None,
    }
    prompt = render_context_bundle_prompt(bundle)
    assert "Base marking (AI grader output — challengeable)" in prompt
    assert "Human amendments (authoritative overrides)" not in prompt
    assert "inconsistent, incomplete, or mistaken" in prompt


def test_load_pedagogy_refs_truncates_large_files(tmp_path: Path):
    rel = Path("subject_understandings/singapore_primary_science/skill_understanding.md")
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text("x" * 9000, encoding="utf-8")

    refs = load_pedagogy_refs(context_root=tmp_path, subject_context="singapore_primary_science")
    assert len(refs) == 1
    assert refs[0]["truncated"] is True
    assert len(refs[0]["text"]) == 8000


def test_context_preview_route_is_hidden_without_debug_flag(monkeypatch):
    monkeypatch.delenv("BUDDY_CONSOLE_TUTOR_CHAT_DEBUG", raising=False)
    client = TestClient(review_workspace_backend.app)
    response = client.get("/api/student/attempts/attempt-1/questions/Q1/tutor-chat/context-preview")
    assert response.status_code == 404


def test_context_preview_route_returns_bundle_when_debug_enabled(monkeypatch):
    monkeypatch.setenv("BUDDY_CONSOLE_TUTOR_CHAT_DEBUG", "1")

    detail = _detail_fixture()

    class _FakeManager:
        def get_file(self, file_id: str):
            return object()

    def _fake_get_attempt_detail(**kwargs):
        return detail

    monkeypatch.setattr(tutor_chat_context_service, "get_attempt_detail", _fake_get_attempt_detail)
    monkeypatch.setattr(api_routes, "_manager", lambda: _FakeManager())

    class _FakeRepo:
        def load_raw_review_state(self, **kwargs):
            return {"updated_at": "2026-06-02T10:00:00Z"}

    monkeypatch.setattr(api_routes, "_repo", lambda: _FakeRepo())
    monkeypatch.setattr(api_routes, "CONTEXT_ROOT", Path("/tmp/context"))

    client = TestClient(review_workspace_backend.app)
    response = client.get("/api/student/attempts/attempt-1/questions/Q2/tutor-chat/context-preview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["result_id"] == "Q2"
    assert payload["context_snapshot"]["marking_result_path"].endswith("sample.json")
    assert render_context_bundle_prompt(payload) == payload["prompt_text"]
