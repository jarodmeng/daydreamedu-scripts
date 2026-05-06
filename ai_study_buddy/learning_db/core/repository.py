from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
import sqlite3
from zoneinfo import ZoneInfo

SINGAPORE_TZ = ZoneInfo("Asia/Singapore")

ACTOR_PREFIXES = ("user:", "script:", "agent:", "system:")


def now_iso() -> str:
    return datetime.now(SINGAPORE_TZ).isoformat()


def new_id() -> str:
    uuid7 = getattr(uuid, "uuid7", None)
    if callable(uuid7):
        return str(uuid7())
    return str(uuid.uuid4())


def validate_actor(actor: str) -> str:
    value = (actor or "").strip()
    if not value:
        return "system:unknown"
    if not value.isascii() or len(value) > 128:
        return "system:unknown"
    if value.startswith(ACTOR_PREFIXES):
        return value
    return "system:unknown"


@dataclass
class OperationEvent:
    operation_type: str
    entity_type: str | None
    entity_id: str | None
    status: str
    actor: str
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict | None = None


def write_operation_log(conn: sqlite3.Connection, event: OperationEvent) -> str:
    operation_id = new_id()
    conn.execute(
        """
        INSERT INTO operation_log(
            operation_id, occurred_at, actor, operation_type, entity_type, entity_id,
            status, error_code, error_message, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            operation_id,
            now_iso(),
            validate_actor(event.actor),
            event.operation_type,
            event.entity_type,
            event.entity_id,
            event.status,
            event.error_code,
            event.error_message,
            json.dumps(event.metadata or {}, ensure_ascii=True),
        ),
    )
    return operation_id


def get_or_create_identity_map(
    conn: sqlite3.Connection,
    *,
    artifact_family: str,
    source_path: str,
    source_content_hash: str,
    suggested_artifact_id: str | None = None,
) -> str:
    row = conn.execute(
        """
        SELECT map_id, artifact_id FROM import_identity_map
        WHERE artifact_family = ? AND source_path = ? AND source_content_hash = ?
        """,
        (artifact_family, source_path, source_content_hash),
    ).fetchone()
    if row:
        existing_artifact_id = str(row["artifact_id"])
        if suggested_artifact_id and existing_artifact_id != suggested_artifact_id:
            # Path-level identity is authoritative for mutable JSON at a stable path.
            conn.execute(
                """
                UPDATE import_identity_map
                SET artifact_id = ?, last_seen_at = ?
                WHERE map_id = ?
                """,
                (suggested_artifact_id, now_iso(), str(row["map_id"])),
            )
            return suggested_artifact_id
        conn.execute(
            """
            UPDATE import_identity_map
            SET last_seen_at = ?
            WHERE artifact_family = ? AND source_path = ? AND source_content_hash = ?
            """,
            (now_iso(), artifact_family, source_path, source_content_hash),
        )
        return existing_artifact_id

    artifact_id = suggested_artifact_id or new_id()
    seen_at = now_iso()
    conn.execute(
        """
        INSERT INTO import_identity_map(
            map_id, artifact_family, source_path, source_content_hash, artifact_id, first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (new_id(), artifact_family, source_path, source_content_hash, artifact_id, seen_at, seen_at),
    )
    return artifact_id


def upsert_quarantine(
    conn: sqlite3.Connection,
    *,
    artifact_family: str,
    source_path: str,
    source_content_hash: str | None,
    schema_version_detected: str | None,
    failure_stage: str,
    error_code: str,
    error_message: str,
    raw_payload_json: str | None,
) -> str:
    now = now_iso()
    row = conn.execute(
        """
        SELECT quarantine_id, retry_count FROM import_quarantine
        WHERE artifact_family = ? AND source_path = ? AND failure_stage = ? AND error_code = ? AND status = 'open'
        ORDER BY first_seen_at ASC LIMIT 1
        """,
        (artifact_family, source_path, failure_stage, error_code),
    ).fetchone()
    if row:
        conn.execute(
            """
            UPDATE import_quarantine
            SET source_content_hash = ?, schema_version_detected = ?, error_message = ?,
                raw_payload_json = ?, last_seen_at = ?, retry_count = retry_count + 1
            WHERE quarantine_id = ?
            """,
            (source_content_hash, schema_version_detected, error_message, raw_payload_json, now, row["quarantine_id"]),
        )
        return str(row["quarantine_id"])

    quarantine_id = new_id()
    conn.execute(
        """
        INSERT INTO import_quarantine(
            quarantine_id, artifact_family, source_path, source_content_hash, schema_version_detected,
            failure_stage, error_code, error_message, raw_payload_json, status, retry_count,
            first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', 0, ?, ?)
        """,
        (
            quarantine_id,
            artifact_family,
            source_path,
            source_content_hash,
            schema_version_detected,
            failure_stage,
            error_code,
            error_message,
            raw_payload_json,
            now,
            now,
        ),
    )
    return quarantine_id


def mark_quarantine_resolved(conn: sqlite3.Connection, source_path: str, artifact_family: str) -> int:
    now = now_iso()
    cur = conn.execute(
        """
        UPDATE import_quarantine
        SET status = 'resolved', resolved_at = ?, last_seen_at = ?
        WHERE status = 'open' AND source_path = ? AND artifact_family = ?
        """,
        (now, now, source_path, artifact_family),
    )
    return int(cur.rowcount)

