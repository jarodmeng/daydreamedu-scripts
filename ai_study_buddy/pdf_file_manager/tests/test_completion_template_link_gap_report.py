from pathlib import Path

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
from ai_study_buddy.pdf_file_manager.scripts.completion_template_link_gap_report import (
    build_report,
)


def _make_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.0\n")
    return path


def test_build_report_excludes_composition_without_template_from_gaps(tmp_path: Path) -> None:
    db_path = tmp_path / "pdf_registry.db"
    mgr = PdfFileManager(db_path=db_path)
    mgr.ensure_student("winston", "Winston Meng", email="winston@example.com")

    exam = mgr.register_file(
        _make_pdf(tmp_path / "exam.pdf"),
        file_type="main",
        doc_type="exam",
        student_id="winston",
        is_template=False,
    )
    composition = mgr.register_file(
        _make_pdf(tmp_path / "composition.pdf"),
        file_type="main",
        doc_type="composition",
        student_id="winston",
        is_template=False,
    )
    assert exam.id
    assert composition.id

    report = build_report(db_path, include_activity_note=False)
    assert report["summary"]["completion_mains"] == 1
    assert report["summary"]["without_template"] == 1
    assert report["summary"]["gap_buckets"] == 1

    report_all = build_report(db_path, include_activity_note=True)
    assert report_all["summary"]["completion_mains"] == 1
    assert report_all["summary"]["without_template"] == 1


def test_build_report_passes_when_only_composition_missing_template(tmp_path: Path) -> None:
    db_path = tmp_path / "pdf_registry.db"
    mgr = PdfFileManager(db_path=db_path)
    mgr.ensure_student("winston", "Winston Meng", email="winston@example.com")
    mgr.register_file(
        _make_pdf(tmp_path / "composition.pdf"),
        file_type="main",
        doc_type="composition",
        student_id="winston",
        is_template=False,
    )

    report = build_report(db_path, include_activity_note=False)
    assert report["summary"]["completion_mains"] == 0
    assert report["summary"]["without_template"] == 0
    assert report["gaps"] == []


def test_build_report_excludes_not_completed_wip_from_gaps(tmp_path: Path) -> None:
    db_path = tmp_path / "pdf_registry.db"
    mgr = PdfFileManager(db_path=db_path)
    mgr.ensure_student("emma", "Emma Meng", email="emma@example.com")

    wip_path = (
        tmp_path
        / "GoodNotes"
        / "Singapore Primary English"
        / "emma@example.com"
        / "P4"
        / "Book"
        / "Some Book"
        / "Not completed"
        / "c_Some Book - 01 Exercise 1.pdf"
    )
    ready_path = tmp_path / "exam.pdf"
    mgr.register_file(
        _make_pdf(wip_path),
        file_type="main",
        doc_type="book",
        student_id="emma",
        is_template=False,
    )
    mgr.register_file(
        _make_pdf(ready_path),
        file_type="main",
        doc_type="exam",
        student_id="emma",
        is_template=False,
    )

    report = build_report(db_path, include_activity_note=False)
    assert report["summary"]["completion_mains"] == 1
    assert report["summary"]["without_template"] == 1
    assert report["summary"]["gap_buckets"] == 1

    report_with_wip = build_report(
        db_path,
        include_activity_note=False,
        exclude_not_completed=False,
    )
    assert report_with_wip["summary"]["completion_mains"] == 2
    assert report_with_wip["summary"]["without_template"] == 2


def test_build_report_counts_exam_gap(tmp_path: Path) -> None:
    db_path = tmp_path / "pdf_registry.db"
    mgr = PdfFileManager(db_path=db_path)
    mgr.ensure_student("winston", "Winston Meng", email="winston@example.com")
    mgr.register_file(
        _make_pdf(tmp_path / "exam.pdf"),
        file_type="main",
        doc_type="exam",
        student_id="winston",
        is_template=False,
    )

    report = build_report(db_path, include_activity_note=False)
    assert report["summary"]["without_template"] == 1
