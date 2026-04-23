from __future__ import annotations

from pathlib import Path, PurePosixPath


def marking_asset_rel_path_from_artifact_path(
    artifact_json_path: str | Path,
    *,
    context_root: str | Path,
) -> str | None:
    root = Path(context_root).resolve()
    artifact_path = Path(artifact_json_path).resolve()
    try:
        rel = artifact_path.relative_to(root)
    except ValueError:
        return None

    parts = rel.parts
    if len(parts) < 4 or parts[0] != "marking_results":
        return None

    student_slug = parts[1]
    subject_context = parts[2]
    artifact_stem = artifact_path.stem
    return f"marking_assets/{student_slug}/{subject_context}/{artifact_stem}"


def _is_normalized_relative_posix_path(path_text: str) -> bool:
    if not path_text.strip():
        return False
    if path_text.startswith("/") or "//" in path_text:
        return False
    pure = PurePosixPath(path_text)
    if pure.is_absolute():
        return False
    if any(part in ("", ".", "..") for part in pure.parts):
        return False
    if len(pure.parts) == 0:
        return False
    return str(pure) == path_text


def bundle_root_from_context(context: dict, *, context_root: str | Path) -> Path | None:
    marking_asset = context.get("marking_asset")
    if not isinstance(marking_asset, str):
        return None
    if not _is_normalized_relative_posix_path(marking_asset):
        return None
    if not marking_asset.startswith("marking_assets/"):
        return None

    root = Path(context_root).resolve()
    bundle_root = (root / Path(marking_asset)).resolve()
    asset_root = (root / "marking_assets").resolve()
    try:
        bundle_root.relative_to(asset_root)
    except ValueError:
        return None
    return bundle_root
