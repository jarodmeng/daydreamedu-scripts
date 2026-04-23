"""Backfill `context.is_partial` and upgrade canonical artifacts to current package schema.

Rules:
- `schema_version` is upgraded to package default (currently `marking_result.v1.4`).
- `context.marking_asset` is added with null default when missing (legacy v1.1).
- `context.is_partial` is set:
  - default `False` for legacy `marking_result.v1.1` artifacts
  - inferred from `context.question_selection.raw_text` for v1.2+ artifacts

Usage (from repo root)::

    PYTHONPATH=. python3 -m ai_study_buddy.marking.workflows.backfill_is_partial_v1_3 --dry-run
    PYTHONPATH=. python3 -m ai_study_buddy.marking.workflows.backfill_is_partial_v1_3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ai_study_buddy.marking.core.artifact_schema import SCHEMA_VERSION, validate_marking_artifact_dict
from ai_study_buddy.marking.core.partial_marking import infer_is_partial_from_raw_text
from ai_study_buddy.marking.workflows.report_renderer import render_learning_report_from_json


def _iter_marking_json_files(marking_root: Path) -> list[Path]:
    if not marking_root.is_dir():
        return []
    return sorted(marking_root.rglob("*.json"))


def _infer_is_partial(context: dict[str, Any], previous_schema_version: str | None) -> bool:
    if previous_schema_version == "marking_result.v1.1":
        return False
    question_selection = context.get("question_selection")
    raw_text = question_selection.get("raw_text") if isinstance(question_selection, dict) else None
    return infer_is_partial_from_raw_text(raw_text)


def run(
    *,
    context_root: str | Path = "ai_study_buddy/context",
    dry_run: bool = False,
    rerender_reports: bool = True,
) -> dict[str, int]:
    root = Path(context_root)
    marking_root = root / "marking_results"
    json_files = _iter_marking_json_files(marking_root)

    summary = {
        "scanned_json": 0,
        "updated_json": 0,
        "unchanged_json": 0,
        "updated_is_partial_true": 0,
        "updated_is_partial_false": 0,
        "defaulted_marking_asset_null": 0,
        "validation_errors": 0,
        "invalid_json": 0,
        "rendered_reports": 0,
        "dry_run": int(dry_run),
    }

    for json_path in json_files:
        summary["scanned_json"] += 1
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            summary["invalid_json"] += 1
            continue

        context = payload.get("context")
        if not isinstance(context, dict):
            summary["validation_errors"] += 1
            continue

        changed = False
        previous_schema_version = payload.get("schema_version")

        if "marking_asset" not in context:
            context["marking_asset"] = None
            summary["defaulted_marking_asset_null"] += 1
            changed = True

        inferred_partial = _infer_is_partial(context, previous_schema_version)
        if context.get("is_partial") != inferred_partial:
            context["is_partial"] = inferred_partial
            changed = True
        if "question_page_map" not in context:
            context["question_page_map"] = []
            changed = True

        if payload.get("schema_version") != SCHEMA_VERSION:
            payload["schema_version"] = SCHEMA_VERSION
            changed = True

        try:
            validate_marking_artifact_dict(payload)
        except Exception:
            summary["validation_errors"] += 1
            continue

        if changed:
            summary["updated_json"] += 1
            if context.get("is_partial") is True:
                summary["updated_is_partial_true"] += 1
            else:
                summary["updated_is_partial_false"] += 1
            if not dry_run:
                json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        else:
            summary["unchanged_json"] += 1

        if rerender_reports and not dry_run:
            render_learning_report_from_json(json_path, context_root=root)
            summary["rendered_reports"] += 1

    print(f"Scanned marking JSON: {summary['scanned_json']}")
    print(f"Updated JSON files: {summary['updated_json']}")
    print(f"Unchanged JSON files: {summary['unchanged_json']}")
    print(f"Updated is_partial=true: {summary['updated_is_partial_true']}")
    print(f"Updated is_partial=false: {summary['updated_is_partial_false']}")
    print(f"Defaulted context.marking_asset=null: {summary['defaulted_marking_asset_null']}")
    print(f"Validation errors: {summary['validation_errors']}")
    print(f"Invalid JSON skipped: {summary['invalid_json']}")
    print(f"Learning reports rendered: {summary['rendered_reports']}")
    if dry_run:
        print("(dry-run: no files written)")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-root", default="ai_study_buddy/context")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-rerender", action="store_true")
    args = parser.parse_args()
    run(
        context_root=args.context_root,
        dry_run=args.dry_run,
        rerender_reports=not args.no_rerender,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
