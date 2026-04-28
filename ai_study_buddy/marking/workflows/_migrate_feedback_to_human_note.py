from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

MIGRATED_FEEDBACK_MARKER = "[Migrated feedback]"
SOURCE_VERSION = "marking_result.v1.4"
TARGET_VERSION = "marking_result.v1.5"


def _migrate_payload(payload: dict[str, Any]) -> tuple[bool, dict[str, int]]:
    stats = {
        "rows_total": 0,
        "rows_feedback_nonempty": 0,
        "case_a_feedback_to_empty_human_note": 0,
        "case_b_feedback_appended_to_existing_human_note": 0,
        "case_c_feedback_empty_or_null": 0,
    }
    if payload.get("schema_version") != SOURCE_VERSION:
        return False, stats
    rows = payload.get("question_results")
    if not isinstance(rows, list):
        return False, stats

    changed = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        stats["rows_total"] += 1
        feedback = row.get("feedback")
        human_note = row.get("human_note")
        if isinstance(feedback, str) and feedback:
            stats["rows_feedback_nonempty"] += 1
            if human_note is None or human_note == "":
                row["human_note"] = feedback
                stats["case_a_feedback_to_empty_human_note"] += 1
            elif isinstance(human_note, str):
                block = f"{MIGRATED_FEEDBACK_MARKER}\n{feedback}"
                if block not in human_note:
                    row["human_note"] = f"{human_note}\n\n{block}"
                stats["case_b_feedback_appended_to_existing_human_note"] += 1
            changed = True
        else:
            stats["case_c_feedback_empty_or_null"] += 1

        if "feedback" in row:
            row.pop("feedback", None)
            changed = True

    payload["schema_version"] = TARGET_VERSION
    changed = True
    return changed, stats


def run(*, context_root: str | Path = "ai_study_buddy/context", dry_run: bool = True) -> dict[str, int]:
    root = Path(context_root) / "marking_results"
    files = sorted(root.rglob("*.json")) if root.is_dir() else []
    summary = {
        "scanned_files": len(files),
        "files_migrated": 0,
        "rows_total": 0,
        "rows_feedback_nonempty": 0,
        "case_a_feedback_to_empty_human_note": 0,
        "case_b_feedback_appended_to_existing_human_note": 0,
        "case_c_feedback_empty_or_null": 0,
        "dry_run": int(dry_run),
    }

    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue

        changed, stats = _migrate_payload(payload)
        if not changed:
            continue
        summary["files_migrated"] += 1
        for key in (
            "rows_total",
            "rows_feedback_nonempty",
            "case_a_feedback_to_empty_human_note",
            "case_b_feedback_appended_to_existing_human_note",
            "case_c_feedback_empty_or_null",
        ):
            summary[key] += stats[key]
        if not dry_run:
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate marking_result.v1.4 feedback fields into v1.5 human_note.")
    parser.add_argument("--context-root", default="ai_study_buddy/context")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = run(context_root=args.context_root, dry_run=args.dry_run)
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
