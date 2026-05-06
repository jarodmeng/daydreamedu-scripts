"""Phase 3: dual-write from saved JSON snapshots into SQLite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_study_buddy.learning_db.core.connection import get_connection
from ai_study_buddy.learning_db.ingest.dual_write import maybe_dual_write_snapshot
from ai_study_buddy.learning_db.core.migrate import apply_migrations


def _minimal_valid_marking(*, stem: str) -> dict:
    root = Path(__file__).resolve().parents[2] / "marking" / "tests" / "fixtures" / "marking_result_v1_5" / "valid_minimal.json"
    data = json.loads(root.read_text(encoding="utf-8"))
    data["created_at"] = "2026-05-02T11:00:00+08:00"
    data["updated_at"] = "2026-05-02T11:00:00+08:00"
    ctx = data["context"]
    ctx["student_id"] = "emma"
    ctx["student_name"] = "Emma"
    ctx["subject_context"] = "singapore_primary_science"
    ctx["attempt_file_id"] = "a-att"
    ctx["attempt_file_path"] = "/tmp/a.pdf"
    ctx["template_file_id"] = "t-id"
    ctx["template_file_path"] = "/tmp/t.pdf"
    ctx["unit_file_id"] = "t-id"
    ctx["unit_file_path"] = "/tmp/t.pdf"
    ctx["unit_label"] = "U"
    ctx["answer_file_id"] = "ans-id"
    ctx["answer_file_path"] = "/tmp/ans.pdf"
    ctx["marking_asset"] = f"marking_assets/emma/singapore_primary_science/{stem}"
    ctx["template_attempt_group_id"] = "emma::t-id"
    return data


@pytest.fixture(autouse=True)
def _clear_dual(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEARNING_DB_ENABLE_DUAL_WRITE", raising=False)
    monkeypatch.delenv("LEARNING_DB_STRICT_DUAL_WRITE", raising=False)


def test_dual_write_disabled_is_no_op(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_DUAL_WRITE", "0")

    db_path = tmp_path / "study_buddy.db"
    apply_migrations(db_path=db_path)
    ctx_root = tmp_path / "context"
    jpath = ctx_root / "marking_results" / "emma" / "singapore_primary_science" / "solo.json"
    jpath.parent.mkdir(parents=True, exist_ok=True)
    jpath.write_text(json.dumps(_minimal_valid_marking(stem="solo")), encoding="utf-8")

    assert maybe_dual_write_snapshot(
        family="marking_result",
        snapshot_path=jpath,
        context_root=ctx_root,
        db_path=db_path,
    ) is False


def test_maybe_dual_write_persists_marking_result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_DUAL_WRITE", "1")
    monkeypatch.setenv("LEARNING_DB_STRICT_DUAL_WRITE", "0")
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(tmp_path / "study.db"))
    db_path = tmp_path / "study.db"
    apply_migrations(db_path=db_path)

    ctx_root = tmp_path / "context"
    jpath = ctx_root / "marking_results" / "emma" / "singapore_primary_science" / "solo2.json"
    jpath.parent.mkdir(parents=True, exist_ok=True)
    jpath.write_text(json.dumps(_minimal_valid_marking(stem="solo2")), encoding="utf-8")

    assert maybe_dual_write_snapshot(
        family="marking_result",
        snapshot_path=jpath,
        context_root=ctx_root,
        db_path=db_path,
    ) is True

    conn = get_connection(db_path)
    try:
        n = conn.execute("SELECT COUNT(*) AS c FROM marking_artifacts").fetchone()["c"]
        assert int(n) >= 1
    finally:
        conn.close()
