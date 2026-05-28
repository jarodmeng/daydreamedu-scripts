#!/usr/bin/env python3
"""Run the L4 file-framework integrity suite as one health check.

Checks included:
1. DaydreamEdu leaf-registry health
2. GoodNotes leaf-registry health (default excludes Not completed)
3. Completion-template link gaps (default excludes activity/note)
4. Registry integrity audit
5. Marking context DB drift (on-disk vs study_buddy.db)

Exit codes:
- 0: all checks pass
- 1: at least one check fails
- 2: registry DB missing
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ai_study_buddy.files.pdf_registry_paths import (
    RegistryPathIndex,
    leaf_folder_registry_status,
    leaf_registry_statuses_for_included_leaves,
    partition_daydreamedu_leaf_folders,
    partition_goodnotes_leaf_folders,
    registration_buckets,
    suspicious_all_leaves_marked_non_scan_root,
)
from ai_study_buddy.files.roots import resolve_daydreamedu_root, resolve_goodnotes_root
from ai_study_buddy.learning_db.cli.context_db_drift_report import (
    build_report as build_context_db_drift_report,
)
from ai_study_buddy.pdf_file_manager import PdfFileManager
from ai_study_buddy.pdf_file_manager.scripts.completion_template_link_gap_report import (
    build_report as build_completion_gap_report,
)
from ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity import (
    build_report as build_registry_integrity_report,
    default_db_path,
)


def _leaf_report(
    *,
    label: str,
    root: Path | None,
    index: RegistryPathIndex,
    partition_fn,
) -> dict[str, Any]:
    if root is None:
        return {
            "label": label,
            "status": "fail",
            "reason": "root_not_resolved",
            "root": None,
        }

    included_leaves, excluded_leaves = partition_fn(root)
    statuses = leaf_registry_statuses_for_included_leaves(included_leaves, root, index)
    buckets = registration_buckets(statuses)
    suspicious = suspicious_all_leaves_marked_non_scan_root(index, statuses)
    excluded_statuses = [leaf_folder_registry_status(p, root, index) for p in excluded_leaves]

    # Pass criteria requested in command specs:
    # All included leaves must be scan-root + all direct PDFs registered.
    pass_ok = (
        buckets.scan_root_some_unregistered == 0
        and buckets.non_scan_root_all_registered == 0
        and buckets.non_scan_root_some_unregistered == 0
        and not suspicious
    )

    return {
        "label": label,
        "status": "pass" if pass_ok else "fail",
        "reason": "ok" if pass_ok else "bucket_or_scanroot_mismatch",
        "root": str(root.resolve()),
        "leaf_folders_total": len(statuses),
        "excluded_leaf_folders_total": len(excluded_statuses),
        "scan_root_yes": sum(1 for s in statuses if s.is_scan_root),
        "scan_root_no": sum(1 for s in statuses if not s.is_scan_root),
        "registration_breakdown": {
            "scan_root_all_registered": buckets.scan_root_all_registered,
            "scan_root_some_unregistered": buckets.scan_root_some_unregistered,
            "non_scan_root_all_registered": buckets.non_scan_root_all_registered,
            "non_scan_root_some_unregistered": buckets.non_scan_root_some_unregistered,
        },
        "suspicious_all_non_scan_root": suspicious,
    }


def build_suite_report(*, db_path: Path, include_activity_note: bool) -> dict[str, Any]:
    pfm = PdfFileManager(db_path=str(db_path))
    index = RegistryPathIndex.from_pdf_file_manager(pfm)

    d_root = resolve_daydreamedu_root()
    g_root = resolve_goodnotes_root()

    daydreamedu_leaf = _leaf_report(
        label="daydreamedu_leaf_registry",
        root=d_root,
        index=index,
        partition_fn=partition_daydreamedu_leaf_folders,
    )
    goodnotes_leaf = _leaf_report(
        label="goodnotes_leaf_registry",
        root=g_root,
        index=index,
        partition_fn=partition_goodnotes_leaf_folders,
    )

    completion_gap = build_completion_gap_report(
        db_path,
        include_activity_note=include_activity_note,
    )
    completion_gap_pass = completion_gap["summary"]["without_template"] == 0

    registry_integrity = build_registry_integrity_report(pfm)
    registry_integrity_pass = not any(registry_integrity["summary"].values())
    try:
        context_db_drift = build_context_db_drift_report(
            db_path=(db_path.parent / "study_buddy.db"),
            context_root=Path("ai_study_buddy/context").resolve(),
            sample_limit=10,
        )
        context_db_drift_pass = (
            context_db_drift["counts"].get("marking_artifacts_missing_artifact_path", 0) == 0
            and context_db_drift["counts"].get("marking_artifacts_missing_marking_asset", 0) == 0
        )
        context_db_drift_reason = (
            "ok" if context_db_drift_pass else "marking_artifact_or_asset_path_drift_present"
        )
    except Exception as exc:
        context_db_drift = {
            "db_path": str((db_path.parent / "study_buddy.db").resolve()),
            "context_root": str(Path("ai_study_buddy/context").resolve()),
            "counts": {},
            "samples": {},
        }
        context_db_drift_pass = False
        context_db_drift_reason = f"drift_report_error:{type(exc).__name__}"

    checks = {
        "daydreamedu_leaf_registry": daydreamedu_leaf,
        "goodnotes_leaf_registry": goodnotes_leaf,
        "completion_template_link_gap": {
            "status": "pass" if completion_gap_pass else "fail",
            "reason": "ok" if completion_gap_pass else "missing_template_links",
            "registry_db": completion_gap["registry_db"],
            "filters": completion_gap["filters"],
            "summary": completion_gap["summary"],
        },
        "registry_integrity_audit": {
            "status": "pass" if registry_integrity_pass else "fail",
            "reason": "ok" if registry_integrity_pass else "integrity_findings_present",
            "db_path": registry_integrity["db_path"],
            "summary": registry_integrity["summary"],
        },
        "marking_context_db_drift": {
            "status": "pass" if context_db_drift_pass else "fail",
            "reason": context_db_drift_reason,
            "db_path": context_db_drift["db_path"],
            "context_root": context_db_drift["context_root"],
            "counts": context_db_drift["counts"],
            "samples": {
                "marking_artifacts_missing_artifact_path": context_db_drift["samples"].get(
                    "marking_artifacts_missing_artifact_path",
                    [],
                ),
                "marking_artifacts_missing_marking_asset": context_db_drift["samples"].get(
                    "marking_artifacts_missing_marking_asset",
                    [],
                ),
            },
        },
    }

    overall_pass = all(c["status"] == "pass" for c in checks.values())
    return {
        "overall_status": "pass" if overall_pass else "fail",
        "registry_db": str(db_path.resolve()),
        "checks": checks,
    }


def _print_human(report: dict[str, Any]) -> None:
    print(f"Registry DB: {report['registry_db']}")
    print(f"Overall: {report['overall_status'].upper()}")
    print()

    for key in (
        "daydreamedu_leaf_registry",
        "goodnotes_leaf_registry",
        "completion_template_link_gap",
        "registry_integrity_audit",
        "marking_context_db_drift",
    ):
        check = report["checks"][key]
        print(f"- {key}: {check['status'].upper()} ({check['reason']})")
        if key in ("daydreamedu_leaf_registry", "goodnotes_leaf_registry") and check.get("root"):
            breakdown = check["registration_breakdown"]
            print(f"  root={check['root']}")
            print(
                "  buckets: "
                f"scan_root_all_registered={breakdown['scan_root_all_registered']}, "
                f"scan_root_some_unregistered={breakdown['scan_root_some_unregistered']}, "
                f"non_scan_root_all_registered={breakdown['non_scan_root_all_registered']}, "
                f"non_scan_root_some_unregistered={breakdown['non_scan_root_some_unregistered']}"
            )
        if key == "completion_template_link_gap":
            s = check["summary"]
            print(
                "  completion_mains="
                f"{s['completion_mains']}, with_template={s['with_template']}, "
                f"without_template={s['without_template']}, gap_buckets={s['gap_buckets']}"
            )
        if key == "registry_integrity_audit":
            nonzero = {k: v for k, v in check["summary"].items() if v}
            if nonzero:
                summary_str = ", ".join(f"{k}={v}" for k, v in nonzero.items())
            else:
                summary_str = "all checks zero"
            print(f"  {summary_str}")
        if key == "marking_context_db_drift":
            counts = check["counts"]
            print(
                "  "
                f"marking_artifacts_missing_artifact_path={counts.get('marking_artifacts_missing_artifact_path', 0)}, "
                f"marking_artifacts_missing_marking_asset={counts.get('marking_artifacts_missing_marking_asset', 0)}"
            )
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run L4 file-framework integrity test suite.")
    parser.add_argument("--db", default=str(default_db_path()), help="Path to pdf_registry.db")
    parser.add_argument(
        "--include-activity-note",
        action="store_true",
        help="Include activity/note in completion-template gap check.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"error: registry database not found: {db_path}", flush=True)
        return 2

    report = build_suite_report(
        db_path=db_path,
        include_activity_note=args.include_activity_note,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

