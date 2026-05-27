import pytest

from ai_study_buddy.pdf_file_manager.completion_date import (
    REASON_SCHOOL_YEAR_MISMATCH,
    adjust_page1_completion_year_for_path_context,
    check_completion_date_school_year,
    expected_school_year,
    infer_primary_level_from_path,
    school_year_expectation,
)


def test_expected_school_year_winston_p5():
    assert expected_school_year("winston", 5) == 2025
    assert expected_school_year("emma", 4) == 2026


def test_infer_primary_level_from_path():
    path = (
        "/DaydreamEdu/completion/Science/winston@x.com/P5/Exam/"
        "_c_P5 EYE 2025 Practice Paper 1.pdf"
    )
    assert infer_primary_level_from_path(path) == 5
    assert infer_primary_level_from_path(path, name="_c_P6 foo.pdf") == 5


def test_check_rejects_year_before_grade_window():
    path = "/DaydreamEdu/completion/English/winston@x.com/P5/Exam/paper.pdf"
    ok, detail = check_completion_date_school_year(
        "2022-02-14",
        student_id="winston",
        path=path,
        name="_c_P5 EYE 2025 Practice Paper 1.pdf",
    )
    assert ok is False
    assert detail["reason"] == REASON_SCHOOL_YEAR_MISMATCH
    assert detail["expected_school_year"] == 2025
    assert detail["completion_year"] == 2022


def test_check_accepts_in_window():
    path = "/DaydreamEdu/completion/English/winston@x.com/P5/Exam/paper.pdf"
    ok, detail = check_completion_date_school_year(
        "2025-09-25",
        student_id="winston",
        path=path,
    )
    assert ok is True
    assert detail["expected_school_year"] == 2025


def test_check_skips_unknown_student():
    ok, detail = check_completion_date_school_year(
        "2022-02-14",
        student_id="unknown",
        path="/DaydreamEdu/completion/x/P5/a.pdf",
    )
    assert ok is True
    assert detail["skipped"] == "unknown_student_or_grade"


def test_school_year_expectation():
    exp = school_year_expectation(
        student_id="winston",
        path="/DaydreamEdu/completion/x/P6/a.pdf",
    )
    assert exp is not None
    assert exp.expected_school_year == 2026


def test_adjust_page1_year_exam_vintage_to_path_school_year():
    path = (
        "/DaydreamEdu/completion/Singapore Primary Math/"
        "winston@x.com/P5/Exam/_c_P5 Math EoY Practice Set 1.pdf"
    )
    adjusted, note = adjust_page1_completion_year_for_path_context(
        "2024-10-09",
        student_id="winston",
        path=path,
        source_detail={
            "evidence": "Date: 9th oct; header EOY 2024/P5",
            "disambiguation": "year from header EOY 2024",
        },
    )
    assert adjusted == "2025-10-09"
    assert note is not None
    assert note["to_year"] == 2025


def test_adjust_page1_year_keeps_explicit_date_line_year():
    path = "/DaydreamEdu/completion/x/winston@x.com/P5/Exam/paper.pdf"
    adjusted, note = adjust_page1_completion_year_for_path_context(
        "2024-10-09",
        student_id="winston",
        path=path,
        source_detail={
            "evidence": "Date: 9th Oct 2024",
            "disambiguation": "year on Date line",
        },
    )
    assert adjusted == "2024-10-09"
    assert note is None
