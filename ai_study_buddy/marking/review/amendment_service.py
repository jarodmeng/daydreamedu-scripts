from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
import re
from typing import Any

from ai_study_buddy.marking.core.artifact_lookup import find_marking_artifacts_for_attempt
from ai_study_buddy.marking.core.artifact_schema import (
    ALLOWED_OUTCOMES,
    ALLOWED_PAGE_MAP_CONFIDENCE,
    compute_percentage,
)
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
from ai_study_buddy.marking.review.models import now_iso_utc
from ai_study_buddy.marking.review.payload_reader import read_marking_result_payload
from ai_study_buddy.marking.review.repository import StudentReviewRepository

SCHEMA_VERSION = "marking_amendment.v1"
UPDATED_BY_DEFAULT = "review_workspace"

QUESTION_FIELD_KEYS = {
    "outcome",
    "earned_marks",
    "max_marks",
    "student_answer",
    "correct_answer",
    "diagnosis.mistake_type",
    "diagnosis.reasoning",
    "skill_tags",
    "human_note",
}
TEXT_FIELD_KEYS = {
    "student_answer",
    "correct_answer",
    "diagnosis.mistake_type",
    "diagnosis.reasoning",
    "human_note",
}
SCORE_REASON_FIELD_KEYS = {"outcome", "earned_marks", "max_marks"}


class AmendmentValidationError(ValueError):
    def __init__(self, errors: list[dict[str, str]]):
        self.errors = errors
        super().__init__("; ".join(error["message"] for error in errors) or "invalid amendment")


class AmendmentWriteError(ValueError):
    pass


def normalize_amendment_state(raw: dict[str, Any] | None, *, context: dict[str, Any]) -> dict[str, Any]:
    review_meta = raw.get("review_meta") if isinstance(raw, dict) and isinstance(raw.get("review_meta"), dict) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "context": context,
        "summary_overrides": _normalize_summary_overrides(raw.get("summary_overrides") if isinstance(raw, dict) else None),
        "question_amendments": _normalize_question_amendments(
            raw.get("question_amendments") if isinstance(raw, dict) else None
        ),
        "question_page_map_amendments": _normalize_page_map_amendments(
            raw.get("question_page_map_amendments") if isinstance(raw, dict) else None
        ),
        "review_meta": {
            "updated_at": review_meta.get("updated_at") if isinstance(review_meta.get("updated_at"), str) else None,
            "updated_by": review_meta.get("updated_by") if isinstance(review_meta.get("updated_by"), str) else None,
        },
    }


def build_amendment_context(
    *,
    base_payload: dict[str, Any],
    attempt_id: str,
    marking_result_path: str,
    fallback_student_id: str | None,
) -> dict[str, Any]:
    base_context = base_payload.get("context") if isinstance(base_payload.get("context"), dict) else {}
    student_id = base_context.get("student_id") if isinstance(base_context.get("student_id"), str) else None
    subject_context = base_context.get("subject_context") if isinstance(base_context.get("subject_context"), str) else None
    return {
        "student_id": student_id or fallback_student_id or "unknown",
        "subject_context": subject_context or "unknown",
        "attempt_file_id": base_context.get("attempt_file_id") or attempt_id,
        "marking_result_path": marking_result_path,
    }


def resolve_marking_result(
    *,
    base_payload: dict[str, Any],
    amendment_state: dict[str, Any],
    valid_attempt_pages: set[int] | None = None,
) -> dict[str, Any]:
    validate_amendment_state(
        base_payload=base_payload,
        amendment_state=amendment_state,
        valid_attempt_pages=valid_attempt_pages,
    )
    resolved = deepcopy(base_payload)
    _apply_question_amendments(resolved, amendment_state)
    _apply_page_map_amendments(resolved, amendment_state)
    _apply_summary_overrides(resolved, amendment_state)
    _recompute_summary_scores(resolved)
    return resolved


def merge_panel_amendment(
    *,
    existing_state: dict[str, Any],
    body: dict[str, Any],
    base_payload: dict[str, Any],
    context: dict[str, Any],
    valid_attempt_pages: set[int] | None,
) -> dict[str, Any]:
    updated_by = body.get("updated_by") if isinstance(body.get("updated_by"), str) and body.get("updated_by").strip() else UPDATED_BY_DEFAULT
    timestamp = now_iso_utc()
    merged = normalize_amendment_state(existing_state, context=context)

    summary_overrides = _normalize_summary_overrides(body.get("summary_overrides"))
    if summary_overrides:
        merged["summary_overrides"].update(summary_overrides)

    for incoming in _normalize_question_amendments(body.get("question_amendments")):
        incoming["updated_at"] = timestamp
        incoming["updated_by"] = updated_by
        _upsert_question_amendment(merged["question_amendments"], incoming)

    for incoming in _normalize_page_map_amendments(body.get("question_page_map_amendments")):
        incoming["updated_at"] = timestamp
        incoming["updated_by"] = updated_by
        _upsert_page_map_amendment(merged["question_page_map_amendments"], incoming)

    merged["review_meta"] = {"updated_at": timestamp, "updated_by": updated_by}
    validate_amendment_state(
        base_payload=base_payload,
        amendment_state=merged,
        valid_attempt_pages=valid_attempt_pages,
    )
    return merged


def put_amendments(
    *,
    attempt_id: str,
    body: dict[str, Any],
    context_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
    valid_attempt_pages: set[int] | None = None,
) -> dict[str, Any]:
    refs = find_marking_artifacts_for_attempt(attempt_id, manager=manager, context_root=context_root)
    latest_ref = refs[0] if refs else None
    if latest_ref is None:
        raise AmendmentWriteError("cannot persist amendments: no marking artifact for attempt")

    completion = manager.get_file(attempt_id)
    if completion is None:
        raise AmendmentWriteError("attempt not found")

    base_payload = read_marking_result_payload(
        marking_result_json=latest_ref.marking_result_json,
        context_root=context_root,
    )
    if base_payload is None:
        raise AmendmentWriteError("invalid marking artifact")

    marking_result_path = latest_ref.marking_result_json.relative_to(context_root).as_posix()
    context = build_amendment_context(
        base_payload=base_payload,
        attempt_id=attempt_id,
        marking_result_path=marking_result_path,
        fallback_student_id=completion.student_id,
    )
    existing = review_repo.load_raw_amendment(
        student_id=context["student_id"],
        subject_context=context["subject_context"],
        artifact_stem=latest_ref.marking_result_json.stem,
    )
    inferred_attempt_pages = valid_attempt_pages
    if inferred_attempt_pages is None:
        inferred_attempt_pages = _valid_attempt_pages(base_payload=base_payload, context_root=context_root)

    merged = merge_panel_amendment(
        existing_state=existing or {},
        body=body,
        base_payload=base_payload,
        context=context,
        valid_attempt_pages=inferred_attempt_pages,
    )
    path = review_repo.save_amendment(
        student_id=context["student_id"],
        subject_context=context["subject_context"],
        artifact_stem=latest_ref.marking_result_json.stem,
        payload=merged,
    )
    resolved = resolve_marking_result(
        base_payload=base_payload,
        amendment_state=merged,
        valid_attempt_pages=inferred_attempt_pages,
    )
    return {
        "ok": True,
        "saved_path": path.relative_to(context_root).as_posix(),
        "amendment_state": merged,
        "marking_result_resolved": resolved,
    }


def validate_amendment_state(
    *,
    base_payload: dict[str, Any],
    amendment_state: dict[str, Any],
    valid_attempt_pages: set[int] | None = None,
) -> None:
    errors: list[dict[str, str]] = []
    rows = _question_rows_by_id(base_payload)
    page_rows = _page_rows_by_id(base_payload)

    for amendment in amendment_state.get("question_amendments", []):
        if not isinstance(amendment, dict):
            errors.append(_error("question_amendments", "question amendment must be an object"))
            continue
        result_id = amendment.get("result_id")
        if not isinstance(result_id, str) or not result_id.strip() or result_id not in rows:
            errors.append(_error("result_id", "question amendment result_id must exist in base artifact"))
            continue
        fields = amendment.get("fields")
        if not isinstance(fields, dict):
            errors.append(_error(f"question_amendments.{result_id}.fields", "fields must be an object"))
            continue
        if any(key in fields for key in SCORE_REASON_FIELD_KEYS):
            reason = amendment.get("reviewer_reason")
            if not isinstance(reason, str) or not reason.strip():
                errors.append(_error(f"question_amendments.{result_id}.reviewer_reason", "reviewer_reason is required for score-changing edits"))
        resolved_row = deepcopy(rows[result_id])
        _apply_fields_to_row(resolved_row, fields)
        _validate_question_fields(result_id=result_id, fields=fields, resolved_row=resolved_row, errors=errors)

    for amendment in amendment_state.get("question_page_map_amendments", []):
        if not isinstance(amendment, dict):
            errors.append(_error("question_page_map_amendments", "page-map amendment must be an object"))
            continue
        result_id = amendment.get("result_id")
        if not isinstance(result_id, str) or not result_id.strip() or result_id not in rows:
            errors.append(_error("question_page_map.result_id", "page-map amendment result_id must exist in base artifact"))
            continue
        if page_rows and result_id not in page_rows:
            errors.append(_error("question_page_map.result_id", "page-map amendment result_id must exist in base page map"))
        attempt_page_start = amendment.get("attempt_page_start")
        if attempt_page_start is not None:
            if not isinstance(attempt_page_start, int) or isinstance(attempt_page_start, bool) or attempt_page_start < 1:
                errors.append(_error(f"question_page_map.{result_id}.attempt_page_start", "attempt_page_start must be an integer >= 1"))
            elif valid_attempt_pages is not None and valid_attempt_pages and attempt_page_start not in valid_attempt_pages:
                errors.append(_error(f"question_page_map.{result_id}.attempt_page_start", "attempt_page_start must refer to an existing attempt page"))
        confidence = amendment.get("confidence")
        if confidence is not None and confidence not in ALLOWED_PAGE_MAP_CONFIDENCE:
            errors.append(_error(f"question_page_map.{result_id}.confidence", "confidence must be high|medium|low"))

    if errors:
        raise AmendmentValidationError(errors)


def _normalize_summary_overrides(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    if "human_note" in raw:
        out["human_note"] = _normalize_nullable_text(raw.get("human_note"))
    return out


def _normalize_question_amendments(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        result_id = row.get("result_id")
        fields = row.get("fields")
        if not isinstance(result_id, str) or not result_id.strip() or not isinstance(fields, dict):
            continue
        normalized_fields: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in QUESTION_FIELD_KEYS:
                normalized_fields[key] = value
                continue
            normalized_fields[key] = _normalize_field_value(key, value)
        item: dict[str, Any] = {"result_id": result_id.strip(), "fields": normalized_fields}
        if isinstance(row.get("reviewer_reason"), str):
            item["reviewer_reason"] = row["reviewer_reason"]
        if isinstance(row.get("evidence"), dict):
            item["evidence"] = row["evidence"]
        if isinstance(row.get("updated_at"), str):
            item["updated_at"] = row["updated_at"]
        if isinstance(row.get("updated_by"), str):
            item["updated_by"] = row["updated_by"]
        out.append(item)
    return out


def _normalize_page_map_amendments(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        result_id = row.get("result_id")
        if not isinstance(result_id, str) or not result_id.strip():
            continue
        item: dict[str, Any] = {"result_id": result_id.strip()}
        if "attempt_page_start" in row:
            item["attempt_page_start"] = row.get("attempt_page_start")
        if "confidence" in row:
            item["confidence"] = row.get("confidence")
        if isinstance(row.get("updated_at"), str):
            item["updated_at"] = row["updated_at"]
        if isinstance(row.get("updated_by"), str):
            item["updated_by"] = row["updated_by"]
        out.append(item)
    return out


def _normalize_field_value(key: str, value: Any) -> Any:
    if key in TEXT_FIELD_KEYS:
        return _normalize_nullable_text(value)
    if key == "skill_tags":
        return [tag for tag in value if isinstance(tag, str)] if isinstance(value, list) else value
    return value


def _normalize_nullable_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _question_rows_by_id(base_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = base_payload.get("question_results") if isinstance(base_payload.get("question_results"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("result_id"), str):
            out[row["result_id"]] = row
    return out


def _page_rows_by_id(base_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    context = base_payload.get("context") if isinstance(base_payload.get("context"), dict) else {}
    rows = context.get("question_page_map") if isinstance(context.get("question_page_map"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("result_id"), str):
            out[row["result_id"]] = row
    return out


def _apply_question_amendments(payload: dict[str, Any], amendment_state: dict[str, Any]) -> None:
    rows = _question_rows_by_id(payload)
    for amendment in amendment_state.get("question_amendments", []):
        if not isinstance(amendment, dict):
            continue
        result_id = amendment.get("result_id")
        fields = amendment.get("fields")
        if isinstance(result_id, str) and isinstance(fields, dict) and result_id in rows:
            _apply_fields_to_row(rows[result_id], fields)


def _apply_fields_to_row(row: dict[str, Any], fields: dict[str, Any]) -> None:
    for key, value in fields.items():
        if key == "diagnosis.mistake_type":
            diagnosis = row.setdefault("diagnosis", {})
            if isinstance(diagnosis, dict):
                diagnosis["mistake_type"] = value
        elif key == "diagnosis.reasoning":
            diagnosis = row.setdefault("diagnosis", {})
            if isinstance(diagnosis, dict):
                diagnosis["reasoning"] = value
        else:
            row[key] = value


def _apply_page_map_amendments(payload: dict[str, Any], amendment_state: dict[str, Any]) -> None:
    context = payload.setdefault("context", {})
    if not isinstance(context, dict):
        return
    page_map = context.setdefault("question_page_map", [])
    if not isinstance(page_map, list):
        return
    page_rows = _page_rows_by_id(payload)
    rows = _question_rows_by_id(payload)
    for amendment in amendment_state.get("question_page_map_amendments", []):
        if not isinstance(amendment, dict):
            continue
        result_id = amendment.get("result_id")
        if not isinstance(result_id, str) or result_id not in rows:
            continue
        target = page_rows.get(result_id)
        if target is None:
            target = {"result_id": result_id, "source": "manual_visual", "note": None}
            page_map.append(target)
            page_rows[result_id] = target
        for key in ("attempt_page_start", "confidence"):
            if key in amendment:
                target[key] = amendment[key]


def _apply_summary_overrides(payload: dict[str, Any], amendment_state: dict[str, Any]) -> None:
    summary = payload.setdefault("summary", {})
    if not isinstance(summary, dict):
        return
    summary.update(amendment_state.get("summary_overrides") or {})


def _recompute_summary_scores(payload: dict[str, Any]) -> None:
    rows = payload.get("question_results") if isinstance(payload.get("question_results"), list) else []
    total = 0.0
    earned = 0.0
    for row in rows:
        if not isinstance(row, dict) or row.get("scoring_status", "counted") != "counted":
            continue
        max_marks = _finite_mark(row.get("max_marks"))
        earned_marks = _finite_mark(row.get("earned_marks"))
        if max_marks is None or earned_marks is None:
            continue
        total += max_marks
        earned += earned_marks
    summary = payload.setdefault("summary", {})
    if isinstance(summary, dict):
        summary["total_marks"] = _clean_mark(total)
        summary["earned_marks"] = _clean_mark(earned)
        summary["percentage"] = compute_percentage(earned, total)


def _validate_question_fields(
    *,
    result_id: str,
    fields: dict[str, Any],
    resolved_row: dict[str, Any],
    errors: list[dict[str, str]],
) -> None:
    for key, value in fields.items():
        if key not in QUESTION_FIELD_KEYS:
            errors.append(_error(f"question_amendments.{result_id}.{key}", f"unsupported amendment field: {key}"))
            continue
        if key == "outcome" and value not in ALLOWED_OUTCOMES:
            errors.append(_error(f"question_amendments.{result_id}.outcome", "outcome must be correct|partial|wrong|disqualified"))
        if key in {"earned_marks", "max_marks"} and _finite_mark(value) is None:
            errors.append(_error(f"question_amendments.{result_id}.{key}", f"{key} must be a finite non-negative number"))
        if key == "skill_tags" and not _is_string_list(value):
            errors.append(_error(f"question_amendments.{result_id}.skill_tags", "skill_tags must be an array of strings"))
        if key in TEXT_FIELD_KEYS and value is not None and not isinstance(value, str):
            errors.append(_error(f"question_amendments.{result_id}.{key}", f"{key} must be a string or null"))
    max_marks = _finite_mark(resolved_row.get("max_marks"))
    earned_marks = _finite_mark(resolved_row.get("earned_marks"))
    if max_marks is not None and earned_marks is not None and earned_marks > max_marks + 1e-6:
        errors.append(_error(f"question_amendments.{result_id}.earned_marks", "earned_marks must be <= resolved max_marks"))


def _finite_mark(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return float(value) if value >= 0 else None
    if isinstance(value, float) and math.isfinite(value) and value >= 0:
        return value
    return None


def _clean_mark(value: float) -> int | float:
    return int(value) if math.isclose(value, round(value), abs_tol=1e-9) else round(value, 2)


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _upsert_question_amendment(rows: list[dict[str, Any]], incoming: dict[str, Any]) -> None:
    result_id = incoming["result_id"]
    for index, row in enumerate(rows):
        if row.get("result_id") == result_id:
            fields = row.get("fields") if isinstance(row.get("fields"), dict) else {}
            rows[index] = {
                **row,
                **incoming,
                "fields": {**fields, **incoming.get("fields", {})},
            }
            return
    rows.append(incoming)


def _upsert_page_map_amendment(rows: list[dict[str, Any]], incoming: dict[str, Any]) -> None:
    result_id = incoming["result_id"]
    for index, row in enumerate(rows):
        if row.get("result_id") == result_id:
            rows[index] = {**row, **incoming}
            return
    rows.append(incoming)


def _error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


def _valid_attempt_pages(*, base_payload: dict[str, Any], context_root: Path) -> set[int] | None:
    context = base_payload.get("context") if isinstance(base_payload.get("context"), dict) else {}
    marking_asset = context.get("marking_asset")
    if not isinstance(marking_asset, str) or not marking_asset.strip():
        return None
    attempt_dir = context_root / marking_asset / "attempt"
    if not attempt_dir.is_dir():
        return None
    pages: set[int] = set()
    for path in attempt_dir.iterdir():
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        match = re.search(r"(\d+)(?!.*\d)", path.stem)
        if match:
            pages.add(int(match.group(1)))
    return pages
