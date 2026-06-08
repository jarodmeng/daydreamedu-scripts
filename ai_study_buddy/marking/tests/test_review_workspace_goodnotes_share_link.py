from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_study_buddy.marking.review.detail_service import get_attempt_detail
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.pdf_file_manager.goodnotes_metadata import GoodnotesDocumentMatch, GoodnotesDocumentTimestamps
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile


def _g_root_attempt() -> PdfFile:
    return PdfFile(
        id="attempt-gn-1",
        name="c_numbers_laq.pdf",
        path="/GoodNotes/Singapore Primary Math/winston@example.com/PSLE/Book/c_numbers_laq.pdf",
        file_type="main",
        doc_type="book",
        student_id="winston",
        subject="math",
        is_template=False,
        size_bytes=None,
        page_count=None,
        has_raw=False,
        metadata={"grade_or_scope": "PSLE"},
        added_at="2026-04-24T12:00:00Z",
        updated_at="2026-04-24T12:00:00Z",
        notes=None,
    )


def _d_root_attempt() -> PdfFile:
    return PdfFile(
        id="attempt-dd-1",
        name="attempt.pdf",
        path="/DaydreamEdu/completion/math/winston/attempt.pdf",
        file_type="main",
        doc_type="book",
        student_id="winston",
        subject="math",
        is_template=False,
        size_bytes=None,
        page_count=None,
        has_raw=False,
        metadata={"grade_or_scope": "P6"},
        added_at="2026-04-24T12:00:00Z",
        updated_at="2026-04-24T12:00:00Z",
        notes=None,
    )


class _FakeManager:
    def __init__(
        self,
        *,
        attempt: PdfFile,
        attempt_share_link: str | None,
        review_share_link: str | None = None,
    ) -> None:
        self._attempt = attempt
        self._attempt_share_link = attempt_share_link
        self._review_share_link = review_share_link

    def get_file(self, file_id: str):
        if file_id == self._attempt.id:
            return self._attempt
        return None

    def get_student(self, student_id: str):
        return None

    def get_template(self, completion_id: str):
        return None

    def get_goodnotes_document_timestamps_for_file(self, file_id: str, *, folder_scope=None):
        if folder_scope == "review":
            share_link = self._review_share_link
        else:
            share_link = self._attempt_share_link
        if share_link is None:
            return GoodnotesDocumentMatch(
                status="not_goodnotes_root",
                file_id=file_id,
                registered_path=self._attempt.path,
                backup_stem="attempt",
                candidate_names=(),
                matched_candidate_name=None,
                goodnotes_document_id=None,
                goodnotes_document_name=None,
                goodnotes_folder_path=None,
                goodnotes_folder_ids=(),
                timestamps=None,
                share_link=None,
            )
        return GoodnotesDocumentMatch(
            status="matched_exact",
            file_id=file_id,
            registered_path=self._attempt.path,
            backup_stem="c_numbers_laq",
            candidate_names=("c_numbers_laq",),
            matched_candidate_name="_c_numbers_laq",
            goodnotes_document_id="DOC1",
            goodnotes_document_name="_c_numbers_laq",
            goodnotes_folder_path=None,
            goodnotes_folder_ids=(),
            timestamps=GoodnotesDocumentTimestamps(
                created_at=None,
                updated_at=None,
                last_modified=None,
                created_at_raw=None,
                updated_at_raw=None,
                last_modified_raw=None,
            ),
            share_link=share_link,
        )


def _write_marking_fixture(tmp_path: Path, *, attempt_id: str) -> None:
    payload = {
        "schema_version": "marking_result.v1.6",
        "created_at": "2026-04-24T12:00:00+08:00",
        "context": {
            "student_id": "winston",
            "subject_context": "singapore_primary_math",
            "attempt_file_id": attempt_id,
            "marking_asset": "marking_assets/winston/singapore_primary_math/sample",
            "question_page_map": [],
        },
        "summary": {"total_marks": 1, "earned_marks": 1, "percentage": 100.0},
        "question_results": [],
    }
    artifact_path = tmp_path / "marking_results/winston/singapore_primary_math/sample.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / payload["context"]["marking_asset"] / "attempt").mkdir(parents=True)


def test_get_attempt_detail_includes_goodnotes_share_link_for_g_root(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    attempt = _g_root_attempt()
    _write_marking_fixture(tmp_path, attempt_id=attempt.id)
    repo = StudentReviewRepository(context_root=tmp_path)

    detail = get_attempt_detail(
        attempt_id=attempt.id,
        context_root=tmp_path,
        manager=_FakeManager(
            attempt=attempt,
            attempt_share_link="https://share.goodnotes.com/s/Amwv4ubzFA1GGgvqwo83b7",
            review_share_link="https://share.goodnotes.com/s/review-alias",
        ),
        review_repo=repo,
    )

    assert detail["viewer"]["goodnotes_share_link"] == "https://share.goodnotes.com/s/Amwv4ubzFA1GGgvqwo83b7"
    assert detail["viewer"]["goodnotes_review_share_link"] == "https://share.goodnotes.com/s/review-alias"


def test_get_attempt_detail_omits_goodnotes_share_links_for_d_root(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    attempt = _d_root_attempt()
    _write_marking_fixture(tmp_path, attempt_id=attempt.id)
    repo = StudentReviewRepository(context_root=tmp_path)

    detail = get_attempt_detail(
        attempt_id=attempt.id,
        context_root=tmp_path,
        manager=_FakeManager(attempt=attempt, attempt_share_link=None, review_share_link=None),
        review_repo=repo,
    )

    assert detail["viewer"]["goodnotes_share_link"] is None
    assert detail["viewer"]["goodnotes_review_share_link"] is None
