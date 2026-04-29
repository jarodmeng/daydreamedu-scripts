"""Failure paths for dual-write: strict vs soft, bad payloads, projection errors, commit abort."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import ai_study_buddy.learning_db.connection as connmod
import ai_study_buddy.learning_db.dual_write as dual_write_mod
from ai_study_buddy.learning_db.dual_write import maybe_dual_write_from_canonical, maybe_dual_write_snapshot
from ai_study_buddy.learning_db.migrate import apply_migrations


def _minimal_valid_marking(*, stem: str) -> dict:
    root = Path(__file__).resolve().parents[2] / "marking" / "tests" / "fixtures" / "marking_result_v1_5" / "valid_minimal.json"
    data = json.loads(root.read_text(encoding="utf-8"))
    data["created_at"] = "2026-05-20T10:00:00+08:00"
    data["updated_at"] = "2026-05-20T10:00:00+08:00"
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
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEARNING_DB_ENABLE_DUAL_WRITE", raising=False)
    monkeypatch.delenv("LEARNING_DB_STRICT_DUAL_WRITE", raising=False)
    monkeypatch.delenv("STUDY_BUDDY_DB_PATH", raising=False)


def test_snapshot_non_object_json_root_strict_unlinks_and_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_DUAL_WRITE", "1")
    monkeypatch.setenv("LEARNING_DB_STRICT_DUAL_WRITE", "1")
    db_path = tmp_path / "x.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    apply_migrations(db_path=db_path)

    ctx = tmp_path / "context"
    jpath = ctx / "marking_results" / "emma" / "singapore_primary_science" / "bad.json"
    jpath.parent.mkdir(parents=True, exist_ok=True)
    jpath.write_text("[1, 2, 3]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON root must be an object"):
        maybe_dual_write_snapshot(
            family="marking_result",
            snapshot_path=jpath,
            context_root=ctx,
            db_path=db_path,
        )
    assert not jpath.exists()


def test_snapshot_non_object_soft_keeps_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_DUAL_WRITE", "1")
    monkeypatch.setenv("LEARNING_DB_STRICT_DUAL_WRITE", "0")
    db_path = tmp_path / "x.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    apply_migrations(db_path=db_path)

    ctx = tmp_path / "context"
    jpath = ctx / "marking_results" / "emma" / "singapore_primary_science" / "bad2.json"
    jpath.parent.mkdir(parents=True, exist_ok=True)
    jpath.write_text("[1]\n", encoding="utf-8")

    assert maybe_dual_write_snapshot(
        family="marking_result",
        snapshot_path=jpath,
        context_root=ctx,
        db_path=db_path,
    ) is False
    assert jpath.exists()


def test_strict_projection_failure_unlinks_valid_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_DUAL_WRITE", "1")
    monkeypatch.setenv("LEARNING_DB_STRICT_DUAL_WRITE", "1")
    db_path = tmp_path / "x.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    apply_migrations(db_path=db_path)

    payload = _minimal_valid_marking(stem="boom")
    text = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    ctx = tmp_path / "context"
    jpath = ctx / "marking_results" / "emma" / "singapore_primary_science" / "boom.json"
    jpath.parent.mkdir(parents=True, exist_ok=True)
    jpath.write_text(text, encoding="utf-8")

    def boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("simulated_projection_failure")

    with patch(
        "ai_study_buddy.learning_db.import_context_json.upsert_marking_result",
        side_effect=boom,
    ):
        with pytest.raises(RuntimeError, match="simulated_projection_failure"):
            maybe_dual_write_snapshot(
                family="marking_result",
                snapshot_path=jpath,
                context_root=ctx,
                db_path=db_path,
            )
    assert not jpath.exists()


def test_soft_projection_failure_keeps_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_DUAL_WRITE", "1")
    monkeypatch.setenv("LEARNING_DB_STRICT_DUAL_WRITE", "0")
    db_path = tmp_path / "x.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    apply_migrations(db_path=db_path)

    payload = _minimal_valid_marking(stem="soft")
    text = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    ctx = tmp_path / "context"
    jpath = ctx / "marking_results" / "emma" / "singapore_primary_science" / "soft.json"
    jpath.parent.mkdir(parents=True, exist_ok=True)
    jpath.write_text(text, encoding="utf-8")

    def boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("simulated_projection_failure")

    with patch(
        "ai_study_buddy.learning_db.import_context_json.upsert_marking_result",
        side_effect=boom,
    ):
        assert maybe_dual_write_snapshot(
            family="marking_result",
            snapshot_path=jpath,
            context_root=ctx,
            db_path=db_path,
        ) is False
    assert jpath.exists()


def test_from_canonical_invalid_marking_schema_soft_returns_false(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LEARNING_DB_ENABLE_DUAL_WRITE", "1")
    monkeypatch.setenv("LEARNING_DB_STRICT_DUAL_WRITE", "0")
    db_path = tmp_path / "x.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    apply_migrations(db_path=db_path)

    bad = {"schema_version": "marking_result.v1.5"}
    text = json.dumps(bad, indent=2, ensure_ascii=True) + "\n"

    assert maybe_dual_write_from_canonical(
        family="marking_result",
        rel_path="marking_results/emma/singapore_primary_science/bad_shape.json",
        canonical_snapshot_text=text,
        db_path=db_path,
    ) is False


def test_commit_failure_leaves_no_committed_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """First ``commit()`` on the dual-write connection raises; transaction rolls back — no artifact rows."""
    monkeypatch.setenv("LEARNING_DB_ENABLE_DUAL_WRITE", "1")
    monkeypatch.setenv("LEARNING_DB_STRICT_DUAL_WRITE", "0")
    db_path = tmp_path / "x.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    apply_migrations(db_path=db_path)

    payload = _minimal_valid_marking(stem="commitfail")
    text = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    ctx = tmp_path / "context"
    jpath = ctx / "marking_results" / "emma" / "singapore_primary_science" / "commitfail.json"
    jpath.parent.mkdir(parents=True, exist_ok=True)
    jpath.write_text(text, encoding="utf-8")

    applied_flaky = False

    def wrapped_get(db_path_arg: Any = None) -> sqlite3.Connection:
        nonlocal applied_flaky
        c = connmod.get_connection(db_path_arg)
        if not applied_flaky:
            applied_flaky = True

            def flaky_commit() -> None:
                raise sqlite3.OperationalError("simulated_commit_failure")

            c.commit = flaky_commit  # type: ignore[method-assign]
        return c

    with patch.object(dual_write_mod, "get_connection", side_effect=wrapped_get):
        assert maybe_dual_write_snapshot(
            family="marking_result",
            snapshot_path=jpath,
            context_root=ctx,
            db_path=db_path,
        ) is False

    conn = connmod.get_connection(db_path)
    try:
        n = int(conn.execute("SELECT COUNT(*) AS c FROM marking_artifacts").fetchone()["c"])
        assert n == 0
    finally:
        conn.close()
    assert jpath.exists()


def test_partial_projection_failure_rolls_back_parent_and_child_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Failure during child inserts rolls back the full dual-write transaction."""
    monkeypatch.setenv("LEARNING_DB_ENABLE_DUAL_WRITE", "1")
    monkeypatch.setenv("LEARNING_DB_STRICT_DUAL_WRITE", "0")
    db_path = tmp_path / "x.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    apply_migrations(db_path=db_path)

    payload = _minimal_valid_marking(stem="txnrollback")
    text = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    ctx = tmp_path / "context"
    jpath = ctx / "marking_results" / "emma" / "singapore_primary_science" / "txnrollback.json"
    jpath.parent.mkdir(parents=True, exist_ok=True)
    jpath.write_text(text, encoding="utf-8")

    class FlakyConn:
        def __init__(self, inner: sqlite3.Connection):
            self._inner = inner
            self._child_inserts = 0

        def execute(self, sql: str, params: Any = ()) -> Any:
            if "INSERT INTO marking_question_results" in sql:
                self._child_inserts += 1
                if self._child_inserts == 1:
                    raise sqlite3.OperationalError("simulated_child_insert_failure")
            return self._inner.execute(sql, params)

        def commit(self) -> None:
            self._inner.commit()

        def rollback(self) -> None:
            self._inner.rollback()

        def close(self) -> None:
            self._inner.close()

    def wrapped_get(db_path_arg: Any = None) -> Any:
        return FlakyConn(connmod.get_connection(db_path_arg))

    with patch.object(dual_write_mod, "get_connection", side_effect=wrapped_get):
        assert maybe_dual_write_snapshot(
            family="marking_result",
            snapshot_path=jpath,
            context_root=ctx,
            db_path=db_path,
        ) is False

    conn = connmod.get_connection(db_path)
    try:
        artifacts = int(conn.execute("SELECT COUNT(*) AS c FROM marking_artifacts").fetchone()["c"])
        results = int(conn.execute("SELECT COUNT(*) AS c FROM marking_question_results").fetchone()["c"])
        page_map = int(conn.execute("SELECT COUNT(*) AS c FROM marking_question_page_map").fetchone()["c"])
        assert artifacts == 0
        assert results == 0
        assert page_map == 0
    finally:
        conn.close()
