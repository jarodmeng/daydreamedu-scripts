from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ai_study_buddy.marking.core.taxonomy import (
    DIAGNOSIS_CONFIDENCE_LEVELS,
    DIAGNOSIS_MISTAKE_TYPES,
    ERROR_TAGS,
)

SCHEMA_VERSION = "marking_result.v1.5"
DEFAULT_MARKING_RESULT_VERSION = SCHEMA_VERSION
SUPPORTED_SCHEMA_VERSIONS = {SCHEMA_VERSION}
SCHEMA_PATHS_BY_VERSION: dict[str, Path] = {
    SCHEMA_VERSION: Path(__file__).resolve().parent.parent / "schemas" / "marking_result.v1.5.schema.json",
}
SCHEMA_PATH = SCHEMA_PATHS_BY_VERSION[SCHEMA_VERSION]
AMENDMENT_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "marking_amendment.v1.schema.json"
ALLOWED_OUTCOMES = {"correct", "partial", "wrong", "disqualified"}
ALLOWED_SCORING_STATUS = {"counted", "excluded_disqualified"}
ALLOWED_PAGE_MAP_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_PAGE_MAP_SOURCES = {"manual_visual", "ai_visual_backfill", "script_inferred"}


class MarkingArtifactValidationError(ValueError):
    pass


class UnsupportedSchemaVersionError(MarkingArtifactValidationError):
    pass


def load_marking_result_schema(version: str) -> dict[str, Any]:
    schema_path = SCHEMA_PATHS_BY_VERSION.get(version)
    if schema_path is None:
        raise UnsupportedSchemaVersionError(
            f"unsupported schema_version: {version}. Supported versions: {SCHEMA_VERSION}"
        )
    return json.loads(schema_path.read_text(encoding="utf-8"))


def load_marking_amendment_schema() -> dict[str, Any]:
    return json.loads(AMENDMENT_SCHEMA_PATH.read_text(encoding="utf-8"))


def compute_percentage(earned_marks: float | int, total_marks: float | int) -> float:
    tm = float(total_marks)
    if tm <= 0:
        return 0.0
    return round((float(earned_marks) / tm) * 100.0, 2)


def _finite_mark_scalar(value: Any) -> float | None:
    """Return a non-negative float mark, or None if invalid (rejects bool)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value
    return None


_MARK_SUM_TOLERANCE = 1e-6


def _normalize_for_json_schema(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalize_for_json_schema(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_normalize_for_json_schema(v) for v in value]
    if isinstance(value, list):
        return [_normalize_for_json_schema(v) for v in value]
    return value


def _collect_schema_errors(data: dict[str, Any]) -> list[str]:
    schema_version = data.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise UnsupportedSchemaVersionError(
            f"unsupported schema_version: {schema_version}. Supported versions: {SCHEMA_VERSION}"
        )
    schema = load_marking_result_schema(schema_version)
    normalized_data = _normalize_for_json_schema(data)
    schema_errors = sorted(Draft202012Validator(schema).iter_errors(normalized_data), key=lambda e: list(e.path))
    messages: list[str] = []
    for error in schema_errors:
        path = ".".join(str(part) for part in error.absolute_path)
        if path:
            messages.append(f"{path}: {error.message}")
        else:
            messages.append(error.message)
    return messages


def validate_marking_artifact_dict(data: dict[str, Any]) -> None:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    errors.extend(_collect_schema_errors(data))

    for key in ("created_at", "updated_at", "context", "summary", "question_results", "review_meta", "generation"):
        require(key in data, f"missing top-level field: {key}")

    context = data.get("context")
    summary = data.get("summary")
    question_results = data.get("question_results")

    require(isinstance(context, dict), "context must be an object")
    require(isinstance(summary, dict), "summary must be an object")
    require(isinstance(question_results, (list, tuple)), "question_results must be an array")

    if isinstance(context, dict):
        require(bool(context.get("subject_context")), "context.subject_context must be non-empty")
        require(bool(context.get("attempt_file_path")), "context.attempt_file_path must be non-empty")
        group_id = context.get("template_attempt_group_id")
        attempt_sequence = context.get("attempt_sequence")
        attempt_label = context.get("attempt_label")

        require(
            group_id is None or (isinstance(group_id, str) and bool(group_id.strip())),
            "context.template_attempt_group_id must be null or non-empty string",
        )
        require(
            attempt_sequence is None or (isinstance(attempt_sequence, int) and attempt_sequence >= 1),
            "context.attempt_sequence must be null or int >= 1",
        )
        require(
            attempt_label is None or (isinstance(attempt_label, str) and bool(attempt_label.strip())),
            "context.attempt_label must be null or non-empty string",
        )
        marking_asset = context.get("marking_asset")
        require(
            marking_asset is None or (isinstance(marking_asset, str) and bool(marking_asset.strip())),
            "context.marking_asset must be null or non-empty string",
        )
        is_partial = context.get("is_partial")
        require(
            isinstance(is_partial, bool),
            "context.is_partial must be a boolean",
        )
        if isinstance(attempt_label, str):
            require(len(attempt_label) <= 64, "context.attempt_label must be <= 64 chars")
        question_page_map = context.get("question_page_map")
        require(isinstance(question_page_map, (list, tuple)), "context.question_page_map must be an array")

    expected_total = 0
    expected_earned = 0

    if isinstance(question_results, (list, tuple)):
        seen_ids: set[str] = set()
        for index, row in enumerate(question_results, start=1):
            require(isinstance(row, dict), f"question_results[{index}] must be an object")
            if not isinstance(row, dict):
                continue
            result_id = row.get("result_id")
            require(bool(result_id), f"question_results[{index}].result_id must be non-empty")
            if isinstance(result_id, str):
                require(result_id not in seen_ids, f"duplicate result_id: {result_id}")
                seen_ids.add(result_id)

            scoring_status = row.get("scoring_status", "counted")
            require(
                scoring_status in ALLOWED_SCORING_STATUS,
                f"question_results[{index}].scoring_status must be counted|excluded_disqualified",
            )

            max_marks = row.get("max_marks")
            earned_marks = row.get("earned_marks")
            mx = _finite_mark_scalar(max_marks)
            er = _finite_mark_scalar(earned_marks)
            require(mx is not None, f"question_results[{index}].max_marks must be a non-negative int or finite float (not bool)")
            require(er is not None, f"question_results[{index}].earned_marks must be a non-negative int or finite float (not bool)")
            require(mx >= 0, f"question_results[{index}].max_marks must be >= 0")
            require(er >= 0, f"question_results[{index}].earned_marks must be >= 0")
            require(er <= mx + _MARK_SUM_TOLERANCE, f"question_results[{index}].earned_marks must be <= max_marks")
            if scoring_status == "counted":
                expected_total += mx
                expected_earned += er

            outcome = row.get("outcome")
            require(
                outcome in ALLOWED_OUTCOMES,
                f"question_results[{index}].outcome must be correct|partial|wrong|disqualified",
            )
            if scoring_status == "excluded_disqualified":
                require(
                    outcome == "disqualified",
                    f"question_results[{index}] with excluded_disqualified must have outcome=disqualified",
                )

            error_tags = row.get("error_tags", [])
            require(isinstance(error_tags, (list, tuple)), f"question_results[{index}].error_tags must be an array")
            if isinstance(error_tags, (list, tuple)):
                for tag in error_tags:
                    require(tag in ERROR_TAGS, f"question_results[{index}].error_tags contains invalid tag: {tag}")

            skill_tags = row.get("skill_tags", [])
            require(isinstance(skill_tags, (list, tuple)), f"question_results[{index}].skill_tags must be an array")

            diagnosis = row.get("diagnosis", {})
            require(isinstance(diagnosis, dict), f"question_results[{index}].diagnosis must be an object")
            if isinstance(diagnosis, dict):
                mistake_type = diagnosis.get("mistake_type")
                confidence = diagnosis.get("confidence")
                require(
                    mistake_type is None or mistake_type in DIAGNOSIS_MISTAKE_TYPES,
                    f"question_results[{index}].diagnosis.mistake_type is invalid",
                )
                require(
                    confidence is None or confidence in DIAGNOSIS_CONFIDENCE_LEVELS,
                    f"question_results[{index}].diagnosis.confidence is invalid",
                )

    if isinstance(context, dict) and isinstance(question_results, (list, tuple)):
        question_page_map = context.get("question_page_map", [])
        result_ids = {row.get("result_id") for row in question_results if isinstance(row, dict) and isinstance(row.get("result_id"), str)}
        if isinstance(question_page_map, (list, tuple)):
            seen_map_result_ids: set[str] = set()
            for index, entry in enumerate(question_page_map, start=1):
                require(isinstance(entry, dict), f"context.question_page_map[{index}] must be an object")
                if not isinstance(entry, dict):
                    continue
                mapped_result_id = entry.get("result_id")
                require(
                    isinstance(mapped_result_id, str) and bool(mapped_result_id.strip()),
                    f"context.question_page_map[{index}].result_id must be a non-empty string",
                )
                if isinstance(mapped_result_id, str):
                    require(
                        mapped_result_id not in seen_map_result_ids,
                        f"duplicate context.question_page_map result_id: {mapped_result_id}",
                    )
                    seen_map_result_ids.add(mapped_result_id)
                    require(
                        mapped_result_id in result_ids,
                        f"context.question_page_map[{index}].result_id must match question_results[].result_id",
                    )

                attempt_page_start = entry.get("attempt_page_start")
                require(
                    isinstance(attempt_page_start, int) and not isinstance(attempt_page_start, bool) and attempt_page_start >= 1,
                    f"context.question_page_map[{index}].attempt_page_start must be int >= 1",
                )
                confidence = entry.get("confidence")
                require(
                    confidence in ALLOWED_PAGE_MAP_CONFIDENCE,
                    f"context.question_page_map[{index}].confidence must be high|medium|low",
                )
                source = entry.get("source")
                require(
                    source in ALLOWED_PAGE_MAP_SOURCES,
                    f"context.question_page_map[{index}].source must be manual_visual|ai_visual_backfill|script_inferred",
                )
                evidence_image = entry.get("evidence_image")
                require(
                    evidence_image is None or (isinstance(evidence_image, str) and bool(evidence_image.strip())),
                    f"context.question_page_map[{index}].evidence_image must be null or non-empty string",
                )
                note = entry.get("note")
                require(
                    note is None or isinstance(note, str),
                    f"context.question_page_map[{index}].note must be null or string",
                )

    if isinstance(summary, dict):
        total_marks = summary.get("total_marks")
        earned_marks = summary.get("earned_marks")
        percentage = summary.get("percentage")
        st = _finite_mark_scalar(total_marks)
        se = _finite_mark_scalar(earned_marks)
        require(st is not None, "summary.total_marks must be a non-negative int or finite float (not bool)")
        require(se is not None, "summary.earned_marks must be a non-negative int or finite float (not bool)")
        require(st >= 0, "summary.total_marks must be >= 0")
        require(se >= 0, "summary.earned_marks must be >= 0")
        require(isinstance(percentage, (int, float)), "summary.percentage must be numeric")
        require(math.isclose(st, expected_total, rel_tol=0, abs_tol=_MARK_SUM_TOLERANCE), "summary.total_marks must equal sum(question_results[].max_marks)")
        require(math.isclose(se, expected_earned, rel_tol=0, abs_tol=_MARK_SUM_TOLERANCE), "summary.earned_marks must equal sum(question_results[].earned_marks)")
        if isinstance(percentage, (int, float)):
            expected_percentage = compute_percentage(se, st)
            require(abs(float(percentage) - expected_percentage) < 0.01, "summary.percentage is inconsistent with totals")

    if errors:
        raise MarkingArtifactValidationError("\n".join(errors))
