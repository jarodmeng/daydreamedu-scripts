from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_study_buddy.marking.core.artifact_writer import write_marking_artifact
from ai_study_buddy.marking.core.models import MarkingArtifact
from ai_study_buddy.marking.core.artifact_schema import validate_marking_artifact_dict
from ai_study_buddy.marking.core.marking_time import now_marking_iso


def update_human_notes(
    artifact_json_path: str | Path,
    *,
    summary_note: str | None = None,
    result_id: str | None = None,
    question_note: str | None = None,
    updated_by: str | None = None,
) -> Path:
    path = Path(artifact_json_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    if summary_note is not None:
        payload.setdefault("summary", {})["human_note"] = summary_note

    if result_id is not None:
        matched = False
        for row in payload.get("question_results", []):
            if row.get("result_id") == result_id:
                row["human_note"] = question_note
                matched = True
                break
        if not matched:
            raise ValueError(f"result_id not found: {result_id}")

    if summary_note is not None or result_id is not None:
        review_meta = payload.setdefault("review_meta", {})
        ts = now_marking_iso()
        review_meta["updated_at"] = ts
        review_meta["updated_by"] = updated_by
        payload["updated_at"] = ts

    validate_marking_artifact_dict(payload)
    artifact = MarkingArtifact.from_dict(payload)
    write_marking_artifact(
        artifact,
        output_path=path,
        context_root=path.parents[3],
        schema_version=payload.get("schema_version"),
        actor="script:ai_study_buddy.marking.workflows.edit_human_notes",
    )
    return path


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update co-located human notes in a marking artifact JSON file.")
    parser.add_argument("artifact_json")
    parser.add_argument("--summary-note")
    parser.add_argument("--result-id")
    parser.add_argument("--question-note")
    parser.add_argument("--updated-by")
    return parser


def main() -> int:
    args = _build_arg_parser().parse_args()
    path = update_human_notes(
        args.artifact_json,
        summary_note=args.summary_note,
        result_id=args.result_id,
        question_note=args.question_note,
        updated_by=args.updated_by,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
