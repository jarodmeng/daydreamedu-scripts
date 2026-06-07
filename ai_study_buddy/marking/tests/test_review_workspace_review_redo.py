from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_study_buddy.marking.review.detail_service import (
    ReviewEvidenceNotFoundError,
    get_attempt_detail,
    get_attempt_review_evidence,
)
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.marking.review.review_redo_service import review_redo_cache_is_stale
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


def _attempt_file(*, path: str) -> PdfFile:
    return PdfFile(
        id="attempt-1",
        name=Path(path).name,
        path=path,
        file_type="main",
        doc_type="exam",
        student_id="winston",
        subject="math",
        is_template=False,
        size_bytes=None,
        page_count=None,
        has_raw=False,
        metadata={"grade_or_scope": "P6"},
        added_at="2026-06-07T12:00:00Z",
        updated_at="2026-06-07T12:00:00Z",
        notes=None,
    )


def _template_file(*, name: str = "_c_P6 Math WA1.pdf") -> PdfFile:
    return PdfFile(
        id="template-1",
        name=name,
        path=f"/tmp/general/{name}",
        file_type="main",
        doc_type="exam",
        student_id=None,
        subject="math",
        is_template=True,
        size_bytes=None,
        page_count=None,
        has_raw=False,
        metadata={"grade_or_scope": "P6"},
        added_at="2026-06-07T12:00:00Z",
        updated_at="2026-06-07T12:00:00Z",
        notes=None,
    )


class _FakeStudent:
    id = "winston"
    name = "Winston"
    email = "winston@example.com"


class _FakeManager:
    def __init__(self, *, attempt_path: str, template: PdfFile | None) -> None:
        self._attempt_path = attempt_path
        self._template = template

    def get_file(self, file_id: str):
        if file_id == "attempt-1":
            return _attempt_file(path=self._attempt_path)
        if file_id == "template-1":
            return self._template
        return None

    def get_student(self, student_id: str):
        return _FakeStudent() if student_id == "winston" else None

    def get_template(self, completion_id: str):
        return self._template if completion_id == "attempt-1" else None


def _write_marking_fixture(tmp_path: Path) -> tuple[Path, Path]:
    context = {
        "student_id": "winston",
        "subject_context": "singapore_primary_math",
        "attempt_file_id": "attempt-1",
        "template_file_id": "template-1",
        "marking_asset": "marking_assets/winston/singapore_primary_math/sample",
        "question_page_map": [
            {
                "result_id": "Q1",
                "attempt_page_start": 1,
                "confidence": "high",
                "source": "script_inferred",
            }
        ],
    }
    payload = {
        "schema_version": "marking_result.v1.6",
        "created_at": "2026-06-07T12:00:00+08:00",
        "context": context,
        "summary": {"total_marks": 1, "earned_marks": 0, "percentage": 0.0},
        "question_results": [
            {
                "result_id": "Q1",
                "outcome": "incorrect",
                "earned_marks": 0,
                "max_marks": 1,
                "student_answer": "b",
                "correct_answer": "a",
                "skill_tags": [],
                "diagnosis": {},
            }
        ],
    }
    artifact_rel = "marking_results/winston/singapore_primary_math/sample.json"
    artifact_path = tmp_path / artifact_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    asset_root = tmp_path / context["marking_asset"]
    (asset_root / "attempt").mkdir(parents=True)
    (asset_root / "attempt" / "page-01.png").write_bytes(_ONE_BY_ONE_PNG)

    goodnotes_root = tmp_path / "GoodNotes"
    review_dir = goodnotes_root / "Singapore Primary Math" / "winston@example.com" / "P6" / "Exam" / "Review"
    review_dir.mkdir(parents=True)
    review_pdf = review_dir / "c_P6 Math WA1.pdf"
    review_pdf.write_bytes(b"%PDF-1.4\n% minimal")

    attempt_path = (
        tmp_path
        / "DaydreamEdu"
        / "completion"
        / "Singapore Primary Math"
        / "winston@example.com"
        / "P6"
        / "Exam"
        / "_c_P6 Math WA1.pdf"
    )
    attempt_path.parent.mkdir(parents=True)
    attempt_path.write_bytes(b"%PDF-1.4\n% minimal")
    return goodnotes_root, review_pdf


def test_get_attempt_detail_includes_review_redo_availability(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    goodnotes_root, _review_pdf = _write_marking_fixture(tmp_path)
    monkeypatch.setattr(
        "ai_study_buddy.marking.review.detail_service.resolve_goodnotes_root",
        lambda: goodnotes_root,
    )

    attempt_path = (
        tmp_path
        / "DaydreamEdu"
        / "completion"
        / "Singapore Primary Math"
        / "winston@example.com"
        / "P6"
        / "Exam"
        / "_c_P6 Math WA1.pdf"
    )
    repo = StudentReviewRepository(context_root=tmp_path)
    detail = get_attempt_detail(
        attempt_id="attempt-1",
        context_root=tmp_path,
        manager=_FakeManager(attempt_path=str(attempt_path), template=_template_file()),
        review_repo=repo,
    )

    assert detail["viewer"]["review_redo"]["available"] is True
    assert detail["viewer"]["review_redo"]["resolved_path"].endswith("Review/c_P6 Math WA1.pdf")
    assert detail["viewer"]["review_images"] == []


def test_get_attempt_detail_review_redo_unavailable_without_review_pdf(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    goodnotes_root, review_pdf = _write_marking_fixture(tmp_path)
    review_pdf.unlink()
    monkeypatch.setattr(
        "ai_study_buddy.marking.review.detail_service.resolve_goodnotes_root",
        lambda: goodnotes_root,
    )

    attempt_path = (
        tmp_path
        / "DaydreamEdu"
        / "completion"
        / "Singapore Primary Math"
        / "winston@example.com"
        / "P6"
        / "Exam"
        / "_c_P6 Math WA1.pdf"
    )
    repo = StudentReviewRepository(context_root=tmp_path)
    detail = get_attempt_detail(
        attempt_id="attempt-1",
        context_root=tmp_path,
        manager=_FakeManager(attempt_path=str(attempt_path), template=_template_file()),
        review_repo=repo,
    )

    assert detail["viewer"]["review_redo"]["available"] is False
    assert detail["viewer"]["review_images"] == []


def test_get_attempt_review_evidence_renders_and_lists_images(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    goodnotes_root, review_pdf = _write_marking_fixture(tmp_path)
    monkeypatch.setattr(
        "ai_study_buddy.marking.review.detail_service.resolve_goodnotes_root",
        lambda: goodnotes_root,
    )

    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    doc.new_page()
    doc.save(str(review_pdf))
    doc.close()

    attempt_path = (
        tmp_path
        / "DaydreamEdu"
        / "completion"
        / "Singapore Primary Math"
        / "winston@example.com"
        / "P6"
        / "Exam"
        / "_c_P6 Math WA1.pdf"
    )
    payload = get_attempt_review_evidence(
        attempt_id="attempt-1",
        context_root=tmp_path,
        manager=_FakeManager(attempt_path=str(attempt_path), template=_template_file()),
    )

    assert len(payload["review_images"]) == 1
    assert payload["review_images"][0]["page_num"] == 1
    assert payload["review_images"][0]["url"].startswith("/review-workspace-static/review_redo/winston/singapore_primary_math/")
    assert payload["review_images"][0]["url"].endswith("page_001.png")
    assert "rendered_at" in payload

    rendered_dir = (
        tmp_path
        / "review_redo"
        / "winston"
        / "singapore_primary_math"
        / "P6 Math WA1"
        / "rendered_pages"
    )
    assert (rendered_dir / "page_001.png").is_file()


def test_get_attempt_review_evidence_404_when_unavailable(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    goodnotes_root, review_pdf = _write_marking_fixture(tmp_path)
    review_pdf.unlink()
    monkeypatch.setattr(
        "ai_study_buddy.marking.review.detail_service.resolve_goodnotes_root",
        lambda: goodnotes_root,
    )

    attempt_path = (
        tmp_path
        / "DaydreamEdu"
        / "completion"
        / "Singapore Primary Math"
        / "winston@example.com"
        / "P6"
        / "Exam"
        / "_c_P6 Math WA1.pdf"
    )
    with pytest.raises(ReviewEvidenceNotFoundError):
        get_attempt_review_evidence(
            attempt_id="attempt-1",
            context_root=tmp_path,
            manager=_FakeManager(attempt_path=str(attempt_path), template=_template_file()),
        )


def test_review_redo_cache_is_stale_when_pdf_newer(tmp_path: Path) -> None:
    rendered_dir = tmp_path / "rendered_pages"
    rendered_dir.mkdir(parents=True)
    png = rendered_dir / "page_001.png"
    png.write_bytes(_ONE_BY_ONE_PNG)

    source_pdf = tmp_path / "review.pdf"
    source_pdf.write_bytes(b"%PDF-1.4")

    png_mtime = 1_000_000_000.0
    pdf_mtime = png_mtime + 100.0
    png.touch()
    source_pdf.touch()
    import os

    os.utime(png, (png_mtime, png_mtime))
    os.utime(source_pdf, (pdf_mtime, pdf_mtime))

    assert review_redo_cache_is_stale(source_pdf=source_pdf, rendered_dir=rendered_dir) is True
