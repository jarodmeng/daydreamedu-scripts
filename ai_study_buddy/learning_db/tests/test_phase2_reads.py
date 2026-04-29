"""Phase 2: DB-backed reads with parity vs filesystem scans."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_study_buddy.learning_db.import_context_json import run_import
from ai_study_buddy.learning_db.migrate import apply_migrations
from ai_study_buddy.learning_db.read_documents import fetch_marking_artifact_raw_json
from ai_study_buddy.learning_db.connection import get_connection
from ai_study_buddy.marking.core.artifact_lookup import find_marking_artifacts_for_attempt
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


@pytest.fixture(autouse=True)
def _unset_learning_db_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEARNING_DB_ENABLE_READS", raising=False)
    monkeypatch.delenv("LEARNING_DB_READ_FALLBACK_FILESYSTEM", raising=False)
    monkeypatch.delenv("STUDY_BUDDY_DB_PATH", raising=False)


def _minimal_valid_payload(*, attempt_id: str, attempt_path: str) -> dict:
    root = Path(__file__).resolve().parents[2] / "marking" / "tests" / "fixtures" / "marking_result_v1_5" / "valid_minimal.json"
    data = json.loads(root.read_text(encoding="utf-8"))
    data["created_at"] = "2026-04-19T11:00:00+08:00"
    data["updated_at"] = "2026-04-19T11:00:00+08:00"
    ctx = data["context"]
    ctx["student_id"] = "emma"
    ctx["student_name"] = "Emma"
    ctx["subject_context"] = "singapore_primary_science"
    ctx["attempt_file_id"] = attempt_id
    ctx["attempt_file_path"] = attempt_path
    ctx["marking_asset"] = "marking_assets/emma/singapore_primary_science/example"
    ctx["template_attempt_group_id"] = "emma::template-1"
    return data


def test_db_reads_par_match_filesystem(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "study_buddy.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    apply_migrations(db_path=db_path)

    manager = PdfFileManager(db_path=tmp_path / "registry.db")
    manager.add_student(id="emma", name="Emma", email="emma@example.com")
    attempt_path = _touch(tmp_path / "attempt.pdf")
    attempt = manager.register_file(
        attempt_path,
        file_type="main",
        doc_type="book",
        student_id="emma",
        is_template=False,
    )

    context_root = tmp_path / "context"
    emma_slug = "emma"
    newest_a = _write_json(
        context_root / "marking_results" / emma_slug / "singapore_primary_science" / "run_a.json",
        _minimal_valid_payload(attempt_id=str(attempt.id), attempt_path=str(attempt_path)),
    )
    data_early = _minimal_valid_payload(attempt_id=str(attempt.id), attempt_path=str(attempt_path))
    data_early["created_at"] = "2026-04-18T10:00:00+08:00"
    data_early["updated_at"] = "2026-04-18T10:00:00+08:00"
    _write_json(context_root / "marking_results" / emma_slug / "singapore_primary_science" / "early.json", data_early)

    run_import(
        db_path=db_path,
        context_root=context_root,
        dry_run=False,
        limit=None,
        artifact_family=None,
        retry_quarantine=False,
        retry_status="open",
        retry_failure_stage=None,
    )

    refs_fs = find_marking_artifacts_for_attempt(
        attempt.id,
        manager=manager,
        context_root=context_root,
    )

    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "1")
    monkeypatch.delenv("LEARNING_DB_READ_FALLBACK_FILESYSTEM", raising=False)

    refs_db = find_marking_artifacts_for_attempt(
        attempt.id,
        manager=manager,
        context_root=context_root,
    )

    assert [r.marking_result_json for r in refs_db] == [r.marking_result_json for r in refs_fs]
    assert refs_db and refs_fs
    assert Path(refs_db[0].marking_result_json).resolve() == newest_a.resolve()


def test_reads_off_ignores_empty_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    apply_migrations(db_path=db_path)
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")

    manager = PdfFileManager(db_path=tmp_path / "registry2.db")
    manager.add_student(id="emma", name="Emma", email=None)
    attempt_path = _touch(tmp_path / "a.pdf")
    attempt = manager.register_file(
        attempt_path,
        file_type="main",
        doc_type="book",
        student_id="emma",
        is_template=False,
    )
    context_root = tmp_path / "ctx"
    _write_json(
        context_root / "marking_results" / "emma" / "sub" / "x.json",
        _payload(attempt_file_id=attempt.id, attempt_file_path=str(attempt_path), created_at="2026-01-01T00:00:00Z"),
    )

    refs = find_marking_artifacts_for_attempt(
        attempt.id,
        manager=manager,
        context_root=context_root,
    )
    assert len(refs) == 1


def test_reads_on_no_fallback_empty_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "e2.db"
    apply_migrations(db_path=db_path)
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "1")
    monkeypatch.setenv("LEARNING_DB_READ_FALLBACK_FILESYSTEM", "0")

    manager = PdfFileManager(db_path=tmp_path / "registry3.db")
    manager.add_student(id="emma", name="Emma", email=None)
    attempt_path = _touch(tmp_path / "b.pdf")
    attempt = manager.register_file(
        attempt_path,
        file_type="main",
        doc_type="book",
        student_id="emma",
        is_template=False,
    )
    context_root = tmp_path / "ctx2"
    _write_json(
        context_root / "marking_results" / "emma" / "sub" / "y.json",
        _payload(attempt_file_id=attempt.id, attempt_file_path=str(attempt_path), created_at="2026-01-01T00:00:00Z"),
    )

    refs = find_marking_artifacts_for_attempt(
        attempt.id,
        manager=manager,
        context_root=context_root,
    )
    assert refs == []


def test_fetch_marking_artifact_reconstructs_from_projection_not_raw_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "study_buddy.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    apply_migrations(db_path=db_path)

    manager = PdfFileManager(db_path=tmp_path / "registry.db")
    manager.add_student(id="emma", name="Emma", email="emma@example.com")
    attempt_path = _touch(tmp_path / "attempt.pdf")
    attempt = manager.register_file(
        attempt_path,
        file_type="main",
        doc_type="book",
        student_id="emma",
        is_template=False,
    )

    context_root = tmp_path / "context"
    rel = "marking_results/emma/singapore_primary_science/run_a.json"
    _write_json(context_root / rel, _minimal_valid_payload(attempt_id=str(attempt.id), attempt_path=str(attempt_path)))
    run_import(
        db_path=db_path,
        context_root=context_root,
        dry_run=False,
        limit=None,
        artifact_family="marking_result",
        retry_quarantine=False,
        retry_status="open",
        retry_failure_stage=None,
    )

    # Poison root raw_json to prove reads come from normalized columns/child tables.
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE marking_artifacts SET raw_json = ? WHERE artifact_path = ?",
            (
                json.dumps(
                    {
                        "created_at": "1900-01-01T00:00:00Z",
                        "context": {"attempt_file_id": "WRONG-FROM-RAW-JSON"},
                    },
                    ensure_ascii=True,
                ),
                rel,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    payload = fetch_marking_artifact_raw_json(rel)
    assert payload is not None
    assert payload.get("created_at") == "2026-04-19T11:00:00+08:00"
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    assert context.get("attempt_file_id") == str(attempt.id)
