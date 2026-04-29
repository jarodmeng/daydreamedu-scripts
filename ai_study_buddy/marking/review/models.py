from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATIC_ROUTE_PREFIX = "/review-workspace-static"


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_timestamp(value: str | None, *, fallback: datetime | None = None) -> datetime:
    if isinstance(value, str) and value.strip():
        candidate = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            pass
    if fallback is not None:
        return fallback
    return datetime.min.replace(tzinfo=timezone.utc)


def attempt_title(context: dict[str, Any], *, attempt_path: str | None = None) -> str:
    unit_label = context.get("unit_label")
    if isinstance(unit_label, str) and unit_label.strip():
        return unit_label.strip()
    if isinstance(attempt_path, str) and attempt_path.strip():
        return Path(attempt_path).stem
    attempt_file_path = context.get("attempt_file_path")
    if isinstance(attempt_file_path, str) and attempt_file_path.strip():
        return Path(attempt_file_path).stem
    return "Untitled Attempt"


def default_review_state() -> dict[str, Any]:
    return {
        "review_status": "not_started",
        "question_reviews": [],
        "attempt_notes": [],
        "student_subject_notes": [],
    }


def normalize_review_state(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return default_review_state()

    summary = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
    review_status = raw.get("review_status") or summary.get("review_status")
    if review_status not in {"not_started", "in_progress", "completed"}:
        review_status = "not_started"

    return {
        "review_status": review_status,
        "question_reviews": raw.get("question_reviews") if isinstance(raw.get("question_reviews"), list) else [],
        "attempt_notes": raw.get("attempt_notes") if isinstance(raw.get("attempt_notes"), list) else [],
        "student_subject_notes": raw.get("student_subject_notes")
        if isinstance(raw.get("student_subject_notes"), list)
        else [],
    }


def infer_grade_bucket(path: str) -> str | None:
    path_upper = path.upper()
    for bucket in ("PSLE", "P6", "P5", "P4", "P3", "P2", "P1"):
        if f"/{bucket}/" in path_upper:
            return bucket
    return None


def infer_subject_context(subject: str | None) -> str | None:
    mapping = {
        "math": "singapore_primary_math",
        "science": "singapore_primary_science",
        "english": "singapore_primary_english",
        "chinese": "singapore_primary_chinese",
    }
    return mapping.get(subject or "")
