from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
from typing import Any

from jsonschema import Draft202012Validator

from ai_study_buddy.learning_db.connection import default_context_root, default_db_path, get_connection
from ai_study_buddy.learning_db.migrate import apply_migrations
from ai_study_buddy.learning_db.repository import (
    OperationEvent,
    get_or_create_identity_map,
    mark_quarantine_resolved,
    upsert_quarantine,
    validate_actor,
    write_operation_log,
)
from ai_study_buddy.marking.core.artifact_schema import (
    load_marking_amendment_schema,
    validate_marking_artifact_dict,
)


@dataclass
class ImportSummary:
    scanned: int = 0
    imported: int = 0
    updated: int = 0
    quarantined: int = 0
    resolved: int = 0
    failure_codes: dict[str, int] = field(default_factory=dict)

    def add_failure(self, code: str) -> None:
        self.quarantined += 1
        self.failure_codes[code] = self.failure_codes.get(code, 0) + 1


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_json_file(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload, text


def _relative_to_context(path: Path, context_root: Path) -> str:
    return str(path.resolve().relative_to(context_root.resolve()))


def _artifact_stem_from_path(rel_path: str) -> str:
    return Path(rel_path).stem


def _operation_actor() -> str:
    return validate_actor("script:ai_study_buddy.learning_db.import_context_json")


def _validate_marking_amendment(payload: dict[str, Any]) -> None:
    schema = load_marking_amendment_schema()
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        path = ".".join(str(x) for x in first.absolute_path)
        raise ValueError(f"marking amendment schema validation failed at {path}: {first.message}")


def _validate_review_state(payload: dict[str, Any]) -> None:
    schema_version = payload.get("schema_version")
    if schema_version != "student_review_state.v1":
        raise ValueError(f"unsupported review_state schema_version: {schema_version}")
    for key in ("created_at", "updated_at", "context"):
        if key not in payload:
            raise ValueError(f"missing required key: {key}")
    if not isinstance(payload.get("context"), dict):
        raise ValueError("context must be object")


def _row_exists(conn: sqlite3.Connection, table: str, key_col: str, value: str) -> bool:
    row = conn.execute(f"SELECT 1 FROM {table} WHERE {key_col} = ? LIMIT 1", (value,)).fetchone()
    return row is not None


def _resolve_marking_artifact_id_by_path(conn: sqlite3.Connection, artifact_path: str) -> str | None:
    row = conn.execute(
        "SELECT artifact_id FROM marking_artifacts WHERE artifact_path = ? LIMIT 1",
        (artifact_path,),
    ).fetchone()
    return str(row["artifact_id"]) if row else None


def _resolve_marking_amendment_id_by_path(conn: sqlite3.Connection, amendment_path: str) -> str | None:
    row = conn.execute(
        "SELECT amendment_id FROM marking_amendments WHERE amendment_path = ? LIMIT 1",
        (amendment_path,),
    ).fetchone()
    return str(row["amendment_id"]) if row else None


def _resolve_review_state_id_by_path(conn: sqlite3.Connection, review_state_path: str) -> str | None:
    row = conn.execute(
        "SELECT review_state_id FROM student_review_states WHERE review_state_path = ? LIMIT 1",
        (review_state_path,),
    ).fetchone()
    return str(row["review_state_id"]) if row else None


def upsert_marking_result(
    conn: sqlite3.Connection,
    *,
    payload: dict[str, Any],
    rel_path: str,
    source_hash: str,
) -> str:
    validate_marking_artifact_dict(payload)
    artifact_id = get_or_create_identity_map(
        conn,
        artifact_family="marking_result",
        source_path=rel_path,
        source_content_hash=source_hash,
        suggested_artifact_id=_resolve_marking_artifact_id_by_path(conn, rel_path),
    )
    context = payload.get("context", {})
    summary = payload.get("summary", {})
    review_meta = payload.get("review_meta", {})
    generation = payload.get("generation", {})

    already_exists = _row_exists(conn, "marking_artifacts", "artifact_id", artifact_id)
    conn.execute(
        """
        INSERT INTO marking_artifacts(
            artifact_id, schema_version, artifact_path, artifact_stem, source_content_hash, created_at, updated_at,
            student_id, student_name, subject_context, attempt_file_id, attempt_file_path, template_file_id, template_file_path,
            book_group_id, book_label, unit_file_id, unit_file_path, unit_label, answer_file_id, answer_file_path,
            answer_page_start, answer_page_end, starts_mid_page, ends_mid_page, answer_mapping_source, answer_mapping_notes,
            marking_asset, is_partial, template_attempt_group_id, attempt_sequence, attempt_label,
            question_selection_json, context_resolution_json, summary_total_marks, summary_earned_marks, summary_percentage,
            summary_overall_assessment, summary_human_note, review_meta_updated_at, review_meta_updated_by,
            generation_produced_by, generation_mode, generation_notes, review_meta_json, generation_json, context_json, summary_json,
            raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(artifact_id) DO UPDATE SET
            schema_version = excluded.schema_version,
            artifact_path = excluded.artifact_path,
            artifact_stem = excluded.artifact_stem,
            source_content_hash = excluded.source_content_hash,
            updated_at = excluded.updated_at,
            student_id = excluded.student_id,
            student_name = excluded.student_name,
            subject_context = excluded.subject_context,
            attempt_file_id = excluded.attempt_file_id,
            attempt_file_path = excluded.attempt_file_path,
            template_file_id = excluded.template_file_id,
            template_file_path = excluded.template_file_path,
            book_group_id = excluded.book_group_id,
            book_label = excluded.book_label,
            unit_file_id = excluded.unit_file_id,
            unit_file_path = excluded.unit_file_path,
            unit_label = excluded.unit_label,
            answer_file_id = excluded.answer_file_id,
            answer_file_path = excluded.answer_file_path,
            answer_page_start = excluded.answer_page_start,
            answer_page_end = excluded.answer_page_end,
            starts_mid_page = excluded.starts_mid_page,
            ends_mid_page = excluded.ends_mid_page,
            answer_mapping_source = excluded.answer_mapping_source,
            answer_mapping_notes = excluded.answer_mapping_notes,
            marking_asset = excluded.marking_asset,
            is_partial = excluded.is_partial,
            template_attempt_group_id = excluded.template_attempt_group_id,
            attempt_sequence = excluded.attempt_sequence,
            attempt_label = excluded.attempt_label,
            question_selection_json = excluded.question_selection_json,
            context_resolution_json = excluded.context_resolution_json,
            summary_total_marks = excluded.summary_total_marks,
            summary_earned_marks = excluded.summary_earned_marks,
            summary_percentage = excluded.summary_percentage,
            summary_overall_assessment = excluded.summary_overall_assessment,
            summary_human_note = excluded.summary_human_note,
            review_meta_updated_at = excluded.review_meta_updated_at,
            review_meta_updated_by = excluded.review_meta_updated_by,
            generation_produced_by = excluded.generation_produced_by,
            generation_mode = excluded.generation_mode,
            generation_notes = excluded.generation_notes,
            review_meta_json = excluded.review_meta_json,
            generation_json = excluded.generation_json,
            context_json = excluded.context_json,
            summary_json = excluded.summary_json,
            raw_json = excluded.raw_json,
            row_version = marking_artifacts.row_version + 1
        """,
        (
            artifact_id,
            payload.get("schema_version"),
            rel_path,
            _artifact_stem_from_path(rel_path),
            source_hash,
            payload.get("created_at"),
            payload.get("updated_at"),
            context.get("student_id"),
            context.get("student_name"),
            context.get("subject_context"),
            context.get("attempt_file_id"),
            context.get("attempt_file_path"),
            context.get("template_file_id"),
            context.get("template_file_path"),
            context.get("book_group_id"),
            context.get("book_label"),
            context.get("unit_file_id"),
            context.get("unit_file_path"),
            context.get("unit_label"),
            context.get("answer_file_id"),
            context.get("answer_file_path"),
            context.get("answer_page_start"),
            context.get("answer_page_end"),
            1 if context.get("starts_mid_page") else 0,
            1 if context.get("ends_mid_page") else 0,
            context.get("answer_mapping_source"),
            context.get("answer_mapping_notes"),
            context.get("marking_asset"),
            1 if context.get("is_partial") else 0,
            context.get("template_attempt_group_id"),
            context.get("attempt_sequence"),
            context.get("attempt_label"),
            json.dumps(context.get("question_selection"), ensure_ascii=True),
            json.dumps(context.get("context_resolution"), ensure_ascii=True),
            summary.get("total_marks"),
            summary.get("earned_marks"),
            summary.get("percentage"),
            summary.get("overall_assessment"),
            summary.get("human_note"),
            review_meta.get("updated_at"),
            review_meta.get("updated_by"),
            generation.get("produced_by"),
            generation.get("mode"),
            generation.get("notes"),
            json.dumps(review_meta, ensure_ascii=True),
            json.dumps(generation, ensure_ascii=True),
            json.dumps(context, ensure_ascii=True),
            json.dumps(summary, ensure_ascii=True),
            json.dumps(payload, ensure_ascii=True),
        ),
    )

    conn.execute("DELETE FROM marking_question_results WHERE artifact_id = ?", (artifact_id,))
    for row in payload.get("question_results", []):
        if not isinstance(row, dict):
            continue
        diagnosis = row.get("diagnosis") or {}
        conn.execute(
            """
            INSERT INTO marking_question_results(
                artifact_id, result_id, scoring_status, outcome, max_marks, earned_marks, student_answer, correct_answer,
                diagnosis_mistake_type, diagnosis_reasoning, diagnosis_confidence, human_note,
                error_tags_json, skill_tags_json, diagnosis_json, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                row.get("result_id"),
                row.get("scoring_status"),
                row.get("outcome"),
                row.get("max_marks"),
                row.get("earned_marks"),
                row.get("student_answer"),
                row.get("correct_answer"),
                diagnosis.get("mistake_type"),
                diagnosis.get("reasoning"),
                diagnosis.get("confidence"),
                row.get("human_note"),
                json.dumps(row.get("error_tags") or [], ensure_ascii=True),
                json.dumps(row.get("skill_tags") or [], ensure_ascii=True),
                json.dumps(diagnosis, ensure_ascii=True),
                json.dumps(row, ensure_ascii=True),
            ),
        )

    conn.execute("DELETE FROM marking_question_page_map WHERE artifact_id = ?", (artifact_id,))
    for row in context.get("question_page_map", []):
        if not isinstance(row, dict):
            continue
        conn.execute(
            """
            INSERT INTO marking_question_page_map(
                artifact_id, result_id, attempt_page_start, confidence, source, evidence_image, note, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                row.get("result_id"),
                row.get("attempt_page_start"),
                row.get("confidence"),
                row.get("source"),
                row.get("evidence_image"),
                row.get("note"),
                json.dumps(row, ensure_ascii=True),
            ),
        )
    return "updated" if already_exists else "inserted"


def _resolve_artifact_id_by_path(conn: sqlite3.Connection, marking_result_path: str) -> str | None:
    row = conn.execute(
        "SELECT artifact_id FROM marking_artifacts WHERE artifact_path = ? LIMIT 1",
        (marking_result_path,),
    ).fetchone()
    return str(row["artifact_id"]) if row else None


def upsert_marking_amendment(
    conn: sqlite3.Connection,
    *,
    payload: dict[str, Any],
    rel_path: str,
    source_hash: str,
) -> str:
    _validate_marking_amendment(payload)
    context = payload.get("context") or {}
    marking_result_path = context.get("marking_result_path")
    artifact_id = _resolve_artifact_id_by_path(conn, marking_result_path)
    if artifact_id is None:
        raise LookupError(f"base artifact not found for marking_result_path={marking_result_path}")

    amendment_id = get_or_create_identity_map(
        conn,
        artifact_family="marking_amendment",
        source_path=rel_path,
        source_content_hash=source_hash,
        suggested_artifact_id=_resolve_marking_amendment_id_by_path(conn, rel_path),
    )
    already_exists = _row_exists(conn, "marking_amendments", "amendment_id", amendment_id)
    review_meta = payload.get("review_meta") or {}
    conn.execute(
        """
        INSERT INTO marking_amendments(
            amendment_id, artifact_id, schema_version, amendment_path, source_content_hash, student_id, subject_context,
            attempt_file_id, marking_result_path, review_meta_updated_at, review_meta_updated_by,
            summary_overrides_json, question_amendments_json, question_page_map_amendments_json,
            context_json, review_meta_json, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(amendment_id) DO UPDATE SET
            artifact_id = excluded.artifact_id,
            schema_version = excluded.schema_version,
            amendment_path = excluded.amendment_path,
            source_content_hash = excluded.source_content_hash,
            student_id = excluded.student_id,
            subject_context = excluded.subject_context,
            attempt_file_id = excluded.attempt_file_id,
            marking_result_path = excluded.marking_result_path,
            review_meta_updated_at = excluded.review_meta_updated_at,
            review_meta_updated_by = excluded.review_meta_updated_by,
            summary_overrides_json = excluded.summary_overrides_json,
            question_amendments_json = excluded.question_amendments_json,
            question_page_map_amendments_json = excluded.question_page_map_amendments_json,
            context_json = excluded.context_json,
            review_meta_json = excluded.review_meta_json,
            raw_json = excluded.raw_json,
            row_version = marking_amendments.row_version + 1
        """,
        (
            amendment_id,
            artifact_id,
            payload.get("schema_version"),
            rel_path,
            source_hash,
            context.get("student_id"),
            context.get("subject_context"),
            context.get("attempt_file_id"),
            marking_result_path,
            review_meta.get("updated_at"),
            review_meta.get("updated_by"),
            json.dumps(payload.get("summary_overrides") or {}, ensure_ascii=True),
            json.dumps(payload.get("question_amendments") or [], ensure_ascii=True),
            json.dumps(payload.get("question_page_map_amendments") or [], ensure_ascii=True),
            json.dumps(context, ensure_ascii=True),
            json.dumps(review_meta, ensure_ascii=True),
            json.dumps(payload, ensure_ascii=True),
        ),
    )
    conn.execute("DELETE FROM marking_question_amendments WHERE amendment_id = ?", (amendment_id,))
    for row in payload.get("question_amendments", []):
        if not isinstance(row, dict):
            continue
        conn.execute(
            """
            INSERT INTO marking_question_amendments(
                amendment_id, result_id, fields_json, reviewer_reason, evidence_json, updated_at, updated_by, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                amendment_id,
                row.get("result_id"),
                json.dumps(row.get("fields") or {}, ensure_ascii=True),
                row.get("reviewer_reason"),
                json.dumps(row.get("evidence") or {}, ensure_ascii=True),
                row.get("updated_at"),
                row.get("updated_by"),
                json.dumps(row, ensure_ascii=True),
            ),
        )
    conn.execute("DELETE FROM marking_page_map_amendments WHERE amendment_id = ?", (amendment_id,))
    for row in payload.get("question_page_map_amendments", []):
        if not isinstance(row, dict):
            continue
        conn.execute(
            """
            INSERT INTO marking_page_map_amendments(
                amendment_id, result_id, attempt_page_start, confidence, updated_at, updated_by, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                amendment_id,
                row.get("result_id"),
                row.get("attempt_page_start"),
                row.get("confidence"),
                row.get("updated_at"),
                row.get("updated_by"),
                json.dumps(row, ensure_ascii=True),
            ),
        )
    return "updated" if already_exists else "inserted"


def upsert_review_state(
    conn: sqlite3.Connection,
    *,
    payload: dict[str, Any],
    rel_path: str,
    source_hash: str,
) -> str:
    _validate_review_state(payload)
    context = payload.get("context") or {}
    marking_result_path = context.get("marking_result_path")
    artifact_id = _resolve_artifact_id_by_path(conn, marking_result_path)
    if artifact_id is None:
        raise LookupError(f"base artifact not found for marking_result_path={marking_result_path}")

    review_state_id = get_or_create_identity_map(
        conn,
        artifact_family="student_review_state",
        source_path=rel_path,
        source_content_hash=source_hash,
        suggested_artifact_id=_resolve_review_state_id_by_path(conn, rel_path),
    )
    already_exists = _row_exists(conn, "student_review_states", "review_state_id", review_state_id)
    conn.execute(
        """
        INSERT INTO student_review_states(
            review_state_id, artifact_id, schema_version, review_state_path, source_content_hash, student_id, subject_context,
            attempt_file_id, marking_result_path, template_attempt_group_id, attempt_sequence, review_status,
            created_at, updated_at, updated_by, summary_json, question_reviews_json, attempt_notes_json, student_subject_notes_json,
            context_json, review_meta_json, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(review_state_id) DO UPDATE SET
            artifact_id = excluded.artifact_id,
            schema_version = excluded.schema_version,
            review_state_path = excluded.review_state_path,
            source_content_hash = excluded.source_content_hash,
            student_id = excluded.student_id,
            subject_context = excluded.subject_context,
            attempt_file_id = excluded.attempt_file_id,
            marking_result_path = excluded.marking_result_path,
            template_attempt_group_id = excluded.template_attempt_group_id,
            attempt_sequence = excluded.attempt_sequence,
            review_status = excluded.review_status,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by,
            summary_json = excluded.summary_json,
            question_reviews_json = excluded.question_reviews_json,
            attempt_notes_json = excluded.attempt_notes_json,
            student_subject_notes_json = excluded.student_subject_notes_json,
            context_json = excluded.context_json,
            review_meta_json = excluded.review_meta_json,
            raw_json = excluded.raw_json,
            row_version = student_review_states.row_version + 1
        """,
        (
            review_state_id,
            artifact_id,
            payload.get("schema_version"),
            rel_path,
            source_hash,
            context.get("student_id"),
            context.get("subject_context"),
            context.get("attempt_file_id"),
            marking_result_path,
            context.get("template_attempt_group_id"),
            context.get("attempt_sequence"),
            payload.get("review_status"),
            payload.get("created_at"),
            payload.get("updated_at"),
            payload.get("updated_by"),
            json.dumps(payload.get("summary") or {}, ensure_ascii=True),
            json.dumps(payload.get("question_reviews") or [], ensure_ascii=True),
            json.dumps(payload.get("attempt_notes") or [], ensure_ascii=True),
            json.dumps(payload.get("student_subject_notes") or [], ensure_ascii=True),
            json.dumps(context, ensure_ascii=True),
            json.dumps(payload.get("review_meta") or {}, ensure_ascii=True),
            json.dumps(payload, ensure_ascii=True),
        ),
    )
    conn.execute("DELETE FROM student_review_notes WHERE review_state_id = ?", (review_state_id,))
    for scope, rows in (
        ("question", payload.get("question_reviews", [])),
        ("attempt", payload.get("attempt_notes", [])),
        ("student_subject", payload.get("student_subject_notes", [])),
    ):
        for row in rows:
            if not isinstance(row, dict):
                continue
            conn.execute(
                """
                INSERT INTO student_review_notes(
                    note_id, review_state_id, artifact_id, scope, result_id, review_status, author_role, note_text, updated_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    get_or_create_identity_map(
                        conn,
                        artifact_family="student_review_state",
                        source_path=f"{rel_path}::{scope}::{row.get('result_id') or row.get('updated_at') or row.get('note_text')}",
                        source_content_hash=_sha256_text(json.dumps(row, ensure_ascii=True)),
                        suggested_artifact_id=None,
                    ),
                    review_state_id,
                    artifact_id,
                    scope,
                    row.get("result_id"),
                    row.get("review_status"),
                    row.get("author_role"),
                    row.get("note_text"),
                    row.get("updated_at"),
                    json.dumps(row, ensure_ascii=True),
                ),
            )
    return "updated" if already_exists else "inserted"


def _process_one(
    conn: sqlite3.Connection,
    *,
    family: str,
    path: Path,
    rel_path: str,
    dry_run: bool,
    summary: ImportSummary,
) -> None:
    actor = _operation_actor()
    write_operation_log(
        conn,
        OperationEvent(
            operation_type=f"import_{family}",
            entity_type=family,
            entity_id=rel_path,
            status="started",
            actor=actor,
        ),
    )
    try:
        payload, raw_text = _parse_json_file(path)
        source_hash = _sha256_text(raw_text)
        if dry_run:
            summary.imported += 1
            write_operation_log(
                conn,
                OperationEvent(
                    operation_type=f"import_{family}",
                    entity_type=family,
                    entity_id=rel_path,
                    status="succeeded",
                    actor=actor,
                    metadata={"dry_run": True},
                ),
            )
            return

        if family == "marking_result":
            result = upsert_marking_result(conn, payload=payload, rel_path=rel_path, source_hash=source_hash)
        elif family == "marking_amendment":
            result = upsert_marking_amendment(conn, payload=payload, rel_path=rel_path, source_hash=source_hash)
        elif family == "student_review_state":
            result = upsert_review_state(conn, payload=payload, rel_path=rel_path, source_hash=source_hash)
        else:
            raise ValueError(f"unsupported family: {family}")

        if result == "updated":
            summary.updated += 1
        else:
            summary.imported += 1
        summary.resolved += mark_quarantine_resolved(conn, rel_path, family)
        write_operation_log(
            conn,
            OperationEvent(
                operation_type=f"import_{family}",
                entity_type=family,
                entity_id=rel_path,
                status="succeeded",
                actor=actor,
                metadata={"result": result},
            ),
        )
    except Exception as exc:
        source_hash = None
        schema_version = None
        raw_payload = None
        failure_stage = "transform"
        code = "IMPORT_ERROR"
        message = str(exc)
        try:
            text = path.read_text(encoding="utf-8")
            source_hash = _sha256_text(text)
            maybe = json.loads(text)
            raw_payload = json.dumps(maybe, ensure_ascii=True) if isinstance(maybe, dict) else None
            if isinstance(maybe, dict):
                schema_version = maybe.get("schema_version")
            if "schema validation failed" in message:
                failure_stage = "schema_validate"
                code = "SCHEMA_VALIDATION_FAILED"
            elif "base artifact not found" in message:
                failure_stage = "fk_resolve"
                code = "BASE_ARTIFACT_NOT_FOUND"
        except Exception:
            failure_stage = "read_json"
            code = "READ_JSON_FAILED"
        quarantine_id = upsert_quarantine(
            conn,
            artifact_family=family,
            source_path=rel_path,
            source_content_hash=source_hash,
            schema_version_detected=schema_version,
            failure_stage=failure_stage,
            error_code=code,
            error_message=message,
            raw_payload_json=raw_payload,
        )
        summary.add_failure(code)
        write_operation_log(
            conn,
            OperationEvent(
                operation_type=f"import_{family}",
                entity_type=family,
                entity_id=rel_path,
                status="failed",
                actor=actor,
                error_code=code,
                error_message=message,
                metadata={"quarantine_id": quarantine_id},
            ),
        )


def _iter_family_files(context_root: Path, family: str) -> list[Path]:
    mapping = {
        "marking_result": context_root / "marking_results",
        "marking_amendment": context_root / "marking_amendments",
        "student_review_state": context_root / "student_review_states",
    }
    base = mapping[family]
    if not base.exists():
        return []
    return sorted(base.rglob("*.json"))


def _normalize_scope_token(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_path_prefix(value: str | None) -> str | None:
    v = _normalize_scope_token(value)
    if v is None:
        return None
    out = v.replace("\\", "/").strip("/")
    return out or None


def rel_path_matches_scope(
    rel_path: str,
    *,
    student_id: str | None,
    subject_context: str | None,
    path_prefix: str | None,
) -> bool:
    """Restrict imports to a student folder, subject segment, and/or a context-relative path prefix.

    Layout is always ``<family_root>/<student_id>/<subject_context>/...``. When only
    ``subject_context`` is set, any student under that subject folder may match.
    """

    posix = rel_path.replace("\\", "/").strip()
    pfx = _normalize_path_prefix(path_prefix)
    if pfx is not None:
        if posix != pfx and not posix.startswith(pfx + "/"):
            return False

    parts = posix.split("/")
    sid = _normalize_scope_token(student_id)
    subj = _normalize_scope_token(subject_context)

    if sid is not None:
        if len(parts) < 2 or parts[1] != sid:
            return False

    if subj is not None:
        if len(parts) < 3 or parts[2] != subj:
            return False

    return True


def _iter_retry_candidates(
    conn: sqlite3.Connection,
    *,
    status: str,
    artifact_family: str | None,
    failure_stage: str | None,
    limit: int | None,
) -> list[tuple[str, str]]:
    sql = """
        SELECT artifact_family, source_path
        FROM import_quarantine
        WHERE status = ?
    """
    params: list[Any] = [status]
    if artifact_family:
        sql += " AND artifact_family = ?"
        params.append(artifact_family)
    if failure_stage:
        sql += " AND failure_stage = ?"
        params.append(failure_stage)
    sql += " ORDER BY first_seen_at ASC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [(str(r["artifact_family"]), str(r["source_path"])) for r in rows]


def run_import(
    *,
    db_path: Path,
    context_root: Path,
    dry_run: bool,
    limit: int | None,
    artifact_family: str | None,
    retry_quarantine: bool,
    retry_status: str,
    retry_failure_stage: str | None,
    student_id: str | None = None,
    subject_context: str | None = None,
    path_prefix: str | None = None,
) -> dict[str, ImportSummary]:
    apply_migrations(db_path=db_path)
    conn = get_connection(db_path)
    summaries = {
        "marking_result": ImportSummary(),
        "marking_amendment": ImportSummary(),
        "student_review_state": ImportSummary(),
    }
    families = [artifact_family] if artifact_family else list(summaries.keys())
    try:
        with conn:
            for family in families:
                if retry_quarantine:
                    candidates = _iter_retry_candidates(
                        conn,
                        status=retry_status,
                        artifact_family=family,
                        failure_stage=retry_failure_stage,
                        limit=limit,
                    )
                    file_paths = [context_root / p for fam, p in candidates if fam == family]
                    rel_paths = [p for fam, p in candidates if fam == family]
                else:
                    files = _iter_family_files(context_root, family)
                    rel_paths_full = [_relative_to_context(p, context_root) for p in files]
                    filtered: list[tuple[Path, str]] = [
                        (path, rel)
                        for path, rel in zip(files, rel_paths_full)
                        if rel_path_matches_scope(
                            rel,
                            student_id=student_id,
                            subject_context=subject_context,
                            path_prefix=path_prefix,
                        )
                    ]
                    if limit is not None:
                        filtered = filtered[:limit]
                    file_paths = [pair[0] for pair in filtered]
                    rel_paths = [pair[1] for pair in filtered]
                for path, rel_path in zip(file_paths, rel_paths):
                    summaries[family].scanned += 1
                    _process_one(
                        conn,
                        family=family,
                        path=path,
                        rel_path=rel_path,
                        dry_run=dry_run,
                        summary=summaries[family],
                    )
    finally:
        conn.close()
    return summaries


def _print_summary(summaries: dict[str, ImportSummary]) -> None:
    print("Import summary:")
    for family, summary in summaries.items():
        print(
            f"- {family}: scanned={summary.scanned} imported={summary.imported} "
            f"updated={summary.updated} quarantined={summary.quarantined} resolved={summary.resolved}"
        )
        if summary.failure_codes:
            print(f"  top failure codes: {summary.failure_codes}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import marking context JSON files into study_buddy.db.")
    parser.add_argument("--db-path", help="Optional DB path override.")
    parser.add_argument("--context-root", help="Optional context root override.")
    parser.add_argument("--dry-run", action="store_true", help="Parse/validate only, do not write rows.")
    parser.add_argument("--limit", type=int, help="Optional max files per family.")
    parser.add_argument(
        "--artifact-family",
        choices=["marking_result", "marking_amendment", "student_review_state"],
        help="Limit import to one family.",
    )
    parser.add_argument("--retry-quarantine", action="store_true", help="Retry only quarantine entries.")
    parser.add_argument("--status", default="open", choices=["open", "resolved", "ignored"], help="Quarantine status filter.")
    parser.add_argument(
        "--failure-stage",
        choices=["read_json", "schema_validate", "fk_resolve", "transform", "upsert", "io"],
        help="Optional quarantine stage filter.",
    )
    parser.add_argument(
        "--student-id",
        help="Only import JSON under <family>/<student_id>/... (POSIX path segment after family root).",
    )
    parser.add_argument(
        "--subject-context",
        help="Only import JSON under <family>/<student>/<subject_context>/... (third path segment).",
    )
    parser.add_argument(
        "--path-prefix",
        help="Only import files whose path relative to context-root starts with this prefix "
        "(POSIX, e.g. marking_results/emma/singapore_primary_science). Ignored for --retry-quarantine.",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path).expanduser().resolve() if args.db_path else default_db_path()
    context_root = Path(args.context_root).expanduser().resolve() if args.context_root else default_context_root()
    summaries = run_import(
        db_path=db_path,
        context_root=context_root,
        dry_run=bool(args.dry_run),
        limit=args.limit,
        artifact_family=args.artifact_family,
        retry_quarantine=bool(args.retry_quarantine),
        retry_status=args.status,
        retry_failure_stage=args.failure_stage,
        student_id=args.student_id,
        subject_context=args.subject_context,
        path_prefix=args.path_prefix,
    )
    _print_summary(summaries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

