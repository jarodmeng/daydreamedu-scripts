#!/usr/bin/env python3
"""Apply index-aligned FQI ids (and optional pages) to marking from a compare report."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
_CONTEXT_ROOT = _REPO_ROOT / "ai_study_buddy" / "context"
_DEFAULT_STUDY_DB = _REPO_ROOT / "ai_study_buddy" / "db" / "study_buddy.db"
_DEFAULT_REPORT = (
    _SCRIPT_DIR / "manifests" / "remaining_fqi_vs_marking_question_page_map_2026-05-29.json"
)

for p in (_REPO_ROOT,):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ai_study_buddy.marking.core.artifact_schema import validate_marking_artifact_dict
from ai_study_buddy.marking.core.artifact_writer import write_marking_artifact
from ai_study_buddy.marking.core.models import MarkingArtifact
from ai_study_buddy.marking.review.amendment_service import validate_amendment_state
from utility_scripts.batch_mark_student_work.compare_fqi_vs_marking_question_page_map import (
    _fqi_flat_ids_and_template_pages,
    _load_fqi_payload,
)


@dataclass
class AlignResult:
    queue_ord: int
    status: str
    id_renames: int
    page_updates: int
    path: str | None = None
    error: str | None = None


def _load_id_map_file(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "id_map" in raw and isinstance(raw["id_map"], dict):
        raw = raw["id_map"]
    if not isinstance(raw, dict):
        raise ValueError("id-map file must be a JSON object of old_id -> new_id")
    return {str(k): str(v) for k, v in raw.items()}


def _migrate_amendment_file(*, marking_rel_path: str, id_map: dict[str, str]) -> int:
    if not id_map:
        return 0
    rel = Path(marking_rel_path)
    if rel.parts[0] == "marking_results":
        rel = Path(*rel.parts[1:])
    amend_path = _CONTEXT_ROOT / "marking_amendments" / rel
    if not amend_path.is_file():
        return 0
    amend = json.loads(amend_path.read_text(encoding="utf-8"))
    renamed = 0
    for key in ("question_amendments", "question_page_map_amendments"):
        rows = amend.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            rid = str(row.get("result_id") or "")
            new_rid = id_map.get(rid)
            if new_rid and new_rid != rid:
                row["result_id"] = new_rid
                renamed += 1
    if renamed:
        base_path = _CONTEXT_ROOT / "marking_results" / rel
        base_payload = json.loads(base_path.read_text(encoding="utf-8"))
        validate_amendment_state(
            base_payload=base_payload,
            amendment_state=amend,
            valid_attempt_pages=None,
        )
        amend_path.write_text(json.dumps(amend, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        from ai_study_buddy.learning_db.ingest.dual_write import maybe_dual_write_snapshot

        maybe_dual_write_snapshot(
            family="marking_amendment",
            snapshot_path=amend_path,
            context_root=_CONTEXT_ROOT,
        )
    return renamed


def _apply_alignment(
    payload: dict[str, Any],
    *,
    marking_ids: list[str],
    fqi_ids: list[str],
    fqi_pages: list[int | None],
    update_pages: bool,
    rename_ids: bool,
) -> tuple[int, int, dict[str, str]]:
    if len(marking_ids) != len(fqi_ids):
        raise ValueError(f"count mismatch: marking={len(marking_ids)} fqi={len(fqi_ids)}")

    id_map = (
        {old: new for old, new in zip(marking_ids, fqi_ids, strict=True) if old != new}
        if rename_ids
        else {}
    )
    id_renames = len(id_map)
    page_updates = 0

    context = payload.setdefault("context", {})
    qpm = context.get("question_page_map")
    if not isinstance(qpm, list):
        raise ValueError("context.question_page_map must be a list")

    new_qpm: list[dict[str, Any]] = []
    for i, row in enumerate(qpm):
        if not isinstance(row, dict):
            continue
        if i >= len(fqi_ids):
            break
        updated = dict(row)
        if rename_ids:
            updated["result_id"] = fqi_ids[i]
        if update_pages and isinstance(fqi_pages[i], int):
            if updated.get("attempt_page_start") != fqi_pages[i]:
                page_updates += 1
            updated["attempt_page_start"] = fqi_pages[i]
            updated["source"] = "script_inferred"
        new_qpm.append(updated)
    context["question_page_map"] = new_qpm

    if rename_ids and id_map:
        qr = payload.get("question_results")
        if isinstance(qr, list):
            new_qr: list[dict[str, Any]] = []
            for row in qr:
                if not isinstance(row, dict):
                    continue
                rid = str(row.get("result_id") or "")
                updated = dict(row)
                updated["result_id"] = id_map.get(rid, rid)
                new_qr.append(updated)
            payload["question_results"] = new_qr

    return id_renames, page_updates, id_map


def align_row(
    row: dict[str, Any],
    *,
    study: sqlite3.Connection,
    dry_run: bool,
    force: bool,
) -> AlignResult:
    queue_ord = int(row.get("queue_ord") or 0)
    try:
        if row.get("category") == "exact_match" and row.get("position_aligned_category") == "exact_match":
            return AlignResult(queue_ord=queue_ord, status="skipped", id_renames=0, page_updates=0, error="already_aligned")

        if row.get("position_aligned_category") == "count_mismatch":
            return AlignResult(
                queue_ord=queue_ord,
                status="skipped",
                id_renames=0,
                page_updates=0,
                error="count_mismatch",
            )

        rel = str(row.get("marking_result_path") or "")
        mr_path = (_CONTEXT_ROOT / rel).resolve()
        if not mr_path.is_file():
            return AlignResult(queue_ord=queue_ord, status="error", id_renames=0, page_updates=0, error="marking_file_missing")

        payload = json.loads(mr_path.read_text(encoding="utf-8"))
        marking_ids = [
            str(x["result_id"])
            for x in (payload.get("context") or {}).get("question_page_map") or []
            if isinstance(x, dict) and x.get("result_id")
        ]
        fqi_payload = _load_fqi_payload(study, str(row["template_file_id"]))
        fqi_ids, fqi_pages, _dupes = _fqi_flat_ids_and_template_pages(fqi_payload)

        if row.get("partial_marking"):
            n = len(marking_ids)
            fqi_ids = fqi_ids[:n]
            fqi_pages = fqi_pages[:n]

        if len(marking_ids) != len(fqi_ids):
            return AlignResult(
                queue_ord=queue_ord,
                status="skipped",
                id_renames=0,
                page_updates=0,
                error=f"count mismatch marking={len(marking_ids)} fqi={len(fqi_ids)}",
            )

        fqi_dupes = bool(row.get("fqi_has_duplicate_question_ids"))
        rename_ids = not fqi_dupes
        update_pages = (
            row.get("position_aligned_category") == "page_mismatch"
            or force
            or (fqi_dupes and row.get("position_aligned_category") == "exact_match")
        )
        if marking_ids == fqi_ids and not update_pages:
            return AlignResult(queue_ord=queue_ord, status="skipped", id_renames=0, page_updates=0, path=rel)

        id_renames, page_updates, id_map = _apply_alignment(
            payload,
            marking_ids=marking_ids,
            fqi_ids=fqi_ids,
            fqi_pages=fqi_pages,
            update_pages=update_pages,
            rename_ids=rename_ids,
        )
        if not id_map and page_updates == 0:
            return AlignResult(queue_ord=queue_ord, status="skipped", id_renames=0, page_updates=0, path=rel)

        payload["updated_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        validate_marking_artifact_dict(payload)

        if dry_run:
            return AlignResult(
                queue_ord=queue_ord,
                status="dry_run",
                id_renames=id_renames,
                page_updates=page_updates,
                path=rel,
            )

        artifact = MarkingArtifact.from_dict(payload)
        write_marking_artifact(artifact, output_path=mr_path, context_root=_CONTEXT_ROOT)
        _migrate_amendment_file(marking_rel_path=rel, id_map=id_map)
        return AlignResult(
            queue_ord=queue_ord,
            status="written",
            id_renames=id_renames,
            page_updates=page_updates,
            path=rel,
        )
    except Exception as exc:
        return AlignResult(queue_ord=queue_ord, status="error", id_renames=0, page_updates=0, error=str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=_DEFAULT_REPORT)
    parser.add_argument("--study-db", type=Path, default=_DEFAULT_STUDY_DB)
    parser.add_argument("--queue-ord", type=int, action="append", dest="queue_ords")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-pages", action="store_true", help="Update pages even when position_aligned is exact_match")
    args = parser.parse_args()

    report = json.loads(args.report.expanduser().resolve().read_text(encoding="utf-8"))
    rows = [r for r in report.get("rows", []) if r.get("status") == "compared"]
    if args.queue_ords:
        wanted = set(args.queue_ords)
        rows = [r for r in rows if int(r.get("queue_ord") or 0) in wanted]

    study = sqlite3.connect(str(args.study_db.expanduser().resolve()))
    try:
        results = [align_row(r, study=study, dry_run=args.dry_run, force=args.force_pages) for r in rows]
    finally:
        study.close()

    print(json.dumps([r.__dict__ for r in results], indent=2, ensure_ascii=False))
    failed = [r for r in results if r.status == "error"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
