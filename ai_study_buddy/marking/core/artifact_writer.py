from __future__ import annotations

import json
from pathlib import Path

from ai_study_buddy.marking.assets.layout import ATTEMPT_DIRNAME, CROPS_DIRNAME
from ai_study_buddy.marking.assets.paths import bundle_root_from_context, marking_asset_rel_path_from_artifact_path
from ai_study_buddy.marking.core.artifact_paths import build_marking_artifact_path, slugify_student
from ai_study_buddy.marking.core.artifact_schema import (
    DEFAULT_MARKING_RESULT_VERSION,
    validate_marking_artifact_dict,
)
from ai_study_buddy.marking.core.marking_time import to_marking_iso
from ai_study_buddy.marking.core.partial_marking import infer_is_partial_from_raw_text
from ai_study_buddy.marking.core.path_privacy import sanitize_marking_artifact_paths
from ai_study_buddy.marking.core.models import MarkingArtifact
from ai_study_buddy.marking.core.artifact_paths import derive_unit_label_from_attempt_name


def _assert_context_contract(payload: dict) -> None:
    context = payload.get("context")
    if not isinstance(context, dict):
        raise ValueError("context contract failure: context must be an object")
    resolution = context.get("context_resolution")
    if not isinstance(resolution, dict):
        raise ValueError("context contract failure: context.context_resolution is required")
    for key in ("method", "resolver_version", "resolved_at", "mode"):
        if not isinstance(resolution.get(key), str) or not resolution[key].strip():
            raise ValueError(f"context contract failure: context.context_resolution.{key} must be non-empty string")

    method = resolution["method"].strip()
    if method != "resolve_marking_context":
        raise ValueError("context contract failure: context.context_resolution.method must be resolve_marking_context")

    mode = resolution["mode"].strip()
    allowed_modes = {"standard_mapped_answer", "embedded_answer_override", "teacher_annotated"}
    if mode not in allowed_modes:
        raise ValueError(
            f"context contract failure: context.context_resolution.mode must be one of {sorted(allowed_modes)}"
        )

    subject_context = context.get("subject_context")
    if not isinstance(subject_context, str) or not subject_context.strip():
        raise ValueError("context contract failure: context.subject_context must be non-empty string")

    attempt_file_path = context.get("attempt_file_path")
    if not isinstance(attempt_file_path, str) or not attempt_file_path.strip():
        raise ValueError("context contract failure: context.attempt_file_path must be non-empty string")

    unit_label = context.get("unit_label")
    unit_file_path = context.get("unit_file_path")
    if isinstance(unit_label, str) and unit_label.strip() and isinstance(unit_file_path, str) and unit_file_path.strip():
        expected = derive_unit_label_from_attempt_name(unit_file_path)
        if unit_label.strip() != expected:
            raise ValueError(
                "context contract failure: context.unit_label must match normalized unit_file_path stem "
                f"(expected {expected!r}, got {unit_label!r})"
            )

    if mode == "embedded_answer_override":
        if context.get("answer_file_id") != context.get("template_file_id"):
            raise ValueError(
                "context contract failure: embedded_answer_override requires answer_file_id == template_file_id"
            )
        if context.get("answer_file_path") != context.get("template_file_path"):
            raise ValueError(
                "context contract failure: embedded_answer_override requires answer_file_path == template_file_path"
            )
        page_start = context.get("answer_page_start")
        page_end = context.get("answer_page_end")
        if not isinstance(page_start, int) or not isinstance(page_end, int) or page_start < 1 or page_end < page_start:
            raise ValueError(
                "context contract failure: embedded_answer_override requires valid answer_page_start/end range"
            )

    if mode == "teacher_annotated":
        for key in ("answer_file_id", "answer_file_path", "answer_page_start", "answer_page_end"):
            if context.get(key) is not None:
                raise ValueError(f"context contract failure: teacher_annotated requires context.{key} to be null")

    if mode == "standard_mapped_answer":
        page_start = context.get("answer_page_start")
        page_end = context.get("answer_page_end")
        if not isinstance(context.get("answer_file_id"), str) or not context["answer_file_id"].strip():
            raise ValueError("context contract failure: standard_mapped_answer requires non-empty answer_file_id")
        if not isinstance(context.get("answer_file_path"), str) or not context["answer_file_path"].strip():
            raise ValueError("context contract failure: standard_mapped_answer requires non-empty answer_file_path")
        if not isinstance(page_start, int) or not isinstance(page_end, int) or page_start < 1 or page_end < page_start:
            raise ValueError(
                "context contract failure: standard_mapped_answer requires valid answer_page_start/end range"
            )


def write_marking_artifact(
    artifact: MarkingArtifact,
    *,
    output_path: str | Path | None = None,
    context_root: str | Path = "ai_study_buddy/context",
    schema_version: str | None = None,
    actor: str = "script:ai_study_buddy.marking.core.artifact_writer",
) -> Path:
    selected_schema_version = DEFAULT_MARKING_RESULT_VERSION if schema_version is None else schema_version
    if selected_schema_version == "latest":
        raise ValueError('schema_version must be explicit; "latest" is not supported')
    payload = artifact.to_dict()
    payload["schema_version"] = selected_schema_version
    payload["created_at"] = to_marking_iso(payload["created_at"])
    payload["updated_at"] = to_marking_iso(payload["updated_at"])
    payload = _apply_attempt_metadata(payload=payload, context_root=context_root)
    payload = _apply_partial_scope(payload=payload)
    payload = sanitize_marking_artifact_paths(payload)
    _assert_context_contract(payload)
    path = Path(output_path) if output_path is not None else build_marking_artifact_path(
        MarkingArtifact.from_dict(payload), context_root=context_root
    )
    payload = _apply_marking_asset_path(payload=payload, artifact_json_path=path, context_root=context_root)
    validate_marking_artifact_dict(payload)

    _ensure_marking_asset_dir(payload=payload, context_root=context_root)

    canonical = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"

    from ai_study_buddy.learning_db.core.config import learning_db_dual_write_enabled, learning_db_json_export_enabled
    from ai_study_buddy.learning_db.ingest.dual_write import maybe_dual_write_from_canonical, maybe_dual_write_snapshot
    from ai_study_buddy.learning_db.cli.write_boundary_audit import audit_write_boundary_event

    ctxp = Path(context_root).expanduser().resolve()

    rel = path.expanduser().resolve().relative_to(ctxp).as_posix()
    try:
        if learning_db_json_export_enabled():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(canonical, encoding="utf-8")
            maybe_dual_write_snapshot(
                family="marking_result",
                snapshot_path=path,
                context_root=context_root,
            )
        else:
            if not learning_db_dual_write_enabled():
                raise ValueError(
                    "LEARNING_DB_ENABLE_JSON_EXPORT=0 requires LEARNING_DB_ENABLE_DUAL_WRITE=1 for write_marking_artifact "
                    "to persist into study_buddy.db (no on-disk snapshot is written)"
                )
            maybe_dual_write_from_canonical(
                family="marking_result",
                rel_path=rel,
                canonical_snapshot_text=canonical,
            )
    except Exception as exc:
        audit_write_boundary_event(
            operation_type="marking_artifact_write",
            entity_type="marking_result",
            entity_id=rel,
            status="failed",
            actor=actor,
            metadata={"context_root": str(ctxp)},
            error_code=type(exc).__name__,
            error_message=str(exc),
        )
        raise
    audit_write_boundary_event(
        operation_type="marking_artifact_write",
        entity_type="marking_result",
        entity_id=rel,
        status="succeeded",
        actor=actor,
        metadata={"context_root": str(ctxp)},
    )
    return path


def _apply_attempt_metadata(*, payload: dict, context_root: str | Path) -> dict:
    context = payload.get("context")
    if not isinstance(context, dict):
        return payload

    student_slug = slugify_student(context.get("student_id"), context.get("student_name"))
    template_file_id = context.get("template_file_id")
    if not isinstance(template_file_id, str) or not template_file_id.strip():
        context["template_attempt_group_id"] = None
        context["attempt_sequence"] = None
        context.setdefault("attempt_label", None)
        return payload

    group_id = f"{student_slug}::{template_file_id}"
    context["template_attempt_group_id"] = group_id
    context.setdefault("attempt_label", None)
    if context.get("attempt_sequence") is None:
        context["attempt_sequence"] = _next_attempt_sequence(
            context_root=Path(context_root),
            student_slug=student_slug,
            group_id=group_id,
            template_file_id=template_file_id,
        )
    return payload


def _next_attempt_sequence(
    *,
    context_root: Path,
    student_slug: str,
    group_id: str,
    template_file_id: str,
) -> int:
    student_results_root = context_root / "marking_results" / student_slug
    if not student_results_root.exists():
        return 1

    sequences: list[int] = []
    legacy_count = 0
    for json_path in student_results_root.rglob("*.json"):
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        context = raw.get("context")
        if not isinstance(context, dict):
            continue
        existing_group = context.get("template_attempt_group_id")
        if isinstance(existing_group, str) and existing_group == group_id:
            seq = context.get("attempt_sequence")
            if isinstance(seq, int) and seq >= 1:
                sequences.append(seq)
                continue
        existing_template_id = context.get("template_file_id")
        if isinstance(existing_template_id, str) and existing_template_id == template_file_id:
            seq = context.get("attempt_sequence")
            if isinstance(seq, int) and seq >= 1:
                sequences.append(seq)
            else:
                # Legacy v1 artifacts without attempt metadata still count as attempts.
                legacy_count += 1
    if sequences:
        return max(max(sequences), legacy_count) + 1
    return legacy_count + 1 if legacy_count else 1


def _apply_marking_asset_path(
    *,
    payload: dict,
    artifact_json_path: Path,
    context_root: str | Path,
) -> dict:
    context = payload.get("context")
    if not isinstance(context, dict):
        return payload

    expected_rel = marking_asset_rel_path_from_artifact_path(
        artifact_json_path=artifact_json_path,
        context_root=context_root,
    )

    existing = context.get("marking_asset")
    if isinstance(existing, str) and existing.strip():
        if bundle_root_from_context(context, context_root=context_root) is None:
            raise ValueError(
                "context contract failure: context.marking_asset must be a normalized relative path under "
                "context_root/marking_assets"
            )
        if expected_rel is not None and existing != expected_rel:
            raise ValueError(
                "context contract failure: context.marking_asset must match canonical artifact-derived path "
                f"(expected {expected_rel!r}, got {existing!r})"
            )
        return payload

    if expected_rel is None:
        context.setdefault("marking_asset", None)
        return payload

    context["marking_asset"] = expected_rel
    return payload


def _apply_partial_scope(*, payload: dict) -> dict:
    context = payload.get("context")
    if not isinstance(context, dict):
        return payload
    context.setdefault("question_page_map", [])
    if isinstance(context.get("is_partial"), bool):
        return payload
    question_selection = context.get("question_selection")
    if isinstance(question_selection, dict):
        raw_text = question_selection.get("raw_text")
    else:
        raw_text = None
    context["is_partial"] = infer_is_partial_from_raw_text(raw_text)
    return payload


def _ensure_marking_asset_dir(*, payload: dict, context_root: str | Path) -> None:
    context = payload.get("context")
    if not isinstance(context, dict):
        return
    marking_asset = context.get("marking_asset")
    if not isinstance(marking_asset, str) or not marking_asset.strip():
        return
    bundle_root = Path(context_root) / marking_asset
    bundle_root.mkdir(parents=True, exist_ok=True)
    # Keep required dirs cheap and deterministic to reduce layout drift across workflows.
    (bundle_root / ATTEMPT_DIRNAME).mkdir(parents=True, exist_ok=True)
    (bundle_root / CROPS_DIRNAME).mkdir(parents=True, exist_ok=True)
