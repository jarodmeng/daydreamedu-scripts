"""DB-only canonical projection (JSON export off path)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_study_buddy.learning_db.connection import get_connection
from ai_study_buddy.learning_db.dual_write import maybe_dual_write_from_canonical
from ai_study_buddy.learning_db.migrate import apply_migrations


def _minimal_valid_marking_payload() -> dict:
    root = Path(__file__).resolve().parents[2] / "marking" / "tests" / "fixtures" / "marking_result_v1_5" / "valid_minimal.json"
    data = json.loads(root.read_text(encoding="utf-8"))
    data["created_at"] = "2026-05-10T09:00:00+08:00"
    data["updated_at"] = "2026-05-10T09:00:00+08:00"
    ctx = data["context"]
    ctx["student_id"] = "emma"
    ctx["student_name"] = "Emma"
    ctx["subject_context"] = "singapore_primary_science"
    ctx["attempt_file_id"] = "id-db-only"
    ctx["attempt_file_path"] = "/tmp/db-only.pdf"
    ctx["template_file_id"] = "tid"
    ctx["template_file_path"] = "/tmp/t.pdf"
    ctx["unit_file_id"] = "tid"
    ctx["unit_file_path"] = "/tmp/t.pdf"
    ctx["unit_label"] = "U"
    ctx["answer_file_id"] = "aid"
    ctx["answer_file_path"] = "/tmp/a.pdf"
    ctx["marking_asset"] = "marking_assets/emma/singapore_primary_science/db_only"
    ctx["template_attempt_group_id"] = "emma::tid"
    return data


def test_dual_write_from_canonical_without_json_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_DUAL_WRITE", "1")
    monkeypatch.setenv("LEARNING_DB_STRICT_DUAL_WRITE", "0")
    db_path = tmp_path / "s.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    apply_migrations(db_path=db_path)

    payload = _minimal_valid_marking_payload()
    text = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    rel = "marking_results/emma/singapore_primary_science/db_only_run.json"

    assert maybe_dual_write_from_canonical(
        family="marking_result",
        rel_path=rel,
        canonical_snapshot_text=text,
        db_path=db_path,
    ) is True

    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT artifact_path FROM marking_artifacts WHERE artifact_path = ?",
            (rel,),
        ).fetchone()
        assert row is not None
    finally:
        conn.close()
