"""Tests for registry-derived completion series."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ai_study_buddy.pdf_file_manager.completion_series import (
    build_completion_series,
    series_id_for,
    slugify_student,
)
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

from .constants import STUDENT_DISPLAY_NAME, STUDENT_FOLDER_EMAIL


def _register_completion(
    mgr: PdfFileManager,
    tmpdir: Path,
    *,
    name: str,
    student_id: str = "winston",
) -> str:
    path = (
        tmpdir
        / "DaydreamEdu"
        / "completion"
        / "english"
        / STUDENT_FOLDER_EMAIL
        / "P6"
        / "Exercise"
        / name
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.0\n")
    f = mgr.register_file(
        path,
        file_type="main",
        doc_type="exercise",
        subject="english",
        is_template=False,
        student_id=student_id,
    )
    return f.id


def _register_template(mgr: PdfFileManager, tmpdir: Path, *, name: str) -> str:
    path = tmpdir / "DaydreamEdu" / "template" / "english" / "P6" / "Exercise" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.0\n")
    f = mgr.register_file(
        path,
        file_type="main",
        doc_type="exercise",
        subject="english",
        is_template=True,
    )
    return f.id


def test_slugify_student_matches_marking_rules():
    from ai_study_buddy.marking.core.artifact_paths import slugify_student as marking_slug

    assert slugify_student("winston", "Winston") == marking_slug("winston", "Winston")
    assert slugify_student("winston", "Winston") == "winston"


def test_series_id_for_student():
    assert series_id_for("winston", "Winston", "tpl-1") == "winston::tpl-1"


def test_get_completion_series_single_member():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        db = tmpdir / "registry.db"
        mgr = PdfFileManager(db_path=str(db))
        mgr.add_student("winston", STUDENT_DISPLAY_NAME, STUDENT_FOLDER_EMAIL)
        tpl_id = _register_template(mgr, tmpdir, name="_c_unit.pdf")
        c1 = _register_completion(mgr, tmpdir, name="_c_unit_pass1.pdf")
        mgr.link_to_template(c1, tpl_id)

        series = mgr.get_completion_series("winston", tpl_id)
        assert series is not None
        assert series.attempt_count == 1
        assert series.members[0].attempt_sequence == 1
        assert series.series_id == f"winston::{tpl_id}"


def test_get_completion_series_two_members_ordered_by_added_at_then_path():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        db = tmpdir / "registry.db"
        mgr = PdfFileManager(db_path=str(db))
        mgr.add_student("winston", STUDENT_DISPLAY_NAME, STUDENT_FOLDER_EMAIL)
        tpl_id = _register_template(mgr, tmpdir, name="_c_unit.pdf")
        c_first = _register_completion(mgr, tmpdir, name="_c_a_first.pdf")
        c_second = _register_completion(mgr, tmpdir, name="_c_b_second.pdf")
        mgr.link_to_template(c_first, tpl_id)
        mgr.link_to_template(c_second, tpl_id)

        conn = mgr._get_connection()
        conn.execute(
            "UPDATE pdf_files SET added_at = ? WHERE id = ?",
            ("2026-01-01T00:00:00Z", c_first),
        )
        conn.execute(
            "UPDATE pdf_files SET added_at = ? WHERE id = ?",
            ("2026-01-02T00:00:00Z", c_second),
        )
        conn.commit()

        series = mgr.get_completion_series("winston", tpl_id)
        assert series is not None
        assert series.attempt_count == 2
        assert [m.file_id for m in series.members] == [c_first, c_second]
        assert [m.attempt_sequence for m in series.members] == [1, 2]


def test_get_completion_series_isolates_students():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        db = tmpdir / "registry.db"
        mgr = PdfFileManager(db_path=str(db))
        mgr.add_student("winston", STUDENT_DISPLAY_NAME, STUDENT_FOLDER_EMAIL)
        mgr.add_student("other", "Other Student", "other@example.com")
        tpl_id = _register_template(mgr, tmpdir, name="_c_unit.pdf")
        w = _register_completion(mgr, tmpdir, name="_c_winston.pdf", student_id="winston")
        o = _register_completion(
            mgr,
            tmpdir,
            name="_c_other.pdf",
            student_id="other",
        )
        mgr.link_to_template(w, tpl_id)
        mgr.link_to_template(o, tpl_id)

        w_series = mgr.get_completion_series("winston", tpl_id)
        o_series = mgr.get_completion_series("other", tpl_id)
        assert w_series is not None and w_series.attempt_count == 1
        assert o_series is not None and o_series.attempt_count == 1
        assert w_series.members[0].file_id == w
        assert o_series.members[0].file_id == o


def test_next_attempt_sequence_idempotent_for_same_file():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        db = tmpdir / "registry.db"
        mgr = PdfFileManager(db_path=str(db))
        mgr.add_student("winston", STUDENT_DISPLAY_NAME, STUDENT_FOLDER_EMAIL)
        tpl_id = _register_template(mgr, tmpdir, name="_c_unit.pdf")
        c1 = _register_completion(mgr, tmpdir, name="_c_pass1.pdf")
        c2 = _register_completion(mgr, tmpdir, name="_c_pass2.pdf")
        mgr.link_to_template(c1, tpl_id)
        mgr.link_to_template(c2, tpl_id)

        assert mgr.next_attempt_sequence_for_completion(c1) == 1
        assert mgr.next_attempt_sequence_for_completion(c2) == 2
        assert mgr.next_attempt_sequence_for_completion(c1) == 1


def test_get_completion_series_missing_template_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = PdfFileManager(db_path=str(Path(tmp) / "registry.db"))
        assert mgr.get_completion_series("winston", "missing-id") is None


def test_build_completion_series_filters_non_main():
    from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile

    main = PdfFile(
        id="m1",
        name="_c_x.pdf",
        path="/a/_c_x.pdf",
        file_type="main",
        doc_type="exercise",
        student_id="winston",
        subject="english",
        is_template=False,
        size_bytes=1,
        page_count=1,
        has_raw=False,
        metadata=None,
        added_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        notes=None,
    )
    raw = PdfFile(
        id="r1",
        name="_raw_x.pdf",
        path="/a/_raw_x.pdf",
        file_type="raw",
        doc_type="exercise",
        student_id="winston",
        subject="english",
        is_template=False,
        size_bytes=1,
        page_count=1,
        has_raw=False,
        metadata=None,
        added_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        notes=None,
    )
    series = build_completion_series(
        student_id="winston",
        student_name="Winston",
        template_file_id="tpl",
        completions=[main, raw],
    )
    assert series is not None
    assert len(series.members) == 1
    assert series.members[0].file_id == "m1"
