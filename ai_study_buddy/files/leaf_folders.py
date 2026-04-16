from __future__ import annotations

import os
from pathlib import Path


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


def _goodnotes_excluded_leaf_folders(root: Path, include_suffixes: set[str]) -> set[Path]:
    all_leaves = list_leaf_folders_under_root(root, include_suffixes=include_suffixes)
    excluded: set[Path] = set()
    root_resolved = root.expanduser().resolve()

    for leaf in all_leaves:
        rel_parts = leaf.relative_to(root_resolved).parts
        if leaf == root_resolved:
            excluded.add(leaf)
            continue
        if rel_parts and rel_parts[0].casefold() == "coding":
            excluded.add(leaf)
            continue
        if any(part.casefold() == "not completed" for part in rel_parts):
            excluded.add(leaf)
    return excluded


def _daydreamedu_excluded_leaf_folders(root: Path, include_suffixes: set[str]) -> set[Path]:
    all_leaves = list_leaf_folders_under_root(root, include_suffixes=include_suffixes)
    root_resolved = root.expanduser().resolve()
    excluded: set[Path] = set()

    for leaf in all_leaves:
        if leaf == root_resolved or leaf.name.casefold() in {"note", "notes"}:
            excluded.add(leaf)
    return excluded


def list_goodnotes_leaf_folders_under_root(root: Path, *, include_suffixes: set[str] | None = None) -> list[Path]:
    suffixes = include_suffixes or {".pdf"}
    excluded = _goodnotes_excluded_leaf_folders(root, suffixes)
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
