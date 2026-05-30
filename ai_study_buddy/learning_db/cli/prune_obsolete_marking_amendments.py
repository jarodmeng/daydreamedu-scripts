"""Prune obsolete marking amendment overrides (dry-run by default)."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_study_buddy.learning_db.analysis.marking_amendment_obsolescence import (
    AuditReport,
    FieldItem,
    build_report,
)
from ai_study_buddy.learning_db.core.connection import default_context_root, default_db_path, get_connection
from ai_study_buddy.learning_db.core.migrate import apply_migrations
from ai_study_buddy.learning_db.ingest.import_context_json import upsert_marking_amendment
from ai_study_buddy.marking.review.amendment_service import normalize_amendment_state

DELETE_REASON = "obsolete_amendment_prune"
SOFT_DELETE_BY = "cli:prune_obsolete_marking_amendments"


@dataclass
class PruneAction:
    amendment_path: str
    action: str  # delete_file | edit_file
    obsolete_field_count: int
    active_field_count: int
    removed_fields: list[tuple[str | None, str]] = field(default_factory=list)
    removed_rows: list[str] = field(default_factory=list)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _trash_path(path: Path) -> Path:
    trash = Path.home() / ".Trash"
    trash.mkdir(parents=True, exist_ok=True)
    target = trash / path.name
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = trash / f"{path.stem}__{stamp}{path.suffix}"
    return target


def _row_has_metadata(row: dict[str, Any]) -> bool:
    reason = row.get("reviewer_reason")
    if isinstance(reason, str) and reason.strip():
        return True
    evidence = row.get("evidence")
    return isinstance(evidence, dict) and bool(evidence)


def _prune_amendment_payload(
    payload: dict[str, Any],
    *,
    obsolete_items: list[FieldItem],
    keep_reviewer_metadata: bool,
) -> tuple[dict[str, Any], list[tuple[str | None, str]], list[str]]:
    removed_fields: list[tuple[str | None, str]] = []
    removed_rows: list[str] = []

    obsolete_question: dict[str, set[str]] = {}
    obsolete_page: dict[str, set[str]] = {}
    obsolete_summary: set[str] = set()
    for item in obsolete_items:
        if item.status != "obsolete":
            continue
        if item.kind == "question_field" and item.result_id:
            obsolete_question.setdefault(item.result_id, set()).add(item.field_key)
        elif item.kind == "page_map" and item.result_id:
            obsolete_page.setdefault(item.result_id, set()).add(item.field_key)
        elif item.kind == "summary":
            obsolete_summary.add(item.field_key)

    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    pruned = normalize_amendment_state(payload, context=context)

    kept_question: list[dict[str, Any]] = []
    for row in pruned.get("question_amendments", []):
        if not isinstance(row, dict):
            continue
        result_id = row.get("result_id")
        fields = row.get("fields") if isinstance(row.get("fields"), dict) else {}
        drop_keys = obsolete_question.get(result_id, set()) if isinstance(result_id, str) else set()
        new_fields = {k: v for k, v in fields.items() if k not in drop_keys}
        for key in drop_keys:
            removed_fields.append((result_id, key))
        if new_fields or (keep_reviewer_metadata and _row_has_metadata(row)):
            kept_question.append({**row, "fields": new_fields})
        elif isinstance(result_id, str):
            removed_rows.append(result_id)

    kept_page: list[dict[str, Any]] = []
    for row in pruned.get("question_page_map_amendments", []):
        if not isinstance(row, dict):
            continue
        result_id = row.get("result_id")
        if not isinstance(result_id, str):
            continue
        drop_keys = obsolete_page.get(result_id, set())
        new_row = dict(row)
        empty = True
        for key in drop_keys:
            if key in new_row:
                removed_fields.append((result_id, key))
                del new_row[key]
        for key in ("attempt_page_start", "confidence"):
            if key in new_row:
                empty = False
        if not empty:
            kept_page.append(new_row)
        else:
            removed_rows.append(result_id)

    summary = pruned.get("summary_overrides") if isinstance(pruned.get("summary_overrides"), dict) else {}
    new_summary = {k: v for k, v in summary.items() if k not in obsolete_summary}
    for key in obsolete_summary:
        removed_fields.append((None, key))

    pruned["question_amendments"] = kept_question
    pruned["question_page_map_amendments"] = kept_page
    pruned["summary_overrides"] = new_summary
    return pruned, removed_fields, removed_rows


def _is_empty_amendment(payload: dict[str, Any]) -> bool:
    summary = payload.get("summary_overrides") if isinstance(payload.get("summary_overrides"), dict) else {}
    questions = payload.get("question_amendments") if isinstance(payload.get("question_amendments"), list) else []
    page_map = payload.get("question_page_map_amendments") if isinstance(payload.get("question_page_map_amendments"), list) else []
    if summary:
        return False
    for row in questions:
        if not isinstance(row, dict):
            continue
        fields = row.get("fields") if isinstance(row.get("fields"), dict) else {}
        if fields or _row_has_metadata(row):
            return False
    for row in page_map:
        if not isinstance(row, dict):
            continue
        if any(row.get(key) is not None for key in ("attempt_page_start", "confidence")):
            return False
    return True


def build_prune_plan(
    report: AuditReport,
    *,
    keep_reviewer_metadata: bool,
    include_partial: bool,
) -> list[PruneAction]:
    actions: list[PruneAction] = []
    for path, group in sorted(report.items_by_amendment_path().items()):
        obsolete = [item for item in group if item.status == "obsolete"]
        active = [item for item in group if item.status == "active"]
        if not obsolete:
            continue
        if active and not include_partial:
            continue
        if obsolete and not active:
            actions.append(
                PruneAction(
                    amendment_path=path,
                    action="delete_file",
                    obsolete_field_count=len(obsolete),
                    active_field_count=len(active),
                )
            )
            continue
        actions.append(
            PruneAction(
                amendment_path=path,
                action="edit_file",
                obsolete_field_count=len(obsolete),
                active_field_count=len(active),
            )
        )
    return actions


def _soft_delete_amendment(conn, *, amendment_path: str, deleted_at: str) -> None:
    conn.execute(
        """
        UPDATE marking_amendments
        SET is_deleted = 1,
            deleted_at = ?,
            deleted_by = ?,
            delete_reason = ?,
            row_version = row_version + 1
        WHERE amendment_path = ? AND is_deleted = 0
        """,
        (deleted_at, SOFT_DELETE_BY, DELETE_REASON, amendment_path),
    )


def _upsert_amendment_json(
    *,
    context_root: Path,
    db_path: Path,
    rel_path: str,
    payload: dict[str, Any],
) -> None:
    canonical = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    abs_path = context_root / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(canonical, encoding="utf-8")
    apply_migrations(db_path=db_path)
    conn = get_connection(db_path)
    try:
        upsert_marking_amendment(
            conn,
            payload=payload,
            rel_path=rel_path,
            source_hash=_sha256_text(canonical),
        )
        conn.commit()
    finally:
        conn.close()


def execute_prune(
    *,
    report: AuditReport,
    context_root: Path,
    db_path: Path,
    keep_reviewer_metadata: bool,
    include_partial: bool,
    execute: bool,
) -> list[PruneAction]:
    context_root = context_root.expanduser().resolve()
    db_path = db_path.expanduser().resolve()
    plan = build_prune_plan(report, keep_reviewer_metadata=keep_reviewer_metadata, include_partial=include_partial)
    deleted_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for action in plan:
        rel_path = action.amendment_path
        abs_path = context_root / rel_path
        group = report.items_by_amendment_path()[rel_path]
        obsolete_items = [item for item in group if item.status == "obsolete"]

        if action.action == "delete_file":
            if execute:
                if abs_path.is_file():
                    trash_target = _trash_path(abs_path)
                    shutil.move(str(abs_path), str(trash_target))
                conn = get_connection(db_path)
                try:
                    _soft_delete_amendment(conn, amendment_path=rel_path, deleted_at=deleted_at)
                    conn.commit()
                finally:
                    conn.close()
            continue

        if not abs_path.is_file():
            continue
        payload = json.loads(abs_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue
        pruned, removed_fields, removed_rows = _prune_amendment_payload(
            payload,
            obsolete_items=obsolete_items,
            keep_reviewer_metadata=keep_reviewer_metadata,
        )
        action.removed_fields = removed_fields
        action.removed_rows = removed_rows

        if _is_empty_amendment(pruned):
            action.action = "delete_file"
            if execute:
                if abs_path.is_file():
                    trash_target = _trash_path(abs_path)
                    shutil.move(str(abs_path), str(trash_target))
                conn = get_connection(db_path)
                try:
                    _soft_delete_amendment(conn, amendment_path=rel_path, deleted_at=deleted_at)
                    conn.commit()
                finally:
                    conn.close()
            continue

        if execute:
            _upsert_amendment_json(context_root=context_root, db_path=db_path, rel_path=rel_path, payload=pruned)

    return plan


def _print_plan(plan: list[PruneAction], *, execute: bool) -> None:
    delete_files = [action for action in plan if action.action == "delete_file"]
    edit_files = [action for action in plan if action.action == "edit_file"]
    print(f"Mode: {'EXECUTE' if execute else 'DRY-RUN'}")
    print(f"Delete amendment files: {len(delete_files)}")
    for action in delete_files:
        print(
            f"  delete_file: {action.amendment_path} "
            f"({action.obsolete_field_count} obsolete / {action.active_field_count} active field items)"
        )
    print(f"Edit amendment files: {len(edit_files)}")
    for action in edit_files:
        print(
            f"  edit_file: {action.amendment_path} "
            f"({action.obsolete_field_count} obsolete / {action.active_field_count} active field items)"
        )
        if action.removed_fields:
            for result_id, field_key in action.removed_fields[:8]:
                label = f"{result_id}.{field_key}" if result_id else field_key
                print(f"    - remove field: {label}")
            if len(action.removed_fields) > 8:
                print(f"    - ... and {len(action.removed_fields) - 8} more field removals")
        if action.removed_rows:
            print(f"    - remove rows: {', '.join(action.removed_rows[:8])}")
            if len(action.removed_rows) > 8:
                print(f"    - ... and {len(action.removed_rows) - 8} more rows")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prune obsolete marking amendment overrides (dry-run by default)."
    )
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--context-root", type=Path, default=None)
    parser.add_argument(
        "--source",
        choices=("db", "json"),
        default="db",
        help="Obsolescence source for prune decisions (default: db).",
    )
    parser.add_argument(
        "--include-partial",
        action="store_true",
        help="Also strip obsolete fields from partially obsolete amendment files (step 2).",
    )
    parser.add_argument(
        "--keep-reviewer-metadata",
        action="store_true",
        help="Keep question-amendment rows that only have reviewer_reason/evidence left.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply prune (move deleted JSON to ~/.Trash/, soft-delete or upsert DB rows).",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path or default_db_path()).expanduser().resolve()
    context_root = Path(args.context_root or default_context_root()).expanduser().resolve()
    report = build_report(source=args.source, db_path=db_path, context_root=context_root)

    plan = execute_prune(
        report=report,
        context_root=context_root,
        db_path=db_path,
        keep_reviewer_metadata=args.keep_reviewer_metadata,
        include_partial=args.include_partial,
        execute=False,
    )
    _print_plan(plan, execute=False)

    if not plan:
        print("\nNothing to prune.")
        return 0

    if not args.execute:
        print("\nDry-run only. Re-run with --execute to apply.")
        if not args.include_partial:
            print("Tip: add --include-partial to also strip obsolete fields from mixed files.")
        return 0

    executed = execute_prune(
        report=report,
        context_root=context_root,
        db_path=db_path,
        keep_reviewer_metadata=args.keep_reviewer_metadata,
        include_partial=args.include_partial,
        execute=True,
    )
    print()
    _print_plan(executed, execute=True)
    print("\nPrune applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
