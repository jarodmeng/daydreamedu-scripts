from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_study_buddy.marking.file_question_info.api import file_question_info_run_dir_for_pdf
from ai_study_buddy.marking.review.detail_service import get_attempt_detail
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile

_ONE_BY_ONE_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
    b"\x0d\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _attempt_file() -> PdfFile:
    return PdfFile(
        id="attempt-1",
        name="attempt.pdf",
        path="/tmp/attempt.pdf",
        file_type="main",
        doc_type="book",
        student_id="emma",
        subject="science",
        is_template=False,
        size_bytes=None,
        page_count=None,
        has_raw=False,
        metadata={"grade_or_scope": "P6"},
        added_at="2026-04-24T12:00:00Z",
        updated_at="2026-04-24T12:00:00Z",
        notes=None,
    )


def _template_file() -> PdfFile:
    return PdfFile(
        id="template-1",
        name="template.pdf",
        path="/tmp/template.pdf",
        file_type="main",
        doc_type="book",
        student_id=None,
        subject="science",
        is_template=True,
        size_bytes=None,
        page_count=None,
        has_raw=False,
        metadata={"grade_or_scope": "P6"},
        added_at="2026-04-24T12:00:00Z",
        updated_at="2026-04-24T12:00:00Z",
        notes=None,
    )


class _FakeStudent:
    id = "emma"
    name = "Emma"
    email = "emma@example.com"


class _FakeManager:
    def get_file(self, file_id: str):
        if file_id == "attempt-1":
            return _attempt_file()
        if file_id == "template-1":
            return _template_file()
        return None

    def get_student(self, student_id: str):
        return _FakeStudent() if student_id == "emma" else None

    def get_template(self, completion_id: str):
        return _template_file() if completion_id == "attempt-1" else None


def _write_marking_fixture(tmp_path: Path, *, template_file_id: str | None) -> None:
    context: dict = {
        "student_id": "emma",
        "subject_context": "singapore_primary_science",
        "attempt_file_id": "attempt-1",
        "marking_asset": "marking_assets/emma/singapore_primary_science/sample",
        "question_page_map": [
            {
                "result_id": "Q1",
                "attempt_page_start": 1,
                "confidence": "high",
                "source": "script_inferred",
            }
        ],
    }
    if template_file_id is not None:
        context["template_file_id"] = template_file_id

    payload = {
        "schema_version": "marking_result.v1.6",
        "created_at": "2026-04-24T12:00:00+08:00",
        "context": context,
        "summary": {"total_marks": 1, "earned_marks": 1, "percentage": 100.0},
        "question_results": [
            {
                "result_id": "Q1",
                "outcome": "correct",
                "earned_marks": 1,
                "max_marks": 1,
                "student_answer": "a",
                "correct_answer": "a",
                "skill_tags": [],
                "diagnosis": {},
            }
        ],
    }
    artifact_rel = "marking_results/emma/singapore_primary_science/sample.json"
    artifact_path = tmp_path / artifact_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    asset_root = tmp_path / context["marking_asset"]
    (asset_root / "attempt").mkdir(parents=True)
    (asset_root / "attempt" / "page-01.png").write_bytes(_ONE_BY_ONE_PNG)

    template = _template_file()
    rendered_dir = file_question_info_run_dir_for_pdf(template, context_root=tmp_path) / "rendered_pages"
    rendered_dir.mkdir(parents=True)
    (rendered_dir / "page_001.png").write_bytes(_ONE_BY_ONE_PNG)
    (rendered_dir / "page_002.png").write_bytes(_ONE_BY_ONE_PNG)


def test_get_attempt_detail_includes_template_images_from_fqi_rendered_pages(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    _write_marking_fixture(tmp_path, template_file_id="template-1")
    repo = StudentReviewRepository(context_root=tmp_path)

    detail = get_attempt_detail(
        attempt_id="attempt-1",
        context_root=tmp_path,
        manager=_FakeManager(),
        review_repo=repo,
    )

    template_images = detail["viewer"]["template_images"]
    assert len(template_images) == 2
    assert template_images[0]["page_num"] == 1
    assert template_images[0]["url"].startswith("/review-workspace-static/file_question_info/")
    assert template_images[0]["url"].endswith("page_001.png")


def test_get_attempt_detail_template_images_empty_without_template_link(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    _write_marking_fixture(tmp_path, template_file_id=None)

    class _NoTemplateManager(_FakeManager):
        def get_template(self, completion_id: str):
            return None

    repo = StudentReviewRepository(context_root=tmp_path)
    detail = get_attempt_detail(
        attempt_id="attempt-1",
        context_root=tmp_path,
        manager=_NoTemplateManager(),
        review_repo=repo,
    )

    assert detail["viewer"]["template_images"] == []
