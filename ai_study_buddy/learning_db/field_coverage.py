#!/usr/bin/env python3
"""
Compare context JSON files to the database by leaf-field paths.

Default mode: compare each file to the row's full `raw_json` snapshot.

With --exclude-raw-json: reconstruct each artifact **without** reading any `raw_json`
columns (normalized columns + child rows only — what you want if `raw_json` is treated
only as a backup redundant copy).

Coverage for one file =
  (# of source leaf paths whose value matches at that path after normalize)
  / (# of leaf paths in source)

Run:

  python3 -m ai_study_buddy.learning_db.field_coverage
  python3 -m ai_study_buddy.learning_db.field_coverage --exclude-raw-json
"""
from __future__ import annotations

import argparse
import copy
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_study_buddy.learning_db.connection import default_context_root, default_db_path, get_connection
from ai_study_buddy.learning_db.migrate import apply_migrations


def _flatten_leaf_paths(prefix: str, obj: Any) -> dict[str, Any]:
    """Map dotted-with-brackets path strings to leaf values."""
    if isinstance(obj, dict):
        if obj == {}:
            return {prefix: {}} if prefix else {}
        out: dict[str, Any] = {}
        for k in sorted(obj.keys()):
            next_p = f"{prefix}.{k}" if prefix else k
            sub = obj[k]
            out.update(_flatten_leaf_paths(next_p, sub))
        return out
    if isinstance(obj, list):
        if obj == []:
            return {prefix: []} if prefix else {}
        out = {}
        for i, item in enumerate(obj):
            next_p = f"{prefix}[{i}]"
            out.update(_flatten_leaf_paths(next_p, item))
        return out
    if prefix:
        return {prefix: obj}
    return {}


def _sorted_by_result_id(items: list[Any], *, rid_key: str = "result_id") -> list[Any]:
    def rid(x: Any) -> str:
        if not isinstance(x, dict):
            return ""
        v = x.get(rid_key)
        return "" if v is None else str(v)

    return sorted(items, key=rid)


def _sorted_by_json_repr(items: list[Any]) -> list[Any]:
    return sorted(items, key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=True))


def _normalize_marking_payload_for_compare(payload: dict[str, Any]) -> dict[str, Any]:
    d = copy.deepcopy(payload)
    qr = d.get("question_results")
    if isinstance(qr, list):
        d["question_results"] = _sorted_by_result_id(qr)
    ctx = d.get("context")
    if isinstance(ctx, dict):
        qpm = ctx.get("question_page_map")
        if isinstance(qpm, list):
            ctx = copy.deepcopy(ctx)
            ctx["question_page_map"] = _sorted_by_result_id(qpm)
            d["context"] = ctx
    return d


def _normalize_amendment_payload_for_compare(payload: dict[str, Any]) -> dict[str, Any]:
    d = copy.deepcopy(payload)
    qa = d.get("question_amendments")
    if isinstance(qa, list):
        d["question_amendments"] = _sorted_by_result_id(qa)
    qpma = d.get("question_page_map_amendments")
    if isinstance(qpma, list):
        d["question_page_map_amendments"] = _sorted_by_result_id(qpma)
    return d


def _normalize_review_state_for_compare(payload: dict[str, Any]) -> dict[str, Any]:
    d = copy.deepcopy(payload)
    x = d.get("question_reviews")
    if isinstance(x, list):
        d["question_reviews"] = _sorted_by_result_id(x, rid_key="result_id")
    x = d.get("attempt_notes")
    if isinstance(x, list):
        d["attempt_notes"] = _sorted_by_json_repr(x)
    x = d.get("student_subject_notes")
    if isinstance(x, list):
        d["student_subject_notes"] = _sorted_by_json_repr(x)
    return d


def _reconstruct_question_result_normalized(row: dict[str, Any]) -> dict[str, Any]:
    diagnosis = json.loads(row["diagnosis_json"] or "{}")
    return {
        "result_id": row["result_id"],
        "scoring_status": row["scoring_status"],
        "outcome": row["outcome"],
        "max_marks": row["max_marks"],
        "earned_marks": row["earned_marks"],
        "student_answer": row["student_answer"],
        "correct_answer": row["correct_answer"],
        "human_note": row["human_note"],
        "error_tags": json.loads(row["error_tags_json"] or "[]"),
        "skill_tags": json.loads(row["skill_tags_json"] or "[]"),
        "diagnosis": diagnosis,
    }


def _reconstruct_marking_from_normalized(conn: sqlite3.Connection, rel_path: str) -> dict[str, Any] | None:
    ma = conn.execute("SELECT * FROM marking_artifacts WHERE artifact_path = ? LIMIT 1", (rel_path,)).fetchone()
    if ma is None:
        return None
    row = dict(ma)
    qr_list: list[dict[str, Any]] = []
    for qrow in conn.execute(
        """
        SELECT result_id, scoring_status, outcome, max_marks, earned_marks, student_answer, correct_answer,
               error_tags_json, skill_tags_json, diagnosis_json, human_note
        FROM marking_question_results WHERE artifact_id = ? ORDER BY result_id
        """,
        (row["artifact_id"],),
    ):
        qr_list.append(_reconstruct_question_result_normalized(dict(qrow)))
    return {
        "schema_version": row["schema_version"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "context": json.loads(row["context_json"]),
        "summary": json.loads(row["summary_json"]),
        "question_results": qr_list,
        "review_meta": json.loads(row["review_meta_json"] or "{}"),
        "generation": json.loads(row["generation_json"] or "{}"),
    }


def _reconstruct_qamend_normalized(sub: dict[str, Any]) -> dict[str, Any]:
    return {
        "result_id": sub["result_id"],
        "fields": json.loads(sub["fields_json"] or "{}"),
        "reviewer_reason": sub["reviewer_reason"],
        "evidence": json.loads(sub["evidence_json"] or "{}"),
        "updated_at": sub["updated_at"],
        "updated_by": sub["updated_by"],
    }


def _reconstruct_qpma_normalized(sub: dict[str, Any]) -> dict[str, Any]:
    return {
        "result_id": sub["result_id"],
        "attempt_page_start": sub["attempt_page_start"],
        "confidence": sub["confidence"],
        "updated_at": sub["updated_at"],
        "updated_by": sub["updated_by"],
    }


def _reconstruct_amendment_from_normalized(conn: sqlite3.Connection, rel_path: str) -> dict[str, Any] | None:
    mr = conn.execute("SELECT * FROM marking_amendments WHERE amendment_path = ? LIMIT 1", (rel_path,)).fetchone()
    if mr is None:
        return None
    row = dict(mr)
    aid = row["amendment_id"]
    qa: list[dict[str, Any]] = []
    for sub in conn.execute(
        """
        SELECT result_id, fields_json, reviewer_reason, evidence_json, updated_at, updated_by
        FROM marking_question_amendments WHERE amendment_id = ? ORDER BY result_id
        """,
        (aid,),
    ):
        qa.append(_reconstruct_qamend_normalized(dict(sub)))
    qpma: list[dict[str, Any]] = []
    for sub in conn.execute(
        """
        SELECT result_id, attempt_page_start, confidence, updated_at, updated_by
        FROM marking_page_map_amendments WHERE amendment_id = ? ORDER BY result_id
        """,
        (aid,),
    ):
        qpma.append(_reconstruct_qpma_normalized(dict(sub)))
    rm = json.loads(row["review_meta_json"] or "{}")
    return {
        "schema_version": row["schema_version"],
        "context": json.loads(row["context_json"]),
        "review_meta": rm,
        "summary_overrides": json.loads(row["summary_overrides_json"] or "{}"),
        "question_amendments": qa,
        "question_page_map_amendments": qpma,
    }


def _reconstruct_review_state_from_normalized(conn: sqlite3.Connection, rel_path: str) -> dict[str, Any] | None:
    rr = conn.execute("SELECT * FROM student_review_states WHERE review_state_path = ? LIMIT 1", (rel_path,)).fetchone()
    if rr is None:
        return None
    row = dict(rr)
    out: dict[str, Any] = {
        "schema_version": row["schema_version"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "context": json.loads(row["context_json"]),
        "review_status": row["review_status"],
        "question_reviews": json.loads(row["question_reviews_json"] or "[]"),
        "attempt_notes": json.loads(row["attempt_notes_json"] or "[]"),
        "student_subject_notes": json.loads(row["student_subject_notes_json"] or "[]"),
        "summary": json.loads(row["summary_json"] or "{}"),
        "review_meta": json.loads(row["review_meta_json"] or "{}"),
    }
    if row.get("updated_by") is not None:
        out["updated_by"] = row["updated_by"]
    return out


def _coverage_one(source_paths: dict[str, Any], db_paths: dict[str, Any]) -> tuple[float, int, int, int]:
    """Return (coverage_ratio, matched, divergent, missing_in_db)."""
    src_keys = set(source_paths.keys())
    matched = 0
    divergent = 0
    missing_in_db = 0
    for pk in sorted(src_keys):
        sv = source_paths[pk]
        if pk not in db_paths:
            missing_in_db += 1
            continue
        if db_paths[pk] == sv:
            matched += 1
        else:
            divergent += 1
    total = len(src_keys)
    ratio = matched / total if total else 1.0
    return ratio, matched, divergent, missing_in_db


@dataclass
class RowResult:
    rel_path: str
    leaf_count_source: int
    coverage: float
    matched: int
    divergent: int
    missing_in_db: int


def _load_db_raw(conn: sqlite3.Connection, *, table: str, path_col: str, rel_path: str) -> str | None:
    row = conn.execute(
        f"SELECT raw_json FROM {table} WHERE {path_col} = ? LIMIT 1",
        (rel_path,),
    ).fetchone()
    return str(row["raw_json"]) if row else None


def run_report(db_path: Path, context_root: Path, *, exclude_raw_json: bool) -> None:
    apply_migrations(db_path=db_path)
    conn = get_connection(db_path)
    configs = [
        (
            "marking_result",
            str(context_root / "marking_results"),
            "marking_artifacts",
            "artifact_path",
        ),
        (
            "marking_amendment",
            str(context_root / "marking_amendments"),
            "marking_amendments",
            "amendment_path",
        ),
        (
            "student_review_state",
            str(context_root / "student_review_states"),
            "student_review_states",
            "review_state_path",
        ),
    ]
    mode = "normalized columns + child rows (no raw_json)" if exclude_raw_json else "raw_json snapshot row"
    print(f"Mode: {mode}")
    try:
        for label, glob_root, db_table, path_col in configs:
            roots = sorted(Path(glob_root).rglob("*.json")) if Path(glob_root).exists() else []
            if not roots:
                print(f"# {label}: no JSON under {glob_root}")
                continue
            rows: list[RowResult] = []
            for filepath in roots:
                rel_path = filepath.relative_to(context_root).as_posix()
                text = filepath.read_text(encoding="utf-8")
                src_obj = json.loads(text)
                if label == "marking_result":
                    src_norm = _normalize_marking_payload_for_compare(src_obj)
                elif label == "marking_amendment":
                    src_norm = _normalize_amendment_payload_for_compare(src_obj)
                else:
                    src_norm = _normalize_review_state_for_compare(src_obj)
                source_paths = _flatten_leaf_paths("", src_norm)

                if exclude_raw_json:
                    if label == "marking_result":
                        db_obj = _reconstruct_marking_from_normalized(conn, rel_path)
                    elif label == "marking_amendment":
                        db_obj = _reconstruct_amendment_from_normalized(conn, rel_path)
                    else:
                        db_obj = _reconstruct_review_state_from_normalized(conn, rel_path)
                    if db_obj is None:
                        rows.append(
                            RowResult(
                                rel_path=rel_path,
                                leaf_count_source=len(source_paths),
                                coverage=0.0,
                                matched=0,
                                divergent=0,
                                missing_in_db=len(source_paths),
                            ),
                        )
                        continue
                    if label == "marking_result":
                        db_norm = _normalize_marking_payload_for_compare(db_obj)
                    elif label == "marking_amendment":
                        db_norm = _normalize_amendment_payload_for_compare(db_obj)
                    else:
                        db_norm = _normalize_review_state_for_compare(db_obj)
                else:
                    raw_js = _load_db_raw(conn, table=db_table, path_col=path_col, rel_path=rel_path)
                    if raw_js is None:
                        rows.append(
                            RowResult(
                                rel_path=rel_path,
                                leaf_count_source=0,
                                coverage=0.0,
                                matched=0,
                                divergent=0,
                                missing_in_db=len(source_paths),
                            ),
                        )
                        continue
                    db_obj = json.loads(raw_js)
                    if label == "marking_result":
                        db_norm = _normalize_marking_payload_for_compare(db_obj)
                    elif label == "marking_amendment":
                        db_norm = _normalize_amendment_payload_for_compare(db_obj)
                    else:
                        db_norm = _normalize_review_state_for_compare(db_obj)

                db_paths = _flatten_leaf_paths("", db_norm)
                ratio, matched, div, missing = _coverage_one(source_paths, db_paths)
                rows.append(
                    RowResult(
                        rel_path=rel_path,
                        leaf_count_source=len(source_paths),
                        coverage=ratio,
                        matched=matched,
                        divergent=div,
                        missing_in_db=missing,
                    ),
                )
            total_leaves = sum(r.leaf_count_source for r in rows)
            agg_matched = sum(r.matched for r in rows)
            pct = 100.0 * agg_matched / total_leaves if total_leaves else 100.0
            print(f"\n## {label}")
            print(
                f"- files={len(rows)}  weighted_field_coverage (matched_leaf_paths/source_leaf_paths) ~= {pct:.2f}%  "
                f"(total_leaf_paths_src={total_leaves}, matched={agg_matched})"
            )
            print("- per-file mean coverage:", f"{sum(r.coverage for r in rows) / len(rows) * 100:.2f}%")
            worst_rows = sorted(rows, key=lambda r: r.coverage)[:5]
            print("- lowest 5 files by coverage:")
            for r in worst_rows:
                if r.leaf_count_source == 0:
                    continue
                print(
                    f"    {r.coverage*100:.1f}%  leaves_src={r.leaf_count_source}  matched={r.matched}  "
                    f"divergent_values={r.divergent}  missing_paths_in_db={r.missing_in_db}  {r.rel_path}"
                )

    finally:
        conn.close()


def main() -> int:
    p = argparse.ArgumentParser(description="Field-path coverage of context JSON vs DB (raw_json or normalized rows).")
    p.add_argument("--db-path", help="SQLite path (default: study_buddy.db)")
    p.add_argument("--context-root", help="Context root containing marking_results/ … (default: ai_study_buddy/context)")
    p.add_argument(
        "--exclude-raw-json",
        action="store_true",
        help="Rebuild each blob from structured columns + child tables only (ignore every raw_json column).",
    )
    args = p.parse_args()
    db_path = Path(args.db_path).expanduser().resolve() if args.db_path else default_db_path()
    context_root = Path(args.context_root).expanduser().resolve() if args.context_root else default_context_root()
    run_report(db_path, context_root, exclude_raw_json=args.exclude_raw_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
