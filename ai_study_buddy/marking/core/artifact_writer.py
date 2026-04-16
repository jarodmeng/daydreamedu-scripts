from __future__ import annotations

import json
from pathlib import Path

from ai_study_buddy.marking.core.artifact_paths import build_marking_artifact_path
from ai_study_buddy.marking.core.path_privacy import sanitize_marking_artifact_paths
from ai_study_buddy.marking.core.artifact_schema import validate_marking_artifact_dict
from ai_study_buddy.marking.core.models import MarkingArtifact


def write_marking_artifact(
    artifact: MarkingArtifact,
    *,
    output_path: str | Path | None = None,
    context_root: str | Path = "ai_study_buddy/context",
) -> Path:
    payload = sanitize_marking_artifact_paths(artifact.to_dict())
    validate_marking_artifact_dict(payload)

    path = Path(output_path) if output_path is not None else build_marking_artifact_path(
        artifact, context_root=context_root
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path

