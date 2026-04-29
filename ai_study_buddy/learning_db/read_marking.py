"""Read latest marking-result references from SQLite (Phase 2)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Literal

from ai_study_buddy.marking.core.artifact_lookup import (
    MarkingArtifactRef,
    _as_utc_epoch,
    _build_report_path,
    _parse_created_at,
)
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile

MatchCondition = Literal["json_only", "json_and_report"]


def find_marking_artifact_refs_from_db(
    *,
    completion_file: PdfFile,
    student_slug: str,
    completion_path: str,
    completion_student_email: str | None,
    match_condition: MatchCondition,
    context_root: Path,
) -> list[MarkingArtifactRef]:
    """Return marking artifact refs from ``marking_artifacts``, matching filesystem semantics."""

    completion_id = completion_file.id
    student_id = completion_file.student_id
    if not student_id:
        return []

    try:
        from ai_study_buddy.learning_db.connection import get_connection
    except ImportError:
        return []

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT artifact_path, created_at, attempt_file_id, attempt_file_path
            FROM marking_artifacts
            WHERE student_id = ? AND is_deleted = 0
            ORDER BY created_at DESC, artifact_path ASC
            """,
            (student_id,),
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()

    matches: list[tuple[datetime, Path, Path]] = []

    for row in rows:
        rel_path = str(row["artifact_path"])
        if not _row_matches_completion(
            row=row,
            completion_id=completion_id,
            completion_path=completion_path,
        ):
            continue

        json_path = (context_root / rel_path).resolve(strict=False)
        report_path = _build_report_path(
            json_path=json_path,
            context_root=context_root,
            student_slug=student_slug,
        )
        if match_condition == "json_and_report" and not report_path.exists():
            continue

        created_at = _parse_created_at(row["created_at"])
        matches.append((created_at, json_path, report_path))

    matches.sort(
        key=lambda row: (
            -_as_utc_epoch(row[0]),
            row[1].as_posix(),
        )
    )
    return [
        MarkingArtifactRef(marking_result_json=json_path, learning_report_md=report_path)
        for _, json_path, report_path in matches
    ]


def _row_matches_completion(*, row: sqlite3.Row, completion_id: str, completion_path: str) -> bool:
    attempt_file_id = row["attempt_file_id"]
    if isinstance(attempt_file_id, str) and attempt_file_id.strip():
        return attempt_file_id.strip() == completion_id

    attempt_file_path = row["attempt_file_path"]
    if isinstance(attempt_file_path, str) and attempt_file_path.strip():
        return _normalize_db_path(attempt_file_path) == completion_path
    return False


def _normalize_db_path(path: str) -> str:
    return str(Path(path).expanduser().resolve(strict=False))
