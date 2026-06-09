from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_study_buddy.marking.review.tutor_chat_repository import (
    TutorChatRepository,
    TutorChatRepositoryError,
    build_new_session,
    marking_artifact_stem_from_path,
    normalize_tutor_chat_session,
)


def _snapshot() -> dict:
    return {
        "marking_result_path": "marking_results/emma/singapore_primary_math/wa1.json",
        "amendment_updated_at": "2026-06-01T10:00:00Z",
        "review_state_updated_at": "2026-06-01T11:00:00Z",
        "resolved_question_fingerprint": "fp-abc123",
    }


def _session_keys() -> dict:
    return {
        "student_id": "emma",
        "subject_context": "singapore_primary_math",
        "marking_artifact_stem": "wa1",
        "result_id": "Q1",
    }


def test_normalize_tutor_chat_session_round_trip():
    payload = build_new_session(
        attempt_id="attempt-1",
        result_id="Q1",
        student_id="emma",
        subject_context="singapore_primary_math",
        marking_artifact_stem="wa1",
        context_snapshot=_snapshot(),
        session_id="sess-1",
    )
    normalized = normalize_tutor_chat_session(payload)
    assert normalized["schema_version"] == "tutor_chat.v1"
    assert normalized["session_id"] == "sess-1"
    assert normalized["messages"] == []
    assert normalized["context_snapshot"]["resolved_question_fingerprint"] == "fp-abc123"


def test_normalize_rejects_invalid_message_role():
    payload = build_new_session(
        attempt_id="attempt-1",
        result_id="Q1",
        student_id="emma",
        subject_context="singapore_primary_math",
        marking_artifact_stem="wa1",
        context_snapshot=_snapshot(),
    )
    payload["messages"] = [{"role": "system", "content": "hi", "at": "2026-06-01T00:00:00Z"}]
    normalized = normalize_tutor_chat_session(payload)
    assert normalized["messages"] == []


def test_marking_artifact_stem_from_path():
    assert (
        marking_artifact_stem_from_path("marking_results/emma/singapore_primary_math/wa1.json")
        == "wa1"
    )


def test_save_and_load_session(tmp_path: Path):
    repo = TutorChatRepository(context_root=tmp_path)
    keys = _session_keys()
    session = build_new_session(
        attempt_id="attempt-1",
        result_id=keys["result_id"],
        student_id=keys["student_id"],
        subject_context=keys["subject_context"],
        marking_artifact_stem=keys["marking_artifact_stem"],
        context_snapshot=_snapshot(),
        session_id="sess-save",
    )
    path = repo.save_session(session)
    assert path.is_file()
    assert path == repo.session_path(session_id="sess-save", **keys)

    loaded = repo.load_session(session_id="sess-save", **keys)
    assert loaded is not None
    assert loaded["session_id"] == "sess-save"
    assert loaded["schema_version"] == "tutor_chat.v1"

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["schema_version"] == "tutor_chat.v1"
    assert on_disk["attempt_id"] == "attempt-1"


def test_append_message_persists(tmp_path: Path):
    repo = TutorChatRepository(context_root=tmp_path)
    keys = _session_keys()
    session = build_new_session(
        attempt_id="attempt-1",
        result_id=keys["result_id"],
        student_id=keys["student_id"],
        subject_context=keys["subject_context"],
        marking_artifact_stem=keys["marking_artifact_stem"],
        context_snapshot=_snapshot(),
        session_id="sess-msg",
    )
    repo.save_session(session)

    updated = repo.append_message(
        session,
        {"role": "student", "content": "Why was I wrong?", "at": "2026-06-02T00:00:00Z"},
    )
    assert len(updated["messages"]) == 1
    assert updated["messages"][0]["role"] == "student"

    reloaded = repo.load_session(session_id="sess-msg", **keys)
    assert reloaded is not None
    assert len(reloaded["messages"]) == 1
    assert reloaded["messages"][0]["content"] == "Why was I wrong?"


def test_append_message_rejects_invalid_role(tmp_path: Path):
    repo = TutorChatRepository(context_root=tmp_path)
    session = build_new_session(
        attempt_id="attempt-1",
        result_id="Q1",
        student_id="emma",
        subject_context="singapore_primary_math",
        marking_artifact_stem="wa1",
        context_snapshot=_snapshot(),
    )
    with pytest.raises(TutorChatRepositoryError):
        repo.append_message(session, {"role": "tool", "content": "x"})


def test_list_and_load_latest_session(tmp_path: Path):
    repo = TutorChatRepository(context_root=tmp_path)
    keys = _session_keys()

    older = build_new_session(
        attempt_id="attempt-1",
        result_id=keys["result_id"],
        student_id=keys["student_id"],
        subject_context=keys["subject_context"],
        marking_artifact_stem=keys["marking_artifact_stem"],
        context_snapshot=_snapshot(),
        session_id="sess-old",
    )
    older["updated_at"] = "2026-06-01T00:00:00Z"
    repo.save_session(older)

    newer = build_new_session(
        attempt_id="attempt-1",
        result_id=keys["result_id"],
        student_id=keys["student_id"],
        subject_context=keys["subject_context"],
        marking_artifact_stem=keys["marking_artifact_stem"],
        context_snapshot=_snapshot(),
        session_id="sess-new",
    )
    newer["updated_at"] = "2026-06-02T00:00:00Z"
    repo.save_session(newer)

    sessions = repo.list_sessions_for_question(**keys)
    assert [row["session_id"] for row in sessions] == ["sess-new", "sess-old"]

    latest = repo.load_latest_session(**keys)
    assert latest is not None
    assert latest["session_id"] == "sess-new"


def test_load_missing_session_returns_none(tmp_path: Path):
    repo = TutorChatRepository(context_root=tmp_path)
    keys = _session_keys()
    assert repo.load_session(session_id="missing", **keys) is None
    assert repo.load_latest_session(**keys) is None
    assert repo.list_sessions_for_question(**keys) == []


def test_result_id_with_parentheses_in_path(tmp_path: Path):
    repo = TutorChatRepository(context_root=tmp_path)
    keys = {
        "student_id": "emma",
        "subject_context": "singapore_primary_english",
        "marking_artifact_stem": "grammar-wa",
        "result_id": "Q1(a)",
    }
    session = build_new_session(
        attempt_id="attempt-1",
        result_id=keys["result_id"],
        student_id=keys["student_id"],
        subject_context=keys["subject_context"],
        marking_artifact_stem=keys["marking_artifact_stem"],
        context_snapshot=_snapshot(),
        session_id="sess-paren",
    )
    path = repo.save_session(session)
    assert "Q1(a)" in path.as_posix()
    loaded = repo.load_session(session_id="sess-paren", **keys)
    assert loaded is not None
    assert loaded["result_id"] == "Q1(a)"
