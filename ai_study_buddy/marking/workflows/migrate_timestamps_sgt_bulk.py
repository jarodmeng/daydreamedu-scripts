"""One-time bulk migration: normalize marking_result.v1 timestamps to SGT (+08:00).

Renames JSON and paired learning reports when the ``__YYYYMMDD_HHMMSS`` stem changes.
Does not re-render markdown bodies.

Usage (from repo root)::

    PYTHONPATH=. python3 -m ai_study_buddy.marking.workflows.migrate_timestamps_sgt_bulk --dry-run
    PYTHONPATH=. python3 -m ai_study_buddy.marking.workflows.migrate_timestamps_sgt_bulk
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_study_buddy.marking.core.artifact_paths import build_attempt_basename
from ai_study_buddy.marking.core.artifact_schema import validate_marking_artifact_dict
from ai_study_buddy.marking.core.marking_time import to_marking_iso

_CONTEXT_ROOT = Path("ai_study_buddy/context")
_MARKING_ROOT = _CONTEXT_ROOT / "marking_results"
_LEARNING_ROOT = _CONTEXT_ROOT / "learning_reports"
_SCRATCH_ROOT = _CONTEXT_ROOT / ".marking_scratch"


def _iter_marking_json_files() -> list[Path]:
    if not _MARKING_ROOT.is_dir():
        return []
    return sorted(_MARKING_ROOT.rglob("*.json"))


def _learning_report_path(stem: str, json_path: Path) -> Path:
    rel_parent = json_path.parent.relative_to(_MARKING_ROOT)
    return _LEARNING_ROOT / rel_parent / f"{stem} - Marking Report.md"


def _apply_timestamp_migration(data: dict) -> None:
    data["created_at"] = to_marking_iso(data["created_at"])
    data["updated_at"] = to_marking_iso(data["updated_at"])
    rm = data.get("review_meta")
    if isinstance(rm, dict) and rm.get("updated_at"):
        rm["updated_at"] = to_marking_iso(rm["updated_at"])
    validate_marking_artifact_dict(data)


def _new_basename(data: dict, json_path: Path) -> str:
    attempt = (data.get("context") or {}).get("attempt_file_path") or ""
    name = Path(attempt).name if attempt else json_path.name
    if not name.endswith(".pdf"):
        name = json_path.name
    return build_attempt_basename(name, marked_at=data["created_at"])


def run(*, dry_run: bool) -> int:
    files = _iter_marking_json_files()
    if not files:
        print("No JSON files under", _MARKING_ROOT)
        return 0

    in_place = 0
    renames_json: list[tuple[Path, Path, str, str]] = []
    renames_md: list[tuple[Path, Path]] = []

    for json_path in files:
        raw = json_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        old_stem = json_path.stem
        _apply_timestamp_migration(data)
        new_stem = _new_basename(data, json_path)
        out_text = json.dumps(data, indent=2, ensure_ascii=True) + "\n"

        if new_stem == old_stem:
            if raw != out_text:
                in_place += 1
                if not dry_run:
                    json_path.write_text(out_text, encoding="utf-8")
            continue

        new_json = json_path.parent / f"{new_stem}.json"
        if new_json.exists() and new_json.resolve() != json_path.resolve():
            raise SystemExit(f"Collision: {new_json} already exists (from {json_path})")

        renames_json.append((json_path, new_json, old_stem, new_stem))
        old_md = _learning_report_path(old_stem, json_path)
        new_md = _learning_report_path(new_stem, json_path)
        if old_md.is_file():
            if new_md.exists() and new_md.resolve() != old_md.resolve():
                raise SystemExit(f"Collision: {new_md} already exists (from {old_md})")
            renames_md.append((old_md, new_md))

        if not dry_run:
            new_json.write_text(out_text, encoding="utf-8")
            json_path.unlink()
            if old_md.is_file():
                new_md.parent.mkdir(parents=True, exist_ok=True)
                old_md.rename(new_md)

    scratch_updates = 0
    if _SCRATCH_ROOT.is_dir() and renames_json and not dry_run:
        mapping = [(t[2], t[3]) for t in renames_json]
        for py in _SCRATCH_ROOT.rglob("*.py"):
            t = py.read_text(encoding="utf-8")
            orig = t
            for old_stem, new_stem in mapping:
                if old_stem != new_stem and old_stem in t:
                    t = t.replace(old_stem, new_stem)
            if t != orig:
                py.write_text(t, encoding="utf-8")
                scratch_updates += 1

    print(f"Marking JSON files scanned: {len(files)}")
    print(f"  Timestamp normalized in place (no rename): {in_place}")
    print(f"  JSON + report renames: {len(renames_json)}")
    if dry_run:
        print("(dry-run: no files written; scratch not scanned for renames)")
        for old_p, new_p, old_s, new_s in renames_json[:30]:
            if old_s != new_s:
                print(f"  {old_p.name} -> {new_p.name}")
        if len(renames_json) > 30:
            print(f"  ... and {len(renames_json) - 30} more")
    else:
        print(f"Scratch *.py files touched: {scratch_updates}")

    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
