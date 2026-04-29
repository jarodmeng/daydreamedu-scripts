from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from ai_study_buddy.marking.core.marking_time import format_basename_timestamp
from ai_study_buddy.marking.core.models import MarkingArtifact

_PREFIXES = ("_raw_", "_c_", "raw_", "c_")


def parse_iso_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)


def normalize_attempt_stem(name_or_path: str | Path) -> str:
    stem = Path(name_or_path).stem
    changed = True
    while changed:
        changed = False
        for prefix in _PREFIXES:
            if stem.startswith(prefix):
                stem = stem[len(prefix) :]
                changed = True
                break
    return stem


def derive_unit_label_from_attempt_name(name_or_path: str | Path) -> str:
    """Human-facing unit label derived from attempt/template filename."""
    return normalize_attempt_stem(name_or_path)


def format_artifact_timestamp(value: str | datetime) -> str:
    """Basename suffix ``YYYYMMDD_HHMMSS`` in **Singapore (SGT)** wall time."""
    return format_basename_timestamp(value)


def build_attempt_basename(name_or_path: str | Path, *, marked_at: str | datetime) -> str:
    stem = normalize_attempt_stem(name_or_path)
    return f"{stem}__{format_artifact_timestamp(marked_at)}"


def slugify_student(student_id: str | None, student_name: str | None) -> str:
    raw = student_id or student_name or "unknown_student"
    return re.sub(r"[^a-z0-9]+", "_", raw.strip().casefold()).strip("_") or "unknown_student"


def build_marking_artifact_path(
    artifact: MarkingArtifact,
    *,
    context_root: str | Path = "ai_study_buddy/context",
) -> Path:
    root = Path(context_root)
    student_slug = slugify_student(artifact.context.student_id, artifact.context.student_name)
    basename = build_attempt_basename(artifact.context.attempt_file_path, marked_at=artifact.created_at)
    return (
        root
        / "marking_results"
        / student_slug
        / artifact.context.subject_context
        / f"{basename}.json"
    )


def build_learning_report_path(
    artifact: MarkingArtifact,
    *,
    context_root: str | Path = "ai_study_buddy/context",
) -> Path:
    root = Path(context_root)
    student_slug = slugify_student(artifact.context.student_id, artifact.context.student_name)
    basename = build_attempt_basename(artifact.context.attempt_file_path, marked_at=artifact.created_at)
    return (
        root
        / "learning_reports"
        / student_slug
        / artifact.context.subject_context
        / f"{basename} - Marking Report.md"
    )


def build_marking_run_paths(
    *,
    attempt_file_path: str | Path,
    student_id: str | None,
    student_name: str | None,
    subject_context: str,
    marked_at: str | datetime,
    context_root: str | Path = "ai_study_buddy/context",
) -> tuple[Path, str, Path]:
    """Build canonical JSON + marking-asset paths from one run timestamp.

    Returns ``(artifact_json_path, marking_asset_rel_path, bundle_root_path)`` where all
    paths share the same ``attempt_basename`` derived from ``marked_at``.
    """

    root = Path(context_root)
    student_slug = slugify_student(student_id, student_name)
    basename = build_attempt_basename(attempt_file_path, marked_at=marked_at)
    artifact_json_path = root / "marking_results" / student_slug / subject_context / f"{basename}.json"
    marking_asset_rel = f"marking_assets/{student_slug}/{subject_context}/{basename}"
    bundle_root = root / Path(marking_asset_rel)
    return artifact_json_path, marking_asset_rel, bundle_root
