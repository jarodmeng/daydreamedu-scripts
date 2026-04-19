from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from ai_study_buddy.marking.core.context_resolver import (
    MarkingContextResolutionError,
    resolve_marking_context,
)
from ai_study_buddy.pdf_file_manager.pdf_file_manager import NotFoundError, PdfFileManager


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n% mock pdf\n")
    return path


def _make_goodnotes_paths(base: Path) -> tuple[Path, Path]:
    attempt_path = (
        base
        / "GoodNotes"
        / "Singapore Primary Math"
        / "emma@example.com"
        / "P4"
        / "Exam"
        / "_c_p4.math.wa1.6 (attempt).pdf"
    )
    template_path = (
        base
        / "DaydreamEdu"
        / "Singapore Primary Math"
        / "P4"
        / "Exam"
        / "_c_p4.math.wa1.6.pdf"
    )
    _touch(attempt_path)
    _touch(template_path)
    return attempt_path, template_path


def test_resolve_context_can_auto_register_and_use_self_answer_override() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        mgr = PdfFileManager(db_path=str(base / "registry.db"))
        attempt_path, template_path = _make_goodnotes_paths(base)

        template = mgr.register_file(template_path, file_type="main", is_template=True, doc_type="book")

        context = resolve_marking_context(
            attempt_file_id_or_path=attempt_path,
            auto_register_attempt=True,
            auto_link_template=True,
            self_answer_pages=(9, 10),
            manager=mgr,
        )

        assert context.attempt_file_path == str(attempt_path.resolve())
        assert context.template_file_id == template.id
        assert context.answer_file_id == template.id
        assert context.answer_file_path == str(template_path.resolve())
        assert context.answer_page_start == 9
        assert context.answer_page_end == 10
        assert context.book_group_id is None
        assert context.book_label is None
        assert context.answer_mapping_source is not None
        assert "self_answer_pages override" in context.answer_mapping_source


def test_resolve_context_rejects_invalid_self_answer_pages() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        mgr = PdfFileManager(db_path=str(base / "registry.db"))
        attempt_path, template_path = _make_goodnotes_paths(base)
        attempt = mgr.register_file(attempt_path, file_type="main", is_template=False, doc_type="exam")
        template = mgr.register_file(template_path, file_type="main", is_template=True, doc_type="book")
        mgr.link_to_template(attempt.id, template.id)

        with pytest.raises(MarkingContextResolutionError) as exc:
            resolve_marking_context(
                attempt_file_id_or_path=attempt_path,
                self_answer_pages=(10, 9),
                manager=mgr,
            )
        assert "begin_page must be <=" in str(exc.value)


def test_resolve_context_without_override_requires_book_mapping() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        mgr = PdfFileManager(db_path=str(base / "registry.db"))
        attempt_path, template_path = _make_goodnotes_paths(base)
        attempt = mgr.register_file(attempt_path, file_type="main", is_template=False, doc_type="exam")
        template = mgr.register_file(template_path, file_type="main", is_template=True, doc_type="book")
        mgr.link_to_template(attempt.id, template.id)

        with pytest.raises(NotFoundError) as exc:
            resolve_marking_context(
                attempt_file_id_or_path=attempt_path,
                manager=mgr,
            )
        assert "No book group found" in str(exc.value)


def test_resolve_context_without_override_uses_registry_answer_mapping() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        mgr = PdfFileManager(db_path=str(base / "registry.db"))
        attempt_path, template_path = _make_goodnotes_paths(base)
        answer_path = _touch(base / "DaydreamEdu" / "Singapore Primary Math" / "P4" / "Exam" / "_c_p4.math.wa1.ans.pdf")

        attempt = mgr.register_file(attempt_path, file_type="main", is_template=False, doc_type="exam")
        template = mgr.register_file(template_path, file_type="main", is_template=True, doc_type="book")
        answer = mgr.register_file(answer_path, file_type="main", is_template=False, doc_type="book")
        mgr.link_to_template(attempt.id, template.id)

        group = mgr.create_file_group("P4 Math WA1", group_type="book")
        mgr.add_to_file_group(group.id, template.id)
        mgr.add_to_file_group(group.id, answer.id)
        mgr.set_book_answer_mapping(
            template.id,
            answer.id,
            answer_page_start=22,
            answer_page_end=24,
            source="unit_mapping",
        )

        context = resolve_marking_context(
            attempt_file_id_or_path=attempt_path,
            manager=mgr,
        )
        assert context.book_group_id == group.id
        assert context.book_label == group.label
        assert context.answer_file_id == answer.id
        assert context.answer_page_start == 22
        assert context.answer_page_end == 24


def test_resolve_context_daydreamedu_attempt_path_accepted() -> None:
    """Student completion under DaydreamEdu (not GoodNotes) resolves like other mains."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        mgr = PdfFileManager(db_path=str(base / "registry.db"))
        attempt_path = (
            base
            / "DaydreamEdu"
            / "Singapore Primary Math"
            / "emma@example.com"
            / "P4"
            / "Exam"
            / "_c_p4.math.wa1.6 (attempt).pdf"
        )
        template_path = (
            base
            / "DaydreamEdu"
            / "Singapore Primary Math"
            / "P4"
            / "Exam"
            / "_c_p4.math.wa1.6.pdf"
        )
        _touch(attempt_path)
        _touch(template_path)

        template = mgr.register_file(template_path, file_type="main", is_template=True, doc_type="book")
        attempt = mgr.register_file(attempt_path, file_type="main", is_template=False, doc_type="exam")
        mgr.link_to_template(attempt.id, template.id)

        context = resolve_marking_context(
            attempt_file_id_or_path=attempt_path,
            self_answer_pages=(9, 10),
            manager=mgr,
        )

        assert "DaydreamEdu" in context.attempt_file_path
        assert context.template_file_id == template.id
