from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal

from ai_study_buddy.marking.assets.paths import bundle_root_from_context

RemovalMode = Literal["strict", "best_effort"]


class MarkingRunArtifactRemovalError(RuntimeError):
    """Raised when a marking-run artifact removal request is invalid or unsafe."""


@dataclass(frozen=True)
class MarkingRunRemovalPlan:
    marking_result_json: Path
    learning_report_md: Path
    marking_asset_bundle: Path | None
    existing_paths: tuple[Path, ...]
    missing_paths: tuple[Path, ...]


@dataclass(frozen=True)
class MarkingRunRemovalResult:
    requested: MarkingRunRemovalPlan
    deleted_paths: tuple[Path, ...]
    skipped_missing_paths: tuple[Path, ...]


def remove_marking_run_artifacts(
    marking_result_json: str | Path,
    *,
    context_root: str | Path = "ai_study_buddy/context",
    dry_run: bool = False,
    mode: RemovalMode = "strict",
) -> MarkingRunRemovalResult:
    """Remove one run's JSON/report/bundle artifacts as one operation.

    ``marking_result_json`` may be absolute, or relative to ``context_root``.

    - ``strict``: fail if any expected artifact is missing.
    - ``best_effort``: skip missing artifacts but keep all path-safety checks.
    """
    if mode not in {"strict", "best_effort"}:
        raise ValueError("mode must be 'strict' or 'best_effort'")

    root = Path(context_root).resolve()
    plan = _build_removal_plan(
        marking_result_json=marking_result_json,
        context_root=root,
    )

    if mode == "strict" and plan.missing_paths:
        raise FileNotFoundError(_format_missing_paths_message(plan.missing_paths))

    if dry_run:
        skipped_missing = plan.missing_paths if mode == "best_effort" else ()
        return MarkingRunRemovalResult(
            requested=plan,
            deleted_paths=(),
            skipped_missing_paths=skipped_missing,
        )

    deleted: list[Path] = []
    skipped_missing: list[Path] = list(plan.missing_paths if mode == "best_effort" else ())

    # Delete report first, bundle second, canonical JSON last.
    ordered_targets: list[Path] = [plan.learning_report_md]
    if plan.marking_asset_bundle is not None:
        ordered_targets.append(plan.marking_asset_bundle)
    ordered_targets.append(plan.marking_result_json)

    for target in ordered_targets:
        if not target.exists():
            if mode == "strict":
                raise FileNotFoundError(f"Expected artifact missing during delete: {target}")
            skipped_missing.append(target)
            continue

        if plan.marking_asset_bundle is not None and target == plan.marking_asset_bundle:
            _delete_directory_tree(target)
        else:
            _delete_file_target(target)
        deleted.append(target)

    return MarkingRunRemovalResult(
        requested=plan,
        deleted_paths=tuple(deleted),
        skipped_missing_paths=tuple(skipped_missing),
    )


def _build_removal_plan(
    *,
    marking_result_json: str | Path,
    context_root: Path,
) -> MarkingRunRemovalPlan:
    json_path = _resolve_input_path(marking_result_json=marking_result_json, context_root=context_root)
    results_root = (context_root / "marking_results").resolve()
    learning_reports_root = (context_root / "learning_reports").resolve()

    _assert_within_root(json_path, results_root, label="marking result")
    if json_path.suffix.lower() != ".json":
        raise MarkingRunArtifactRemovalError(
            f"marking_result_json must point to a .json file under {results_root}: {json_path}"
        )
    if not json_path.exists():
        raise FileNotFoundError(f"Canonical marking result JSON not found: {json_path}")
    if not json_path.is_file():
        raise MarkingRunArtifactRemovalError(f"marking_result_json is not a file: {json_path}")

    payload = _load_artifact_payload(json_path)

    relative_parent = json_path.parent.relative_to(results_root)
    learning_report_path = (
        learning_reports_root
        / relative_parent
        / f"{json_path.stem} - Marking Report.md"
    ).resolve()
    _assert_within_root(learning_report_path, learning_reports_root, label="learning report")

    bundle_path = _resolve_bundle_path(payload=payload, context_root=context_root)

    expected_paths: list[Path] = [json_path, learning_report_path]
    if bundle_path is not None:
        expected_paths.append(bundle_path)

    existing_paths = tuple(path for path in expected_paths if path.exists())
    missing_paths = tuple(path for path in expected_paths if not path.exists())

    return MarkingRunRemovalPlan(
        marking_result_json=json_path,
        learning_report_md=learning_report_path,
        marking_asset_bundle=bundle_path,
        existing_paths=existing_paths,
        missing_paths=missing_paths,
    )


def _resolve_input_path(*, marking_result_json: str | Path, context_root: Path) -> Path:
    raw = Path(marking_result_json).expanduser()
    if raw.is_absolute():
        return raw.resolve(strict=False)
    return (context_root / raw).resolve(strict=False)


def _resolve_bundle_path(*, payload: dict, context_root: Path) -> Path | None:
    context = payload.get("context")
    if not isinstance(context, dict):
        raise MarkingRunArtifactRemovalError("Artifact JSON is missing object 'context'")

    marking_asset = context.get("marking_asset")
    if marking_asset is None:
        return None
    if not isinstance(marking_asset, str) or not marking_asset.strip():
        raise MarkingRunArtifactRemovalError(
            "Artifact context.marking_asset must be null or a non-empty string"
        )

    bundle_root = bundle_root_from_context(context, context_root=context_root)
    if bundle_root is None:
        raise MarkingRunArtifactRemovalError(
            "Artifact context.marking_asset is invalid or unsafe"
        )

    assets_root = (context_root / "marking_assets").resolve()
    _assert_within_root(bundle_root, assets_root, label="marking asset bundle")
    return bundle_root


def _load_artifact_payload(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MarkingRunArtifactRemovalError(f"Artifact JSON is malformed: {path}") from exc
    if not isinstance(payload, dict):
        raise MarkingRunArtifactRemovalError(f"Artifact JSON root must be an object: {path}")
    return payload


def _assert_within_root(path: Path, root: Path, *, label: str) -> None:
    candidate = path.resolve(strict=False)
    anchor = root.resolve(strict=False)
    try:
        candidate.relative_to(anchor)
    except ValueError as exc:
        raise MarkingRunArtifactRemovalError(
            f"Unsafe {label} path outside allowed root ({anchor}): {candidate}"
        ) from exc


def _delete_file_target(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        raise MarkingRunArtifactRemovalError(f"Expected file path but got directory: {path}")
    path.unlink()


def _delete_directory_tree(path: Path) -> None:
    if path.is_symlink():
        raise MarkingRunArtifactRemovalError(f"Refusing to delete symlink bundle root: {path}")
    if not path.is_dir():
        raise MarkingRunArtifactRemovalError(f"Expected bundle directory but got non-directory: {path}")

    for child in path.iterdir():
        if child.is_symlink():
            child.unlink()
            continue
        if child.is_dir():
            _delete_directory_tree(child)
            continue
        child.unlink()
    path.rmdir()


def _format_missing_paths_message(paths: tuple[Path, ...]) -> str:
    formatted = ", ".join(str(path) for path in paths)
    return f"Missing expected artifact(s): {formatted}"
