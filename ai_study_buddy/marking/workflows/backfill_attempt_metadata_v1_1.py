"""Backfill v1.1 attempt metadata on canonical marking artifacts.

Adds/normalizes these context fields for artifacts with `template_file_id`:

- `template_attempt_group_id`
- `attempt_sequence`
- `attempt_label` (defaults to null when missing)

Also upgrades `schema_version` to the package default (`marking_result.v1.1`).

Usage (from repo root)::

    PYTHONPATH=. python3 -m ai_study_buddy.marking.workflows.backfill_attempt_metadata_v1_1 --dry-run
    PYTHONPATH=. python3 -m ai_study_buddy.marking.workflows.backfill_attempt_metadata_v1_1
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_study_buddy.marking.core.artifact_paths import parse_iso_datetime
from ai_study_buddy.marking.core.artifact_schema import (
    SCHEMA_VERSION,
    validate_marking_artifact_dict,
)


@dataclass(frozen=True)
class _Candidate:
    path: Path
    payload: dict[str, Any]
    student_slug: str
    template_file_id: str
    created_at_sort_key: tuple[int, int, int, int, int, int, str]


def _iter_marking_json_files(marking_root: Path) -> list[Path]:
    if not marking_root.is_dir():
        return []
    return sorted(marking_root.rglob("*.json"))


def _created_at_sort_key(value: str) -> tuple[int, int, int, int, int, int, str]:
    dt = parse_iso_datetime(value)
    return (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.isoformat())


def _collect_candidates(files: list[Path], marking_root: Path) -> tuple[list[_Candidate], dict[str, int]]:
    stats = {
        "scanned_files": len(files),
        "invalid_json": 0,
        "invalid_shape": 0,
        "missing_template_file_id": 0,
    }
    out: list[_Candidate] = []

    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            stats["invalid_json"] += 1
            continue

        context = payload.get("context")
        created_at = payload.get("created_at")
        if not isinstance(context, dict) or not isinstance(created_at, str) or not created_at.strip():
            stats["invalid_shape"] += 1
            continue

        template_file_id = context.get("template_file_id")
        if not isinstance(template_file_id, str) or not template_file_id.strip():
            stats["missing_template_file_id"] += 1
            continue

        rel = path.relative_to(marking_root)
        student_slug = rel.parts[0] if rel.parts else ""
        if not student_slug:
            stats["invalid_shape"] += 1
            continue

        try:
            sort_key = _created_at_sort_key(created_at)
        except Exception:
            stats["invalid_shape"] += 1
            continue

        out.append(
            _Candidate(
                path=path,
                payload=payload,
                student_slug=student_slug,
                template_file_id=template_file_id,
                created_at_sort_key=sort_key,
            )
        )
    return out, stats


def _assign_and_write(candidates: list[_Candidate], *, dry_run: bool) -> dict[str, int]:
    stats = {
        "groups": 0,
        "updated_files": 0,
        "unchanged_files": 0,
        "validation_errors": 0,
    }

    grouped: dict[tuple[str, str], list[_Candidate]] = {}
    for c in candidates:
        grouped.setdefault((c.student_slug, c.template_file_id), []).append(c)
    stats["groups"] = len(grouped)

    for (student_slug, template_file_id), rows in grouped.items():
        rows_sorted = sorted(rows, key=lambda r: (r.created_at_sort_key, r.path.as_posix()))
        group_id = f"{student_slug}::{template_file_id}"

        for idx, row in enumerate(rows_sorted, start=1):
            payload = row.payload
            context = payload["context"]
            changed = False

            if payload.get("schema_version") != SCHEMA_VERSION:
                payload["schema_version"] = SCHEMA_VERSION
                changed = True
            if context.get("template_attempt_group_id") != group_id:
                context["template_attempt_group_id"] = group_id
                changed = True
            if context.get("attempt_sequence") != idx:
                context["attempt_sequence"] = idx
                changed = True
            if "attempt_label" not in context:
                context["attempt_label"] = None
                changed = True

            try:
                validate_marking_artifact_dict(payload)
            except Exception:
                stats["validation_errors"] += 1
                continue

            if not changed:
                stats["unchanged_files"] += 1
                continue

            stats["updated_files"] += 1
            if not dry_run:
                row.path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    return stats


def run(*, context_root: str | Path = "ai_study_buddy/context", dry_run: bool = True) -> dict[str, int]:
    root = Path(context_root)
    marking_root = root / "marking_results"
    files = _iter_marking_json_files(marking_root)
    candidates, collect_stats = _collect_candidates(files, marking_root)
    write_stats = _assign_and_write(candidates, dry_run=dry_run)

    summary = {
        **collect_stats,
        "candidate_files": len(candidates),
        **write_stats,
        "dry_run": int(dry_run),
    }
    print(f"Scanned JSON files: {summary['scanned_files']}")
    print(f"Candidate files (with template_file_id): {summary['candidate_files']}")
    print(f"Groups discovered: {summary['groups']}")
    print(f"Updated files: {summary['updated_files']}")
    print(f"Unchanged files: {summary['unchanged_files']}")
    print(f"Skipped invalid JSON: {summary['invalid_json']}")
    print(f"Skipped invalid shape/timestamps: {summary['invalid_shape']}")
    print(f"Skipped missing template_file_id: {summary['missing_template_file_id']}")
    print(f"Validation errors: {summary['validation_errors']}")
    if dry_run:
        print("(dry-run: no files written)")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-root", default="ai_study_buddy/context")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(context_root=args.context_root, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

