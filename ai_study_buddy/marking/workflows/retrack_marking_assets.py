"""Backfill `context.marking_asset` and refresh learning reports.

This workflow helps migrate from legacy `.marking_scratch` references to
`marking_assets` and links each canonical marking JSON to the most likely asset
folder.

Usage (from repo root)::

    PYTHONPATH=. python3 -m ai_study_buddy.marking.workflows.retrack_marking_assets --dry-run
    PYTHONPATH=. python3 -m ai_study_buddy.marking.workflows.retrack_marking_assets
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_study_buddy.marking.core.artifact_paths import slugify_student
from ai_study_buddy.marking.core.artifact_schema import validate_marking_artifact_dict
from ai_study_buddy.marking.core.artifact_writer import write_marking_artifact
from ai_study_buddy.marking.core.models import MarkingArtifact
from ai_study_buddy.marking.workflows.report_renderer import render_learning_report_from_json
from ai_study_buddy.pdf_file_manager.pdf_file_manager import normalize_pdf_display_name

_LEGACY_ROOT = ".marking_scratch"
_ASSET_ROOT = "marking_assets"


@dataclass(frozen=True)
class _AssetCandidate:
    path: Path
    slug: str


def _iter_marking_json_files(marking_root: Path) -> list[Path]:
    if not marking_root.is_dir():
        return []
    return sorted(marking_root.rglob("*.json"))


def _asset_candidates(asset_root: Path) -> list[_AssetCandidate]:
    if not asset_root.is_dir():
        return []
    out: list[_AssetCandidate] = []
    for p in sorted(asset_root.iterdir()):
        if p.is_dir():
            out.append(_AssetCandidate(path=p, slug=p.name.casefold()))
    return out


def _replace_legacy_root_refs(text: str | None) -> str | None:
    if text is None:
        return None
    updated = text.replace(_LEGACY_ROOT, _ASSET_ROOT)
    return updated


_ASSET_REF_RE = re.compile(
    r"(?:ai_study_buddy/context/)?(?:marking_assets|\.marking_scratch)/([^\s`\"')]+)"
)


def _path_from_reference(candidate: str, asset_root: Path) -> Path | None:
    rel = candidate.strip().lstrip("/")
    if not rel:
        return None

    options = [asset_root / rel.split("/", 1)[0], asset_root / rel]
    for option in options:
        cur = option
        while cur != asset_root:
            if cur.is_dir():
                return cur
            cur = cur.parent
    return None


def _extract_hint_asset_path(payload: dict[str, Any], asset_root: Path) -> Path | None:
    context = payload.get("context")
    generation = payload.get("generation")
    hint_texts: list[str] = []
    if isinstance(context, dict):
        amn = context.get("answer_mapping_notes")
        if isinstance(amn, str):
            hint_texts.append(amn)
    if isinstance(generation, dict):
        notes = generation.get("notes")
        if isinstance(notes, str):
            hint_texts.append(notes)

    for text in hint_texts:
        for match in _ASSET_REF_RE.finditer(text):
            path = _path_from_reference(match.group(1), asset_root)
            if path is not None:
                return path
    return None


def _extract_tokens(text: str) -> set[str]:
    out: set[str] = set()
    for token in re.split(r"[^a-z0-9]+", text.casefold()):
        if not token:
            continue
        if token.isdigit():
            out.add(token)
            continue
        if len(token) >= 2:
            out.add(token)
    return out


def _guess_asset_path_from_attempt(
    payload: dict[str, Any], candidates: list[_AssetCandidate]
) -> Path | None:
    context = payload.get("context")
    if not isinstance(context, dict):
        return None

    attempt_file_path = context.get("attempt_file_path")
    if not isinstance(attempt_file_path, str) or not attempt_file_path.strip():
        return None

    student_slug = slugify_student(context.get("student_id"), context.get("student_name"))
    attempt_name = Path(attempt_file_path).name
    stem = normalize_pdf_display_name(attempt_name)
    stem_tokens = _extract_tokens(stem)
    if not stem_tokens:
        return None

    best: tuple[int, Path] | None = None
    for candidate in candidates:
        score = 0
        if student_slug in candidate.slug:
            score += 2
        cand_tokens = _extract_tokens(candidate.slug)
        score += len(stem_tokens.intersection(cand_tokens))
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, candidate.path)
    if best is None:
        return None
    if best[0] < 2:
        return None
    return best[1]


def _rel_to_context_root(path: Path, context_root: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(context_root.resolve())
    except ValueError:
        return None
    return rel.as_posix()


def run(
    *,
    context_root: str | Path = "ai_study_buddy/context",
    dry_run: bool = False,
    rerender_reports: bool = True,
) -> dict[str, int]:
    root = Path(context_root)
    marking_root = root / "marking_results"
    asset_root = root / _ASSET_ROOT

    json_files = _iter_marking_json_files(marking_root)
    candidates = _asset_candidates(asset_root)

    scanned = 0
    updated_json = 0
    updated_marking_asset = 0
    updated_legacy_refs = 0
    rendered_reports = 0
    unresolved_assets = 0

    for json_path in json_files:
        scanned += 1
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        context = payload.get("context")
        if not isinstance(context, dict):
            continue

        changed = False

        amn = context.get("answer_mapping_notes")
        if isinstance(amn, str):
            new_amn = _replace_legacy_root_refs(amn)
            if new_amn != amn:
                context["answer_mapping_notes"] = new_amn
                updated_legacy_refs += 1
                changed = True

        generation = payload.get("generation")
        if isinstance(generation, dict):
            notes = generation.get("notes")
            if isinstance(notes, str):
                new_notes = _replace_legacy_root_refs(notes)
                if new_notes != notes:
                    generation["notes"] = new_notes
                    updated_legacy_refs += 1
                    changed = True

        target_asset: Path | None = None
        existing = context.get("marking_asset")
        if isinstance(existing, str) and existing.strip():
            existing_path = root / existing
            if existing_path.is_dir():
                try:
                    rel_existing = existing_path.resolve().relative_to(asset_root.resolve())
                except ValueError:
                    target_asset = existing_path
                else:
                    top_level = asset_root / rel_existing.parts[0]
                    target_asset = top_level if top_level.is_dir() else existing_path

        if target_asset is None:
            target_asset = _extract_hint_asset_path(payload, asset_root)
        if target_asset is None:
            target_asset = _guess_asset_path_from_attempt(payload, candidates)

        if target_asset is None:
            unresolved_assets += 1
            if context.get("marking_asset") is not None:
                context["marking_asset"] = None
                changed = True
        else:
            rel = _rel_to_context_root(target_asset, root)
            if rel and context.get("marking_asset") != rel:
                context["marking_asset"] = rel
                updated_marking_asset += 1
                changed = True

        try:
            validate_marking_artifact_dict(payload)
        except Exception:
            continue

        if changed:
            updated_json += 1
            if not dry_run:
                artifact = MarkingArtifact.from_dict(payload)
                write_marking_artifact(
                    artifact,
                    output_path=json_path,
                    context_root=root,
                    schema_version=payload.get("schema_version"),
                    actor="script:ai_study_buddy.marking.workflows.retrack_marking_assets",
                )

        if rerender_reports and not dry_run:
            render_learning_report_from_json(json_path, context_root=root)
            rendered_reports += 1

    summary = {
        "scanned_json": scanned,
        "updated_json": updated_json,
        "updated_marking_asset": updated_marking_asset,
        "updated_legacy_refs": updated_legacy_refs,
        "unresolved_assets": unresolved_assets,
        "rendered_reports": rendered_reports,
        "dry_run": int(dry_run),
    }
    print(f"Scanned marking JSON: {summary['scanned_json']}")
    print(f"Updated JSON files: {summary['updated_json']}")
    print(f"Updated context.marking_asset: {summary['updated_marking_asset']}")
    print(f"Updated legacy text refs: {summary['updated_legacy_refs']}")
    print(f"Unresolved assets: {summary['unresolved_assets']}")
    print(f"Learning reports rendered: {summary['rendered_reports']}")
    if dry_run:
        print("(dry-run: no files written)")
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--context-root", default="ai_study_buddy/context")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-rerender", action="store_true")
    args = p.parse_args()
    run(
        context_root=args.context_root,
        dry_run=args.dry_run,
        rerender_reports=not args.no_rerender,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
