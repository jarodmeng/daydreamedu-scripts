#!/usr/bin/env python3
"""Backfill marking_result.context.question_page_map from template file_question_info."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
_CONTEXT_ROOT = _REPO_ROOT / "ai_study_buddy" / "context"
_DEFAULT_REPORT = (
    _SCRIPT_DIR / "manifests" / "remaining_fqi_vs_marking_question_page_map_2026-05-29.json"
)
_DEFAULT_STUDY_DB = _REPO_ROOT / "ai_study_buddy" / "db" / "study_buddy.db"

for p in (_REPO_ROOT,):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ai_study_buddy.marking.core.artifact_schema import validate_marking_artifact_dict
from ai_study_buddy.marking.core.artifact_writer import write_marking_artifact
from ai_study_buddy.marking.core.marking_time import now_marking_iso
from ai_study_buddy.marking.core.models import MarkingArtifact
from ai_study_buddy.marking.file_question_info.api import (
    build_detector_question_id_list,
    question_page_map_from_question_sections,
)


def _load_fqi_payload(study: sqlite3.Connection, template_file_id: str) -> dict[str, Any]:
    row = study.execute(
        """
        SELECT raw_json
        FROM file_question_info_runs
        WHERE primary_file_id = ? AND is_deleted = 0
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (template_file_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"no active file_question_info for template {template_file_id}")
    payload = json.loads(str(row["raw_json"]))
    if not isinstance(payload, dict):
        raise ValueError("file_question_info raw_json is not an object")
    return payload


def _merge_page_map(
    old_entries: list[dict[str, Any]],
    fqi_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    ordered_ids = list(build_detector_question_id_list(fqi_payload))
    fqi_map = question_page_map_from_question_sections(fqi_payload)
    old_by_id = {
        str(entry["result_id"]): entry
        for entry in old_entries
        if isinstance(entry, dict) and entry.get("result_id") is not None
    }
    merged: list[dict[str, Any]] = []
    for qid in ordered_ids:
        row = dict(fqi_map[qid])
        prior = old_by_id.get(qid)
        if isinstance(prior, dict):
            if prior.get("evidence_image"):
                row["evidence_image"] = prior["evidence_image"]
            if prior.get("note") is not None:
                row["note"] = prior["note"]
        merged.append(row)
    return merged


def backfill_one(
    *,
    marking_result_path: Path,
    template_file_id: str,
    study: sqlite3.Connection,
    dry_run: bool,
) -> dict[str, Any]:
    payload = json.loads(marking_result_path.read_text(encoding="utf-8"))
    context = payload.get("context")
    if not isinstance(context, dict):
        raise ValueError("marking result missing context object")
    old_qpm = context.get("question_page_map")
    if not isinstance(old_qpm, list):
        old_qpm = []

    fqi_payload = _load_fqi_payload(study, template_file_id)
    new_qpm = _merge_page_map(old_qpm, fqi_payload)
    changes = []
    old_by_id = {str(e.get("result_id")): e for e in old_qpm if isinstance(e, dict)}
    for entry in new_qpm:
        rid = str(entry["result_id"])
        old_page = old_by_id.get(rid, {}).get("attempt_page_start")
        new_page = entry.get("attempt_page_start")
        if old_page != new_page:
            changes.append({"result_id": rid, "from": old_page, "to": new_page})

    if not changes and old_qpm == new_qpm:
        return {"status": "unchanged", "changes": []}

    if dry_run:
        return {"status": "would_update", "changes": changes, "question_count": len(new_qpm)}

    context["question_page_map"] = new_qpm
    payload["updated_at"] = now_marking_iso()
    validate_marking_artifact_dict(payload)
    artifact = MarkingArtifact.from_dict(payload)
    write_marking_artifact(
        artifact,
        output_path=marking_result_path,
        context_root=_CONTEXT_ROOT,
        schema_version=str(payload.get("schema_version") or ""),
        actor="script:utility_scripts.batch_mark_student_work.backfill_question_page_map_from_fqi",
    )
    return {"status": "updated", "changes": changes, "question_count": len(new_qpm)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=_DEFAULT_REPORT)
    parser.add_argument("--study-db", type=Path, default=_DEFAULT_STUDY_DB)
    parser.add_argument(
        "--category",
        default="page_mismatch",
        help="Only process report rows with this category (default: page_mismatch)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report = json.loads(args.report.expanduser().resolve().read_text(encoding="utf-8"))
    rows = [
        r
        for r in report.get("rows", [])
        if r.get("status") == "compared" and r.get("category") == args.category
    ]
    study = sqlite3.connect(str(args.study_db.expanduser().resolve()))
    study.row_factory = sqlite3.Row
    try:
        results: list[dict[str, Any]] = []
        for row in rows:
            rel = str(row.get("marking_result_path") or "")
            path = (_CONTEXT_ROOT / rel).resolve()
            outcome = backfill_one(
                marking_result_path=path,
                template_file_id=str(row["template_file_id"]),
                study=study,
                dry_run=bool(args.dry_run),
            )
            results.append(
                {
                    "queue_ord": row.get("queue_ord") or row.get("manifest_ord"),
                    "marking_result_path": rel,
                    **outcome,
                }
            )
    finally:
        study.close()

    summary = {
        "dry_run": bool(args.dry_run),
        "category": args.category,
        "processed": len(results),
        "updated": sum(1 for r in results if r.get("status") == "updated"),
        "would_update": sum(1 for r in results if r.get("status") == "would_update"),
        "unchanged": sum(1 for r in results if r.get("status") == "unchanged"),
        "errors": [],
    }
    print(json.dumps(summary, indent=2))
    for item in results:
        if item.get("status") in {"updated", "would_update"}:
            print(
                json.dumps(
                    {
                        "queue_ord": item.get("queue_ord") or item.get("manifest_ord"),
                        "status": item.get("status"),
                        "changes": item.get("changes"),
                    },
                    ensure_ascii=False,
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
