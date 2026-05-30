import pytest

from ai_study_buddy.pdf_file_manager.composition_filenames import is_composition_basename


@pytest.mark.parametrize(
    "name",
    [
        "_c_Composition 1b.pdf",
        "_raw_P5 English EoY (Paper 1).pdf",
        "_c_四年级 作文 1.pdf",
        "_c_三年级华文 期末考试 试卷一.pdf",
        "_c_Situational Writing Exercise.pdf",
        "_c_P6 English Situational Writing 1.pdf",
        "c_PP English Situational Writing Practice 2.pdf",
        "Practice 7 Composition.pdf",
    ],
)
def test_is_composition_basename_positive(name: str):
    assert is_composition_basename(name)


@pytest.mark.parametrize(
    "name",
    [
        "_c_四年级 华文 听写1.pdf",
        "_c_P5 English Practice 1.pdf",
        "regular_worksheet.pdf",
        "Paper 2 Comprehension.pdf",
    ],
)
def test_is_composition_basename_negative(name: str):
    assert not is_composition_basename(name)
