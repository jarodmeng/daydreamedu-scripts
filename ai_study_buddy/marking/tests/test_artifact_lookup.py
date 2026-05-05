from __future__ import annotations

import json
from pathlib import Path
import tempfile

import pytest

from ai_study_buddy.marking import find_marking_artifacts_for_attempt
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n% mock pdf\n")
    return path


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _payload(*, attempt_file_id: str | None, attempt_file_path: str, created_at: str) -> dict:
    context: dict[str, object] = {"attempt_file_path": attempt_file_path}
    if attempt_file_id is not None:
        context["attempt_file_id"] = attempt_file_id
    return {
        "created_at": created_at,
        "context": context,
    }


def test_lookup_student_scoped_sorted_and_condition_filtered(monkeypatch: pytest.MonkeyPatch) -> None:
    # These tests exercise the filesystem scan behavior. Force DB reads off so the
    # lookup doesn't depend on a configured study_buddy.db in test runs.
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        manager = PdfFileManager(db_path=base / "registry.db")
        manager.add_student(id="emma", name="Emma", email="emma@example.com")
        manager.add_student(id="noah", name="Noah", email="noah@example.com")

        attempt_path = _touch(
            base
            / "GoodNotes"
            / "Singapore Primary Science"
            / "emma@example.com"
            / "P6"
            / "Unit"
            / "_c_unit_1_attempt.pdf"
        )
        attempt = manager.register_file(
            attempt_path,
            file_type="main",
            doc_type="book",
            student_id="emma",
            is_template=False,
        )

        context_root = base / "context"
        emma_slug = "emma"
        noah_slug = "noah"

        early = _write_json(
            context_root / "marking_results" / emma_slug / "science" / "run_c.json",
            _payload(
                attempt_file_id=attempt.id,
                attempt_file_path=str(attempt_path),
                created_at="2026-04-18T10:00:00Z",
            ),
        )
        newest_a = _write_json(
            context_root / "marking_results" / emma_slug / "science" / "run_a.json",
            _payload(
                attempt_file_id=attempt.id,
                attempt_file_path=str(attempt_path),
                created_at="2026-04-19T11:00:00Z",
            ),
        )
        newest_b = _write_json(
            context_root / "marking_results" / emma_slug / "science" / "run_b.json",
            _payload(
                attempt_file_id=attempt.id,
                attempt_file_path=str(attempt_path),
                created_at="2026-04-19T11:00:00Z",
            ),
        )
        _write_json(
            context_root / "marking_results" / noah_slug / "science" / "other_student.json",
            _payload(
                attempt_file_id=attempt.id,
                attempt_file_path=str(attempt_path),
                created_at="2026-04-20T11:00:00Z",
            ),
        )
        _write_json(
            context_root / "marking_results" / emma_slug / "science" / "broken.json",
            {"created_at": "2026-04-19T11:00:00Z", "context": "invalid"},
        )
        _write_json(
            context_root / "marking_results" / emma_slug / "science" / "malformed.json",
            {"context": {"attempt_file_id": attempt.id, "attempt_file_path": str(attempt_path)}},
        ).write_text("{not-json", encoding="utf-8")

        report_for_a = (
            context_root
            / "learning_reports"
            / emma_slug
            / "science"
            / "run_a - Marking Report.md"
        )
        report_for_a.parent.mkdir(parents=True, exist_ok=True)
        report_for_a.write_text("# report", encoding="utf-8")

        refs = find_marking_artifacts_for_attempt(
            attempt.id,
            manager=manager,
            context_root=context_root,
        )
        assert [r.marking_result_json for r in refs] == [newest_a, newest_b, early]
        assert refs[0].learning_report_md == report_for_a
        assert refs[1].learning_report_md.name == "run_b - Marking Report.md"

        refs_with_report = find_marking_artifacts_for_attempt(
            attempt.id,
            match_condition="json_and_report",
            manager=manager,
            context_root=context_root,
        )
        assert [r.marking_result_json for r in refs_with_report] == [newest_a]


def test_lookup_path_fallback_only_when_attempt_file_id_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        manager = PdfFileManager(db_path=base / "registry.db")
        manager.add_student(id="emma", name="Emma", email="emma@example.com")

        attempt_path = _touch(
            base
            / "GoodNotes"
            / "Singapore Primary Math"
            / "emma@example.com"
            / "P4"
            / "Unit"
            / "_c_wa.pdf"
        )
        attempt = manager.register_file(
            attempt_path,
            file_type="main",
            doc_type="book",
            student_id="emma",
            is_template=False,
        )

        context_root = base / "context"
        matched = _write_json(
            context_root / "marking_results" / "emma" / "math" / "legacy_no_id.json",
            _payload(
                attempt_file_id=None,
                attempt_file_path=str(attempt_path.resolve()),
                created_at="2026-04-19T10:00:00Z",
            ),
        )
        _write_json(
            context_root / "marking_results" / "emma" / "math" / "mismatch_id.json",
            _payload(
                attempt_file_id="some-other-id",
                attempt_file_path=str(attempt_path.resolve()),
                created_at="2026-04-19T11:00:00Z",
            ),
        )

        refs = find_marking_artifacts_for_attempt(
            attempt.id,
            manager=manager,
            context_root=context_root,
        )
        assert [r.marking_result_json for r in refs] == [matched]


def test_lookup_requires_manager_for_student_scoped_scan() -> None:
    with pytest.raises(ValueError) as exc:
        find_marking_artifacts_for_attempt("/tmp/example.pdf", manager=None)
    assert "requires manager for student-scoped lookup" in str(exc.value)


def test_lookup_rejects_invalid_match_condition() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        manager = PdfFileManager(db_path=base / "registry.db")
        manager.add_student(id="emma", name="Emma", email="emma@example.com")
        attempt_path = _touch(base / "GoodNotes" / "x" / "emma@example.com" / "_c_attempt.pdf")
        attempt = manager.register_file(
            attempt_path,
            file_type="main",
            doc_type="book",
            student_id="emma",
            is_template=False,
        )
        with pytest.raises(ValueError) as exc:
            find_marking_artifacts_for_attempt(
                attempt.id,
                match_condition="both",  # type: ignore[arg-type]
                manager=manager,
                context_root=base / "context",
            )
        assert "match_condition must be" in str(exc.value)
