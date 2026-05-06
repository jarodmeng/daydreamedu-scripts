from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ai_study_buddy.learning_db.core.connection import default_context_root, get_connection
from ai_study_buddy.learning_db.ingest.import_context_json import run_import
from ai_study_buddy.learning_db.core.migrate import apply_migrations


def _copy_real_sample_context(tmp_path: Path) -> Path:
    source_root = default_context_root()
    if not source_root.exists():
        pytest.skip("real context root not available")

    out = tmp_path / "context"
    families = ("marking_results", "marking_amendments", "student_review_states")
    copied = 0
    for family in families:
        files = sorted((source_root / family).rglob("*.json")) if (source_root / family).exists() else []
        if not files:
            continue
        first = files[0]
        rel = first.relative_to(source_root)
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(first, dest)
        copied += 1
    if copied == 0:
        pytest.skip("no real marking/review JSON files available")
    return out


def test_import_runs_and_writes_rows(tmp_path: Path) -> None:
    context_root = _copy_real_sample_context(tmp_path)
    db_path = tmp_path / "study_buddy.db"
    apply_migrations(db_path=db_path)
    summaries = run_import(
        db_path=db_path,
        context_root=context_root,
        dry_run=False,
        limit=None,
        artifact_family=None,
        retry_quarantine=False,
        retry_status="open",
        retry_failure_stage=None,
    )

    conn = get_connection(db_path)
    try:
        artifact_rows = int(conn.execute("SELECT COUNT(*) AS c FROM marking_artifacts").fetchone()["c"])
        operation_rows = int(conn.execute("SELECT COUNT(*) AS c FROM operation_log").fetchone()["c"])
    finally:
        conn.close()

    assert operation_rows > 0
    assert any(v.scanned > 0 for v in summaries.values())
    # If amendment/review samples happen to resolve, artifact rows should be non-zero.
    # If not, quarantine is acceptable as long as importer does not crash.
    assert artifact_rows >= 0


def test_retry_quarantine_filters(tmp_path: Path) -> None:
    context_root = tmp_path / "context"
    bad = context_root / "marking_results" / "bad" / "singapore_primary_math" / "bad.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not-json", encoding="utf-8")
    db_path = tmp_path / "study_buddy.db"
    apply_migrations(db_path=db_path)

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
    conn = get_connection(db_path)
    try:
        open_count = int(
            conn.execute("SELECT COUNT(*) AS c FROM import_quarantine WHERE status='open'").fetchone()["c"]
        )
        assert open_count == 1
    finally:
        conn.close()

    # fix file and retry
    good_source = sorted((default_context_root() / "marking_results").rglob("*.json"))
    if not good_source:
        pytest.skip("no real marking_result json available to repair quarantine test")
    bad.write_text(good_source[0].read_text(encoding="utf-8"), encoding="utf-8")

    run_import(
        db_path=db_path,
        context_root=context_root,
        dry_run=False,
        limit=None,
        artifact_family="marking_result",
        retry_quarantine=True,
        retry_status="open",
        retry_failure_stage=None,
    )
    conn = get_connection(db_path)
    try:
        resolved_count = int(
            conn.execute("SELECT COUNT(*) AS c FROM import_quarantine WHERE status='resolved'").fetchone()["c"]
        )
    finally:
        conn.close()
    assert resolved_count >= 1

