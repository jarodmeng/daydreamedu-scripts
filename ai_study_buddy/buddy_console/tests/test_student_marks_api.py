from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_study_buddy.buddy_console.backend.app import app
from ai_study_buddy.buddy_console.backend.student_portal_service import (
    build_marks_by_question_type_response,
)


def _sample_marks() -> dict:
    return {
        "question_count": 3,
        "earned_marks": 6.0,
        "max_marks": 9.0,
        "percentage": 66.7,
        "by_type": {
            "MCQ": {
                "question_count": 1,
                "earned_marks": 1.0,
                "max_marks": 2.0,
                "percentage": 50.0,
            },
            "SAQ": {
                "question_count": 2,
                "earned_marks": 5.0,
                "max_marks": 7.0,
                "percentage": 71.4,
            },
        },
    }


_HIGHER_ONLY_MARKS = {
    "question_count": 25,
    "earned_marks": 44.0,
    "max_marks": 50.0,
    "percentage": 88.0,
    "by_type": {
        "字词改正": {
            "question_count": 25,
            "earned_marks": 44.0,
            "max_marks": 50.0,
            "percentage": 88.0,
        },
    },
}


def _fake_build(
    *,
    student_slug: str,
    subject_contexts: tuple[str, ...],
    include_fqi_schema_prefixes: tuple[str, ...] = (),
    exclude_fqi_schema_prefixes: tuple[str, ...] = (),
    **_kwargs,
) -> dict:
    _ = student_slug
    if include_fqi_schema_prefixes == ("high-chinese",):
        return {"marking_marks_by_type": _HIGHER_ONLY_MARKS}
    if exclude_fqi_schema_prefixes == ("high-chinese",):
        return {"marking_marks_by_type": _sample_marks()}
    if subject_contexts == ("singapore_primary_higher_chinese",):
        return {"marking_marks_by_type": {"question_count": 0, "by_type": {}}}
    return {"marking_marks_by_type": _sample_marks()}


@pytest.fixture
def portal_paths(tmp_path: Path) -> dict[str, Path]:
    db_path = tmp_path / "study_buddy.db"
    db_path.write_bytes(b"")
    context_root = tmp_path / "context"
    context_root.mkdir()
    return {"study_db": db_path, "context_root": context_root}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, portal_paths: dict[str, Path]) -> TestClient:
    def _serve(*, student_id: str, subject: str) -> dict:
        return build_marks_by_question_type_response(
            student_id=student_id,
            subject=subject,
            build_stats=_fake_build,
            study_db=portal_paths["study_db"],
            context_root=portal_paths["context_root"],
        )

    monkeypatch.setattr(
        "ai_study_buddy.buddy_console.backend.student_portal_api.build_marks_by_question_type_response",
        _serve,
    )
    return TestClient(app)


def test_marks_api_requires_student_id(client: TestClient) -> None:
    res = client.get("/api/student/marks-by-question-type", params={"subject": "math"})
    assert res.status_code == 400


def test_marks_api_rejects_invalid_subject(client: TestClient) -> None:
    res = client.get(
        "/api/student/marks-by-question-type",
        params={"student_id": "winston", "subject": "history"},
    )
    assert res.status_code == 400


def test_marks_api_math_shape(client: TestClient) -> None:
    res = client.get(
        "/api/student/marks-by-question-type",
        params={"student_id": "winston", "subject": "math"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["student_id"] == "winston"
    assert body["subject"] == "math"
    assert "generated_at" in body
    assert len(body["subjects"]) == 1
    block = body["subjects"][0]
    assert block["subject_context"] == "singapore_primary_math"
    assert block["display_label"] == "Math"
    assert block["type_order"] == ["MCQ", "SAQ"]
    assert block["marks_by_question_type"]["by_type"]["MCQ"]["earned_marks"] == 1.0


def test_marks_api_chinese_splits_by_fqi_schema(client: TestClient) -> None:
    res = client.get(
        "/api/student/marks-by-question-type",
        params={"student_id": "winston", "subject": "chinese"},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["subjects"]) == 2
    standard = body["subjects"][0]
    higher = body["subjects"][1]
    assert standard["subject_context"] == "singapore_primary_chinese"
    assert "字词改正" not in (standard["marks_by_question_type"].get("by_type") or {})
    assert higher["subject_context"] == "singapore_primary_higher_chinese"
    assert "字词改正" in (higher["marks_by_question_type"].get("by_type") or {})


def test_chinese_compute_passes_schema_filters(monkeypatch: pytest.MonkeyPatch, portal_paths: dict[str, Path]) -> None:
    calls: list[dict] = []

    def _recording_build(**kwargs) -> dict:
        calls.append(kwargs)
        return _fake_build(**kwargs)

    build_marks_by_question_type_response(
        student_id="winston",
        subject="chinese",
        build_stats=_recording_build,
        study_db=portal_paths["study_db"],
        context_root=portal_paths["context_root"],
    )
    assert len(calls) == 2
    assert calls[0]["subject_contexts"] == ("singapore_primary_chinese",)
    assert calls[0]["exclude_fqi_schema_prefixes"] == ("high-chinese",)
    assert calls[1]["subject_contexts"] == (
        "singapore_primary_chinese",
        "singapore_primary_higher_chinese",
    )
    assert calls[1]["include_fqi_schema_prefixes"] == ("high-chinese",)


def test_marks_api_empty_subjects_message(
    monkeypatch: pytest.MonkeyPatch, portal_paths: dict[str, Path]
) -> None:
    def _empty_build(**_kwargs) -> dict:
        return {"marking_marks_by_type": {"question_count": 0, "by_type": {}}}

    def _serve(*, student_id: str, subject: str) -> dict:
        return build_marks_by_question_type_response(
            student_id=student_id,
            subject=subject,
            build_stats=_empty_build,
            study_db=portal_paths["study_db"],
            context_root=portal_paths["context_root"],
        )

    monkeypatch.setattr(
        "ai_study_buddy.buddy_console.backend.student_portal_api.build_marks_by_question_type_response",
        _serve,
    )
    client = TestClient(app)
    res = client.get(
        "/api/student/marks-by-question-type",
        params={"student_id": "winston", "subject": "science"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["subjects"] == []
    assert body["message"] == "No counted markings in scope for this subject."


def test_marks_api_503_when_db_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing_db = tmp_path / "missing.db"
    context_root = tmp_path / "context"
    context_root.mkdir()

    def _serve(*, student_id: str, subject: str) -> dict:
        return build_marks_by_question_type_response(
            student_id=student_id,
            subject=subject,
            study_db=missing_db,
            context_root=context_root,
        )

    monkeypatch.setattr(
        "ai_study_buddy.buddy_console.backend.student_portal_api.build_marks_by_question_type_response",
        _serve,
    )
    client = TestClient(app)
    res = client.get(
        "/api/student/marks-by-question-type",
        params={"student_id": "winston", "subject": "math"},
    )
    assert res.status_code == 503
    assert "Study database unavailable" in res.json()["detail"]


def test_service_ignores_student_understandings_export_json(portal_paths: dict[str, Path]) -> None:
    export_dir = (
        portal_paths["context_root"]
        / "student_understandings"
        / "winston"
        / "singapore_primary_math"
    )
    export_dir.mkdir(parents=True)
    (export_dir / "marked_completion_fqi_stats.json").write_text('{"stale": true}', encoding="utf-8")

    payload = build_marks_by_question_type_response(
        student_id="winston",
        subject="math",
        build_stats=_fake_build,
        study_db=portal_paths["study_db"],
        context_root=portal_paths["context_root"],
    )
    assert payload["subjects"][0]["marks_by_question_type"]["earned_marks"] == 6.0
