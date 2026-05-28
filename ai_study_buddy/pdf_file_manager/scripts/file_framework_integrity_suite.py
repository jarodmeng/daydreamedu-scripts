#!/usr/bin/env python3
"""Run the L4 file-framework integrity suite as one health check.

Checks included:
1. DaydreamEdu leaf-registry health
2. GoodNotes leaf-registry health (default excludes Not completed)
3. Completion-template link gaps (default excludes activity/note)
4. Registry integrity audit

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

