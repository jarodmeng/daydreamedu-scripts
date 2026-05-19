"""Tests for ai_study_buddy.files.path_facets."""

from pathlib import Path

from ai_study_buddy.files.path_facets import infer_path_facets


def test_infer_path_facets_completion_exam() -> None:
    path = Path("/fake/DaydreamEdu/Singapore Primary Science/winston@mail.com/P5/Exam/paper.pdf")
    facets = infer_path_facets(path, root_id="daydreamedu")
    assert facets.parse_status == "ok"
    assert facets.scope == "completion"
    assert facets.subject == "science"
    assert facets.doc_type == "exam"
    assert facets.grade_or_scope == "P5"
    assert facets.student_email == "winston@mail.com"
    assert facets.root_id == "daydreamedu"


def test_infer_path_facets_template_exercise() -> None:
    path = Path("/fake/Singapore Primary English/P6/Exercise/sheet.pdf")
    facets = infer_path_facets(path, root_id="daydreamedu")
    assert facets.scope == "template"
    assert facets.subject == "english"
    assert facets.doc_type == "exercise"
    assert facets.student_email is None


def test_infer_path_facets_book_group() -> None:
    path = Path(
        "/fake/DaydreamEdu/Singapore Primary Chinese/PSLE/Book/Power Pack Chinese PSLE/_c_unit.pdf"
    )
    facets = infer_path_facets(path, root_id="daydreamedu")
    assert facets.doc_type == "book"
    assert facets.book_group_name == "Power Pack Chinese PSLE"


def test_infer_path_facets_invalid_doc_type() -> None:
    path = Path("/fake/DaydreamEdu/Singapore Primary Science/P6/SomeOtherFolder/file.pdf")
    facets = infer_path_facets(path, root_id="daydreamedu")
    assert facets.parse_status == "invalid"
