import pytest

from ai_study_buddy.pdf_file_manager.completion_date import school_year_expectation
from ai_study_buddy.pdf_file_manager.completion_date.filename_term import (
    completion_date_from_term_end,
    infer_completion_date_from_filename_term,
    infer_term_from_title,
    load_school_term_calendar,
)


def test_infer_term_groups():
    assert infer_term_from_title("P5 EYE 2025 Practice Paper 1") == (4, "EYE")
    assert infer_term_from_title("P3 English WA2") == (2, "WA2")
    assert infer_term_from_title("P5 English Term 3 WA Practice") == (3, "Term 3")
    assert infer_term_from_title("五年级华文 期末考试 (试卷二)") == (4, "期末考试")
    assert infer_term_from_title("五年级高华 测验2 (试卷二)") == (2, "测验2")
    assert infer_term_from_title("Primary 5 Grammar MCQ Exercises Term 4 2025") == (
        4,
        "Term 4",
    )
    assert infer_term_from_title("Subtraction worksheet") is None


def test_completion_date_two_weeks_before_term_end():
    assert completion_date_from_term_end("2025-11-21") == "2025-11-07"
    assert completion_date_from_term_end("2025-03-14") == "2025-02-28"


def test_infer_winston_p5_eye():
    path = (
        "/DaydreamEdu/completion/Science/winston@x.com/P5/Exam/"
        "_c_P5 EYE 2025 Practice Paper 1.pdf"
    )
    row = infer_completion_date_from_filename_term(
        "P5 EYE 2025 Practice Paper 1",
        student_id="winston",
        path=path,
        calendar=load_school_term_calendar(),
    )
    assert row is not None
    assert row.term == 4
    assert row.school_year == 2025
    assert row.completion_date == "2025-11-07"
    assert row.matched_keyword == "EYE"


def test_infer_chinese_exam_title():
    path = (
        "/DaydreamEdu/completion/Chinese/winston@x.com/P5/Exam/"
        "_c_五年级华文 期末考试 (试卷二).pdf"
    )
    row = infer_completion_date_from_filename_term(
        "五年级华文 期末考试 (试卷二)",
        student_id="winston",
        path=path,
        calendar=load_school_term_calendar(),
    )
    assert row is not None
    assert row.completion_date == "2025-11-07"


def test_unknown_student_returns_none():
    row = infer_completion_date_from_filename_term(
        "P5 EYE 2025",
        student_id="nobody",
        path="/DaydreamEdu/completion/x/P5/a.pdf",
    )
    assert row is None


def test_school_year_expectation_winston_p6():
    exp = school_year_expectation(
        student_id="winston",
        path="/DaydreamEdu/completion/x/P6/a.pdf",
    )
    assert exp is not None
    assert exp.expected_school_year == 2026
