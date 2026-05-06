from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_study_buddy.review_workspace.backend import app as review_workspace_app
from ai_study_buddy.marking.review import api_routes
from ai_study_buddy.marking.review.amendment_service import (
    AmendmentValidationError,
    build_amendment_context,
    merge_panel_amendment,
    normalize_amendment_state,
    resolve_marking_result,
)
from ai_study_buddy.marking.review.attempt_service import list_attempts_for_student
from ai_study_buddy.marking.review.detail_service import get_attempt_detail
from ai_study_buddy.marking.review.repository import StudentReviewRepository


_ONE_BY_ONE_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
    b"\x0d\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _FakeStudent:
    id = "emma"
    name = "Emma"
    email = None


class _FakeFile:
    id = "attempt-1"
    name = "attempt.pdf"
    normal_name = "attempt"
    path = "/tmp/attempt.pdf"
    file_type = "main"
    doc_type = "book"
    student_id = "emma"
    subject = "science"
    is_template = False
    updated_at = "2026-04-24T12:00:00Z"
    added_at = "2026-04-24T12:00:00Z"


class _FakeManager:
    def get_file(self, file_id: str):
        return _FakeFile() if file_id == "attempt-1" else None

    def get_student(self, student_id: str):
        return _FakeStudent() if student_id == "emma" else None

    def find_files(self, **kwargs):
        return [_FakeFile()] if kwargs.get("student_id") == "emma" else []


def _base_payload() -> dict:
    return {
        "schema_version": "marking_result.v1.5",
        "created_at": "2026-04-24T12:00:00+08:00",
        "updated_at": "2026-04-24T12:00:00+08:00",
        "context": {
            "student_id": "emma",
            "subject_context": "singapore_primary_science",
            "attempt_file_id": "attempt-1",
            "marking_asset": "marking_assets/emma/singapore_primary_science/sample",
            "question_page_map": [
                {
                    "result_id": "Q1",
                    "attempt_page_start": 1,
                    "confidence": "medium",
                    "source": "manual_visual",
                    "evidence_image": "attempt/page-01.png",
                    "note": None,
                },
                {
                    "result_id": "Q2",
                    "attempt_page_start": 2,
                    "confidence": "medium",
                    "source": "manual_visual",
                    "evidence_image": "attempt/page-02.png",
                    "note": None,
                },
            ],
        },
        "summary": {
            "total_marks": 4,
            "earned_marks": 3,
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
                "human_note": "Correct.",
                "skill_tags": ["plants"],
                "diagnosis": {"mistake_type": None, "reasoning": None},
            },
            {
                "result_id": "Q2",
                "outcome": "partial",
                "earned_marks": 1,
                "max_marks": 2,
                "student_answer": "stem",
                "correct_answer": "stem and leaves",
                "human_note": "Incomplete.",
                "skill_tags": ["plants"],
                "diagnosis": {"mistake_type": "incomplete", "reasoning": "Missing leaves."},
            },
        ],
        "review_meta": {"updated_by": None, "updated_at": None},
        "generation": {"produced_by": "test"},
    }


def _context(payload: dict) -> dict:
    return build_amendment_context(
        base_payload=payload,
        attempt_id="attempt-1",
        marking_result_path="marking_results/emma/singapore_primary_science/sample.json",
        fallback_student_id="emma",
    )


def test_valid_amendment_overlay_merges_and_recomputes_totals():
    base = _base_payload()
    amendment = normalize_amendment_state(
        {
            "question_amendments": [
                {
                    "result_id": "Q2",
                    "fields": {
                        "earned_marks": 2,
                        "outcome": "correct",
                        "human_note": "Now checked against evidence.",
                    },
                    "reviewer_reason": "AI under-awarded Q2.",
                }
            ],
            "question_page_map_amendments": [
                {"result_id": "Q2", "attempt_page_start": 1, "confidence": "high"}
            ],
        },
        context=_context(base),
    )

    resolved = resolve_marking_result(
        base_payload=base,
        amendment_state=amendment,
        valid_attempt_pages={1, 2},
    )

    q2 = resolved["question_results"][1]
    assert q2["earned_marks"] == 2
    assert q2["outcome"] == "correct"
    assert q2["human_note"] == "Now checked against evidence."
    assert resolved["summary"]["earned_marks"] == 4
    assert resolved["summary"]["total_marks"] == 4
    assert resolved["summary"]["percentage"] == 100.0
    assert resolved["context"]["question_page_map"][1]["attempt_page_start"] == 1


def test_invalid_result_id_amendment_is_rejected():
    base = _base_payload()
    amendment = normalize_amendment_state(
        {
            "question_amendments": [
                {
                    "result_id": "Q999",
                    "fields": {"earned_marks": 1},
                    "reviewer_reason": "Typo.",
                }
            ]
        },
        context=_context(base),
    )

    with pytest.raises(AmendmentValidationError) as exc:
        resolve_marking_result(base_payload=base, amendment_state=amendment)

    assert exc.value.errors[0]["field"] == "result_id"


def test_invalid_earned_marks_is_rejected():
    base = _base_payload()
    amendment = normalize_amendment_state(
        {
            "question_amendments": [
                {
                    "result_id": "Q2",
                    "fields": {"earned_marks": 3},
                    "reviewer_reason": "Too many marks.",
                }
            ]
        },
        context=_context(base),
    )

    with pytest.raises(AmendmentValidationError) as exc:
        resolve_marking_result(base_payload=base, amendment_state=amendment)

    assert any(error["field"] == "question_amendments.Q2.earned_marks" for error in exc.value.errors)


def test_invalid_page_map_amendment_is_rejected():
    base = _base_payload()
    amendment = normalize_amendment_state(
        {"question_page_map_amendments": [{"result_id": "Q2", "attempt_page_start": 99}]},
        context=_context(base),
    )

    with pytest.raises(AmendmentValidationError) as exc:
        resolve_marking_result(
            base_payload=base,
            amendment_state=amendment,
            valid_attempt_pages={1, 2},
        )

    assert any(error["field"] == "question_page_map.Q2.attempt_page_start" for error in exc.value.errors)


def test_panel_save_merges_fields_for_same_question():
    base = _base_payload()
    existing = normalize_amendment_state(
        {
            "question_amendments": [
                {
                    "result_id": "Q2",
                    "fields": {"human_note": "Checked."},
                }
            ]
        },
        context=_context(base),
    )

    merged = merge_panel_amendment(
        existing_state=existing,
        body={
            "updated_by": "review_workspace_ui",
            "question_amendments": [
                {
                    "result_id": "Q2",
                    "fields": {"earned_marks": 2, "outcome": "correct"},
                    "reviewer_reason": "Evidence supports full credit.",
                }
            ],
        },
        base_payload=base,
        context=_context(base),
        valid_attempt_pages={1, 2},
    )

    fields = merged["question_amendments"][0]["fields"]
    assert fields["human_note"] == "Checked."
    assert fields["earned_marks"] == 2
    assert fields["outcome"] == "correct"


def test_amendment_api_saves_overlay_and_returns_resolved_payload(tmp_path, monkeypatch):
    # This test uses filesystem-backed artifacts under tmp_path; ensure we don't
    # force DB reads (which would require a populated study_buddy.db).
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    base = _base_payload()
    asset_root = tmp_path / "marking_assets" / "emma" / "singapore_primary_science" / "sample" / "attempt"
    asset_root.mkdir(parents=True)
    (asset_root / "page-01.png").write_bytes(_ONE_BY_ONE_PNG)
    (asset_root / "page-02.png").write_bytes(_ONE_BY_ONE_PNG)
    artifact_path = tmp_path / "marking_results" / "emma" / "singapore_primary_science" / "sample.json"
    artifact_path.parent.mkdir(parents=True)
    import json

    artifact_path.write_text(json.dumps(base), encoding="utf-8")

    monkeypatch.setattr(api_routes, "CONTEXT_ROOT", tmp_path)
    monkeypatch.setattr(api_routes, "_manager", lambda: _FakeManager())
    client = TestClient(review_workspace_app.app)

    response = client.put(
        "/api/student/attempts/attempt-1/amendments",
        json={
            "updated_by": "review_workspace_ui",
            "question_amendments": [
                {
                    "result_id": "Q2",
                    "fields": {"earned_marks": 2, "outcome": "correct"},
                    "reviewer_reason": "Evidence supports full credit.",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["marking_result_resolved"]["summary"]["earned_marks"] == 4
    assert payload["marking_result_base"]["summary"]["earned_marks"] == 3
    saved_path = tmp_path / payload["saved_path"]
    assert saved_path.exists()


def test_my_work_attempt_list_uses_amended_score(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    base = _base_payload()
    artifact_path = tmp_path / "marking_results" / "emma" / "singapore_primary_science" / "sample.json"
    artifact_path.parent.mkdir(parents=True)
    import json

    artifact_path.write_text(json.dumps(base), encoding="utf-8")

    amendment = normalize_amendment_state(
        {
            "question_amendments": [
                {
                    "result_id": "Q2",
                    "fields": {"earned_marks": 2, "outcome": "correct"},
                    "reviewer_reason": "Evidence supports full credit.",
                }
            ]
        },
        context=_context(base),
    )
    amendment_path = tmp_path / "marking_amendments" / "emma" / "singapore_primary_science" / "sample.json"
    amendment_path.parent.mkdir(parents=True)
    amendment_path.write_text(json.dumps(amendment), encoding="utf-8")

    items = list_attempts_for_student(
        student_id="emma",
        context_root=tmp_path,
        manager=_FakeManager(),
        review_repo=StudentReviewRepository(context_root=tmp_path),
    )

    assert items[0]["score"] == {"earned_marks": 4, "total_marks": 4, "percentage": 100.0}


def test_review_workspace_reads_marking_result_payload_from_db_when_enabled(tmp_path, monkeypatch):
    stale_file_payload = _base_payload()
    db_payload = _base_payload()
    db_payload["summary"] = {
        **db_payload["summary"],
        "earned_marks": 4,
        "total_marks": 4,
        "percentage": 100.0,
    }
    db_payload["question_results"][1] = {
        **db_payload["question_results"][1],
        "earned_marks": 2,
        "outcome": "correct",
    }

    artifact_rel = "marking_results/emma/singapore_primary_science/sample.json"
    artifact_path = tmp_path / artifact_rel
    artifact_path.parent.mkdir(parents=True)
    import json

    artifact_path.write_text(json.dumps(stale_file_payload), encoding="utf-8")

    db_path = tmp_path / "study_buddy.db"
    conn = sqlite3.connect(db_path)
    migration = Path("ai_study_buddy/learning_db/migrations/001_initial_schema.sql")
    conn.executescript(migration.read_text(encoding="utf-8"))
    conn.execute(
        """
        INSERT INTO marking_artifacts(
            artifact_id, schema_version, artifact_path, artifact_stem, source_content_hash,
            created_at, updated_at, student_id, student_name, subject_context, attempt_file_id,
            attempt_file_path, marking_asset, summary_total_marks, summary_earned_marks,
            summary_percentage, summary_overall_assessment, context_json, summary_json,
            review_meta_json, generation_json, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "artifact-1",
            db_payload["schema_version"],
            artifact_rel,
            "sample",
            "hash",
            db_payload["created_at"],
            db_payload["updated_at"],
            "emma",
            None,
            "singapore_primary_science",
            "attempt-1",
            "/tmp/attempt.pdf",
            "marking_assets/emma/singapore_primary_science/sample",
            4,
            4,
            100.0,
            "ok",
            json.dumps(db_payload["context"]),
            json.dumps(db_payload["summary"]),
            json.dumps(db_payload["review_meta"]),
            json.dumps(db_payload["generation"]),
            json.dumps(db_payload),
        ),
    )
    for row in db_payload["question_results"]:
        diagnosis = row.get("diagnosis") or {}
        conn.execute(
            """
            INSERT INTO marking_question_results(
                artifact_id, result_id, scoring_status, outcome, max_marks, earned_marks,
                student_answer, correct_answer, diagnosis_mistake_type, diagnosis_reasoning,
                human_note, error_tags_json, skill_tags_json, diagnosis_json, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "artifact-1",
                row["result_id"],
                row.get("scoring_status"),
                row.get("outcome"),
                row.get("max_marks"),
                row.get("earned_marks"),
                row.get("student_answer"),
                row.get("correct_answer"),
                diagnosis.get("mistake_type"),
                diagnosis.get("reasoning"),
                row.get("human_note"),
                json.dumps(row.get("error_tags") or []),
                json.dumps(row.get("skill_tags") or []),
                json.dumps(diagnosis),
                json.dumps(row),
            ),
        )
    for row in db_payload["context"]["question_page_map"]:
        conn.execute(
            """
            INSERT INTO marking_question_page_map(
                artifact_id, result_id, attempt_page_start, confidence, source, evidence_image, note, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "artifact-1",
                row["result_id"],
                row.get("attempt_page_start"),
                row.get("confidence"),
                row.get("source"),
                row.get("evidence_image"),
                row.get("note"),
                json.dumps(row),
            ),
        )
    conn.commit()
    conn.close()

    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "1")
    monkeypatch.setenv("LEARNING_DB_READ_FALLBACK_FILESYSTEM", "0")

    repo = StudentReviewRepository(context_root=tmp_path)
    items = list_attempts_for_student(
        student_id="emma",
        context_root=tmp_path,
        manager=_FakeManager(),
        review_repo=repo,
    )
    detail = get_attempt_detail(
        attempt_id="attempt-1",
        context_root=tmp_path,
        manager=_FakeManager(),
        review_repo=repo,
    )

    assert items[0]["score"] == {"earned_marks": 4, "total_marks": 4, "percentage": 100.0}
    assert detail["marking_result_base"]["summary"]["earned_marks"] == 4
