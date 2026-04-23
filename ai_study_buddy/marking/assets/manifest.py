from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_study_buddy.marking.assets.layout import (
    ANSWERS_DIRNAME,
    ATTEMPT_DIRNAME,
    BUNDLE_MANIFEST_FILENAME,
    is_supported_image_file,
)
from ai_study_buddy.marking.assets.paths import bundle_root_from_context


def _count_supported_images(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    return sum(1 for p in folder.iterdir() if p.is_file() and is_supported_image_file(p.name))


def build_bundle_manifest_payload(
    *,
    bundle_root: Path,
    artifact_dict: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "bundle_layout_version": 1,
        "attempt_page_count": _count_supported_images(bundle_root / ATTEMPT_DIRNAME),
        "answers_page_count": _count_supported_images(bundle_root / ANSWERS_DIRNAME),
    }
    if isinstance(artifact_dict, dict):
        schema_version = artifact_dict.get("schema_version")
        if isinstance(schema_version, str) and schema_version.strip():
            payload["marking_result_schema_version"] = schema_version
        created_at = artifact_dict.get("created_at")
        if isinstance(created_at, str) and created_at.strip():
            payload["created_at"] = created_at
    return payload


def write_bundle_manifest(bundle_root: Path, payload: dict[str, Any]) -> Path:
    manifest_path = bundle_root / BUNDLE_MANIFEST_FILENAME
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return manifest_path


def write_bundle_manifest_for_artifact(
    *,
    artifact_dict: dict[str, Any],
    context_root: str | Path = "ai_study_buddy/context",
    require_attempt_images: bool = True,
) -> Path | None:
    context = artifact_dict.get("context")
    if not isinstance(context, dict):
        return None
    bundle_root = bundle_root_from_context(context, context_root=context_root)
    if bundle_root is None or not bundle_root.is_dir():
        return None

    attempt_count = _count_supported_images(bundle_root / ATTEMPT_DIRNAME)
    if require_attempt_images and attempt_count <= 0:
        # Avoid writing provisional manifests before visual render finalization.
        return None

    payload = build_bundle_manifest_payload(bundle_root=bundle_root, artifact_dict=artifact_dict)
    return write_bundle_manifest(bundle_root, payload)
