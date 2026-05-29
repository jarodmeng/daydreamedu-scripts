#!/usr/bin/env python3
"""Export a completion-level manifest from priority_template_fqi_detector_queue.json."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STUDY_DB = REPO_ROOT / "ai_study_buddy" / "db" / "study_buddy.db"
CONTEXT_ROOT = REPO_ROOT / "ai_study_buddy" / "context"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _fqi_disk_path(source_rel_path: str) -> Path:
    rel = source_rel_path.strip().lstrip("/")
    if rel.endswith("question_sections.json"):
        return CONTEXT_ROOT / rel
    if rel.startswith("file_question_info/"):
        return CONTEXT_ROOT / rel / "question_sections.json"
    return CONTEXT_ROOT / "file_question_info" / rel / "question_sections.json"


def _latest_fqi(study: sqlite3.Connection, template_id: str) -> dict[str, Any] | None:
    row = study.execute(
        """
        SELECT run_id, primary_file_id, source_rel_path, created_at, detector_model
        FROM file_question_info_runs
        WHERE primary_file_id = ? AND is_deleted = 0
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (template_id,),
    ).fetchone()
    if row is None:
        return None
    rel = str(row["source_rel_path"] or "")
    disk = _fqi_disk_path(rel) if rel else None
    return {
        "fqi_run_id": str(row["run_id"]),
        "template_file_id": str(row["primary_file_id"]),
        "source_rel_path": rel,
        "question_sections_path": str(disk) if disk else "",
        "question_sections_exists": bool(disk and disk.is_file()),
        "fqi_created_at": str(row["created_at"] or ""),
        "detector_model": str(row["detector_model"] or ""),
    }


def build_manifest(*, queue_path: Path, study_db: Path) -> dict[str, Any]:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    study = sqlite3.connect(str(study_db))
    study.row_factory = sqlite3.Row
    try:
        completions: list[dict[str, Any]] = []
        for item in queue.get("items", []):
            if not isinstance(item, dict):
                continue
            ord_num = int(item.get("ord") or 0)
            template_id = str(item.get("template_file_id") or "")
            template_path = str(item.get("template_path") or "")
            detector = str(item.get("detector") or "")
            detector_completed_at = item.get("detector_completed_at")
            queue_status = str(item.get("status") or "")
            fqi = _latest_fqi(study, template_id)
            ids = item.get("linked_completion_file_ids") or []
            paths = item.get("linked_completion_paths") or []
            students = item.get("linked_student_names") or []
            for i, cid in enumerate(ids):
                completions.append(
                    {
                        "manifest_ord": len(completions) + 1,
                        "completion_file_id": str(cid),
                        "completion_path": str(paths[i]) if i < len(paths) else "",
                        "student_name": str(students[i])
                        if i < len(students)
                        else (students[0] if students else ""),
                        "template_file_id": template_id,
                        "template_path": template_path,
                        "queue_ord": ord_num,
                        "detector": detector,
                        "detector_completed_at": detector_completed_at,
                        "queue_item_status": queue_status,
                        "file_question_info": fqi,
                    }
                )
        completions.sort(key=lambda r: (int(r["queue_ord"]), str(r["completion_path"])))
        for i, row in enumerate(completions, start=1):
            row["manifest_ord"] = i

        summary = queue.get("summary") or {}
        items = queue.get("items") or []
        return {
            "schema_version": "priority-fqi-completion-manifest-v1",
            "generated_at": _now_iso(),
            "purpose": (
                "Logging manifest of completion files whose linked templates were targeted "
                "by the priority template FQI detector batch (see source_queue)."
            ),
            "source_queue": str(queue_path.resolve().relative_to(REPO_ROOT)),
            "batch": {
                "filters": summary.get("filters"),
                "prioritized_completion_total": summary.get("prioritized_completion_total"),
                "prioritized_template_total": summary.get("prioritized_template_total"),
                "detector_counts": summary.get("detector_counts"),
                "queue_items_done": sum(1 for i in items if i.get("status") == "done"),
                "queue_items_failed": sum(1 for i in items if i.get("status") == "failed"),
            },
            "completion_count": len(completions),
            "completions": completions,
        }
    finally:
        study.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--study-db", type=Path, default=DEFAULT_STUDY_DB)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent
        / "manifests"
        / "priority_template_fqi_detector_completions_2026-05-28.json",
    )
    args = parser.parse_args()
    manifest = build_manifest(queue_path=args.queue.resolve(), study_db=args.study_db.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "completion_count": manifest["completion_count"]}, indent=2))


if __name__ == "__main__":
    main()
