from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_study_buddy.marking.assets.paths import bundle_root_from_context
from ai_study_buddy.marking.assets.validate import validate_marking_asset_bundle


def run(
    artifact_json_path: str | Path,
    *,
    context_root: str | Path = "ai_study_buddy/context",
    strict: bool = False,
) -> int:
    artifact_path = Path(artifact_json_path)
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    context = payload.get("context")
    if not isinstance(context, dict):
        print("Invalid artifact JSON: missing object context")
        return 2

    bundle_root = bundle_root_from_context(context, context_root=context_root)
    if bundle_root is None:
        print("Artifact has no valid context.marking_asset bundle path")
        return 2

    report = validate_marking_asset_bundle(
        bundle_root=bundle_root,
        artifact_dict=payload,
        strict=strict,
    )
    for issue in report.issues:
        path_suffix = f" [{issue.path}]" if issue.path else ""
        print(f"{issue.severity.upper()}: {issue.code}: {issue.message}{path_suffix}")
    if report.ok:
        print("Bundle validation passed")
        return 0
    print(f"Bundle validation failed with {len(report.errors)} error(s)")
    return 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a marking asset bundle for one artifact JSON.")
    parser.add_argument("artifact_json_path", help="Path to marking_result JSON")
    parser.add_argument(
        "--context-root",
        default="ai_study_buddy/context",
        help="Context root containing marking_assets/ and marking_results/",
    )
    parser.add_argument("--strict", action="store_true", help="Enable strict checks")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    raise SystemExit(
        run(
            args.artifact_json_path,
            context_root=args.context_root,
            strict=args.strict,
        )
    )
