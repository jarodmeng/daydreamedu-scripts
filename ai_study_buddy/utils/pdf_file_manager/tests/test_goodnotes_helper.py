import tempfile
from pathlib import Path

import pytest

from pdf_file_manager import PdfFileManager


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"pdf")


def test_resolve_goodnotes_template_math_wa1_student_scope():
    """P6 WA1 practice paper (empty) (attempt) under student scope should map to student-scoped DaydreamEdu _c_ template."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        goodnotes = base / "GoodNotes"
        daydream = base / "DaydreamEdu"

        # GoodNotes completion
        gn_path = (
            goodnotes
            / "Singapore Primary Math"
            / "winston.ry.meng@gmail.com"
            / "P6"
            / "Exam"
            / "P6 WA1 practice paper 1 (empty) (attempt).pdf"
        )
        _touch(gn_path)

        # DaydreamEdu template (student scoped)
        dd_tpl = (
            daydream
            / "Singapore Primary Math"
            / "winston.ry.meng@gmail.com"
            / "P6"
            / "Exam"
            / "_c_P6 WA1 practice paper 1 (empty).pdf"
        )
        _touch(dd_tpl)

        resolved = PdfFileManager.resolve_goodnotes_template_path(gn_path)
        assert resolved == dd_tpl


def test_resolve_goodnotes_template_math_p6_general_scope():
    """p6.math.wa1.K (attempt) under student scope should map to general-scope DaydreamEdu P6/Exam _c_ template."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        goodnotes = base / "GoodNotes"
        daydream = base / "DaydreamEdu"

        gn_path = (
            goodnotes
            / "Singapore Primary Math"
            / "winston.ry.meng@gmail.com"
            / "P6"
            / "Exam"
            / "p6.math.wa1.1 (attempt).pdf"
        )
        _touch(gn_path)

        # General-scope DaydreamEdu P6/Exam (no student email segment)
        dd_tpl = (
            daydream
            / "Singapore Primary Math"
            / "P6"
            / "Exam"
            / "_c_p6.math.wa1.1.pdf"
        )
        _touch(dd_tpl)

        resolved = PdfFileManager.resolve_goodnotes_template_path(gn_path)
        assert resolved == dd_tpl


def test_resolve_goodnotes_template_english_epo_attempt_general_scope():
    """EPO_* (attempt) under English PSLE/Exercise should map to general-scope DaydreamEdu _c_EPO_*.pdf."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        goodnotes = base / "GoodNotes"
        daydream = base / "DaydreamEdu"

        gn_path = (
            goodnotes
            / "Singapore Primary English"
            / "winston.ry.meng@gmail.com"
            / "PSLE"
            / "Exercise"
            / "EPO_Comprehension_Cloze_04 (attempt).pdf"
        )
        _touch(gn_path)

        dd_tpl = (
            daydream
            / "Singapore Primary English"
            / "PSLE"
            / "Exercise"
            / "_c_EPO_Comprehension_Cloze_04.pdf"
        )
        _touch(dd_tpl)

        resolved = PdfFileManager.resolve_goodnotes_template_path(gn_path)
        assert resolved == dd_tpl


def test_resolve_goodnotes_template_science_reviewed_student_scope():
    """Reviewed Science file with c_ prefix should map to student-scoped DaydreamEdu _c_ template."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        goodnotes = base / "GoodNotes"
        daydream = base / "DaydreamEdu"

        gn_path = (
            goodnotes
            / "Singapore Primary Science"
            / "winston.ry.meng@gmail.com"
            / "P6"
            / "Exam"
            / "c_P6 Science Weighted Review 1 (reviewed).pdf"
        )
        _touch(gn_path)

        dd_tpl = (
            daydream
            / "Singapore Primary Science"
            / "winston.ry.meng@gmail.com"
            / "P6"
            / "Exam"
            / "_c_P6 Science Weighted Review 1.pdf"
        )
        _touch(dd_tpl)

        resolved = PdfFileManager.resolve_goodnotes_template_path(gn_path)
        assert resolved == dd_tpl


def test_resolve_goodnotes_template_raises_when_no_match():
    """Helper should fail clearly when no matching DaydreamEdu _c_ file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        goodnotes = base / "GoodNotes"

        gn_path = (
            goodnotes
            / "Singapore Primary English"
            / "winston.ry.meng@gmail.com"
            / "P6"
            / "Exam"
            / "Nonexistent Paper 1 (reviewed).pdf"
        )
        _touch(gn_path)

        with pytest.raises(ValueError) as exc:
            PdfFileManager.resolve_goodnotes_template_path(gn_path)
        assert "no matching _c_ file found" in str(exc.value)

