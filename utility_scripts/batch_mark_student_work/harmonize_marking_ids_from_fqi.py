#!/usr/bin/env python3
"""Harmonize marking result_id labels (and page map pages) to match template FQI.

For 1:1 index-aligned relabel cases only (same question count, same order).
Updates question_page_map and question_results, then re-validates and writes via
write_marking_artifact.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai_study_buddy.marking.core.artifact_schema import validate_marking_artifact_dict
from ai_study_buddy.marking.core.artifact_writer import write_marking_artifact
from ai_study_buddy.marking.core.models import MarkingArtifact
from ai_study_buddy.marking.review.amendment_service import validate_amendment_state
from ai_study_buddy.marking.file_question_info.api import (
    build_detector_question_id_list,
    question_page_map_from_question_sections,
)

CONTEXT_ROOT = _REPO_ROOT / "ai_study_buddy" / "context"
STUDY_DB = _REPO_ROOT / "ai_study_buddy" / "db" / "study_buddy.db"


@dataclass
class HarmonizeResult:
    ord: int
    status: str
    renames: int
    path: str | None = None
    error: str | None = None


def _load_fqi(template_file_id: str, study: sqlite3.Connection) -> tuple[list[str], dict[str, int]]:
    row = study.execute(
        """
        SELECT raw_json FROM file_question_info_runs
        WHERE primary_file_id = ? AND is_deleted = 0
        ORDER BY updated_at DESC LIMIT 1
        """,
        (template_file_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"no FQI run for template {template_file_id}")
    payload = json.loads(str(row[0]))
    ids = list(build_detector_question_id_list(payload))
    page_map = question_page_map_from_question_sections(payload)
    pages = {k: int(v["attempt_page_start"]) for k, v in page_map.items()}
    return ids, pages


def _build_index_map(marking_ids: list[str], fqi_ids: list[str]) -> dict[str, str]:
    if len(marking_ids) != len(fqi_ids):
        raise ValueError(f"count mismatch: marking={len(marking_ids)} fqi={len(fqi_ids)}")
    mapping: dict[str, str] = {}
    for old, new in zip(marking_ids, fqi_ids, strict=True):
        if old != new:
            if new in mapping.values():
                raise ValueError(f"collision: multiple marking ids map to {new}")
            mapping[old] = new
    return mapping


def _load_id_map_file(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "id_map" in raw and isinstance(raw["id_map"], dict):
        raw = raw["id_map"]
    if not isinstance(raw, dict):
        raise ValueError("id-map file must be a JSON object of old_id -> new_id")
    return {str(k): str(v) for k, v in raw.items()}


def _apply_id_map(payload: dict, id_map: dict[str, str], fqi_pages: dict[str, int]) -> int:
    renames = 0
    context = payload.setdefault("context", {})
    qpm = context.get("question_page_map")
    if not isinstance(qpm, list):
        raise ValueError("context.question_page_map must be a list")

    new_qpm: list[dict] = []
    for row in qpm:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("result_id") or "")
        new_rid = id_map.get(rid, rid)
        if new_rid != rid:
            renames += 1
        updated = dict(row)
        updated["result_id"] = new_rid
        if new_rid in fqi_pages:
            updated["attempt_page_start"] = fqi_pages[new_rid]
            updated["source"] = "script_inferred"
        new_qpm.append(updated)
    context["question_page_map"] = new_qpm

    qr = payload.get("question_results")
    if not isinstance(qr, list):
        raise ValueError("question_results must be a list")

    new_qr: list[dict] = []
    for row in qr:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("result_id") or "")
        new_rid = id_map.get(rid, rid)
        updated = dict(row)
        updated["result_id"] = new_rid
        new_qr.append(updated)
    payload["question_results"] = new_qr

    return renames


def _migrate_amendment_file(
    *,
    marking_rel_path: str,
    id_map: dict[str, str],
    context_root: Path,
) -> int:
    """Rename amendment result_ids to match a marking harmonize id_map."""
    if not id_map:
        return 0
    rel = Path(marking_rel_path)
    if rel.parts[0] == "marking_results":
        rel = Path(*rel.parts[1:])
    amend_path = context_root / "marking_amendments" / rel
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
        base_path = context_root / "marking_results" / rel
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
            context_root=context_root,
        )
    return renamed


def harmonize_marking(
    *,
    marking_rel_path: str,
    template_file_id: str,
    dry_run: bool,
    id_map: dict[str, str] | None = None,
    label: str = "",
) -> HarmonizeResult:
    """Harmonize one marking artifact to template FQI ids (optional explicit id_map)."""
    ord_num = 0
    try:
        if label.isdigit():
            ord_num = int(label)
    except ValueError:
        pass

    study = sqlite3.connect(str(STUDY_DB))
    try:
        mr_path = CONTEXT_ROOT / marking_rel_path
        if not mr_path.is_file():
            return HarmonizeResult(ord=ord_num, status="error", renames=0, error="marking_file_missing")

        payload = json.loads(mr_path.read_text(encoding="utf-8"))
        mr_ids = [
            str(x["result_id"])
            for x in (payload.get("context") or {}).get("question_page_map") or []
            if isinstance(x, dict) and x.get("result_id")
        ]
        fqi_ids, fqi_pages = _load_fqi(template_file_id, study)
        if id_map is None:
            id_map = _build_index_map(mr_ids, fqi_ids)
        else:
            unknown = [k for k in id_map if k not in mr_ids]
            if unknown:
                raise ValueError(f"id_map keys not in marking: {unknown[:5]}")
            targets = set(id_map.values())
            if len(targets) != len(id_map):
                raise ValueError("id_map target collision")
            if not targets.issubset(set(fqi_ids)):
                missing = sorted(targets - set(fqi_ids))[:8]
                raise ValueError(f"id_map targets missing from FQI: {missing}")
        if not id_map and mr_ids == fqi_ids:
            return HarmonizeResult(ord=ord_num, status="skipped", renames=0, path=marking_rel_path, error="already_aligned")

        renames = _apply_id_map(payload, id_map, fqi_pages)
        payload["updated_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

        validate_marking_artifact_dict(payload)

        if dry_run:
            return HarmonizeResult(ord=ord_num, status="dry_run", renames=renames, path=marking_rel_path)

        artifact = MarkingArtifact.from_dict(payload)
        written = write_marking_artifact(artifact, output_path=mr_path, context_root=CONTEXT_ROOT)
        _migrate_amendment_file(
            marking_rel_path=marking_rel_path,
            id_map=id_map,
            context_root=CONTEXT_ROOT,
        )
        return HarmonizeResult(
            ord=ord_num,
            status="written",
            renames=renames,
            path=str(written.relative_to(_REPO_ROOT)),
        )
    except Exception as exc:
        return HarmonizeResult(ord=ord_num, status="error", renames=0, error=str(exc))
    finally:
        study.close()


def harmonize_ord(
    ord_num: int,
    *,
    completion_manifest: Path,
    dry_run: bool,
    id_map: dict[str, str] | None = None,
) -> HarmonizeResult:
    manifest = json.loads(completion_manifest.read_text(encoding="utf-8"))
    completion = next((c for c in manifest["completions"] if int(c["manifest_ord"]) == ord_num), None)
    if completion is None:
        return HarmonizeResult(ord=ord_num, status="error", renames=0, error="ord_not_in_manifest")

    study = sqlite3.connect(str(STUDY_DB))
    try:
        art = study.execute(
            """
            SELECT artifact_path FROM marking_artifacts
            WHERE is_deleted = 0 AND attempt_file_id = ?
            LIMIT 1
            """,
            (completion["completion_file_id"],),
        ).fetchone()
    finally:
        study.close()
    if art is None:
        return HarmonizeResult(ord=ord_num, status="error", renames=0, error="no_marking_artifact")
    return harmonize_marking(
        marking_rel_path=str(art[0]),
        template_file_id=str(completion["template_file_id"]),
        dry_run=dry_run,
        id_map=id_map,
        label=str(ord_num),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ord", type=int, action="append", dest="ords", help="Manifest ord(s) to harmonize")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--id-map-json",
        type=Path,
        help="JSON object old_id->new_id (or {\"id_map\": {...}}); use with a single --ord",
    )
    parser.add_argument("--marking-result-path", type=str, help="Relative path under context/")
    parser.add_argument("--template-file-id", type=str)
    parser.add_argument(
        "--id-maps-manifest",
        type=Path,
        help="JSON with ord_* entries (marking_result_path, template_file_id, id_map)",
    )
    parser.add_argument(
        "--completion-manifest",
        type=Path,
        help="export_priority_fqi_completion_manifest output; required with --ord",
    )
    args = parser.parse_args()

    if args.id_maps_manifest:
        manifest = json.loads(args.id_maps_manifest.read_text(encoding="utf-8"))
        results = []
        for key, entry in sorted(manifest.items()):
            if not key.startswith("ord_") or not isinstance(entry, dict):
                continue
            results.append(
                harmonize_marking(
                    marking_rel_path=str(entry["marking_result_path"]),
                    template_file_id=str(entry["template_file_id"]),
                    dry_run=args.dry_run,
                    id_map=dict(entry["id_map"]),
                    label=str(entry.get("queue_ord", key)),
                )
            )
    elif args.marking_result_path and args.template_file_id:
        explicit_map = _load_id_map_file(args.id_map_json) if args.id_map_json else None
        results = [
            harmonize_marking(
                marking_rel_path=args.marking_result_path,
                template_file_id=args.template_file_id,
                dry_run=args.dry_run,
                id_map=explicit_map,
            )
        ]
    elif args.ords and args.completion_manifest:
        explicit_map = _load_id_map_file(args.id_map_json) if args.id_map_json else None
        if explicit_map is not None and len(args.ords) != 1:
            raise SystemExit("--id-map-json requires exactly one --ord")
        results = [
            harmonize_ord(
                o,
                completion_manifest=args.completion_manifest,
                dry_run=args.dry_run,
                id_map=explicit_map if len(args.ords) == 1 else None,
            )
            for o in args.ords
        ]
    else:
        raise SystemExit(
            "Specify --id-maps-manifest, or --marking-result-path with --template-file-id, "
            "or --ord with --completion-manifest"
        )
    print(json.dumps([r.__dict__ for r in results], indent=2, ensure_ascii=False))
    failed = [r for r in results if r.status == "error"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
