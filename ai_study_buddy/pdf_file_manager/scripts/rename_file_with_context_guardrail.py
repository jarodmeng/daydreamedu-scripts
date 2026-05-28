from __future__ import annotations

import argparse
import json
import os
import sqlite3
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from ai_study_buddy.marking.core.artifact_paths import slugify_student
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager, normalize_pdf_display_name


FAMILIES = (
    "marking_results",
    "learning_reports",
    "marking_assets",
    "student_review_states",
    "marking_amendments",
)
ARCHIVE_DIR_NAMES = {"archive", "_archive"}


@dataclass(frozen=True)
class PlannedMove:
    family: str
    src: str
    dst: str
    reason: str


def _is_archived(path: Path) -> bool:
    return any(part.casefold() in ARCHIVE_DIR_NAMES for part in path.parts)


def _resolve_file(manager: PdfFileManager, file_id_or_path: str):
    raw = str(file_id_or_path)
    is_path_like = "/" in raw or "\\" in raw or raw.lower().endswith(".pdf")
    if is_path_like:
        return manager.get_file_by_path(Path(raw).expanduser().resolve(strict=False))
    return manager.get_file(raw)


def _completion_scope_ids(manager: PdfFileManager, renamed_file) -> tuple[set[str], set[str]]:
    completion_ids: set[str] = set()
    template_ids: set[str] = set()
    if renamed_file.is_template:
        template_ids.add(renamed_file.id)
        for completion in manager.get_completions(renamed_file.id):
            completion_ids.add(completion.id)
        return completion_ids, template_ids
    completion_ids.add(renamed_file.id)
    return completion_ids, template_ids


def _build_recovery_manifest_path(context_root: Path, file_id: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = context_root / "rename_manifests"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"rename_{file_id}_{stamp}.json"


def _add_move(planned: dict[tuple[str, str], PlannedMove], family: str, src: Path, dst: Path, reason: str) -> None:
    src_r = src.resolve(strict=False)
    dst_r = dst.resolve(strict=False)
    if src_r == dst_r:
        return
    key = (str(src_r), str(dst_r))
    planned[key] = PlannedMove(family=family, src=str(src_r), dst=str(dst_r), reason=reason)


def _report_path_for(marking_json: Path, context_root: Path) -> Path:
    parts = marking_json.relative_to(context_root / "marking_results").parts
    student_and_subject = parts[:-1]
    stem = marking_json.stem
    return context_root / "learning_reports" / Path(*student_and_subject) / f"{stem} - Marking Report.md"


def _marking_matches_scope(payload: dict, completion_ids: set[str], template_ids: set[str]) -> bool:
    context = payload.get("context")
    if not isinstance(context, dict):
        return False
    attempt_id = context.get("attempt_file_id")
    template_id = context.get("template_file_id")
    if isinstance(attempt_id, str) and attempt_id in completion_ids:
        return True
    if isinstance(template_id, str) and template_id in template_ids:
        return True
    return False


def _new_stem_for(old_stem: str, old_normal_name: str, new_normal_name: str) -> str | None:
    prefix = f"{old_normal_name}__"
    if not old_stem.startswith(prefix):
        return None
    suffix = old_stem[len(prefix) :]
    return f"{new_normal_name}__{suffix}"


def _plan_context_moves(
    *,
    context_root: Path,
    completion_ids: set[str],
    template_ids: set[str],
    old_normal_name: str,
    new_normal_name: str,
) -> list[PlannedMove]:
    planned: dict[tuple[str, str], PlannedMove] = {}
    marking_root = context_root / "marking_results"
    if not marking_root.exists():
        return []

    for marking_json in marking_root.rglob("*.json"):
        if _is_archived(marking_json):
            continue
        try:
            payload = json.loads(marking_json.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if not _marking_matches_scope(payload, completion_ids, template_ids):
            continue

        new_stem = _new_stem_for(marking_json.stem, old_normal_name, new_normal_name)
        if new_stem is None:
            continue

        marking_dst = marking_json.with_name(f"{new_stem}.json")
        _add_move(planned, "marking_results", marking_json, marking_dst, "rename matched marking result")

        report_src = _report_path_for(marking_json, context_root)
        if report_src.exists() and not _is_archived(report_src):
            report_dst = report_src.with_name(f"{new_stem} - Marking Report.md")
            _add_move(planned, "learning_reports", report_src, report_dst, "paired report stem rename")

        context = payload.get("context")
        if isinstance(context, dict):
            student_slug = slugify_student(context.get("student_id"), context.get("student_name"))
            subject_context = context.get("subject_context")
            if isinstance(subject_context, str) and subject_context.strip():
                review_src = context_root / "student_review_states" / student_slug / subject_context / f"{marking_json.stem}.json"
                if review_src.exists() and not _is_archived(review_src):
                    review_dst = review_src.with_name(f"{new_stem}.json")
                    _add_move(
                        planned,
                        "student_review_states",
                        review_src,
                        review_dst,
                        "linked review-state stem rename",
                    )
                amend_src = context_root / "marking_amendments" / student_slug / subject_context / f"{marking_json.stem}.json"
                if amend_src.exists() and not _is_archived(amend_src):
                    amend_dst = amend_src.with_name(f"{new_stem}.json")
                    _add_move(
                        planned,
                        "marking_amendments",
                        amend_src,
                        amend_dst,
                        "linked amendment stem rename",
                    )
            marking_asset = context.get("marking_asset")
            if isinstance(marking_asset, str) and marking_asset.strip():
                bundle_src = (context_root / marking_asset).resolve(strict=False)
                if bundle_src.exists() and bundle_src.is_dir() and not _is_archived(bundle_src):
                    bundle_new_stem = _new_stem_for(bundle_src.name, old_normal_name, new_normal_name)
                    if bundle_new_stem:
                        bundle_dst = bundle_src.with_name(bundle_new_stem)
                        _add_move(planned, "marking_assets", bundle_src, bundle_dst, "linked marking-asset bundle rename")

    return sorted(planned.values(), key=lambda m: (m.family, m.src, m.dst))


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _to_rel_context_path(*, context_root: Path, absolute_path: str) -> str:
    return Path(absolute_path).resolve(strict=False).relative_to(context_root.resolve(strict=False)).as_posix()


def _apply_learning_db_remap(
    *,
    learning_db_path: Path | None,
    context_root: Path,
    moves: list[PlannedMove],
) -> dict[str, int | str]:
    if learning_db_path is None:
        return {"status": "skipped_no_db_path"}
    if not learning_db_path.exists():
        return {"status": "skipped_db_missing", "db_path": str(learning_db_path)}

    rel_map_by_family: dict[str, dict[str, str]] = {}
    for move in moves:
        old_rel = _to_rel_context_path(context_root=context_root, absolute_path=move.src)
        new_rel = _to_rel_context_path(context_root=context_root, absolute_path=move.dst)
        rel_map_by_family.setdefault(move.family, {})[old_rel] = new_rel

    marking_results_map = rel_map_by_family.get("marking_results", {})
    review_map = rel_map_by_family.get("student_review_states", {})
    amendment_map = rel_map_by_family.get("marking_amendments", {})
    assets_map = rel_map_by_family.get("marking_assets", {})

    counters = {
        "marking_artifacts_paths_updated": 0,
        "marking_assets_updated": 0,
        "review_states_paths_updated": 0,
        "review_states_marking_result_path_updated": 0,
        "amendments_paths_updated": 0,
        "amendments_marking_result_path_updated": 0,
        "import_identity_source_path_updated": 0,
        "import_quarantine_source_path_updated": 0,
    }

    conn = sqlite3.connect(str(learning_db_path))
    conn.row_factory = sqlite3.Row
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        with conn:
            if "marking_artifacts" in tables:
                for old_rel, new_rel in marking_results_map.items():
                    counters["marking_artifacts_paths_updated"] += conn.execute(
                        """
                        UPDATE marking_artifacts
                        SET artifact_path = ?, artifact_stem = ?
                        WHERE artifact_path = ?
                        """,
                        (new_rel, Path(new_rel).stem, old_rel),
                    ).rowcount
                for old_rel, new_rel in assets_map.items():
                    counters["marking_assets_updated"] += conn.execute(
                        "UPDATE marking_artifacts SET marking_asset = ? WHERE marking_asset = ?",
                        (new_rel, old_rel),
                    ).rowcount
            if "student_review_states" in tables:
                for old_rel, new_rel in review_map.items():
                    counters["review_states_paths_updated"] += conn.execute(
                        "UPDATE student_review_states SET review_state_path = ? WHERE review_state_path = ?",
                        (new_rel, old_rel),
                    ).rowcount
                for old_rel, new_rel in marking_results_map.items():
                    counters["review_states_marking_result_path_updated"] += conn.execute(
                        "UPDATE student_review_states SET marking_result_path = ? WHERE marking_result_path = ?",
                        (new_rel, old_rel),
                    ).rowcount
            if "marking_amendments" in tables:
                for old_rel, new_rel in amendment_map.items():
                    counters["amendments_paths_updated"] += conn.execute(
                        "UPDATE marking_amendments SET amendment_path = ? WHERE amendment_path = ?",
                        (new_rel, old_rel),
                    ).rowcount
                for old_rel, new_rel in marking_results_map.items():
                    counters["amendments_marking_result_path_updated"] += conn.execute(
                        "UPDATE marking_amendments SET marking_result_path = ? WHERE marking_result_path = ?",
                        (new_rel, old_rel),
                    ).rowcount
            if "import_identity_map" in tables:
                for old_rel, new_rel in {**marking_results_map, **review_map, **amendment_map}.items():
                    counters["import_identity_source_path_updated"] += conn.execute(
                        "UPDATE import_identity_map SET source_path = ? WHERE source_path = ?",
                        (new_rel, old_rel),
                    ).rowcount
                    counters["import_identity_source_path_updated"] += conn.execute(
                        "UPDATE import_identity_map SET source_path = ? || substr(source_path, ?) WHERE source_path LIKE ?",
                        (new_rel, len(old_rel) + 1, f"{old_rel}::%"),
                    ).rowcount
            if "import_quarantine" in tables:
                for old_rel, new_rel in {**marking_results_map, **review_map, **amendment_map}.items():
                    counters["import_quarantine_source_path_updated"] += conn.execute(
                        "UPDATE import_quarantine SET source_path = ? WHERE source_path = ?",
                        (new_rel, old_rel),
                    ).rowcount
                    counters["import_quarantine_source_path_updated"] += conn.execute(
                        "UPDATE import_quarantine SET source_path = ? || substr(source_path, ?) WHERE source_path LIKE ?",
                        (new_rel, len(old_rel) + 1, f"{old_rel}::%"),
                    ).rowcount
    finally:
        conn.close()
    counters["status"] = "updated"
    counters["db_path"] = str(learning_db_path)
    return counters


def rename_file_with_context_guardrail(
    *,
    file_id_or_path: str,
    new_name: str,
    context_root: str | Path = "ai_study_buddy/context",
    db_path: str | Path | None = None,
    learning_db_path: str | Path | None = None,
    dry_run: bool = True,
    manifest_path: str | Path | None = None,
) -> dict:
    if db_path is not None:
        os.environ["PDF_REGISTRY_PATH"] = str(Path(db_path).resolve())
    manager = PdfFileManager()
    target = _resolve_file(manager, file_id_or_path)
    if target is None:
        raise ValueError(f"File not found: {file_id_or_path}")
    if not new_name.lower().endswith(".pdf"):
        raise ValueError("new_name must end with .pdf")
    if "/" in new_name or "\\" in new_name:
        raise ValueError("new_name must be a filename, not a path")

    old_normal = normalize_pdf_display_name(target.name)
    new_normal = normalize_pdf_display_name(new_name)
    context_root_path = Path(context_root).resolve(strict=False)
    completion_ids, template_ids = _completion_scope_ids(manager, target)
    moves = _plan_context_moves(
        context_root=context_root_path,
        completion_ids=completion_ids,
        template_ids=template_ids,
        old_normal_name=old_normal,
        new_normal_name=new_normal,
    )

    for move in moves:
        dst = Path(move.dst)
        if dst.exists():
            raise ValueError(f"Refusing to rename; destination exists: {dst}")

    manifest = {
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dry_run": dry_run,
        "file_id": target.id,
        "old_name": target.name,
        "new_name": new_name,
        "old_normal_name": old_normal,
        "new_normal_name": new_normal,
        "completion_scope_ids": sorted(completion_ids),
        "template_scope_ids": sorted(template_ids),
        "planned_moves": [asdict(m) for m in moves],
        "applied_moves": [],
        "pending_moves": [asdict(m) for m in moves],
        "errors": [],
        "registry_rename_applied": False,
        "learning_db_remap": {"status": "not_started"},
    }

    if dry_run:
        return manifest

    out_manifest = Path(manifest_path).resolve(strict=False) if manifest_path else _build_recovery_manifest_path(context_root_path, target.id)
    applied: list[PlannedMove] = []
    try:
        manager.rename_file(target.id, new_name)
        manifest["registry_rename_applied"] = True
        for move in moves:
            src = Path(move.src)
            dst = Path(move.dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            applied.append(move)
            manifest["applied_moves"] = [asdict(m) for m in applied]
            manifest["pending_moves"] = [asdict(m) for m in moves[len(applied) :]]
            _write_manifest(out_manifest, manifest)
        resolved_learning_db_path = (
            Path(learning_db_path).resolve(strict=False)
            if learning_db_path is not None
            else (Path("ai_study_buddy/db/study_buddy.db").resolve(strict=False))
        )
        manifest["learning_db_remap"] = _apply_learning_db_remap(
            learning_db_path=resolved_learning_db_path,
            context_root=context_root_path,
            moves=moves,
        )
    except Exception as exc:
        manifest["errors"].append(f"{type(exc).__name__}: {exc}")
        manifest["applied_moves"] = [asdict(m) for m in applied]
        applied_set = {(m.src, m.dst) for m in applied}
        manifest["pending_moves"] = [asdict(m) for m in moves if (m.src, m.dst) not in applied_set]
        _write_manifest(out_manifest, manifest)
        raise

    _write_manifest(out_manifest, manifest)
    manifest["manifest_path"] = str(out_manifest)
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Rename one registered PDF plus linked context artifact stems with guardrails.")
    parser.add_argument("--file", required=True, help="Target file_id or file path to rename.")
    parser.add_argument("--new-name", required=True, help="New PDF filename (e.g. 'P4 Math WA1.pdf').")
    parser.add_argument("--context-root", type=Path, default=Path("ai_study_buddy/context"), help="Context root path.")
    parser.add_argument("--db", type=Path, help="Optional explicit registry DB path.")
    parser.add_argument("--manifest", type=Path, help="Optional recovery manifest output path.")
    parser.add_argument(
        "--learning-db-path",
        type=Path,
        help="Optional study_buddy.db path for path-coupled row remap (default: ai_study_buddy/db/study_buddy.db).",
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run.")
    args = parser.parse_args(argv)

    result = rename_file_with_context_guardrail(
        file_id_or_path=args.file,
        new_name=args.new_name,
        context_root=args.context_root,
        db_path=args.db,
        learning_db_path=args.learning_db_path,
        dry_run=not args.apply,
        manifest_path=args.manifest,
    )
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
