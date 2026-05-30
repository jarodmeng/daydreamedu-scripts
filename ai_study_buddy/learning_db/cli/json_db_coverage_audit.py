"""Venn-style audit: context JSON files vs study_buddy.db rows by relative path.

For each supported artifact family, reports:
  - json_only: on disk, no active DB row at that path
  - db_only: active DB row, no matching JSON file
  - both: path present in both; classifies hash sync vs drift

Sync uses ``source_content_hash`` (SHA-256 of raw file bytes), matching the importer.
When hash differs, also checks whether parsed JSON objects are semantically equal
(reformat-only drift).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_study_buddy.learning_db.core.connection import default_context_root, default_db_path, get_connection


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rel(context_root: Path, path: Path) -> str:
    return path.resolve().relative_to(context_root.resolve()).as_posix()


def _load_json_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


@dataclass
class FamilyAudit:
    family: str
    json_paths: set[str] = field(default_factory=set)
    db_paths: set[str] = field(default_factory=set)
    db_deleted_paths: set[str] = field(default_factory=set)
    db_hashes: dict[str, str] = field(default_factory=dict)
    db_raw_json: dict[str, str] = field(default_factory=dict)
    json_only: list[str] = field(default_factory=list)
    db_only: list[str] = field(default_factory=list)
    both_hash_synced: list[str] = field(default_factory=list)
    both_hash_drift_semantic_synced: list[str] = field(default_factory=list)
    both_hash_drift_semantic_drift: list[str] = field(default_factory=list)
    both_json_unreadable: list[str] = field(default_factory=list)

    @property
    def json_only_count(self) -> int:
        return len(self.json_only)

    @property
    def db_only_count(self) -> int:
        return len(self.db_only)

    @property
    def both_count(self) -> int:
        return (
            len(self.both_hash_synced)
            + len(self.both_hash_drift_semantic_synced)
            + len(self.both_hash_drift_semantic_drift)
            + len(self.both_json_unreadable)
        )

    @property
    def both_fully_synced_count(self) -> int:
        return len(self.both_hash_synced)

    @property
    def both_drift_count(self) -> int:
        return (
            len(self.both_hash_drift_semantic_synced)
            + len(self.both_hash_drift_semantic_drift)
            + len(self.both_json_unreadable)
        )

    def to_dict(self, *, sample_limit: int) -> dict[str, Any]:
        def sample(items: list[str]) -> list[str]:
            return items[: max(sample_limit, 0)]

        return {
            "counts": {
                "json_on_disk": len(self.json_paths),
                "db_active_rows": len(self.db_paths),
                "db_deleted_rows": len(self.db_deleted_paths),
                "json_only": self.json_only_count,
                "db_only": self.db_only_count,
                "both": self.both_count,
                "both_hash_synced": len(self.both_hash_synced),
                "both_reformat_only_drift": len(self.both_hash_drift_semantic_synced),
                "both_semantic_drift": len(self.both_hash_drift_semantic_drift),
                "both_json_unreadable": len(self.both_json_unreadable),
            },
            "samples": {
                "json_only": sample(self.json_only),
                "db_only": sample(self.db_only),
                "both_hash_synced": sample(self.both_hash_synced),
                "both_reformat_only_drift": sample(self.both_hash_drift_semantic_synced),
                "both_semantic_drift": sample(self.both_hash_drift_semantic_drift),
                "both_json_unreadable": sample(self.both_json_unreadable),
            },
        }


def _iter_json_files(context_root: Path, family: str) -> list[Path]:
    mapping = {
        "marking_result": context_root / "marking_results",
        "marking_amendment": context_root / "marking_amendments",
        "student_review_state": context_root / "student_review_states",
        "file_question_info": context_root / "file_question_info",
    }
    base = mapping[family]
    if not base.is_dir():
        return []
    if family == "file_question_info":
        return sorted(base.rglob("question_sections.json"))
    return sorted(base.rglob("*.json"))


def _fetch_db_rows(conn, family: str) -> tuple[dict[str, str], dict[str, str], set[str]]:
    """Return (active path->hash, active path->raw_json, deleted paths)."""
    if family == "marking_result":
        sql = "SELECT artifact_path, source_content_hash, raw_json, is_deleted FROM marking_artifacts"
        path_key = "artifact_path"
    elif family == "marking_amendment":
        sql = "SELECT amendment_path, source_content_hash, raw_json, is_deleted FROM marking_amendments"
        path_key = "amendment_path"
    elif family == "student_review_state":
        sql = "SELECT review_state_path, source_content_hash, raw_json, is_deleted FROM student_review_states"
        path_key = "review_state_path"
    elif family == "file_question_info":
        sql = "SELECT source_rel_path, source_content_hash, raw_json, is_deleted FROM file_question_info_runs"
        path_key = "source_rel_path"
    else:
        raise ValueError(f"unsupported family: {family}")

    active_hashes: dict[str, str] = {}
    active_raw: dict[str, str] = {}
    deleted: set[str] = set()
    for row in conn.execute(sql).fetchall():
        path = str(row[path_key])
        if int(row["is_deleted"]) != 0:
            deleted.add(path)
            continue
        active_hashes[path] = str(row["source_content_hash"])
        active_raw[path] = str(row["raw_json"])
    return active_hashes, active_raw, deleted


def audit_family(*, context_root: Path, family: str, conn) -> FamilyAudit:
    audit = FamilyAudit(family=family)
    db_hashes, db_raw, deleted = _fetch_db_rows(conn, family)
    audit.db_paths = set(db_hashes)
    audit.db_hashes = db_hashes
    audit.db_raw_json = db_raw
    audit.db_deleted_paths = deleted

    for path in _iter_json_files(context_root, family):
        audit.json_paths.add(_rel(context_root, path))

    json_only_set = audit.json_paths - audit.db_paths
    db_only_set = audit.db_paths - audit.json_paths
    both_set = audit.json_paths & audit.db_paths

    audit.json_only = sorted(json_only_set)
    audit.db_only = sorted(db_only_set)

    for rel_path in sorted(both_set):
        disk_path = context_root / rel_path
        try:
            disk_text = disk_path.read_text(encoding="utf-8")
        except OSError:
            audit.both_json_unreadable.append(rel_path)
            continue

        disk_hash = _sha256_text(disk_text)
        db_hash = audit.db_hashes[rel_path]
        if disk_hash == db_hash:
            audit.both_hash_synced.append(rel_path)
            continue

        disk_obj = _load_json_object(disk_text)
        db_obj = _load_json_object(audit.db_raw_json[rel_path])
        if disk_obj is not None and db_obj is not None and disk_obj == db_obj:
            audit.both_hash_drift_semantic_synced.append(rel_path)
        elif disk_obj is None:
            audit.both_json_unreadable.append(rel_path)
        else:
            audit.both_hash_drift_semantic_drift.append(rel_path)

    return audit


def build_report(*, db_path: Path, context_root: Path, sample_limit: int = 10) -> dict[str, Any]:
    conn = get_connection(db_path)
    try:
        families = ("marking_result", "marking_amendment", "student_review_state", "file_question_info")
        by_family = {
            family: audit_family(context_root=context_root, family=family, conn=conn).to_dict(
                sample_limit=sample_limit
            )
            for family in families
        }
    finally:
        conn.close()

    totals = {
        "json_only": sum(by_family[f]["counts"]["json_only"] for f in by_family),
        "db_only": sum(by_family[f]["counts"]["db_only"] for f in by_family),
        "both": sum(by_family[f]["counts"]["both"] for f in by_family),
        "both_hash_synced": sum(by_family[f]["counts"]["both_hash_synced"] for f in by_family),
        "both_reformat_only_drift": sum(by_family[f]["counts"]["both_reformat_only_drift"] for f in by_family),
        "both_semantic_drift": sum(by_family[f]["counts"]["both_semantic_drift"] for f in by_family),
        "both_json_unreadable": sum(by_family[f]["counts"]["both_json_unreadable"] for f in by_family),
    }

    return {
        "db_path": str(db_path.resolve()),
        "context_root": str(context_root.resolve()),
        "totals": totals,
        "families": by_family,
    }


def _print_human(report: dict[str, Any]) -> None:
    print(f"DB: {report['db_path']}")
    print(f"Context: {report['context_root']}")
    print()
    print("=== Totals (all families) ===")
    t = report["totals"]
    print(f"  json_only:              {t['json_only']}")
    print(f"  db_only:                {t['db_only']}")
    print(f"  both:                   {t['both']}")
    print(f"    hash_synced:          {t['both_hash_synced']}")
    print(f"    reformat_only_drift:  {t['both_reformat_only_drift']}")
    print(f"    semantic_drift:       {t['both_semantic_drift']}")
    print(f"    json_unreadable:      {t['both_json_unreadable']}")

    for family, block in report["families"].items():
        c = block["counts"]
        print()
        print(f"=== {family} ===")
        print(f"  JSON on disk:           {c['json_on_disk']}")
        print(f"  DB active rows:         {c['db_active_rows']}")
        print(f"  DB deleted rows:        {c['db_deleted_rows']}")
        print(f"  json_only:              {c['json_only']}")
        print(f"  db_only:                {c['db_only']}")
        print(f"  both:                   {c['both']}")
        print(f"    hash_synced:          {c['both_hash_synced']}")
        print(f"    reformat_only_drift:  {c['both_reformat_only_drift']}")
        print(f"    semantic_drift:       {c['both_semantic_drift']}")
        print(f"    json_unreadable:      {c['both_json_unreadable']}")
        for key, rows in block["samples"].items():
            if not rows:
                continue
            print(f"  sample {key}:")
            for row in rows:
                print(f"    - {row}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Venn audit: context JSON files vs study_buddy.db rows (path + hash sync)."
    )
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--context-root", type=Path, default=None)
    parser.add_argument("--sample-limit", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="Emit full report as JSON.")
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit 1 if any both-side semantic drift, json_only, or db_only entries exist.",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path or default_db_path()).expanduser().resolve()
    context_root = Path(args.context_root or default_context_root()).expanduser().resolve()
    report = build_report(db_path=db_path, context_root=context_root, sample_limit=args.sample_limit)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)

    if args.fail_on_drift:
        t = report["totals"]
        if t["json_only"] or t["db_only"] or t["both_semantic_drift"] or t["both_json_unreadable"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
