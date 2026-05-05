from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ai_study_buddy.learning_db.connection import default_context_root, get_connection
from ai_study_buddy.learning_db.dual_write import maybe_dual_write_snapshot
from ai_study_buddy.learning_db.import_context_json import run_import
from ai_study_buddy.learning_db.migrate import apply_migrations


def _copy_one_file_question_info_sample(tmp_path: Path) -> tuple[Path, Path]:
    source_root = default_context_root() / "file_question_info"
    if not source_root.exists():
        pytest.skip("file_question_info context root not available")
    samples = sorted(source_root.rglob("question_sections.json"))
    if not samples:
        pytest.skip("no file_question_info question_sections.json sample found")

    sample = samples[0]
    context_root = tmp_path / "context"
    dest = context_root / sample.relative_to(default_context_root())
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sample, dest)
    return context_root, dest


def test_import_file_question_info_family(tmp_path: Path) -> None:
    context_root, _ = _copy_one_file_question_info_sample(tmp_path)
    db_path = tmp_path / "study_buddy.db"
    apply_migrations(db_path=db_path)

    summaries = run_import(
        db_path=db_path,
        context_root=context_root,
        dry_run=False,
        limit=None,
        artifact_family="file_question_info",
        retry_quarantine=False,
        retry_status="open",
        retry_failure_stage=None,
    )

    conn = get_connection(db_path)
    try:
        runs = int(conn.execute("SELECT COUNT(*) AS c FROM file_question_info_runs").fetchone()["c"])
        sections = int(conn.execute("SELECT COUNT(*) AS c FROM file_question_info_sections").fetchone()["c"])
        items = int(conn.execute("SELECT COUNT(*) AS c FROM file_question_info_items").fetchone()["c"])
        quarantine_open = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM import_quarantine WHERE artifact_family='file_question_info' AND status='open'"
            ).fetchone()["c"]
        )
    finally:
        conn.close()

    assert summaries["file_question_info"].scanned == 1
    assert runs == 1
    assert sections >= 1
    assert items >= 1
    assert quarantine_open == 0


def test_dual_write_snapshot_file_question_info(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_DUAL_WRITE", "1")
    monkeypatch.setenv("LEARNING_DB_STRICT_DUAL_WRITE", "1")

    context_root, snapshot_path = _copy_one_file_question_info_sample(tmp_path)
    db_path = tmp_path / "study_buddy.db"
    apply_migrations(db_path=db_path)

    ok = maybe_dual_write_snapshot(
        family="file_question_info",
        snapshot_path=snapshot_path,
        context_root=context_root,
        db_path=db_path,
    )
    assert ok is True

    conn = get_connection(db_path)
    try:
        run_row = conn.execute(
            "SELECT run_id, raw_json FROM file_question_info_runs LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    assert run_row is not None
    payload = json.loads(str(run_row["raw_json"]))
    assert payload.get("schema_version")
