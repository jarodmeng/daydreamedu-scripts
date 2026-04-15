from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_study_buddy.marking.core.taxonomy import (
    DIAGNOSIS_CONFIDENCE_LEVELS,
    DIAGNOSIS_MISTAKE_TYPES,
    ERROR_TAGS,
)

SCHEMA_VERSION = "marking_result.v1"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "marking_result.v1.schema.json"
ALLOWED_OUTCOMES = {"correct", "partial", "wrong", "disqualified"}
ALLOWED_SCORING_STATUS = {"counted", "excluded_disqualified"}


class MarkingArtifactValidationError(ValueError):
    pass


def load_marking_result_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def compute_percentage(earned_marks: int, total_marks: int) -> float:
    if total_marks <= 0:
        return 0.0
    return round((earned_marks / total_marks) * 100.0, 2)


def validate_marking_artifact_dict(data: dict[str, Any]) -> None:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(data.get("schema_version") == SCHEMA_VERSION, "schema_version must be marking_result.v1")

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
            require(isinstance(max_marks, int), f"question_results[{index}].max_marks must be int")
            require(isinstance(earned_marks, int), f"question_results[{index}].earned_marks must be int")
            if isinstance(max_marks, int) and isinstance(earned_marks, int):
                require(max_marks >= 0, f"question_results[{index}].max_marks must be >= 0")
                require(earned_marks >= 0, f"question_results[{index}].earned_marks must be >= 0")
                require(earned_marks <= max_marks, f"question_results[{index}].earned_marks must be <= max_marks")
                if scoring_status == "counted":
                    expected_total += max_marks
                    expected_earned += earned_marks

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

    if isinstance(summary, dict):
        total_marks = summary.get("total_marks")
        earned_marks = summary.get("earned_marks")
        percentage = summary.get("percentage")
        require(isinstance(total_marks, int), "summary.total_marks must be int")
        require(isinstance(earned_marks, int), "summary.earned_marks must be int")
        require(isinstance(percentage, (int, float)), "summary.percentage must be numeric")
        if isinstance(total_marks, int) and isinstance(earned_marks, int):
            require(total_marks == expected_total, "summary.total_marks must equal sum(question_results[].max_marks)")
            require(earned_marks == expected_earned, "summary.earned_marks must equal sum(question_results[].earned_marks)")
            if isinstance(percentage, (int, float)):
                expected_percentage = compute_percentage(earned_marks, total_marks)
                require(abs(float(percentage) - expected_percentage) < 0.01, "summary.percentage is inconsistent with totals")

    if errors:
        raise MarkingArtifactValidationError("\n".join(errors))
