"""Phase 3: Mirror canonical marking/review payloads into ``study_buddy.db`` (dual-write).

Two entry points:

* After a UTF-8 JSON file is written under ``context/`` (**``maybe_dual_write_snapshot``** reads bytes from disk — hash matches importer semantics).
* When ``LEARNING_DB_ENABLE_JSON_EXPORT=0`` but dual-write stays on (**``maybe_dual_write_from_canonical``** uses the canonical snapshot **string**, same ``indent=2`` + trailing newline convention as callers).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Literal

from ai_study_buddy.learning_db.config import (
    learning_db_dual_write_enabled,
    learning_db_strict_dual_write,
)
from ai_study_buddy.learning_db.connection import default_db_path, get_connection
from ai_study_buddy.learning_db.migrate import apply_migrations
from ai_study_buddy.learning_db.repository import OperationEvent, validate_actor, write_operation_log

Family = Literal["marking_result", "marking_amendment", "student_review_state", "file_question_info"]

_ACTOR_PRIMARY = validate_actor("script:ai_study_buddy.learning_db.dual_write")
_ACTOR_AUDIT = validate_actor("script:ai_study_buddy.learning_db.dual_write#audit")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _audit_dual_write_failure(
    *,
    family: Family,
    entity_id: str,
    db_path: Path,
    exc: BaseException,
) -> None:
    try:
        apply_migrations(db_path=db_path)
        lc = get_connection(db_path)
        try:
            write_operation_log(
                lc,
                OperationEvent(
                    operation_type="dual_write_snapshot",
                    entity_type=family,
                    entity_id=entity_id,
                    status="failed",
                    actor=_ACTOR_AUDIT,
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                ),
            )
        finally:
            lc.close()
    except Exception:
        pass


def _commit_projection(
    conn: sqlite3.Connection,
    *,
    family: Family,
    rel_path: str,
    payload: dict[str, Any],
    source_hash: str,
    metadata_source_tag: str,
) -> None:
    from ai_study_buddy.learning_db.import_context_json import (
        upsert_file_question_info_run,
        upsert_marking_amendment,
        upsert_marking_result,
        upsert_review_state,
    )

    if family == "marking_result":
        upsert_marking_result(conn, payload=payload, rel_path=rel_path, source_hash=source_hash)
    elif family == "marking_amendment":
        upsert_marking_amendment(conn, payload=payload, rel_path=rel_path, source_hash=source_hash)
    elif family == "student_review_state":
        upsert_review_state(conn, payload=payload, rel_path=rel_path, source_hash=source_hash)
    elif family == "file_question_info":
        upsert_file_question_info_run(conn, payload=payload, rel_path=rel_path, source_hash=source_hash)
    else:  # pragma: no cover
        raise AssertionError(f"unknown family for dual_write: {family}")

    write_operation_log(
        conn,
        OperationEvent(
            operation_type="dual_write_snapshot",
            entity_type=family,
            entity_id=rel_path,
            status="succeeded",
            actor=_ACTOR_PRIMARY,
            metadata={"source": metadata_source_tag},
        ),
    )


def maybe_dual_write_from_canonical(
    *,
    family: Family,
    rel_path: str,
    canonical_snapshot_text: str,
    db_path: Path | str | None = None,
) -> bool:
    """Upsert SQLite from canonical UTF-8 text (typically ``indent=2`` + trailing newline).

    Use when **no** filesystem snapshot exists (``LEARNING_DB_ENABLE_JSON_EXPORT=0`` with dual-write on).

    No JSON file is touched; strict rollback never unlinks paths (there is none).
    """

    if not learning_db_dual_write_enabled():
        return False

    resolved_db = Path(db_path).expanduser().resolve() if db_path else default_db_path()
    payload = json.loads(canonical_snapshot_text)
    if not isinstance(payload, dict):
        err = ValueError("dual_write: JSON root must be an object")
        _audit_dual_write_failure(family=family, entity_id=rel_path, db_path=resolved_db, exc=err)
        if learning_db_strict_dual_write():
            raise err
        return False

    apply_migrations(db_path=resolved_db)
    source_hash = _sha256_text(canonical_snapshot_text)

    conn: sqlite3.Connection | None = None

    try:
        conn = get_connection(resolved_db)
        conn.execute("BEGIN IMMEDIATE")
        _commit_projection(
            conn,
            family=family,
            rel_path=rel_path,
            payload=payload,
            source_hash=source_hash,
            metadata_source_tag="canonical_text_dual_write_without_json_snapshot",
        )
        conn.commit()
        return True
    except BaseException as exc:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass

        _audit_dual_write_failure(family=family, entity_id=rel_path, db_path=resolved_db, exc=exc)

        if learning_db_strict_dual_write():
            raise exc
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def maybe_dual_write_snapshot(
    *,
    family: Family,
    snapshot_path: Path,
    context_root: str | Path,
    db_path: Path | str | None = None,
) -> bool:
    """Upsert SQLite after ``snapshot_path`` was written relative to ``context_root``."""

    if not learning_db_dual_write_enabled():
        return False

    ctx = Path(context_root).expanduser().resolve()
    resolved_json = Path(snapshot_path).expanduser().resolve()
    rel_path = resolved_json.relative_to(ctx).as_posix()
    resolved_db = Path(db_path).expanduser().resolve() if db_path else default_db_path()

    raw_text = resolved_json.read_text(encoding="utf-8")
    payload = json.loads(raw_text)
    if not isinstance(payload, dict):
        err = ValueError("dual_write: JSON root must be an object")
        _audit_dual_write_failure(family=family, entity_id=rel_path, db_path=resolved_db, exc=err)
        if learning_db_strict_dual_write():
            if resolved_json.exists():
                resolved_json.unlink(missing_ok=True)
            raise err
        return False

    apply_migrations(db_path=resolved_db)
    source_hash = _sha256_text(raw_text)

    conn: sqlite3.Connection | None = None

    try:
        conn = get_connection(resolved_db)
        conn.execute("BEGIN IMMEDIATE")
        _commit_projection(
            conn,
            family=family,
            rel_path=rel_path,
            payload=payload,
            source_hash=source_hash,
            metadata_source_tag="after_json_snapshot_write",
        )
        conn.commit()
        return True
    except BaseException as exc:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass

        _audit_dual_write_failure(family=family, entity_id=rel_path, db_path=resolved_db, exc=exc)

        if learning_db_strict_dual_write():
            try:
                resolved_json.unlink(missing_ok=True)
            except OSError:
                pass
            raise exc
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
