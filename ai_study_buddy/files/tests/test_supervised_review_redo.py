from __future__ import annotations

from pathlib import Path

import pytest

from ai_study_buddy.files.supervised_review_redo import resolve_supervised_review_pdf_for_attempt
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile


def _attempt(*, path: str, attempt_id: str = "attempt-1") -> PdfFile:
    return PdfFile(
        id=attempt_id,
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


def _template(*, name: str, template_id: str = "template-1") -> PdfFile:
    return PdfFile(
        id=template_id,
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


class _FakeManager:
    def __init__(self, *, template: PdfFile | None) -> None:
        self._template = template

    def get_template(self, completion_id: str):
        return self._template


def test_resolve_review_pdf_from_d_root_attempt(tmp_path: Path) -> None:
    goodnotes_root = tmp_path / "GoodNotes"
    review_dir = (
        goodnotes_root
        / "Singapore Primary Math"
        / "winston@example.com"
        / "P6"
        / "Exam"
        / "Review"
    )
    review_dir.mkdir(parents=True)
    review_pdf = review_dir / "c_P6 Math WA1.pdf"
    review_pdf.write_bytes(b"%PDF-1.4")

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
    attempt_path.write_bytes(b"%PDF-1.4")

    resolution = resolve_supervised_review_pdf_for_attempt(
        _attempt(path=str(attempt_path)),
        manager=_FakeManager(template=_template(name="_c_P6 Math WA1.pdf")),
        goodnotes_root=goodnotes_root,
    )

    assert resolution.available is True
    assert resolution.resolved_path == review_pdf
    assert resolution.resolved_path_relative_to(goodnotes_root) == (
        "Singapore Primary Math/winston@example.com/P6/Exam/Review/c_P6 Math WA1.pdf"
    )


def test_resolve_review_pdf_from_g_root_attempt(tmp_path: Path) -> None:
    goodnotes_root = tmp_path / "GoodNotes"
    review_dir = goodnotes_root / "Singapore Primary Math" / "winston@example.com" / "P6" / "Exam" / "Review"
    review_dir.mkdir(parents=True)
    review_pdf = review_dir / "c_p6.math.wa1.4.pdf"
    review_pdf.write_bytes(b"%PDF-1.4")

    attempt_path = (
        goodnotes_root
        / "Singapore Primary Math"
        / "winston@example.com"
        / "P6"
        / "Exam"
        / "c_p6.math.wa1.4.pdf"
    )
    attempt_path.write_bytes(b"%PDF-1.4")

    resolution = resolve_supervised_review_pdf_for_attempt(
        _attempt(path=str(attempt_path)),
        manager=_FakeManager(template=_template(name="_c_p6.math.wa1.4.pdf")),
        goodnotes_root=goodnotes_root,
    )

    assert resolution.available is True
    assert resolution.resolved_path == review_pdf


def test_resolve_review_pdf_nested_book_path(tmp_path: Path) -> None:
    goodnotes_root = tmp_path / "GoodNotes"
    review_dir = (
        goodnotes_root
        / "Singapore Primary Math"
        / "winston@example.com"
        / "P6"
        / "Book"
        / "Math Model P5 and P6"
        / "Review"
    )
    review_dir.mkdir(parents=True)
    review_pdf = review_dir / "c_Math Model P5 and P6_028_Unit 2 - 07 - 2.7.pdf"
    review_pdf.write_bytes(b"%PDF-1.4")

    attempt_path = (
        tmp_path
        / "DaydreamEdu"
        / "completion"
        / "Singapore Primary Math"
        / "winston@example.com"
        / "P6"
        / "Book"
        / "Math Model P5 and P6"
        / "_c_Math Model P5 and P6_028_Unit 2 - 07 - 2.7.pdf"
    )
    attempt_path.parent.mkdir(parents=True)
    attempt_path.write_bytes(b"%PDF-1.4")

    resolution = resolve_supervised_review_pdf_for_attempt(
        _attempt(path=str(attempt_path)),
        manager=_FakeManager(
            template=_template(name="_c_Math Model P5 and P6_028_Unit 2 - 07 - 2.7.pdf"),
        ),
        goodnotes_root=goodnotes_root,
    )

    assert resolution.available is True
    assert resolution.resolved_path == review_pdf


def test_resolve_review_pdf_missing_file(tmp_path: Path) -> None:
    goodnotes_root = tmp_path / "GoodNotes"
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
    attempt_path.write_bytes(b"%PDF-1.4")

    resolution = resolve_supervised_review_pdf_for_attempt(
        _attempt(path=str(attempt_path)),
        manager=_FakeManager(template=_template(name="_c_P6 Math WA1.pdf")),
        goodnotes_root=goodnotes_root,
    )

    assert resolution.available is False
    assert resolution.resolved_path is None


def test_resolve_review_pdf_without_template_link(tmp_path: Path) -> None:
    attempt_path = tmp_path / "GoodNotes" / "Singapore Primary Math" / "winston@example.com" / "P6" / "Exam" / "c_x.pdf"
    attempt_path.parent.mkdir(parents=True)
    attempt_path.write_bytes(b"%PDF-1.4")

    resolution = resolve_supervised_review_pdf_for_attempt(
        _attempt(path=str(attempt_path)),
        manager=_FakeManager(template=None),
        goodnotes_root=tmp_path / "GoodNotes",
    )

    assert resolution.available is False


def test_resolve_review_pdf_without_goodnotes_root(tmp_path: Path) -> None:
    attempt_path = tmp_path / "attempt.pdf"
    attempt_path.write_bytes(b"%PDF-1.4")

    resolution = resolve_supervised_review_pdf_for_attempt(
        _attempt(path=str(attempt_path)),
        manager=_FakeManager(template=_template(name="_c_attempt.pdf")),
        goodnotes_root=None,
    )

    assert resolution.available is False


def test_resolve_review_pdf_fallback_underscore_candidate(tmp_path: Path) -> None:
    goodnotes_root = tmp_path / "GoodNotes"
    review_dir = goodnotes_root / "Singapore Primary Math" / "winston@example.com" / "P6" / "Exam" / "Review"
    review_dir.mkdir(parents=True)
    review_pdf = review_dir / "_c_P6 Math WA1.pdf"
    review_pdf.write_bytes(b"%PDF-1.4")

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
    attempt_path.write_bytes(b"%PDF-1.4")

    resolution = resolve_supervised_review_pdf_for_attempt(
        _attempt(path=str(attempt_path)),
        manager=_FakeManager(template=_template(name="_c_P6 Math WA1.pdf")),
        goodnotes_root=goodnotes_root,
    )

    assert resolution.available is True
    assert resolution.resolved_path == review_pdf
