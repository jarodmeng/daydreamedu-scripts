from __future__ import annotations

import json
from pathlib import Path

from ai_study_buddy.marking.core.artifact_paths import build_marking_artifact_path, slugify_student
from ai_study_buddy.marking.core.artifact_schema import SCHEMA_VERSION, validate_marking_artifact_dict
from ai_study_buddy.marking.core.marking_time import to_marking_iso
from ai_study_buddy.marking.core.partial_marking import infer_is_partial_from_raw_text
from ai_study_buddy.marking.core.path_privacy import sanitize_marking_artifact_paths
from ai_study_buddy.marking.core.models import MarkingArtifact


def write_marking_artifact(
    artifact: MarkingArtifact,
    *,
    output_path: str | Path | None = None,
    context_root: str | Path = "ai_study_buddy/context",
) -> Path:
    payload = artifact.to_dict()
    payload["schema_version"] = SCHEMA_VERSION
    payload["created_at"] = to_marking_iso(payload["created_at"])
    payload["updated_at"] = to_marking_iso(payload["updated_at"])
    payload = _apply_attempt_metadata(payload=payload, context_root=context_root)
    payload = _apply_partial_scope(payload=payload)
    payload = sanitize_marking_artifact_paths(payload)
    path = Path(output_path) if output_path is not None else build_marking_artifact_path(
        MarkingArtifact.from_dict(payload), context_root=context_root
    )
    payload = _apply_marking_asset_path(payload=payload, artifact_json_path=path, context_root=context_root)
    validate_marking_artifact_dict(payload)

    _ensure_marking_asset_dir(payload=payload, context_root=context_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
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

    root = Path(context_root).resolve()
    artifact_path = artifact_json_path.resolve()
    try:
        rel = artifact_path.relative_to(root)
    except ValueError:
        context.setdefault("marking_asset", None)
        return payload

    parts = rel.parts
    if len(parts) < 4 or parts[0] != "marking_results":
        context.setdefault("marking_asset", None)
        return payload

    student_slug = parts[1]
    subject_context = parts[2]
    artifact_stem = artifact_path.stem
    context["marking_asset"] = f"marking_assets/{student_slug}/{subject_context}/{artifact_stem}"
    return payload


def _apply_partial_scope(*, payload: dict) -> dict:
    context = payload.get("context")
    if not isinstance(context, dict):
        return payload
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
    target = Path(context_root) / marking_asset
    target.mkdir(parents=True, exist_ok=True)
