from __future__ import annotations

import argparse
from pathlib import Path

from ai_study_buddy.marking.core.artifact_cleanup import (
    MarkingRunArtifactRemovalError,
    remove_marking_run_artifacts,
)


def run(
    artifact_json_path: str | Path,
    *,
    context_root: str | Path = "ai_study_buddy/context",
    dry_run: bool = False,
    best_effort: bool = False,
) -> int:
    mode = "best_effort" if best_effort else "strict"
    try:
        result = remove_marking_run_artifacts(
            artifact_json_path,
            context_root=context_root,
            dry_run=dry_run,
            mode=mode,
        )
    except (MarkingRunArtifactRemovalError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Artifact JSON: {result.requested.marking_result_json}")
    _print_status("marking_result_json", result.requested.marking_result_json, result)
    _print_status("learning_report_md", result.requested.learning_report_md, result)
    if result.requested.marking_asset_bundle is not None:
        _print_status("marking_asset_bundle", result.requested.marking_asset_bundle, result)

    print(f"Deleted: {len(result.deleted_paths)}")
    print(f"Skipped (missing): {len(result.skipped_missing_paths)}")
    return 0


def _print_status(label: str, path: Path, result) -> None:
    if path in result.deleted_paths:
        status = "deleted"
    elif path in result.skipped_missing_paths:
        status = "skipped"
    elif path in result.requested.missing_paths:
        status = "missing"
    elif path in result.requested.existing_paths:
        status = "exists"
    else:
        status = "unknown"
    print(f"- {label}: {status}: {path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove one marking run's JSON/report/bundle artifacts.")
    parser.add_argument("artifact_json_path", help="Path to marking_result JSON")
    parser.add_argument(
        "--context-root",
        default="ai_study_buddy/context",
        help="Context root containing marking_results/, learning_reports/, and marking_assets/",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only; do not delete files")
    parser.add_argument(
        "--best-effort",
        action="store_true",
        help="Skip missing artifacts (strict mode is default)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    raise SystemExit(
        run(
            args.artifact_json_path,
            context_root=args.context_root,
            dry_run=args.dry_run,
            best_effort=args.best_effort,
        )
    )
