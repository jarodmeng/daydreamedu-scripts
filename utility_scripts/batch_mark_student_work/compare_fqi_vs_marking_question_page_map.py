#!/usr/bin/env python3
"""Compare template FQI question ids/pages vs marking question_page_map for queue items."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
_CONTEXT_ROOT = _REPO_ROOT / "ai_study_buddy" / "context"
_DEFAULT_STUDY_DB = _REPO_ROOT / "ai_study_buddy" / "db" / "study_buddy.db"

for p in (_REPO_ROOT,):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_fqi_payload(study: sqlite3.Connection, template_file_id: str) -> dict[str, Any]:
    row = study.execute(
        """
        SELECT raw_json FROM file_question_info_runs
        WHERE primary_file_id = ? AND is_deleted = 0
        ORDER BY created_at DESC LIMIT 1
        """,
        (template_file_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"no active FQI for template {template_file_id}")
    payload = json.loads(str(row[0]))
    if not isinstance(payload, dict):
        raise ValueError("FQI raw_json is not an object")
    return payload


def _load_marking_for_completion(study: sqlite3.Connection, completion_file_id: str) -> dict[str, Any]:
    row = study.execute(
        """
        SELECT artifact_path, is_partial, context_json, raw_json
        FROM marking_artifacts
        WHERE is_deleted = 0 AND attempt_file_id = ?
        ORDER BY created_at DESC LIMIT 1
        """,
        (completion_file_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"no marking for completion {completion_file_id}")
    for source in (row["context_json"], row["raw_json"]):
        try:
            payload = json.loads(str(source or "{}"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("context"), dict):
            return {
                "artifact_path": str(row["artifact_path"] or ""),
                "is_partial": bool(row["is_partial"]),
                "payload": payload,
            }
    raise ValueError(f"marking context missing for completion {completion_file_id}")


def _marking_page_map(payload: dict[str, Any]) -> list[dict[str, Any]]:
    ctx = payload.get("context") or {}
    qpm = ctx.get("question_page_map")
    if not isinstance(qpm, list):
        return []
    out: list[dict[str, Any]] = []
    for row in qpm:
        if not isinstance(row, dict):
            continue
        rid = row.get("result_id")
        if not isinstance(rid, str) or not rid.strip():
            continue
        page = row.get("attempt_page_start")
        out.append(
            {
                "result_id": rid.strip(),
                "attempt_page_start": page if isinstance(page, int) else None,
            }
        )
    return out


def _fqi_flat_ids_and_template_pages(payload: dict[str, Any]) -> tuple[list[str], list[int | None], bool]:
    """Flatten FQI in section order; template start_page per row (allows duplicate question_index)."""
    from collections import defaultdict

    from ai_study_buddy.marking.file_question_info.api import (
        _compute_attempt_span,
        iter_questions_ordered,
        iter_sections_ordered,
    )

    section_by_idx = {row["section_index"]: row for row in iter_sections_ordered(payload)}
    by_section: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in iter_questions_ordered(payload):
        by_section[int(row["section_index"])].append(row)

    flat_ids: list[str] = []
    flat_pages: list[int | None] = []
    for section_index in sorted(by_section):
        questions = by_section[section_index]
        section_row = section_by_idx[section_index]
        for idx, qrow in enumerate(questions):
            next_row = questions[idx + 1] if idx + 1 < len(questions) else None
            start, _end = _compute_attempt_span(
                section_row=section_row,
                question_row=qrow,
                next_question_row=next_row,
            )
            flat_ids.append(str(qrow["question_index"]))
            flat_pages.append(int(start))
    has_dupes = len(flat_ids) != len(set(flat_ids))
    return flat_ids, flat_pages, has_dupes


def _compare_one(
    *,
    queue_ord: int,
    template_file_id: str,
    completion_file_id: str,
    student_name: str,
    completion_basename: str,
    template_basename: str,
    marking_ref: dict[str, Any] | None,
    study: sqlite3.Connection,
) -> dict[str, Any]:
    marking = _load_marking_for_completion(study, completion_file_id)
    payload = marking["payload"]
    marking_rows = _marking_page_map(payload)
    marking_ids = [r["result_id"] for r in marking_rows]
    marking_set = set(marking_ids)

    fqi_payload = _load_fqi_payload(study, template_file_id)
    fqi_ids, fqi_template_pages, fqi_has_duplicate_ids = _fqi_flat_ids_and_template_pages(fqi_payload)
    fqi_set = set(fqi_ids)

    is_partial = bool(marking["is_partial"])
    fqi_full_count = len(fqi_ids)

    # Partial marking: compare only first N FQI rows (N = marking count).
    if is_partial and len(marking_ids) <= len(fqi_ids):
        compared_fqi_ids = fqi_ids[: len(marking_ids)]
        compared_fqi_pages = fqi_template_pages[: len(marking_ids)]
    else:
        compared_fqi_ids = fqi_ids
        compared_fqi_pages = fqi_template_pages

    compared_fqi_set = set(compared_fqi_ids)
    ids_only_marking = sorted(marking_set - compared_fqi_set)
    ids_only_fqi = sorted(compared_fqi_set - marking_set)

    # Strict id-keyed page diffs (meaningful only when question_index is unique in FQI).
    page_diffs: list[dict[str, Any]] = []
    if not fqi_has_duplicate_ids:
        fqi_page_by_id = dict(zip(compared_fqi_ids, compared_fqi_pages, strict=True))
        for rid in sorted(marking_set & compared_fqi_set):
            m_page = next(r["attempt_page_start"] for r in marking_rows if r["result_id"] == rid)
            f_page = fqi_page_by_id.get(rid)
            if m_page != f_page:
                page_diffs.append({"result_id": rid, "marking_page": m_page, "fqi_page": f_page})

    if ids_only_marking or ids_only_fqi:
        category = "id_set_mismatch"
    elif len(marking_ids) != len(compared_fqi_ids):
        category = "count_mismatch"
    elif page_diffs:
        category = "page_mismatch"
    else:
        category = "exact_match"

    # Position-aligned page diffs (index i): handles A1/B1/C1 vs per-section Q1..Qn and duplicate FQI ids.
    position_page_diffs: list[dict[str, Any]] = []
    if len(marking_ids) == len(compared_fqi_ids):
        for i, (mid, fid) in enumerate(zip(marking_ids, compared_fqi_ids, strict=True)):
            mp = marking_rows[i].get("attempt_page_start")
            fp = compared_fqi_pages[i]
            if mp != fp:
                position_page_diffs.append(
                    {
                        "index": i,
                        "marking_id": mid,
                        "fqi_id": fid,
                        "marking_page": mp,
                        "fqi_page": fp,
                    }
                )

    if len(marking_ids) == len(compared_fqi_ids) and not position_page_diffs:
        position_aligned_category = "exact_match"
    elif len(marking_ids) == len(compared_fqi_ids) and position_page_diffs:
        position_aligned_category = "page_mismatch"
    else:
        position_aligned_category = "count_mismatch"

    rel_path = marking["artifact_path"]
    try:
        rel_path = str(Path(rel_path).resolve().relative_to(_CONTEXT_ROOT.resolve()))
    except ValueError:
        pass

    linked_name = ""
    if isinstance(marking_ref, dict):
        linked = marking_ref.get("linked_completions") or []
        if linked and isinstance(linked[0], dict):
            linked_name = str(linked[0].get("marking_result_path") or "")

    return {
        "queue_ord": queue_ord,
        "completion_file_id": completion_file_id,
        "template_file_id": template_file_id,
        "student_name": student_name,
        "completion_basename": completion_basename,
        "template_basename": template_basename,
        "status": "compared",
        "category": category,
        "partial_marking": is_partial,
        "marking_result_path": rel_path,
        "marking_question_page_map_count": len(marking_ids),
        "fqi_full_question_count": fqi_full_count,
        "fqi_compared_question_count": len(compared_fqi_ids),
        "marking_question_page_map_ids": marking_ids,
        "fqi_question_ids_ordered": fqi_ids,
        "fqi_compared_ids": compared_fqi_ids,
        "fqi_has_duplicate_question_ids": fqi_has_duplicate_ids,
        "ids_only_in_marking": ids_only_marking or None,
        "ids_only_in_fqi": ids_only_fqi or None,
        "page_diffs": page_diffs or None,
        "position_aligned_category": position_aligned_category,
        "position_aligned_page_diffs": position_page_diffs or None,
        "id_sets_equal": not ids_only_marking and not ids_only_fqi and len(marking_set) == len(compared_fqi_set),
    }


def build_report(*, queue_path: Path, study_db: Path) -> dict[str, Any]:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    items = [i for i in queue.get("items", []) if isinstance(i, dict) and i.get("status") == "done"]

    study = sqlite3.connect(str(study_db))
    study.row_factory = sqlite3.Row
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    try:
        for item in sorted(items, key=lambda x: int(x.get("ord") or 0)):
            try:
                tpath = Path(str(item.get("template_path") or ""))
                cpaths = item.get("linked_completion_paths") or []
                cpath = Path(str(cpaths[0])) if cpaths else Path()
                names = item.get("linked_student_names") or []
                rows.append(
                    _compare_one(
                        queue_ord=int(item.get("ord") or 0),
                        template_file_id=str(item.get("template_file_id") or ""),
                        completion_file_id=str((item.get("linked_completion_file_ids") or [""])[0]),
                        student_name=str(names[0] if names else ""),
                        completion_basename=cpath.name,
                        template_basename=tpath.name,
                        marking_ref=item.get("marking_reference")
                        if isinstance(item.get("marking_reference"), dict)
                        else None,
                        study=study,
                    )
                )
            except Exception as exc:
                errors.append(
                    {
                        "queue_ord": item.get("ord"),
                        "template_file_id": item.get("template_file_id"),
                        "error": str(exc),
                    }
                )
    finally:
        study.close()

    categories = Counter(r["category"] for r in rows)
    position_categories = Counter(r.get("position_aligned_category") for r in rows)
    return {
        "schema_version": "priority-fqi-vs-marking-question-page-map-v1",
        "generated_at": _now_iso(),
        "source_queue": str(queue_path.resolve().relative_to(_REPO_ROOT)),
        "completion_total": len(rows),
        "summary": {
            "compared": len(rows),
            "errors": len(errors),
            "categories": dict(sorted(categories.items())),
            "position_aligned_categories": dict(sorted(position_categories.items())),
            "partial_marking_count": sum(1 for r in rows if r.get("partial_marking")),
            "fqi_duplicate_question_ids_count": sum(1 for r in rows if r.get("fqi_has_duplicate_question_ids")),
        },
        "rows": rows,
        "errors_detail": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True, help="FQI detector queue JSON")
    parser.add_argument("--study-db", type=Path, default=_DEFAULT_STUDY_DB)
    parser.add_argument(
        "--output",
        type=Path,
        default=_SCRIPT_DIR / "manifests" / "remaining_fqi_vs_marking_question_page_map_2026-05-29.json",
    )
    args = parser.parse_args()

    report = build_report(
        queue_path=args.queue.expanduser().resolve(),
        study_db=args.study_db.expanduser().resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": report["summary"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
