from __future__ import annotations

from pathlib import Path

from ai_study_buddy.learning_db.core.connection import get_connection
from ai_study_buddy.learning_db.core.migrate import apply_migrations


def test_apply_migrations_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "study_buddy.db"
    first = apply_migrations(db_path=db_path)
    second = apply_migrations(db_path=db_path)

    assert first
    assert second == []

    conn = get_connection(db_path)
    try:
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()

    assert "marking_artifacts" in tables
    assert "operation_log" in tables
    assert "import_identity_map" in tables
    assert "import_quarantine" in tables
    assert "file_question_info_runs" in tables
    assert "file_question_info_sections" in tables
    assert "file_question_info_items" in tables
