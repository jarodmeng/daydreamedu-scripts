from __future__ import annotations

import os
import re
from pathlib import Path

# GoodNotes excluded segment: lowercase x, uppercase second letter (see L4 framework + leaf-registry-report.md).
_GOODNOTES_X_PREFIX_SEGMENT_RE = re.compile(r"^x[A-Z].*$")


def _normalize_suffixes(include_suffixes: set[str]) -> set[str]:
    normalized: set[str] = set()
    for suffix in include_suffixes:
        s = suffix.strip().lower()
        if not s:
            continue
        if not s.startswith("."):
            s = f".{s}"
        normalized.add(s)
    return normalized


def list_leaf_folders_under_root(
    root: Path,
    *,
    include_suffixes: set[str],
    excluded_leaf_folders: set[Path] | None = None,
) -> list[Path]:
    """List leaf folders under root that contain matching direct files.

    A folder is a leaf if it contains at least one direct file whose suffix
    matches include_suffixes. Returned paths are absolute and sorted.
    """
    resolved_root = root.expanduser().resolve()
    if not resolved_root.is_dir():
        return []

    suffixes = _normalize_suffixes(include_suffixes)
    if not suffixes:
        return []

    excluded = {p.expanduser().resolve() for p in (excluded_leaf_folders or set())}
    leaves: list[Path] = []

    for dirpath, _, filenames in os.walk(resolved_root):
        folder = Path(dirpath).resolve()
        has_match = any(Path(name).suffix.lower() in suffixes for name in filenames)
        if not has_match:
            continue
        if folder in excluded:
            continue
        leaves.append(folder)

    return sorted(leaves)


def _goodnotes_segment_x_prefix_excluded(segment: str) -> bool:
    return bool(_GOODNOTES_X_PREFIX_SEGMENT_RE.fullmatch(segment))


def _rel_segments_normalized(rel: str) -> tuple[str, ...]:
    rel = (rel or "").strip().replace("\\", "/")
    while "//" in rel:
        rel = rel.replace("//", "/")
    rel = rel.strip("/")
    if not rel:
        return ()
    return tuple(seg for seg in rel.split("/") if seg and seg != ".")


def is_goodnotes_excluded_relative_path(rel: str, *, exclude_not_completed: bool = True) -> bool:
    """True when *rel* should be omitted under ``GOODNOTES_ROOT`` (POSIX segments).

    Always excludes segments matching ``^x[A-Z].*$``. Excludes ``Not completed`` segments
    when *exclude_not_completed* is True (default); pass False so WIP *Not completed*
    trees stay visible (e.g. ``root_pdf_browser``). Empty *rel* is never excluded."""
    for part in _rel_segments_normalized(rel):
        if _goodnotes_segment_x_prefix_excluded(part):
            return True
        if exclude_not_completed and part.casefold() == "not completed":
            return True
    return False


def _goodnotes_excluded_leaf_folders(
    root: Path,
    include_suffixes: set[str],
    *,
    exclude_not_completed: bool,
) -> set[Path]:
    # Root + x-prefix: same as L4 / goodnotes-leaf-registry-report structural rules.
    # "Not completed" is optional (registry/coverage vs browse / view WIP completions).
    all_leaves = list_leaf_folders_under_root(root, include_suffixes=include_suffixes)
    excluded: set[Path] = set()
    root_resolved = root.expanduser().resolve()

    for leaf in all_leaves:
        rel_parts = leaf.relative_to(root_resolved).parts
        if leaf == root_resolved:
            excluded.add(leaf)
            continue
        if any(_goodnotes_segment_x_prefix_excluded(part) for part in rel_parts):
            excluded.add(leaf)
            continue
        if exclude_not_completed and any(part.casefold() == "not completed" for part in rel_parts):
            excluded.add(leaf)
    return excluded


def _daydreamedu_excluded_leaf_folders(root: Path, include_suffixes: set[str]) -> set[Path]:
    # Parity: `.cursor/commands/daydreamedu-leaf-registry-report.md`.
    all_leaves = list_leaf_folders_under_root(root, include_suffixes=include_suffixes)
    root_resolved = root.expanduser().resolve()
    excluded: set[Path] = set()

    for leaf in all_leaves:
        if leaf == root_resolved:
            excluded.add(leaf)
    return excluded


def list_goodnotes_leaf_folders_under_root(
    root: Path,
    *,
    include_suffixes: set[str] | None = None,
    exclude_not_completed: bool = True,
) -> list[Path]:
    """List GoodNotes leaf folders (default *exclude_not_completed* matches leaf-registry WIP policy)."""
    suffixes = include_suffixes or {".pdf"}
    excluded = _goodnotes_excluded_leaf_folders(
        root, suffixes, exclude_not_completed=exclude_not_completed
    )
    return list_leaf_folders_under_root(
        root,
        include_suffixes=suffixes,
        excluded_leaf_folders=excluded,
    )


def list_daydreamedu_leaf_folders_under_root(root: Path, *, include_suffixes: set[str] | None = None) -> list[Path]:
    suffixes = include_suffixes or {".pdf"}
    excluded = _daydreamedu_excluded_leaf_folders(root, suffixes)
    return list_leaf_folders_under_root(
        root,
        include_suffixes=suffixes,
        excluded_leaf_folders=excluded,
    )
