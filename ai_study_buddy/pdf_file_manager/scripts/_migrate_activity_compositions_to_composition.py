#!/usr/bin/env python3
"""Migrate d_root composition files from Activity/ to sibling Composition/ folders.

Selection (all required):
  - Registered row under d_root (resolve_daydreamedu_root)
  - Path segment Activity; not Not completed; not Book; not already Composition
  - Basename matches composition_filenames.is_composition_basename

Uses PdfFileManager.move_file for disk + registry updates.

Before first --execute on production data, run scripts/backup_pdf_registry.py.

Default mode is dry-run. Pass --execute to apply file moves and scan-root updates.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ai_study_buddy.files.roots import resolve_daydreamedu_root, resolve_goodnotes_root
from ai_study_buddy.pdf_file_manager.composition_filenames import is_composition_basename
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def _path_has_part(path: Path, name: str) -> bool:
    return name in path.parts


def is_composition_migration_candidate(path: Path, *, d_root: Path) -> bool:
    """True when *path* should move from Activity/ to Composition/."""
    resolved = path.resolve()
    d_root = d_root.resolve()
    if not resolved.is_relative_to(d_root):
        return False
    if not _path_has_part(resolved, "Activity"):
        return False
    if _path_has_part(resolved, "Composition"):
        return False
    if _path_has_part(resolved, "Not completed"):
        return False
    if _path_has_part(resolved, "Book"):
        return False
    return is_composition_basename(resolved.name)


def composition_target_dir(source_path: Path) -> Path:
    return source_path.parent.with_name("Composition")


def composition_target_path(source_path: Path) -> Path:
    return composition_target_dir(source_path) / source_path.name


def _logical_item_key(row: dict[str, Any]) -> tuple[str, str]:
    name = Path(row["old_path"]).name
    for prefix in ("_c_", "_raw_", "c_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return row["source_activity_dir"], name


def collect_file_move_candidates(
    manager: PdfFileManager,
    *,
    d_root: Path,
    g_root: Path | None,
) -> tuple[list[dict[str, Any]], Counter[str], list[str]]:
    rows: list[dict[str, Any]] = []
    stats: Counter[str] = Counter()

    for pdf_file in manager.find_files():
        source = Path(pdf_file.path).resolve()
        if g_root is not None and source.is_relative_to(g_root.resolve()):
            stats["skipped_g_root"] += 1
            continue
        if not source.is_relative_to(d_root.resolve()):
            stats["skipped_outside_d_root"] += 1
            continue
        if not is_composition_migration_candidate(source, d_root=d_root):
            continue

        target = composition_target_path(source)
        rows.append(
            {
                "file_id": pdf_file.id,
                "file_type": pdf_file.file_type,
                "doc_type_before": pdf_file.doc_type,
                "old_path": str(source),
                "new_path": str(target),
                "source_activity_dir": str(source.parent),
                "target_composition_dir": str(target.parent),
            }
        )
        stats["file_candidates"] += 1
        if target.exists():
            stats["file_collisions_on_disk"] += 1

    dest_counts = Counter(r["new_path"] for r in rows)
    dup_dests = [p for p, c in dest_counts.items() if c > 1]
    if dup_dests:
        stats["file_duplicate_target_paths"] = len(dup_dests)

    return rows, stats, dup_dests


def _scan_root_by_path(manager: PdfFileManager) -> dict[str, Any]:
    return {str(Path(sr.path).resolve()): sr for sr in manager.list_scan_roots()}


def _student_id_for_scan_root(
    manager: PdfFileManager,
    *,
    activity_dir: Path,
    scan_roots: dict[str, Any],
) -> str | None:
    existing = scan_roots.get(str(activity_dir.resolve()))
    if existing is not None:
        return existing.student_id
    return manager._infer_student_id_from_path(activity_dir)  # type: ignore[attr-defined]


def plan_scan_root_updates(
    manager: PdfFileManager,
    move_rows: list[dict[str, Any]],
    *,
    d_root: Path,
) -> tuple[list[dict[str, Any]], Counter[str], list[str]]:
    """Plan ensure/remove scan-root actions from Activity→Composition file moves."""
    stats: Counter[str] = Counter()
    scan_roots = _scan_root_by_path(manager)
    actions: list[dict[str, Any]] = []

    by_activity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in move_rows:
        by_activity[row["source_activity_dir"]].append(row)

    composition_dirs: set[str] = set()
    for row in move_rows:
        composition_dirs.add(row["target_composition_dir"])

    for activity_str, rows in sorted(by_activity.items()):
        activity_dir = Path(activity_str).resolve()
        if not activity_dir.is_relative_to(d_root.resolve()):
            continue
        on_disk = sorted(p.name for p in activity_dir.glob("*.pdf"))
        moving_names = {Path(r["old_path"]).name for r in rows}
        will_empty = bool(on_disk) and set(on_disk) <= moving_names

        if str(activity_dir) in scan_roots:
            if will_empty:
                actions.append(
                    {
                        "action": "remove_scan_root",
                        "path": str(activity_dir),
                        "reason": "activity_leaf_will_empty",
                    }
                )
                stats["scan_root_remove_candidates"] += 1
            else:
                stats["scan_root_activity_kept"] += 1

    for composition_str in sorted(composition_dirs):
        composition_dir = Path(composition_str).resolve()
        if str(composition_dir) in scan_roots:
            stats["scan_root_composition_already"] += 1
            continue
        source_rows = [r for r in move_rows if r["target_composition_dir"] == composition_str]
        activity_dir = Path(source_rows[0]["source_activity_dir"]).resolve()
        student_id = _student_id_for_scan_root(manager, activity_dir=activity_dir, scan_roots=scan_roots)
        actions.append(
            {
                "action": "ensure_scan_root",
                "path": str(composition_dir),
                "student_id": student_id,
                "reason": "composition_leaf_receives_files",
            }
        )
        stats["scan_root_ensure_candidates"] += 1

    ensure_paths = [a["path"] for a in actions if a["action"] == "ensure_scan_root"]
    dup_ensure = [p for p, c in Counter(ensure_paths).items() if c > 1]
    if dup_ensure:
        stats["scan_root_duplicate_ensure_paths"] = len(dup_ensure)

    return actions, stats, dup_ensure


def run(args: argparse.Namespace) -> dict[str, Any]:
    d_root = resolve_daydreamedu_root()
    if d_root is None:
        raise RuntimeError("DAYDREAMEDU_ROOT is not configured.")

    d_root = d_root.resolve()
    g_root = resolve_goodnotes_root()
    g_root_resolved = g_root.resolve() if g_root is not None else None

    manager = PdfFileManager()
    move_rows, file_stats, dup_dests = collect_file_move_candidates(
        manager, d_root=d_root, g_root=g_root_resolved
    )
    scan_actions, scan_stats, dup_scan_ensure = plan_scan_root_updates(
        manager, move_rows, d_root=d_root
    )

    stats = dict(file_stats)
    stats.update(scan_stats)

    report: dict[str, Any] = {
        "d_root": str(d_root),
        "g_root": str(g_root_resolved) if g_root_resolved else None,
        "mode": "execute" if args.execute else "dry_run",
        "stats": stats,
        "logical_items": len({_logical_item_key(r) for r in move_rows}),
        "file_moves_preview": move_rows[: args.preview_limit],
        "scan_root_actions_preview": scan_actions[: args.preview_limit],
        "collision_examples": {
            "file_duplicate_target_paths": dup_dests[: args.preview_limit],
            "scan_root_duplicate_ensure_paths": dup_scan_ensure[: args.preview_limit],
        },
    }

    if not args.execute:
        return report

    if stats.get("file_collisions_on_disk", 0) > 0 or dup_dests or dup_scan_ensure:
        raise RuntimeError("Refusing execute mode due to collisions/duplicate targets.")

    moved = 0
    for row in move_rows:
        new_dir = str(Path(row["new_path"]).parent)
        manager.move_file(row["file_id"], new_dir)
        moved += 1

    scan_roots_ensured = 0
    scan_roots_removed = 0
    for action in scan_actions:
        if action["action"] == "ensure_scan_root":
            manager.ensure_scan_root(action["path"], student_id=action.get("student_id"))
            scan_roots_ensured += 1
        elif action["action"] == "remove_scan_root":
            manager.remove_scan_root(action["path"])
            scan_roots_removed += 1

    report["execute_result"] = {
        "files_moved": moved,
        "scan_roots_ensured": scan_roots_ensured,
        "scan_roots_removed": scan_roots_removed,
    }
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true", help="Apply changes (default is dry-run).")
    p.add_argument(
        "--preview-limit",
        type=int,
        default=20,
        help="Number of candidate rows to include in previews.",
    )
    p.add_argument(
        "--output-json",
        help="Optional path to write full report JSON.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    result = run(args)
    out = json.dumps(result, indent=2, ensure_ascii=False)
    print(out)
    if args.output_json:
        Path(args.output_json).write_text(out + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
