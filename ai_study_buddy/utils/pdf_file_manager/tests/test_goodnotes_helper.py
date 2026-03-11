import tempfile
from pathlib import Path

import pytest

from pdf_file_manager import NotFoundError, PdfFileManager


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


def test_link_goodnotes_template_for_file_links_registered_template():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db_path = base / "registry.db"
        mgr = PdfFileManager(db_path=str(db_path))

        goodnotes_main = (
            base
            / "GoodNotes"
            / "Singapore Primary Chinese"
            / "winston.ry.meng@gmail.com"
            / "P6"
            / "Exam"
            / "_c_p6.chinese.wa1.1 (attempt).pdf"
        )
        template_path = (
            base
            / "DaydreamEdu"
            / "Singapore Primary Chinese"
            / "P6"
            / "Exam"
            / "_c_p6.chinese.wa1.1.pdf"
        )
        _touch(goodnotes_main)
        _touch(template_path)

        completed = mgr.register_file(goodnotes_main, file_type="main", doc_type="exam", subject="chinese")
        template = mgr.register_file(template_path, file_type="main", doc_type="exam", subject="chinese", is_template=True)

        outcome = mgr.link_goodnotes_template_for_file(goodnotes_main)

        assert outcome.linked is True
        assert outcome.already_linked is False
        assert outcome.template_path == str(template_path.resolve())
        linked_template = mgr.get_template(completed.id)
        assert linked_template is not None
        assert linked_template.id == template.id


def test_link_goodnotes_template_for_file_can_auto_fix_template_flag():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db_path = base / "registry.db"
        mgr = PdfFileManager(db_path=str(db_path))

        goodnotes_main = (
            base
            / "GoodNotes"
            / "Singapore Primary English"
            / "winston.ry.meng@gmail.com"
            / "P6"
            / "Exam"
            / "_c_P6 English Term 1 Weighted Review (reviewed).pdf"
        )
        template_path = (
            base
            / "DaydreamEdu"
            / "Singapore Primary English"
            / "winston.ry.meng@gmail.com"
            / "P6"
            / "Exam"
            / "_c_P6 English Term 1 Weighted Review.pdf"
        )
        _touch(goodnotes_main)
        _touch(template_path)

        mgr.register_file(goodnotes_main, file_type="main", doc_type="exam", subject="english")
        template = mgr.register_file(template_path, file_type="main", doc_type="exam", subject="english", is_template=False)

        outcome = mgr.link_goodnotes_template_for_file(goodnotes_main, auto_fix_template=True)

        assert outcome.linked is True
        assert outcome.auto_fixed_template is True
        assert mgr.get_file(template.id).is_template is True


def test_link_goodnotes_template_for_file_fails_when_resolved_template_not_registered():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db_path = base / "registry.db"
        mgr = PdfFileManager(db_path=str(db_path))

        goodnotes_main = (
            base
            / "GoodNotes"
            / "Singapore Primary Math"
            / "winston.ry.meng@gmail.com"
            / "P6"
            / "Exam"
            / "_c_p6.math.wa1.1 (attempt).pdf"
        )
        template_path = (
            base
            / "DaydreamEdu"
            / "Singapore Primary Math"
            / "P6"
            / "Exam"
            / "_c_p6.math.wa1.1.pdf"
        )
        _touch(goodnotes_main)
        _touch(template_path)

        mgr.register_file(goodnotes_main, file_type="main", doc_type="exam", subject="math")

        with pytest.raises(NotFoundError) as exc:
            mgr.link_goodnotes_template_for_file(goodnotes_main)
        assert "exists on disk but is not registered" in str(exc.value)


def test_link_goodnotes_template_for_file_is_idempotent_for_same_template():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db_path = base / "registry.db"
        mgr = PdfFileManager(db_path=str(db_path))

        goodnotes_main = (
            base
            / "GoodNotes"
            / "Singapore Primary Science"
            / "winston.ry.meng@gmail.com"
            / "P6"
            / "Exam"
            / "_c_P6 Science Weighted Review 1 (reviewed).pdf"
        )
        template_path = (
            base
            / "DaydreamEdu"
            / "Singapore Primary Science"
            / "winston.ry.meng@gmail.com"
            / "P6"
            / "Exam"
            / "_c_P6 Science Weighted Review 1.pdf"
        )
        _touch(goodnotes_main)
        _touch(template_path)

        completed = mgr.register_file(goodnotes_main, file_type="main", doc_type="exam", subject="science")
        template = mgr.register_file(template_path, file_type="main", doc_type="exam", subject="science", is_template=True)
        mgr.link_to_template(completed.id, template.id)

        outcome = mgr.link_goodnotes_template_for_file(goodnotes_main)

        assert outcome.linked is False
        assert outcome.already_linked is True
        assert "already linked" in (outcome.message or "")


def test_link_goodnotes_templates_for_root_dry_run_reports_actions():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db_path = base / "registry.db"
        mgr = PdfFileManager(db_path=str(db_path))

        root = base / "GoodNotes" / "Singapore Primary Chinese" / "winston.ry.meng@gmail.com" / "P6" / "Exam"
        goodnotes_main = root / "_c_p6.chinese.wa1.1 (attempt).pdf"
        template_path = (
            base
            / "DaydreamEdu"
            / "Singapore Primary Chinese"
            / "P6"
            / "Exam"
            / "_c_p6.chinese.wa1.1.pdf"
        )
        _touch(goodnotes_main)
        _touch(template_path)

        mgr.register_file(goodnotes_main, file_type="main", doc_type="exam", subject="chinese")
        mgr.register_file(template_path, file_type="main", doc_type="exam", subject="chinese", is_template=False)

        outcomes = mgr.link_goodnotes_templates_for_root(root, dry_run=True)

        assert len(outcomes) == 1
        assert outcomes[0].dry_run is True
        assert outcomes[0].linked is False
        assert outcomes[0].message == "Would auto-fix resolved template is_template and link"
