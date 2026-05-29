from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal

from ai_study_buddy.marking.core.artifact_paths import parse_iso_datetime, slugify_student
from ai_study_buddy.marking.core.path_privacy import resolve_marking_artifact_paths
from ai_study_buddy.pdf_file_manager.pdf_file_manager import NotFoundError, PdfFile, PdfFileManager

MatchCondition = Literal["json_only", "json_and_report"]


@dataclass(frozen=True)
class MarkingArtifactRef:
    """One matched marking run: canonical JSON plus paired report path."""

    marking_result_json: Path
    learning_report_md: Path


@dataclass(frozen=True)
class MarkingArtifactIndex:
    """Pre-built marking artifact lookup (one filesystem scan under ``marking_results/``)."""

    by_completion_id: dict[str, tuple[MarkingArtifactRef, ...]]
    by_completion_path: dict[str, tuple[MarkingArtifactRef, ...]]


def build_marking_artifact_index(
    *,
    context_root: str | Path,
    match_condition: MatchCondition = "json_only",
) -> MarkingArtifactIndex:
    """Index marking-result JSON files by completion id and normalized attempt path."""
    root = Path(context_root)
    results_root = root / "marking_results"
    if not results_root.is_dir():
        return MarkingArtifactIndex(by_completion_id={}, by_completion_path={})

    by_id: dict[str, list[tuple[float, str, MarkingArtifactRef]]] = defaultdict(list)
    by_path: dict[str, list[tuple[float, str, MarkingArtifactRef]]] = defaultdict(list)

    for student_dir in results_root.iterdir():
        if not student_dir.is_dir():
            continue
        student_slug = student_dir.name
        for json_path in student_dir.rglob("*.json"):
            payload = _load_json_safely(json_path)
            if payload is None:
                continue
            context = payload.get("context")
            if not isinstance(context, dict):
                continue
            report_path = _build_report_path(
                json_path=json_path,
                context_root=root,
                student_slug=student_slug,
            )
            if match_condition == "json_and_report" and not report_path.exists():
                continue
            ref = MarkingArtifactRef(marking_result_json=json_path, learning_report_md=report_path)
            created_epoch = _as_utc_epoch(_parse_created_at(payload.get("created_at")))
            sort_key = json_path.as_posix()

            attempt_file_id = context.get("attempt_file_id")
            if isinstance(attempt_file_id, str) and attempt_file_id.strip():
                by_id[attempt_file_id.strip()].append((created_epoch, sort_key, ref))

            attempt_file_path = context.get("attempt_file_path")
            if isinstance(attempt_file_path, str) and attempt_file_path.strip():
                resolved = resolve_marking_artifact_paths(payload)
                resolved_context = resolved.get("context")
                if isinstance(resolved_context, dict):
                    resolved_path = resolved_context.get("attempt_file_path")
                    if isinstance(resolved_path, str) and resolved_path.strip():
                        norm = _normalize_path(resolved_path)
                        by_path[norm].append((created_epoch, sort_key, ref))

    def _finalize(
        buckets: dict[str, list[tuple[float, str, MarkingArtifactRef]]],
    ) -> dict[str, tuple[MarkingArtifactRef, ...]]:
        out: dict[str, tuple[MarkingArtifactRef, ...]] = {}
        for key, entries in buckets.items():
            entries.sort(key=lambda row: (-row[0], row[1]))
            out[key] = tuple(ref for _, _, ref in entries)
        return out

    return MarkingArtifactIndex(
        by_completion_id=_finalize(by_id),
        by_completion_path=_finalize(by_path),
    )


def _refs_from_index(
    index: MarkingArtifactIndex,
    *,
    completion_id: str,
    completion_path: str,
) -> list[MarkingArtifactRef]:
    refs = index.by_completion_id.get(completion_id)
    if refs:
        return list(refs)
    refs = index.by_completion_path.get(completion_path)
    if refs:
        return list(refs)
    return []


def _find_via_filesystem(
    *,
    completion_file: PdfFile,
    student_slug: str,
    student_email: str | None,
    completion_path: str,
    match_condition: MatchCondition,
    root: Path,
) -> list[MarkingArtifactRef]:
    completion_id = completion_file.id

    student_results_root = root / "marking_results" / student_slug
    if not student_results_root.exists():
        return []

    matches: list[tuple[datetime, Path, Path]] = []
    for json_path in student_results_root.rglob("*.json"):
        matched, created_at = _json_matches_completion(
            json_path=json_path,
            completion_id=completion_id,
            completion_path=completion_path,
            completion_student_email=student_email,
        )
        if not matched:
            continue
        report_path = _build_report_path(
            json_path=json_path,
            context_root=root,
            student_slug=student_slug,
        )
        if match_condition == "json_and_report" and not report_path.exists():
            continue
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


def find_marking_artifacts_for_attempt(
    attempt_file_id_or_path: str | Path,
    *,
    match_condition: MatchCondition = "json_only",
    manager: PdfFileManager | None = None,
    context_root: str | Path = "ai_study_buddy/context",
    artifact_index: MarkingArtifactIndex | None = None,
) -> list[MarkingArtifactRef]:
    """Return matched artifacts for one completion attempt.

    Results are sorted by created_at (descending), then by JSON path (ascending).

    When ``LEARNING_DB_ENABLE_READS=1``, rows in ``study_buddy.db`` are considered first (same
    match rules via ``payload_matches_completion``). If no rows qualify and
    ``LEARNING_DB_READ_FALLBACK_FILESYSTEM=1`` (default), falls back to scanning
    ``context/marking_results/<student_slug>/**/*.json`` as historically.
    """
    if match_condition not in {"json_only", "json_and_report"}:
        raise ValueError(
            "match_condition must be 'json_only' or 'json_and_report'"
        )
    completion_file, student_slug, student_email = _resolve_completion_and_student(
        attempt_file_id_or_path, manager=manager
    )
    completion_path = _normalize_path(completion_file.path)

    if artifact_index is not None:
        indexed = _refs_from_index(
            artifact_index,
            completion_id=completion_file.id,
            completion_path=completion_path,
        )
        if indexed:
            return indexed

    root = Path(context_root)

    try:
        from ai_study_buddy.learning_db.core.config import (
            learning_db_read_fallback_filesystem,
            learning_db_reads_enabled,
        )
        from ai_study_buddy.learning_db.read.read_marking import find_marking_artifact_refs_from_db
    except ImportError:
        return _find_via_filesystem(
            completion_file=completion_file,
            student_slug=student_slug,
            student_email=student_email,
            completion_path=completion_path,
            match_condition=match_condition,
            root=root,
        )

    if not learning_db_reads_enabled():
        return _find_via_filesystem(
            completion_file=completion_file,
            student_slug=student_slug,
            student_email=student_email,
            completion_path=completion_path,
            match_condition=match_condition,
            root=root,
        )

    db_refs = find_marking_artifact_refs_from_db(
        completion_file=completion_file,
        student_slug=student_slug,
        completion_path=completion_path,
        completion_student_email=student_email,
        match_condition=match_condition,
        context_root=root,
    )
    if db_refs:
        return db_refs
    if learning_db_read_fallback_filesystem():
        return _find_via_filesystem(
            completion_file=completion_file,
            student_slug=student_slug,
            student_email=student_email,
            completion_path=completion_path,
            match_condition=match_condition,
            root=root,
        )
    return []


def _resolve_completion_and_student(
    attempt_file_id_or_path: str | Path,
    *,
    manager: PdfFileManager | None,
) -> tuple[PdfFile, str, str | None]:
    if manager is None:
        raise ValueError(
            "find_marking_artifacts_for_attempt requires manager for student-scoped lookup"
        )

    raw = str(attempt_file_id_or_path)
    is_path_like = "/" in raw or "\\" in raw or raw.lower().endswith(".pdf")
    completion = (
        manager.get_file_by_path(Path(raw).expanduser().resolve(strict=False))
        if is_path_like
        else manager.get_file(raw)
    )
    if completion is None:
        raise NotFoundError(f"Attempt file not found: {attempt_file_id_or_path}")

    if not completion.student_id:
        raise ValueError(
            "Completion file is missing student_id; cannot derive student-scoped lookup root"
        )
    student = manager.get_student(completion.student_id)
    student_slug = slugify_student(completion.student_id, student.name if student else None)
    student_email = student.email if student else None
    return completion, student_slug, student_email


def payload_matches_completion(
    payload: dict,
    *,
    completion_id: str,
    completion_path: str,
    completion_student_email: str | None,
) -> tuple[bool, datetime]:
    """Return whether a marking-result dict belongs to this completion (+ created_at ordering key)."""

    created_at = _parse_created_at(payload.get("created_at"))
    context = payload.get("context")
    if not isinstance(context, dict):
        return False, created_at

    attempt_file_id = context.get("attempt_file_id")
    attempt_file_id = attempt_file_id.strip() if isinstance(attempt_file_id, str) else None
    attempt_file_id = attempt_file_id or None

    if attempt_file_id is not None:
        if attempt_file_id == completion_id:
            return True, created_at
        return False, created_at

    resolved_attempt_path = _resolve_artifact_attempt_path(
        payload=payload,
        completion_student_email=completion_student_email,
    )
    if resolved_attempt_path is None:
        return False, created_at

    return resolved_attempt_path == completion_path, created_at


def _json_matches_completion(
    *,
    json_path: Path,
    completion_id: str,
    completion_path: str,
    completion_student_email: str | None,
) -> tuple[bool, datetime]:
    payload = _load_json_safely(json_path)
    if payload is None:
        return False, datetime.min.replace(tzinfo=timezone.utc)
    return payload_matches_completion(
        payload,
        completion_id=completion_id,
        completion_path=completion_path,
        completion_student_email=completion_student_email,
    )


def _load_json_safely(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_artifact_attempt_path(
    *,
    payload: dict,
    completion_student_email: str | None,
) -> str | None:
    context = payload.get("context")
    if not isinstance(context, dict):
        return None
    attempt_file_path = context.get("attempt_file_path")
    if not isinstance(attempt_file_path, str) or not attempt_file_path.strip():
        return None

    resolved_payload = resolve_marking_artifact_paths(payload)
    resolved_context = resolved_payload.get("context")
    if not isinstance(resolved_context, dict):
        return None
    resolved_path = resolved_context.get("attempt_file_path")
    if not isinstance(resolved_path, str) or not resolved_path.strip():
        return None

    if completion_student_email:
        resolved_path = resolved_path.replace("<student_email>", completion_student_email)
    return _normalize_path(resolved_path)


def _normalize_path(value: str | Path) -> str:
    return Path(value).expanduser().resolve(strict=False).as_posix()


def _build_report_path(
    *,
    json_path: Path,
    context_root: Path,
    student_slug: str,
) -> Path:
    """Map a marking-result JSON path to its paired learning report path.

    Supports subject-scope subfolders (e.g. ``marking_results/winston/singapore_primary_math/``).
    """
    results_student_root = (context_root / "marking_results" / student_slug).resolve(strict=False)
    json_resolved = Path(json_path).resolve(strict=False)
    relative_parent = json_resolved.parent.relative_to(results_student_root)
    return (
        context_root.resolve(strict=False)
        / "learning_reports"
        / student_slug
        / relative_parent
        / f"{json_path.stem} - Marking Report.md"
    )


def _parse_created_at(value: object) -> datetime:
    if isinstance(value, str) and value.strip():
        try:
            parsed = parse_iso_datetime(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


def _as_utc_epoch(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).timestamp()
