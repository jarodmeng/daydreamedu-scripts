"""Classify missing marking_asset paths into actionable buckets.

This is a read-only heuristic triage helper for `marking_artifacts.marking_asset`
rows whose on-disk bundle folder is missing.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from ai_study_buddy.learning_db.core.connection import default_context_root, default_db_path, get_connection


_TS_RE = re.compile(r"__(\d{8}_\d{6})$")


def _parse_ts(stem_or_dirname: str) -> str | None:
    m = _TS_RE.search(stem_or_dirname)
    return m.group(1) if m else None


def _sample(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return rows[: max(limit, 0)]


def build_report(*, db_path: Path, context_root: Path, sample_limit: int = 5) -> dict[str, Any]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT artifact_id, artifact_path, marking_asset, created_at, attempt_file_id, template_file_id
            FROM marking_artifacts
            WHERE is_deleted = 0 AND marking_asset IS NOT NULL AND TRIM(marking_asset) != ''
            ORDER BY created_at DESC, artifact_id ASC
            """
        ).fetchall()

        probable_rename_drift: list[dict[str, Any]] = []
        likely_legacy_or_pruned_assets: list[dict[str, Any]] = []
        hard_inconsistency: list[dict[str, Any]] = []

        for r in rows:
            artifact_id = str(r["artifact_id"])
            artifact_path = str(r["artifact_path"])
            marking_asset_rel = str(r["marking_asset"])
            asset_abs = (context_root / marking_asset_rel).resolve(strict=False)
            artifact_abs = (context_root / artifact_path).resolve(strict=False)

            if asset_abs.exists():
                continue

            # canonical JSON missing + asset missing is a harder inconsistency
            if not artifact_abs.exists():
                hard_inconsistency.append(
                    {
                        "artifact_id": artifact_id,
                        "artifact_path": artifact_path,
                        "marking_asset": marking_asset_rel,
                        "reason": "artifact_json_and_asset_both_missing",
                    }
                )
                continue

            parent = asset_abs.parent
            ts = _parse_ts(asset_abs.name)
            sibling_candidates: list[str] = []
            if parent.exists() and parent.is_dir() and ts:
                for p in sorted(parent.iterdir()):
                    if not p.is_dir():
                        continue
                    if _parse_ts(p.name) == ts:
                        sibling_candidates.append(p.name)

            if sibling_candidates:
                probable_rename_drift.append(
                    {
                        "artifact_id": artifact_id,
                        "artifact_path": artifact_path,
                        "marking_asset": marking_asset_rel,
                        "reason": "missing_asset_but_same_timestamp_sibling_exists",
                        "sibling_asset_dirs": sibling_candidates[:8],
                        "attempt_file_id": r["attempt_file_id"],
                        "template_file_id": r["template_file_id"],
                    }
                )
            else:
                likely_legacy_or_pruned_assets.append(
                    {
                        "artifact_id": artifact_id,
                        "artifact_path": artifact_path,
                        "marking_asset": marking_asset_rel,
                        "reason": "asset_missing_without_timestamp_sibling",
                        "attempt_file_id": r["attempt_file_id"],
                        "template_file_id": r["template_file_id"],
                    }
                )

        counts = {
            "probable_rename_drift": len(probable_rename_drift),
            "likely_legacy_or_pruned_assets": len(likely_legacy_or_pruned_assets),
            "hard_inconsistency": len(hard_inconsistency),
        }
        return {
            "db_path": str(db_path.resolve()),
            "context_root": str(context_root.resolve()),
            "total_missing_marking_assets": sum(counts.values()),
            "counts": counts,
            "samples": {
                "probable_rename_drift": _sample(probable_rename_drift, sample_limit),
                "likely_legacy_or_pruned_assets": _sample(likely_legacy_or_pruned_assets, sample_limit),
                "hard_inconsistency": _sample(hard_inconsistency, sample_limit),
            },
        }
    finally:
        conn.close()


def _print_human(report: dict[str, Any]) -> None:
    print(f"DB: {report['db_path']}")
    print(f"Context: {report['context_root']}")
    print(f"Total missing marking_asset rows: {report['total_missing_marking_assets']}")
    print("\nCounts:")
    for k, v in report["counts"].items():
        print(f"- {k}: {v}")
    print("\nSamples:")
    for k, rows in report["samples"].items():
        if not rows:
            continue
        print(f"- {k}:")
        for row in rows:
            print("  - " + ", ".join(f"{rk}={rv}" for rk, rv in row.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description="Triage missing marking_asset rows into drift/pruned buckets.")
    parser.add_argument("--db-path", type=Path, default=None, help="Path to study_buddy.db.")
    parser.add_argument("--context-root", type=Path, default=None, help="Path to context root.")
    parser.add_argument("--sample-limit", type=int, default=5, help="Sample rows per bucket.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    db_path = args.db_path or default_db_path()
    context_root = args.context_root or default_context_root()
    report = build_report(
        db_path=Path(db_path).expanduser().resolve(),
        context_root=Path(context_root).expanduser().resolve(),
        sample_limit=args.sample_limit,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
