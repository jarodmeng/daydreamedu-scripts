"""Backfill attempt_sequence and template_attempt_group_id from registry completion series.

Usage (from repo root)::

    PYTHONPATH=. python3 -m ai_study_buddy.marking.workflows.backfill_attempt_sequence_from_registry --dry-run
    PYTHONPATH=. python3 -m ai_study_buddy.marking.workflows.backfill_attempt_sequence_from_registry
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_study_buddy.marking.core.artifact_schema import validate_marking_artifact_dict
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def _iter_marking_json_files(marking_root: Path) -> list[Path]:
    if not marking_root.is_dir():
        return []
    return sorted(marking_root.rglob("*.json"))


def backfill_attempt_sequence_from_registry(
    *,
    context_root: Path,
    dry_run: bool,
    pfm: PdfFileManager | None = None,
) -> dict[str, int]:
    stats = {
        "scanned": 0,
        "skipped_no_context": 0,
        "skipped_no_attempt_file_id": 0,
        "skipped_not_in_registry": 0,
        "unchanged": 0,
        "updated": 0,
        "validation_errors": 0,
    }
    manager = pfm or PdfFileManager()
    marking_root = context_root / "marking_results"

    for path in _iter_marking_json_files(marking_root):
        stats["scanned"] += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            stats["skipped_no_context"] += 1
            continue
        context = payload.get("context")
        if not isinstance(context, dict):
            stats["skipped_no_context"] += 1
            continue

        attempt_file_id = context.get("attempt_file_id")
        if not isinstance(attempt_file_id, str) or not attempt_file_id.strip():
            stats["skipped_no_attempt_file_id"] += 1
            continue

        seq = manager.next_attempt_sequence_for_completion(attempt_file_id.strip())
        if seq is None:
            stats["skipped_not_in_registry"] += 1
            continue

        completion = manager.get_file(attempt_file_id.strip())
        template_file_id = context.get("template_file_id")
        group_id = None
        if (
            completion is not None
            and completion.student_id
            and isinstance(template_file_id, str)
            and template_file_id.strip()
        ):
            group_id = manager.completion_series_id(completion.student_id, template_file_id.strip())

        changed = False
        if context.get("attempt_sequence") != seq:
            context["attempt_sequence"] = seq
            changed = True
        if group_id and context.get("template_attempt_group_id") != group_id:
            context["template_attempt_group_id"] = group_id
            changed = True

        if not changed:
            stats["unchanged"] += 1
            continue

        try:
            validate_marking_artifact_dict(payload)
        except Exception:
            stats["validation_errors"] += 1
            continue

        stats["updated"] += 1
        if not dry_run:
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--context-root",
        type=Path,
        default=Path("ai_study_buddy/context"),
        help="Context root containing marking_results/",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    args = parser.parse_args()
    stats = backfill_attempt_sequence_from_registry(
        context_root=args.context_root.expanduser().resolve(),
        dry_run=args.dry_run,
    )
    mode = "dry-run" if args.dry_run else "apply"
    print(f"backfill_attempt_sequence_from_registry ({mode}): {stats}")


if __name__ == "__main__":
    main()
