# Goodnotes document timestamps → completion_date (proposal 17 §5.3).

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from ai_study_buddy.files import build_main_pdf_index_for_roots
from ai_study_buddy.files.pdf_registry_paths import (
    RegistryPathIndex,
    resolved_path_from_registry_row,
)

from ..completion_date.core import normalize_completion_date
from ..goodnotes_metadata import GoodnotesDocumentMatch, GoodnotesDocumentMatchStatus

if TYPE_CHECKING:
    from .pdf_file_manager import PdfFile, PdfFileManager

GOODNOTES_LAST_MODIFIED_SOURCE = "goodnotes_last_modified"
GOODNOTES_UPDATED_AT_SOURCE = "goodnotes_updated_at"
SINGAPORE_TZ = ZoneInfo("Asia/Singapore")

_HIGH_CONFIDENCE_STATUSES: frozenset[GoodnotesDocumentMatchStatus] = frozenset(
    {"matched_exact"}
)
_MEDIUM_CONFIDENCE_STATUSES: frozenset[GoodnotesDocumentMatchStatus] = frozenset(
    {
        "matched_leading_underscore_restored",
        "matched_raw_source",
        "matched_raw_source_leading_underscore_restored",
    }
)


@dataclass(frozen=True)
class GoodnotesCompletionInference:
    completion_date: str
    source: str
    confidence: str
    source_detail: dict[str, Any]


def completion_date_from_utc_iso(
    iso_utc: str, *, tz: ZoneInfo = SINGAPORE_TZ
) -> tuple[str, str]:
    """Return (YYYY-MM-DD in tz, normalized UTC ISO string)."""
    text = str(iso_utc).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt_utc = datetime.fromisoformat(text)
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    else:
        dt_utc = dt_utc.astimezone(timezone.utc)
    dt_local = dt_utc.astimezone(tz)
    normalized_utc = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt_local.date().isoformat(), normalized_utc


def confidence_for_goodnotes_match_status(status: GoodnotesDocumentMatchStatus) -> str | None:
    if status in _HIGH_CONFIDENCE_STATUSES:
        return "high"
    if status in _MEDIUM_CONFIDENCE_STATUSES:
        return "medium"
    return None


def infer_completion_date_from_goodnotes_match(
    match: GoodnotesDocumentMatch,
) -> GoodnotesCompletionInference | None:
    """Map a Goodnotes metadata match to completion_date per §5.3."""
    confidence = confidence_for_goodnotes_match_status(match.status)
    if confidence is None:
        return None
    if match.timestamps is None:
        return None

    chosen_iso: str | None = match.timestamps.last_modified
    source = GOODNOTES_LAST_MODIFIED_SOURCE
    timestamp_field = "last_modified"
    if not chosen_iso:
        chosen_iso = match.timestamps.updated_at
        source = GOODNOTES_UPDATED_AT_SOURCE
        timestamp_field = "updated_at"
    if not chosen_iso:
        return None

    completion_date, normalized_utc = completion_date_from_utc_iso(chosen_iso)
    normalize_completion_date(completion_date)

    source_detail: dict[str, Any] = {
        "timezone": "Asia/Singapore",
        "goodnotes_match_status": match.status,
        "goodnotes_document_id": match.goodnotes_document_id,
        "goodnotes_document_name": match.goodnotes_document_name,
        "matched_candidate_name": match.matched_candidate_name,
        "timestamp_field": timestamp_field,
        "timestamp_utc": normalized_utc,
    }
    if match.goodnotes_folder_path:
        source_detail["goodnotes_folder_path"] = match.goodnotes_folder_path

    return GoodnotesCompletionInference(
        completion_date=completion_date,
        source=source,
        confidence=confidence,
        source_detail=source_detail,
    )


def list_g_root_browser_cohort_files(
    mgr: PdfFileManager,
    *,
    registry_index: RegistryPathIndex | None = None,
) -> list[PdfFile]:
    """Same population as Student File Browser: GoodNotes completion mains on disk."""
    index = registry_index or RegistryPathIndex.from_pdf_file_manager(mgr)
    rows = build_main_pdf_index_for_roots(
        exclude_activity_note_completions=True,
        registry_index=index,
    )
    out: list[PdfFile] = []
    for row in rows:
        if row.root_id != "goodnotes" or row.facets.scope != "completion":
            continue
        key = str(row.absolute_path.resolve())
        reg_row = index.file_by_resolved_path.get(key)
        if reg_row is None:
            continue
        file_id = getattr(reg_row, "id", None)
        if not file_id:
            continue
        pdf = mgr.get_file(file_id)
        if pdf is not None:
            out.append(pdf)
    out.sort(key=lambda f: resolved_path_from_registry_row(f).casefold())
    return out
