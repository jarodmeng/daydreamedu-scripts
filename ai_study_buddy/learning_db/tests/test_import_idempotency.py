"""Phase 1 / checklist: importer is idempotent — second run keeps entity row counts stable."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ai_study_buddy.learning_db.connection import get_connection
from ai_study_buddy.learning_db.import_context_json import run_import
from ai_study_buddy.learning_db.migrate import apply_migrations
from ai_study_buddy.learning_db.repository import now_iso
from ai_study_buddy.learning_db.tests.fixtures import _minimal_mr


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _marking_projection_counts(db_path: Path) -> dict[str, int]:
    """Row counts that must be identical across two unchanged imports (excludes append-only audit tables)."""

    conn = get_connection(db_path)
    try:
        return {
            "marking_artifacts": int(conn.execute("SELECT COUNT(*) FROM marking_artifacts").fetchone()[0]),
            "marking_question_results": int(
                conn.execute("SELECT COUNT(*) FROM marking_question_results").fetchone()[0]
            ),
            "marking_question_page_map": int(
                conn.execute("SELECT COUNT(*) FROM marking_question_page_map").fetchone()[0]
            ),
            "import_identity_map": int(conn.execute("SELECT COUNT(*) FROM import_identity_map").fetchone()[0]),
            "open_quarantine": int(
                conn.execute("SELECT COUNT(*) FROM import_quarantine WHERE status='open'").fetchone()[0]
            ),
        }
    finally:
        conn.close()


def test_double_import_stable_row_counts(tmp_path: Path) -> None:
    ctx = tmp_path / "context"
    db = tmp_path / "study_buddy.db"
    apply_migrations(db_path=db)

    payload = _minimal_mr("attempt-idem-1", "emma", "singapore_primary_science")
    _write_json(ctx / "marking_results" / "emma" / "singapore_primary_science" / "idem.json", payload)

    common = dict(
        db_path=db,
        context_root=ctx,
        dry_run=False,
        limit=None,
        artifact_family="marking_result",
        retry_quarantine=False,
        retry_status="open",
        retry_failure_stage=None,
        student_id=None,
        subject_context=None,
        path_prefix=None,
    )

    s1 = run_import(**common)
    c1 = _marking_projection_counts(db)

    s2 = run_import(**common)
    c2 = _marking_projection_counts(db)

    assert c1 == c2, f"row counts diverged: first={c1} second={c2}"
    assert c1["marking_artifacts"] == 1
    assert c1["open_quarantine"] == 0

    # Second pass should update existing rows, not insert new primary keys
    assert s2["marking_result"].imported == 0
    assert s2["marking_result"].updated >= 1


def test_changed_content_same_path_updates_existing_artifact(tmp_path: Path) -> None:
    ctx = tmp_path / "context"
    db = tmp_path / "study_buddy.db"
    apply_migrations(db_path=db)

    path = ctx / "marking_results" / "emma" / "singapore_primary_science" / "idem-update.json"
    payload = _minimal_mr("attempt-idem-2", "emma", "singapore_primary_science")
    _write_json(path, payload)

    common = dict(
        db_path=db,
        context_root=ctx,
        dry_run=False,
        limit=None,
        artifact_family="marking_result",
        retry_quarantine=False,
        retry_status="open",
        retry_failure_stage=None,
        student_id=None,
        subject_context=None,
        path_prefix=None,
    )
    run_import(**common)

    payload["summary"]["earned_marks"] = 0
    payload["summary"]["percentage"] = 0.0
    payload["summary"]["overall_assessment"] = "retry"
    payload["question_results"][0]["earned_marks"] = 0
    payload["question_results"][0]["outcome"] = "wrong"
    _write_json(path, payload)

    s2 = run_import(**common)
    conn = get_connection(db)
    try:
        artifact_rows = int(conn.execute("SELECT COUNT(*) FROM marking_artifacts").fetchone()[0])
        open_quarantine = int(conn.execute("SELECT COUNT(*) FROM import_quarantine WHERE status='open'").fetchone()[0])
        row = conn.execute(
            "SELECT summary_earned_marks FROM marking_artifacts WHERE artifact_path=?",
            ("marking_results/emma/singapore_primary_science/idem-update.json",),
        ).fetchone()
    finally:
        conn.close()

    assert artifact_rows == 1
    assert open_quarantine == 0
    assert row is not None
    assert float(row["summary_earned_marks"]) == 0.0
    assert s2["marking_result"].updated >= 1


def test_stale_identity_map_hash_is_rebound_to_existing_path_identity(tmp_path: Path) -> None:
    ctx = tmp_path / "context"
    db = tmp_path / "study_buddy.db"
    apply_migrations(db_path=db)

    path = ctx / "marking_results" / "emma" / "singapore_primary_science" / "idem-rebind.json"
    payload = _minimal_mr("attempt-idem-3", "emma", "singapore_primary_science")
    _write_json(path, payload)

    common = dict(
        db_path=db,
        context_root=ctx,
        dry_run=False,
        limit=None,
        artifact_family="marking_result",
        retry_quarantine=False,
        retry_status="open",
        retry_failure_stage=None,
        student_id=None,
        subject_context=None,
        path_prefix=None,
    )
    run_import(**common)

    payload["summary"]["earned_marks"] = 0
    payload["summary"]["percentage"] = 0.0
    payload["question_results"][0]["earned_marks"] = 0
    payload["question_results"][0]["outcome"] = "wrong"
    _write_json(path, payload)
    source_hash = hashlib.sha256(json.dumps(payload).encode("utf-8")).hexdigest()

    conn = get_connection(db)
    try:
        existing = conn.execute(
            "SELECT artifact_id FROM marking_artifacts WHERE artifact_path=?",
            ("marking_results/emma/singapore_primary_science/idem-rebind.json",),
        ).fetchone()
        assert existing is not None
        conn.execute(
            """
            INSERT INTO import_identity_map(
                map_id, artifact_family, source_path, source_content_hash, artifact_id, first_seen_at, last_seen_at
            ) VALUES (?, 'marking_result', ?, ?, ?, ?, ?)
            """,
            (
                "stale-map-id",
                "marking_results/emma/singapore_primary_science/idem-rebind.json",
                source_hash,
                "stale-artifact-id",
                now_iso(),
                now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    run_import(**common)
    conn = get_connection(db)
    try:
        open_quarantine = int(conn.execute("SELECT COUNT(*) FROM import_quarantine WHERE status='open'").fetchone()[0])
        rebound = conn.execute(
            """
            SELECT artifact_id FROM import_identity_map
            WHERE artifact_family='marking_result' AND source_path=? AND source_content_hash=?
            """,
            ("marking_results/emma/singapore_primary_science/idem-rebind.json", source_hash),
        ).fetchone()
    finally:
        conn.close()

    assert open_quarantine == 0
    assert rebound is not None
    assert str(rebound["artifact_id"]) == str(existing["artifact_id"])
