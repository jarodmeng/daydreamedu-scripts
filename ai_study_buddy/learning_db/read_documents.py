"""Reconstruct review-workspace documents from SQLite projections."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ai_study_buddy.learning_db.connection import get_connection


def _parse_raw_dict(raw_js: object) -> dict | None:
    if raw_js is None:
        return None
    if isinstance(raw_js, dict):
        return raw_js
    if isinstance(raw_js, (bytes, bytearray)):
        try:
            data = json.loads(raw_js.decode("utf-8"))
        except Exception:
            return None
        return data if isinstance(data, dict) else None
    if isinstance(raw_js, str):
        try:
            data = json.loads(raw_js)
        except Exception:
            return None
        return data if isinstance(data, dict) else None
    return None


def _parse_json_obj(raw_js: object, default: object) -> object:
    if raw_js is None:
        return default
    if isinstance(raw_js, (dict, list)):
        return raw_js
    if isinstance(raw_js, (bytes, bytearray)):
        raw_js = raw_js.decode("utf-8", errors="replace")
    if isinstance(raw_js, str):
        try:
            return json.loads(raw_js)
        except Exception:
            return default
    return default


def _clean_none_dict(data: dict) -> dict:
    return {key: value for key, value in data.items() if value is not None}


def _row_get(row: sqlite3.Row, key: str, default: object = None) -> object:
    return row[key] if key in row.keys() else default


def fetch_student_review_state_raw_json(review_state_relative_path: str) -> dict | None:
    """``review_state_relative_path`` is relative to ``context_root`` e.g. ``student_review_states/emma/foo.json``."""

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM student_review_states
            WHERE review_state_path = ? AND is_deleted = 0
            LIMIT 1
            """,
            (review_state_relative_path,),
        ).fetchone()
        if not row:
            return None
        note_rows = conn.execute(
            """
            SELECT scope, result_id, review_status, author_role, note_text, updated_at
            FROM student_review_notes
            WHERE review_state_id = ?
            ORDER BY updated_at ASC, note_id ASC
            """,
            (row["review_state_id"],),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        conn.close()

    question_reviews: list[dict] = []
    attempt_notes: list[dict] = []
    student_subject_notes: list[dict] = []
    for note in note_rows:
        item = _clean_none_dict(
            {
                "result_id": note["result_id"],
                "review_status": note["review_status"],
                "note_text": note["note_text"],
                "author_role": note["author_role"],
                "updated_at": note["updated_at"],
            }
        )
        if note["scope"] == "question":
            question_reviews.append(item)
        elif note["scope"] == "attempt":
            attempt_notes.append(item)
        elif note["scope"] == "student_subject":
            student_subject_notes.append(item)

    context = _parse_json_obj(row["context_json"], {})
    review_meta = _parse_json_obj(row["review_meta_json"], {})
    summary = _parse_json_obj(row["summary_json"], {})
    return {
        "schema_version": _row_get(row, "schema_version"),
        "created_at": _row_get(row, "created_at"),
        "updated_at": _row_get(row, "updated_at"),
        "context": context if isinstance(context, dict) else {},
        "summary": summary if isinstance(summary, dict) else {},
        "review_status": _row_get(row, "review_status"),
        "question_reviews": question_reviews,
        "attempt_notes": attempt_notes,
        "student_subject_notes": student_subject_notes,
        "review_meta": review_meta if isinstance(review_meta, dict) else {},
        "updated_by": _row_get(row, "updated_by"),
    }


def fetch_marking_artifact_raw_json(artifact_relative_path: str) -> dict | None:
    """``artifact_relative_path`` e.g. ``marking_results/emma/subject/foo.json``."""

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM marking_artifacts
            WHERE artifact_path = ? AND is_deleted = 0
            LIMIT 1
            """,
            (artifact_relative_path,),
        ).fetchone()
        if not row:
            return None
        question_rows = conn.execute(
            """
            SELECT *
            FROM marking_question_results
            WHERE artifact_id = ?
            ORDER BY rowid ASC
            """,
            (row["artifact_id"],),
        ).fetchall()
        page_rows = conn.execute(
            """
            SELECT *
            FROM marking_question_page_map
            WHERE artifact_id = ?
            ORDER BY rowid ASC
            """,
            (row["artifact_id"],),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        conn.close()

    question_page_map = [
        _clean_none_dict(
            {
                "result_id": page["result_id"],
                "attempt_page_start": page["attempt_page_start"],
                "confidence": page["confidence"],
                "source": page["source"],
                "evidence_image": page["evidence_image"],
                "note": page["note"],
            }
        )
        for page in page_rows
    ]
    context = _clean_none_dict(
        {
            "student_id": _row_get(row, "student_id"),
            "student_name": _row_get(row, "student_name"),
            "subject_context": _row_get(row, "subject_context"),
            "attempt_file_id": _row_get(row, "attempt_file_id"),
            "attempt_file_path": _row_get(row, "attempt_file_path"),
            "template_file_id": _row_get(row, "template_file_id"),
            "template_file_path": _row_get(row, "template_file_path"),
            "book_group_id": _row_get(row, "book_group_id"),
            "book_label": _row_get(row, "book_label"),
            "unit_file_id": _row_get(row, "unit_file_id"),
            "unit_file_path": _row_get(row, "unit_file_path"),
            "unit_label": _row_get(row, "unit_label"),
            "answer_file_id": _row_get(row, "answer_file_id"),
            "answer_file_path": _row_get(row, "answer_file_path"),
            "answer_page_start": _row_get(row, "answer_page_start"),
            "answer_page_end": _row_get(row, "answer_page_end"),
            "starts_mid_page": bool(_row_get(row, "starts_mid_page", 0)),
            "ends_mid_page": bool(_row_get(row, "ends_mid_page", 0)),
            "answer_mapping_source": _row_get(row, "answer_mapping_source"),
            "answer_mapping_notes": _row_get(row, "answer_mapping_notes"),
            "marking_asset": _row_get(row, "marking_asset"),
            "is_partial": bool(_row_get(row, "is_partial", 0)),
            "template_attempt_group_id": _row_get(row, "template_attempt_group_id"),
            "attempt_sequence": _row_get(row, "attempt_sequence"),
            "attempt_label": _row_get(row, "attempt_label"),
            "question_selection": _parse_json_obj(_row_get(row, "question_selection_json"), {}),
            "context_resolution": _parse_json_obj(_row_get(row, "context_resolution_json"), {}),
            "question_page_map": question_page_map,
        }
    )
    summary = _clean_none_dict(
        {
            "total_marks": _row_get(row, "summary_total_marks"),
            "earned_marks": _row_get(row, "summary_earned_marks"),
            "percentage": _row_get(row, "summary_percentage"),
            "overall_assessment": _row_get(row, "summary_overall_assessment"),
            "human_note": _row_get(row, "summary_human_note"),
        }
    )
    review_meta = _parse_json_obj(_row_get(row, "review_meta_json"), {})
    generation_json = _parse_json_obj(_row_get(row, "generation_json"), {})
    generation = _clean_none_dict(
        {
            "produced_by": _row_get(row, "generation_produced_by"),
            "mode": _row_get(row, "generation_mode"),
            "notes": _row_get(row, "generation_notes"),
            **(generation_json if isinstance(generation_json, dict) else {}),
        }
    )
    question_results = []
    for question in question_rows:
        diagnosis = _parse_json_obj(question["diagnosis_json"], {})
        if not isinstance(diagnosis, dict):
            diagnosis = {}
        diagnosis.update(
            _clean_none_dict(
                {
                    "mistake_type": question["diagnosis_mistake_type"],
                    "reasoning": question["diagnosis_reasoning"],
                    "confidence": question["diagnosis_confidence"],
                }
            )
        )
        question_results.append(
            _clean_none_dict(
                {
                    "result_id": question["result_id"],
                    "scoring_status": question["scoring_status"],
                    "outcome": question["outcome"],
                    "max_marks": question["max_marks"],
                    "earned_marks": question["earned_marks"],
                    "student_answer": question["student_answer"],
                    "correct_answer": question["correct_answer"],
                    "diagnosis": diagnosis,
                    "human_note": question["human_note"],
                    "error_tags": _parse_json_obj(question["error_tags_json"], []),
                    "skill_tags": _parse_json_obj(question["skill_tags_json"], []),
                }
            )
        )
    return {
        "schema_version": _row_get(row, "schema_version"),
        "created_at": _row_get(row, "created_at"),
        "updated_at": _row_get(row, "updated_at"),
        "context": context,
        "summary": summary,
        "question_results": question_results,
        "review_meta": review_meta if isinstance(review_meta, dict) else {},
        "generation": generation,
    }


def fetch_marking_amendment_raw_json(amendment_relative_path: str) -> dict | None:
    """``amendment_relative_path`` e.g. ``marking_amendments/emma/subject/foo.json``."""

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM marking_amendments
            WHERE amendment_path = ? AND is_deleted = 0
            LIMIT 1
            """,
            (amendment_relative_path,),
        ).fetchone()
        if not row:
            return None
        question_rows = conn.execute(
            """
            SELECT result_id, fields_json, reviewer_reason, evidence_json, updated_at, updated_by
            FROM marking_question_amendments
            WHERE amendment_id = ?
            ORDER BY rowid ASC
            """,
            (row["amendment_id"],),
        ).fetchall()
        page_rows = conn.execute(
            """
            SELECT result_id, attempt_page_start, confidence, updated_at, updated_by
            FROM marking_page_map_amendments
            WHERE amendment_id = ?
            ORDER BY rowid ASC
            """,
            (row["amendment_id"],),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        conn.close()

    context = _clean_none_dict(
        {
            "student_id": _row_get(row, "student_id"),
            "subject_context": _row_get(row, "subject_context"),
            "attempt_file_id": _row_get(row, "attempt_file_id"),
            "marking_result_path": _row_get(row, "marking_result_path"),
        }
    )
    question_amendments = []
    for question in question_rows:
        item = _clean_none_dict(
            {
                "result_id": question["result_id"],
                "fields": _parse_json_obj(question["fields_json"], {}),
                "reviewer_reason": question["reviewer_reason"],
                "evidence": _parse_json_obj(question["evidence_json"], {}),
                "updated_at": question["updated_at"],
                "updated_by": question["updated_by"],
            }
        )
        if item.get("evidence") == {}:
            item.pop("evidence", None)
        question_amendments.append(item)
    page_map_amendments = [
        _clean_none_dict(
            {
                "result_id": page["result_id"],
                "attempt_page_start": page["attempt_page_start"],
                "confidence": page["confidence"],
                "updated_at": page["updated_at"],
                "updated_by": page["updated_by"],
            }
        )
        for page in page_rows
    ]
    review_meta = _clean_none_dict(
        {
            "updated_at": _row_get(row, "review_meta_updated_at"),
            "updated_by": _row_get(row, "review_meta_updated_by"),
        }
    )
    return {
        "schema_version": _row_get(row, "schema_version"),
        "context": context,
        "summary_overrides": _parse_json_obj(_row_get(row, "summary_overrides_json"), {}),
        "question_amendments": question_amendments,
        "question_page_map_amendments": page_map_amendments,
        "review_meta": review_meta,
    }


def relative_review_state_path(student_id: str, subject_context: str, artifact_stem: str) -> str:
    return Path("student_review_states", student_id, subject_context, f"{artifact_stem}.json").as_posix()


def relative_amendment_path(student_id: str, subject_context: str, artifact_stem: str) -> str:
    return Path("marking_amendments", student_id, subject_context, f"{artifact_stem}.json").as_posix()
