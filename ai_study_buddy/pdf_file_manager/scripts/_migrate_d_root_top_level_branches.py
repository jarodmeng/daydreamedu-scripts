#!/usr/bin/env python3
"""Migrate DAYDREAMEDU_ROOT paths to top-level template/completion branches.

Old:
  <subject>/<grade>/<type>/.../file.pdf
  <subject>/<student>/<grade>/<type>/.../file.pdf

New:
  template/<subject>/<grade>/<type>/.../file.pdf
  completion/<subject>/<student>/<grade>/<type>/.../file.pdf

Also migrates D_ROOT scan_roots to the same top-level branch convention.

Default mode is dry-run. Pass --execute to apply changes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ai_study_buddy.files.roots import resolve_daydreamedu_root
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def _branch_for_file(is_template: bool) -> str:
    return "template" if is_template else "completion"


def _is_prefixed(rel: Path) -> bool:
    return bool(rel.parts) and rel.parts[0] in {"template", "completion"}


def _compute_target_rel(file_path: Path, d_root: Path, is_template: bool) -> Path:
    rel = file_path.resolve().relative_to(d_root.resolve())
    if _is_prefixed(rel):
        return rel
    return Path(_branch_for_file(is_template), *rel.parts)


def _passes_filters(rel: Path, branch: str, subject_filter: str | None, branch_filter: str | None) -> bool:
    if _is_prefixed(rel):
        current_subject = rel.parts[1] if len(rel.parts) > 1 else None
        current_branch = rel.parts[0]
    else:
        current_subject = rel.parts[0] if len(rel.parts) > 0 else None
        current_branch = branch
    if subject_filter and current_subject != subject_filter:
        return False
    if branch_filter and current_branch != branch_filter:
        return False
    return True


def _compute_scan_root_target_rel(sr_path: Path, d_root: Path, student_id: str | None) -> Path:
    rel = sr_path.resolve().relative_to(d_root.resolve())
    if _is_prefixed(rel):
        return rel
    branch = "completion" if student_id else "template"
    return Path(branch, *rel.parts)


def run(args: argparse.Namespace) -> dict:
    manager = PdfFileManager()
    d_root = resolve_daydreamedu_root().resolve()

    files = manager.find_files()
    rows = []
    stats = Counter()

    for f in files:
        p = Path(f.path).resolve()
        if not p.is_relative_to(d_root):
            continue
        rel = p.relative_to(d_root)
        branch = _branch_for_file(bool(f.is_template))
        if not _passes_filters(rel, branch, args.subject, args.branch):
            stats["file_skipped_by_filter"] += 1
            continue
        target_rel = _compute_target_rel(p, d_root, bool(f.is_template))
        if target_rel == rel:
            stats["file_already_prefixed"] += 1
            continue
        target_abs = d_root / target_rel
        rows.append(
            {
                "file_id": f.id,
                "old_path": str(p),
                "new_path": str(target_abs),
                "branch": branch,
                "subject": rel.parts[0] if rel.parts else None,
            }
        )
        stats["file_candidates"] += 1
        stats[f"file_candidates_{branch}"] += 1
        if target_abs.exists():
            stats["file_collisions_on_disk"] += 1

    # scan roots
    scan_root_updates = []
    for sr in manager.list_scan_roots():
        p = Path(sr.path).resolve()
        if not p.is_relative_to(d_root):
            continue
        rel = p.relative_to(d_root)
        branch = "completion" if sr.student_id else "template"
        if not _passes_filters(rel, branch, args.subject, args.branch):
            stats["scan_root_skipped_by_filter"] += 1
            continue
        new_rel = _compute_scan_root_target_rel(p, d_root, sr.student_id)
        if new_rel == rel:
            stats["scan_root_already_prefixed"] += 1
            continue
        scan_root_updates.append(
            {
                "id": sr.id,
                "student_id": sr.student_id,
                "old_path": str(p),
                "new_path": str((d_root / new_rel).resolve()),
                "branch": branch,
            }
        )
        stats["scan_root_candidates"] += 1
        stats[f"scan_root_candidates_{branch}"] += 1

    # duplicate destination guards
    dest_counts = Counter(r["new_path"] for r in rows)
    dup_dests = [p for p, c in dest_counts.items() if c > 1]
    if dup_dests:
        stats["file_duplicate_target_paths"] = len(dup_dests)

    scan_dest_counts = Counter(r["new_path"] for r in scan_root_updates)
    dup_scan_dest = [p for p, c in scan_dest_counts.items() if c > 1]
    if dup_scan_dest:
        stats["scan_root_duplicate_target_paths"] = len(dup_scan_dest)

    report = {
        "d_root": str(d_root),
        "mode": "execute" if args.execute else "dry_run",
        "filters": {"subject": args.subject, "branch": args.branch},
        "stats": dict(stats),
        "file_moves_preview": rows[: args.preview_limit],
        "scan_root_updates_preview": scan_root_updates[: args.preview_limit],
        "collision_examples": {
            "file_duplicate_target_paths": dup_dests[: args.preview_limit],
            "scan_root_duplicate_target_paths": dup_scan_dest[: args.preview_limit],
        },
    }

    if not args.execute:
        return report

    if stats.get("file_collisions_on_disk", 0) > 0 or dup_dests or dup_scan_dest:
        raise RuntimeError("Refusing execute mode due to collisions/duplicate targets.")

    # Execute file moves first, then scan roots.
    moved = 0
    for r in rows:
        new_dir = str(Path(r["new_path"]).parent)
        manager.move_file(r["file_id"], new_dir)
        moved += 1

    updated_scan_roots = 0
    for sr in scan_root_updates:
        manager.remove_scan_root(sr["old_path"])
        manager.ensure_scan_root(sr["new_path"], student_id=sr["student_id"])
        updated_scan_roots += 1

    report["execute_result"] = {
        "files_moved": moved,
        "scan_roots_updated": updated_scan_roots,
    }
    return report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true", help="Apply changes (default is dry-run).")
    p.add_argument(
        "--subject",
        help="Optional subject filter matching top-level legacy subject folder exactly.",
    )
    p.add_argument(
        "--branch",
        choices=["template", "completion"],
        help="Optional branch filter for batching.",
    )
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
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run(args)
    out = json.dumps(result, indent=2, ensure_ascii=False)
    print(out)
    if args.output_json:
        Path(args.output_json).write_text(out + "\n", encoding="utf-8")
