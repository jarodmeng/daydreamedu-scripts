"""Correlate on-disk leaf folders with ``PdfFileManager`` / ``pdf_registry.db`` path rows.

This module is the **composition layer** between :mod:`ai_study_buddy.files` (roots + leaf
lists) and :class:`ai_study_buddy.pdf_file_manager.pdf_file_manager.PdfFileManager`.
It implements the same path-string rules as
``.cursor/commands/daydreamedu-leaf-registry-report`` and
``.cursor/commands/goodnotes-leaf-registry-report``: resolved paths as strings,
never mixing ``Path`` instances with ``set[str]`` membership tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, Sequence

from pathlib import Path

from ai_study_buddy.files.leaf_folders import (
    list_daydreamedu_leaf_folders_under_root,
    list_goodnotes_leaf_folders_under_root,
    list_leaf_folders_under_root,
)

if TYPE_CHECKING:
    from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def resolved_path_from_registry_row(row: object) -> str:
    """Return the resolved filesystem path string for a registry or scan-root row.

    Supports row objects with a ``path`` attribute and ``dict`` rows with a ``"path"``
    key (defensive / forward-compatible). Used when building sets for membership tests.
    """
    raw_path = getattr(row, "path", None)
    if raw_path is None and isinstance(row, dict):
        raw_path = row.get("path")
    if not raw_path:
        raise ValueError(f"Row has no path attribute/key: {type(row)!r}")
    return str(Path(raw_path).resolve())


@dataclass(frozen=True)
class RegistryPathIndex:
    """Resolved path-string sets from a ``PdfFileManager`` snapshot (no ad hoc SQL)."""

    registered_resolved_paths: frozenset[str]
    scan_root_resolved_paths: frozenset[str]
    pdf_files_row_count: int
    scan_roots_row_count: int
    file_by_resolved_path: dict[str, object]

    @classmethod
    def from_pdf_file_manager(cls, pfm: PdfFileManager) -> RegistryPathIndex:
        files = pfm.find_files()
        roots = pfm.list_scan_roots()
        file_by: dict[str, object] = {}
        for f in files:
            key = resolved_path_from_registry_row(f)
            if key in file_by:
                # Last wins; duplicate paths should not occur in a healthy registry.
                pass
            file_by[key] = f
        registered = frozenset(file_by.keys())
        scan_roots = frozenset(resolved_path_from_registry_row(r) for r in roots)
        return cls(
            registered_resolved_paths=registered,
            scan_root_resolved_paths=scan_roots,
            pdf_files_row_count=len(files),
            scan_roots_row_count=len(roots),
            file_by_resolved_path=file_by,
        )


def registry_file_for_path(
    pdf_path: Path | str,
    index: RegistryPathIndex,
) -> object | None:
    """Return the registry row object for *pdf_path*, or ``None`` if unregistered."""
    key = str(Path(pdf_path).expanduser().resolve())
    return index.file_by_resolved_path.get(key)


def registry_file_type_for_path(
    pdf_path: Path | str,
    index: RegistryPathIndex,
) -> str | None:
    """Return ``file_type`` for a registered path, or ``None`` when unregistered."""
    row = registry_file_for_path(pdf_path, index)
    if row is None:
        return None
    return getattr(row, "file_type", None)


def has_template_link(pfm: PdfFileManager, completion_file_id: str) -> bool:
    """True when a ``completed_from`` template is linked to this completion."""
    return pfm.get_template(completion_file_id) is not None


@dataclass(frozen=True)
class PdfFileRegistryStatus:
    """Atomic per-PDF registration status for one filesystem path."""

    pdf_path: Path
    basename: str
    is_pdf: bool
    is_registered: bool
    parent_is_scan_root: bool


def is_pdf_registered(pdf_path: Path, index: RegistryPathIndex) -> bool:
    """True when *pdf_path* resolves to a registered PDF file path."""
    p = pdf_path.expanduser().resolve()
    return str(p) in index.registered_resolved_paths


def pdf_file_registry_status(
    pdf_path: Path,
    index: RegistryPathIndex,
) -> PdfFileRegistryStatus:
    """Atomic one-path status for UI and per-file workflows."""
    p = pdf_path.expanduser().resolve()
    parent_str = str(p.parent)
    return PdfFileRegistryStatus(
        pdf_path=p,
        basename=p.name,
        is_pdf=p.suffix.lower() == ".pdf",
        is_registered=str(p) in index.registered_resolved_paths,
        parent_is_scan_root=parent_str in index.scan_root_resolved_paths,
    )


def direct_pdf_paths_in_leaf_folder(leaf_dir: Path) -> list[Path]:
    """Sorted list of direct ``*.pdf`` files inside *leaf_dir* (resolved). Non-directories -> []."""
    folder = leaf_dir.expanduser().resolve()
    if not folder.is_dir():
        return []
    out: list[Path] = []
    try:
        for child in folder.iterdir():
            if child.is_file() and child.suffix.lower() == ".pdf":
                out.append(child.resolve())
    except OSError:
        return []
    out.sort(key=lambda p: str(p).casefold())
    return out


def leaf_pdf_file_registry_statuses(
    leaf_dir: Path,
    index: RegistryPathIndex,
) -> list[PdfFileRegistryStatus]:
    """Atomic per-PDF statuses for direct PDFs in one leaf folder."""
    return [pdf_file_registry_status(p, index) for p in direct_pdf_paths_in_leaf_folder(leaf_dir)]


@dataclass(frozen=True)
class LeafFolderRegistryStatus:
    """Per leaf-folder view: direct PDFs vs registry membership and scan-root flag."""

    leaf_dir: Path
    rel_posix_to_sync_root: str
    direct_pdf_total: int
    unregistered_total: int
    unregistered_basenames: tuple[str, ...]
    is_scan_root: bool

    @property
    def all_direct_pdfs_registered(self) -> bool:
        return self.unregistered_total == 0


def leaf_folder_registry_status(
    leaf_dir: Path,
    sync_root: Path,
    index: RegistryPathIndex,
) -> LeafFolderRegistryStatus:
    """Classify one leaf folder: direct PDFs registered? Is this folder a scan root?"""
    root_r = sync_root.expanduser().resolve()
    leaf_r = leaf_dir.expanduser().resolve()
    rel = leaf_r.relative_to(root_r).as_posix()
    pdf_statuses = leaf_pdf_file_registry_statuses(leaf_r, index)
    unreg_names = [s.basename for s in pdf_statuses if not s.is_registered]
    unreg_names.sort(key=str.casefold)
    leaf_str = str(leaf_r)
    return LeafFolderRegistryStatus(
        leaf_dir=leaf_r,
        rel_posix_to_sync_root=rel,
        direct_pdf_total=len(pdf_statuses),
        unregistered_total=len(unreg_names),
        unregistered_basenames=tuple(unreg_names),
        is_scan_root=leaf_str in index.scan_root_resolved_paths,
    )


def partition_daydreamedu_leaf_folders(root: Path) -> tuple[list[Path], list[Path]]:
    """Included leaves (profile) vs excluded leaves (difference vs raw ``list_leaf_folders``).

    Matches ``daydreamedu-leaf-registry-report``: *included* =
    ``list_daydreamedu_leaf_folders_under_root``; *excluded* = all PDF leaves minus that set.
    """
    included = list_daydreamedu_leaf_folders_under_root(root)
    inc_set = set(included)
    all_leaves = list_leaf_folders_under_root(root, include_suffixes={".pdf"})
    excluded = sorted(set(all_leaves) - inc_set, key=lambda p: str(p).casefold())
    return included, excluded


def partition_goodnotes_leaf_folders(
    root: Path,
    *,
    exclude_not_completed: bool = True,
) -> tuple[list[Path], list[Path]]:
    """Same partition pattern as :func:`partition_daydreamedu_leaf_folders` for GoodNotes.

    *exclude_not_completed* is forwarded to ``list_goodnotes_leaf_folders_under_root``
    (default ``True`` matches the GoodNotes leaf-registry report command).
    """
    included = list_goodnotes_leaf_folders_under_root(
        root,
        exclude_not_completed=exclude_not_completed,
    )
    inc_set = set(included)
    all_leaves = list_leaf_folders_under_root(root, include_suffixes={".pdf"})
    excluded = sorted(set(all_leaves) - inc_set, key=lambda p: str(p).casefold())
    return included, excluded


def leaf_registry_statuses_for_included_leaves(
    included_leaves: Iterable[Path],
    sync_root: Path,
    index: RegistryPathIndex,
) -> list[LeafFolderRegistryStatus]:
    """Map each included leaf path to a :class:`LeafFolderRegistryStatus` (stable sort)."""
    root_r = sync_root.expanduser().resolve()
    leaves = sorted(
        (p.expanduser().resolve() for p in included_leaves),
        key=lambda p: str(p).casefold(),
    )
    return [leaf_folder_registry_status(p, root_r, index) for p in leaves]


@dataclass(frozen=True)
class ScanRootRegistrationBuckets:
    """Four-way breakdown used by the leaf-registry report commands."""

    scan_root_all_registered: int
    scan_root_some_unregistered: int
    non_scan_root_all_registered: int
    non_scan_root_some_unregistered: int


def registration_buckets(
    statuses: Sequence[LeafFolderRegistryStatus],
) -> ScanRootRegistrationBuckets:
    """Aggregate included leaf folders into the four scan-root × registration buckets."""
    a = b = c = d = 0
    for s in statuses:
        reg = s.all_direct_pdfs_registered
        if s.is_scan_root:
            if reg:
                a += 1
            else:
                b += 1
        else:
            if reg:
                c += 1
            else:
                d += 1
    return ScanRootRegistrationBuckets(
        scan_root_all_registered=a,
        scan_root_some_unregistered=b,
        non_scan_root_all_registered=c,
        non_scan_root_some_unregistered=d,
    )


def suspicious_all_leaves_marked_non_scan_root(
    index: RegistryPathIndex,
    statuses: Sequence[LeafFolderRegistryStatus],
) -> bool:
    """True when the registry lists scan roots but every *included* leaf looks non-scan-root.

    Triggers re-check for Path/str membership bugs (see leaf-registry-report hardening).
    """
    if len(index.scan_root_resolved_paths) == 0:
        return False
    if not statuses:
        return False
    return all(not s.is_scan_root for s in statuses)
