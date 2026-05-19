"""Enumerate on-disk main PDFs under leaf folders."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_study_buddy.files.leaf_folders import (
    list_daydreamedu_leaf_folders_under_root,
    list_goodnotes_leaf_folders_under_root,
)
from ai_study_buddy.files.path_facets import PathFacets, infer_path_facets
from ai_study_buddy.files.pdf_registry_paths import (
    RegistryPathIndex,
    direct_pdf_paths_in_leaf_folder,
    registry_file_for_path,
)
from ai_study_buddy.files.roots import resolve_daydreamedu_root, resolve_goodnotes_root
from ai_study_buddy.pdf_file_manager.pdf_file_manager import has_raw_pdf_prefix

_UNSET = object()

# Same default completion universe as ``completion_template_link_gap_report``.
COMPLETION_UNIVERSE_EXCLUDED_DOC_TYPES = frozenset({"activity", "note"})


def is_main_pdf_basename(name: str) -> bool:
    """True when basename is not a ``_raw_`` archive name (unregistered gap-triage heuristic)."""
    return not has_raw_pdf_prefix(name)


def is_inventory_main_pdf(
    pdf_path: Path,
    *,
    registry_index: RegistryPathIndex | None = None,
) -> bool:
    """Whether *pdf_path* belongs in the on-disk main-PDF inventory.

    When *registry_index* is provided and the path is registered, ``file_type == 'main'``
    is authoritative (matches ``completion_template_link_gap_report``). Unregistered paths
    use :func:`is_main_pdf_basename` on the basename. With no index, only the basename rule
    applies.
    """
    if registry_index is not None:
        row = registry_file_for_path(pdf_path, registry_index)
        if row is not None:
            return getattr(row, "file_type", None) == "main"
    return is_main_pdf_basename(pdf_path.name)


def list_main_pdfs_in_leaf_folder(
    leaf_dir: Path,
    *,
    registry_index: RegistryPathIndex | None = None,
) -> list[Path]:
    """Sorted resolved paths of direct main ``*.pdf`` files in *leaf_dir*."""
    return [
        p
        for p in direct_pdf_paths_in_leaf_folder(leaf_dir)
        if is_inventory_main_pdf(p, registry_index=registry_index)
    ]


@dataclass(frozen=True)
class OnDiskMainPdfRow:
    absolute_path: Path
    basename: str
    root_id: str
    facets: PathFacets


def include_in_completion_operator_universe(facets: PathFacets) -> bool:
    """Whether a row belongs in the operator completion inventory (templates always included)."""
    if facets.scope == "template":
        return True
    return facets.doc_type not in COMPLETION_UNIVERSE_EXCLUDED_DOC_TYPES


def build_main_pdf_index_for_roots(
    *,
    daydreamedu_root: Path | None | object = _UNSET,
    goodnotes_root: Path | None | object = _UNSET,
    exclude_activity_note_completions: bool = False,
    registry_index: RegistryPathIndex | None = None,
) -> list[OnDiskMainPdfRow]:
    """Walk configured roots and collect main PDF rows with path facets.

    Omit a root argument to auto-resolve via env/local config. Pass ``None`` to skip that root.

    Pass *registry_index* so registered paths are included only when ``file_type='main'``.
    Without it, inclusion uses the basename heuristic only (tests / offline walks).

    When *exclude_activity_note_completions* is True, omit completion rows whose inferred
    ``doc_type`` is ``activity`` or ``note`` (aligned with ``completion_template_link_gap_report``).
    """
    if daydreamedu_root is _UNSET:
        dd = resolve_daydreamedu_root()
    else:
        dd = daydreamedu_root  # type: ignore[assignment]
    if goodnotes_root is _UNSET:
        gn = resolve_goodnotes_root()
    else:
        gn = goodnotes_root  # type: ignore[assignment]

    rows: list[OnDiskMainPdfRow] = []

    def _maybe_append(pdf_path: Path, *, root_id: str) -> None:
        facets = infer_path_facets(pdf_path, root_id=root_id)
        if exclude_activity_note_completions and not include_in_completion_operator_universe(facets):
            return
        rows.append(
            OnDiskMainPdfRow(
                absolute_path=pdf_path,
                basename=pdf_path.name,
                root_id=root_id,
                facets=facets,
            )
        )

    if dd is not None:
        for leaf in list_daydreamedu_leaf_folders_under_root(dd):
            for pdf_path in list_main_pdfs_in_leaf_folder(leaf, registry_index=registry_index):
                _maybe_append(pdf_path, root_id="daydreamedu")

    if gn is not None:
        # Default GoodNotes profile matches goodnotes-leaf-registry-report (exclude Not completed, x-prefix, root leaf).
        for leaf in list_goodnotes_leaf_folders_under_root(gn):
            for pdf_path in list_main_pdfs_in_leaf_folder(leaf, registry_index=registry_index):
                _maybe_append(pdf_path, root_id="goodnotes")

    rows.sort(key=lambda r: str(r.absolute_path).casefold())
    return rows
