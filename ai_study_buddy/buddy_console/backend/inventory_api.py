from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import os
from pathlib import Path
import threading
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ai_study_buddy.files import (
    __version__ as FILES_VERSION,
    build_enriched_inventory,
    build_main_pdf_index_for_roots,
    filter_main_pdf_cards,
    filter_meta_for_response,
    inventory_meta,
    list_daydreamedu_leaf_folders_under_root,
    list_goodnotes_leaf_folders_under_root,
    resolve_daydreamedu_root,
    resolve_goodnotes_root,
    sort_main_pdf_cards,
)
from ai_study_buddy.files.main_pdfs import OnDiskMainPdfRow
from ai_study_buddy.files.pdf_registry_paths import RegistryPathIndex, is_pdf_registered
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.pdf_file_manager import PdfFileManager
from ai_study_buddy.pdf_file_manager.completion_date import CompletionDateRecord
from ai_study_buddy.student_file_browser.filters import filter_criteria_from_query
from ai_study_buddy.student_file_browser.path_guard import safe_resolve_under_root

router = APIRouter()

DEFAULT_CONTEXT_ROOT = Path(__file__).resolve().parents[2] / "context"
INDEX_WARN_THRESHOLD = 2000


@dataclass
class InventoryRuntime:
    roots: dict[str, Path]
    leaf_dirs_by_id: dict[str, frozenset[Path]]
    leaf_rels_by_id: dict[str, frozenset[str]]
    index_rows: list[OnDiskMainPdfRow]
    context_root: Path
    # Backwards-compatible field for tests/fixtures; no longer used for serving.
    enriched_cache: list[Any] | None = None
    # Keep index/roots cached, but do not cache enriched cards across requests.
    # Review/amendment state can change outside this process (e.g. via review workspace),
    # and stale enrichment causes inventory cards to show outdated workflow status.
    _enrich_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)


def _default_context_root() -> Path:
    raw = os.environ.get("AI_STUDY_BUDDY_CONTEXT_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_CONTEXT_ROOT.resolve()


def _roots_config() -> dict[str, Path]:
    out: dict[str, Path] = {}
    dd = resolve_daydreamedu_root()
    if dd is not None:
        out["daydreamedu"] = dd
    gn = resolve_goodnotes_root()
    if gn is not None:
        out["goodnotes"] = gn
    return out


def _leaf_paths_set(root: Path, *, rid: str) -> frozenset[Path]:
    if rid == "daydreamedu":
        leaves = list_daydreamedu_leaf_folders_under_root(root)
    elif rid == "goodnotes":
        leaves = list_goodnotes_leaf_folders_under_root(root)
    else:
        return frozenset()
    return frozenset(p.resolve() for p in leaves)


def _pdf_blocked_not_in_leaf(leaves: frozenset[Path], pdf_path: Path) -> bool:
    return pdf_path.resolve().parent not in leaves


def _content_disposition_inline(filename: str) -> str:
    fallback_ascii = filename.encode("ascii", "replace").decode("ascii").replace('"', "")
    utf8_encoded = quote(filename, safe="")
    return f'inline; filename="{fallback_ascii}"; filename*=UTF-8\'\'{utf8_encoded}'


def _normalize_tree_rel(rel: str) -> str:
    rel = rel.strip().replace("\\", "/")
    if rel in ("", "."):
        return ""
    while "//" in rel:
        rel = rel.replace("//", "/")
    return rel.strip("/")


def _posix_rel_under(root_rr: Path, path: Path) -> str:
    return _normalize_tree_rel(path.resolve().relative_to(root_rr).as_posix())


def _leaf_relative_paths_sync_root(root: Path, *, rid: str) -> frozenset[str]:
    rr = root.resolve()
    if rid == "daydreamedu":
        leaves = list_daydreamedu_leaf_folders_under_root(root)
    elif rid == "goodnotes":
        leaves = list_goodnotes_leaf_folders_under_root(root, exclude_not_completed=False)
    else:
        return frozenset()
    return frozenset(_posix_rel_under(rr, leaf) for leaf in leaves)


def _on_leaf_prefix_tree(leaf_rels: frozenset[str], curr_rel: str) -> bool:
    curr = _normalize_tree_rel(curr_rel)
    if curr == "":
        return True
    for lf in leaf_rels:
        if lf == curr or lf.startswith(f"{curr}/"):
            return True
    return False


def _list_dir_children(
    root: Path,
    rel: str,
    *,
    leaf_rels: frozenset[str],
) -> tuple[list[str], list[str]] | None:
    root_resolved = root.resolve()
    target = safe_resolve_under_root(root, rel)
    if target is None or not target.is_dir():
        return None

    curr = _posix_rel_under(root_resolved, target)
    if not leaf_rels:
        return ([], []) if curr == "" else None
    if not _on_leaf_prefix_tree(leaf_rels, curr):
        return None

    dirs: list[str] = []
    pdfs: list[str] = []
    listing_pdfs_here = curr in leaf_rels
    try:
        for child in target.iterdir():
            name = child.name
            if name.startswith("."):
                continue
            try:
                if child.is_dir():
                    nxt_rel = _posix_rel_under(root_resolved, child)
                    if _on_leaf_prefix_tree(leaf_rels, nxt_rel):
                        dirs.append(name)
                elif listing_pdfs_here and child.is_file() and child.suffix.lower() == ".pdf":
                    pdfs.append(name)
            except OSError:
                continue
    except OSError:
        return None
    dirs.sort(key=str.lower)
    pdfs.sort(key=str.lower)
    return dirs, pdfs


def _query_params_as_lists(request: Request) -> dict[str, list[str]]:
    params: dict[str, list[str]] = defaultdict(list)
    for key, value in request.query_params.multi_items():
        params[key].append(value)
    return params


def _build_runtime() -> InventoryRuntime | None:
    roots = _roots_config()
    if not roots:
        return None
    pfm = PdfFileManager()
    registry_index = RegistryPathIndex.from_pdf_file_manager(pfm)
    index_rows = build_main_pdf_index_for_roots(
        exclude_activity_note_completions=True,
        registry_index=registry_index,
    )
    leaf_map = {rid: _leaf_paths_set(root, rid=rid) for rid, root in roots.items()}
    leaf_rel_map = {rid: _leaf_relative_paths_sync_root(root, rid=rid) for rid, root in roots.items()}
    return InventoryRuntime(
        roots=roots,
        leaf_dirs_by_id=leaf_map,
        leaf_rels_by_id=leaf_rel_map,
        index_rows=index_rows,
        context_root=_default_context_root(),
    )


def _get_runtime(request: Request) -> InventoryRuntime:
    runtime = getattr(request.app.state, "inventory_runtime", None)
    if runtime is None:
        runtime = _build_runtime()
        request.app.state.inventory_runtime = runtime
    if runtime is None:
        raise HTTPException(
            status_code=503,
            detail="Inventory roots are not configured. Set DAYDREAMEDU_ROOT and/or GOODNOTES_ROOT.",
        )
    return runtime


class CompletionDatePatchBody(BaseModel):
    completion_date: str = Field(min_length=1)


def build_buddy_console_source_detail(
    existing: CompletionDateRecord | None,
) -> dict[str, str]:
    detail: dict[str, str] = {"set_via": "buddy_console"}
    if existing is None:
        return detail
    detail["previous_completion_date"] = existing.completion_date
    detail["previous_source"] = existing.source
    if existing.confidence is not None:
        detail["previous_confidence"] = existing.confidence
    return detail


def _get_enriched_cards(runtime: InventoryRuntime) -> list[Any]:
    # Test/runtime override hook: when explicitly provided, trust the injected cache.
    if runtime.enriched_cache is not None:
        return runtime.enriched_cache
    with runtime._enrich_lock:
        pfm = PdfFileManager()
        index = RegistryPathIndex.from_pdf_file_manager(pfm)
        review_repo = StudentReviewRepository(context_root=runtime.context_root)
        return build_enriched_inventory(
            runtime.index_rows,
            index=index,
            pfm=pfm,
            review_repo=review_repo,
            context_root=runtime.context_root,
        )


def warm_enriched_cache(app: Any) -> None:
    """Build inventory enrichment once in a background thread (first load is slow)."""
    runtime = getattr(app.state, "inventory_runtime", None)
    if runtime is None:
        runtime = _build_runtime()
        if runtime is None:
            return
        app.state.inventory_runtime = runtime

    def _run() -> None:
        try:
            _get_enriched_cards(runtime)
        except Exception:
            pass

    threading.Thread(target=_run, name="buddy-console-inventory-warm", daemon=True).start()


@router.get("/api/inventory/health")
def inventory_health(request: Request) -> dict[str, Any]:
    runtime = _get_runtime(request)
    return {
        "status": "ok",
        "index_count": len(runtime.index_rows),
        "files_version": FILES_VERSION,
    }


@router.get("/api/config")
def inventory_config(request: Request) -> dict[str, Any]:
    runtime = _get_runtime(request)
    criteria = filter_criteria_from_query(_query_params_as_lists(request))
    cards = _get_enriched_cards(runtime)
    pfm = PdfFileManager()
    filter_meta = filter_meta_for_response(cards, criteria, pfm=pfm)
    students: list[dict[str, str]] = []
    try:
        for s in pfm.list_students():
            students.append(
                {
                    "student_id": s.id,
                    "display_name": s.name,
                    "email": s.email,
                }
            )
    except Exception:
        pass
    return {
        "roots": [
            {"id": rid, "label": "DaydreamEdu" if rid == "daydreamedu" else "GoodNotes", "path": str(path)}
            for rid, path in runtime.roots.items()
        ],
        "students": students,
        **filter_meta,
    }


@router.patch("/api/inventory/items/{registry_file_id}/completion-date")
def patch_inventory_completion_date(
    request: Request,
    registry_file_id: str,
    body: CompletionDatePatchBody,
) -> dict[str, str]:
    runtime = _get_runtime(request)
    try:
        pfm = PdfFileManager()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Registry unavailable") from exc

    if pfm.get_file(registry_file_id) is None:
        raise HTTPException(status_code=404, detail="File not found")

    existing = pfm.get_completion_date(registry_file_id)
    source_detail = build_buddy_console_source_detail(existing)
    try:
        row = pfm.set_completion_date(
            registry_file_id,
            body.completion_date,
            source="manual",
            confidence=None,
            inference_model=None,
            source_detail=source_detail,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "registry_file_id": registry_file_id,
        "completion_date": row.completion_date,
        "completion_date_source": row.source,
    }


@router.get("/api/inventory")
def inventory_list(request: Request) -> dict[str, Any]:
    runtime = _get_runtime(request)
    criteria = filter_criteria_from_query(_query_params_as_lists(request))
    cards = _get_enriched_cards(runtime)
    pfm = PdfFileManager()
    filtered = filter_main_pdf_cards(cards, criteria, pfm=pfm)
    filtered = sort_main_pdf_cards(filtered, criteria.sort)
    filter_meta = filter_meta_for_response(cards, criteria, pfm=pfm)
    meta = inventory_meta(
        cards,
        filtered_count=len(filtered),
        show_is_registered_filter=filter_meta["show_is_registered_filter"],
    )
    warn = len(runtime.index_rows) > INDEX_WARN_THRESHOLD
    return {
        "items": [card.to_dict() for card in filtered],
        "meta": {
            "total_in_index": meta.total_in_index,
            "total_after_filter": meta.total_after_filter,
            "unregistered_in_index": meta.unregistered_in_index,
            "index_size_warning": warn,
            **filter_meta,
        },
    }


@router.get("/api/pdf-browser/config")
def pdf_browser_config(request: Request) -> dict[str, Any]:
    runtime = _get_runtime(request)
    return {
        "roots": [
            {"id": rid, "label": "DaydreamEdu" if rid == "daydreamedu" else "GoodNotes", "path": str(path)}
            for rid, path in runtime.roots.items()
        ]
    }


@router.get("/api/pdf-browser/list")
def pdf_browser_list(request: Request, id: str, rel: str = "") -> dict[str, Any]:
    runtime = _get_runtime(request)
    root = runtime.roots.get(id)
    if root is None:
        raise HTTPException(status_code=400, detail="Unknown or unavailable root id")
    leaf_set = runtime.leaf_rels_by_id.get(id, frozenset())
    children = _list_dir_children(root, rel, leaf_rels=leaf_set)
    if children is None:
        raise HTTPException(status_code=400, detail="Not a directory or path not allowed")
    dirs, pdfs = children
    root_resolved = root.resolve()
    target = safe_resolve_under_root(root, rel)
    curr_rel = _posix_rel_under(root_resolved, target) if target is not None else ""
    listing_pdfs_here = curr_rel in leaf_set
    try:
        idx = RegistryPathIndex.from_pdf_file_manager(PdfFileManager())
    except Exception:
        idx = None
    pdf_status: dict[str, bool | None] = {}
    if idx is not None and target is not None and listing_pdfs_here:
        for name in pdfs:
            pdf_status[name] = is_pdf_registered(target / name, idx)
    return {
        "dirs": dirs,
        "pdfs": pdfs,
        "pdfRegistration": pdf_status,
        "registryAvailable": idx is not None,
        "currentRel": curr_rel,
    }


@router.get("/api/pdf")
def inventory_pdf(request: Request, id: str, rel: str) -> Response:
    runtime = _get_runtime(request)
    root = runtime.roots.get(id)
    if root is None:
        raise HTTPException(status_code=400, detail="Unknown or unavailable root id")
    target = safe_resolve_under_root(root, rel)
    if target is None or not target.is_file() or target.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Not found")
    leaf_set = runtime.leaf_dirs_by_id.get(id, frozenset())
    if _pdf_blocked_not_in_leaf(leaf_set, target):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        data = target.read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Read failed") from exc
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition_inline(target.name)},
    )
