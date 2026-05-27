# Proposal 17 Phase 2: page-1/2 render, batch manifest, apply agent inspection JSON (no vision API).

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, Literal

from .core import (
    CompletionDateRecord,
    InferCompletionDatesReport,
    adjust_page1_completion_year_for_path_context,
    check_completion_date_school_year,
    expected_school_year,
    infer_primary_level_from_path,
    normalize_completion_date,
    normalize_completion_date_confidence,
    normalize_inference_model,
)

if TYPE_CHECKING:
    from .pdf_file_manager import PdfFile, PdfFileManager

MANIFEST_SCHEMA_VERSION = "completion-date-page1-v3"
SUPPORTED_MANIFEST_SCHEMA_VERSIONS = frozenset(
    {
        "completion-date-page1-v1",
        "completion-date-page1-v2",
        "completion-date-page1-v3",
    }
)
DEFAULT_WORK_DIR_NAME = ".completion_date_page1"
PAGE1_SOURCE = "handwritten_page1"
REASON_NO_DATE_PAGE1 = "no_date_on_page_1"
REASON_NO_DATE_PAGES_1_AND_2 = "no_date_on_pages_1_or_2"

_D_ROOT_MARKER = "/DaydreamEdu/"
_G_ROOT_MARKER = "/GoodNotes/"


@dataclass(frozen=True)
class Page1InspectionResult:
    file_id: str
    completion_date: str | None
    confidence: str | None
    inference_model: str | None
    source_detail: dict | None


@dataclass(frozen=True)
class Page1BatchManifestItem:
    file_id: str
    path: str
    normal_name: str
    student_id: str
    doc_type: str
    page1_image_path: str
    slice: Literal["priority", "deprioritized"]
    page2_image_path: str | None = None
    existing_completion_date: str | None = None
    path_primary_level: int | None = None
    expected_school_year: int | None = None


@dataclass(frozen=True)
class Page1BatchManifest:
    schema_version: str
    created_at: str
    root: Literal["d_root"]
    skip_doc_types: tuple[str, ...]
    items: tuple[Page1BatchManifestItem, ...]
    counts: dict[str, int]


def default_page1_work_dir(*, package_dir: Path | None = None) -> Path:
    base = package_dir or Path(__file__).resolve().parent
    return base / DEFAULT_WORK_DIR_NAME


def normalize_registry_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def inventory_root_from_path(path: str | Path) -> Literal["d_root", "g_root", "unknown"]:
    normalized = normalize_registry_path(path)
    if _G_ROOT_MARKER in normalized:
        return "g_root"
    if _D_ROOT_MARKER in normalized:
        return "d_root"
    return "unknown"


def page_png_path_for(work_dir: Path, file_id: str, page_index: int) -> Path:
    if page_index < 0:
        raise ValueError("page_index must be >= 0")
    return work_dir / "images" / file_id / f"page-{page_index + 1:02d}.png"


def page1_image_path_for(work_dir: Path, file_id: str) -> Path:
    return page_png_path_for(work_dir, file_id, 0)


def page2_image_path_for(work_dir: Path, file_id: str) -> Path:
    return page_png_path_for(work_dir, file_id, 1)


def page1_result_path_for(work_dir: Path, file_id: str) -> Path:
    return work_dir / "results" / f"{file_id}.json"


def manifest_path_for(work_dir: Path) -> Path:
    return work_dir / "batch_manifest.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pdf_page_count(pdf_path: str | Path) -> int:
    """Return the number of pages in a PDF (PyMuPDF)."""
    try:
        import fitz  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            "PyMuPDF dependency missing: install with `pip3 install pymupdf`"
        ) from exc

    source = Path(pdf_path)
    if not source.is_file():
        raise FileNotFoundError(f"PDF does not exist: {source}")

    doc = fitz.open(str(source))
    try:
        return int(doc.page_count)
    finally:
        doc.close()


def render_page_png(
    pdf_path: str | Path,
    out_path: str | Path,
    *,
    page_index: int = 0,
    dpi_scale: float = 2.0,
) -> Path:
    """Render one PDF page to a PNG (PyMuPDF only; no OCR). ``page_index`` is 0-based."""
    try:
        import fitz  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            "PyMuPDF dependency missing: install with `pip3 install pymupdf`"
        ) from exc

    if page_index < 0:
        raise ValueError("page_index must be >= 0")
    if dpi_scale <= 0:
        raise ValueError("dpi_scale must be > 0")

    source = Path(pdf_path)
    if not source.is_file():
        raise FileNotFoundError(f"PDF does not exist: {source}")

    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(source))
    try:
        if doc.page_count < 1:
            raise ValueError(f"PDF has no pages: {source}")
        if page_index >= doc.page_count:
            raise ValueError(
                f"page_index {page_index} out of range for {source} ({doc.page_count} pages)"
            )
        page = doc[page_index]
        matrix = fitz.Matrix(dpi_scale, dpi_scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        pix.save(str(destination))
    finally:
        doc.close()
    return destination


def render_page1_png(
    pdf_path: str | Path,
    out_path: str | Path,
    *,
    dpi_scale: float = 2.0,
) -> Path:
    """Render PDF page 1 (index 0) to a PNG."""
    return render_page_png(pdf_path, out_path, page_index=0, dpi_scale=dpi_scale)


def parse_page1_inspection_payload(payload: dict[str, Any]) -> Page1InspectionResult:
    """Validate agent JSON (§5.1) into a Page1InspectionResult."""
    if not isinstance(payload, dict):
        raise ValueError("page-1 inspection payload must be a JSON object")

    file_id = payload.get("file_id")
    if not isinstance(file_id, str) or not file_id.strip():
        raise ValueError("payload.file_id must be a non-empty string")

    raw_date = payload.get("completion_date")
    completion_date: str | None
    if raw_date is None:
        completion_date = None
    elif isinstance(raw_date, str):
        completion_date = normalize_completion_date(raw_date)
    else:
        raise ValueError("payload.completion_date must be a string or null")

    raw_confidence = payload.get("confidence")
    confidence: str | None
    if raw_confidence is None:
        confidence = None
    elif isinstance(raw_confidence, str):
        confidence = normalize_completion_date_confidence(raw_confidence)
    else:
        raise ValueError("payload.confidence must be a string or null")

    if completion_date is None and confidence is not None:
        raise ValueError("confidence must be null when completion_date is null")

    raw_model = payload.get("inference_model")
    if raw_model is None:
        raw_model = payload.get("generation_model")
    inference_model: str | None
    if raw_model is None:
        inference_model = None
    elif isinstance(raw_model, str):
        inference_model = normalize_inference_model(raw_model)
    else:
        raise ValueError("payload.inference_model must be a string or null")

    if completion_date is None and inference_model is not None:
        raise ValueError("inference_model must be null when completion_date is null")

    if completion_date is not None:
        if confidence is None:
            raise ValueError("confidence is required when completion_date is set")
        if inference_model is None:
            raise ValueError("inference_model is required when completion_date is set")

    source_detail = payload.get("source_detail")
    if source_detail is not None and not isinstance(source_detail, dict):
        raise ValueError("payload.source_detail must be an object or null")

    return Page1InspectionResult(
        file_id=file_id.strip(),
        completion_date=completion_date,
        confidence=confidence,
        inference_model=inference_model,
        source_detail=source_detail,
    )


def merge_page_inspection_payloads(
    file_id: str,
    page1_payload: dict[str, Any],
    page2_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Page-1-first flow: use page 1 when dated; else page 2 when provided; else null."""
    if page1_payload.get("file_id") != file_id:
        raise ValueError("page1_payload.file_id must match file_id")

    page1 = parse_page1_inspection_payload(page1_payload)
    if page1.completion_date is not None:
        merged = dict(page1_payload)
        detail = dict(merged.get("source_detail") or {})
        detail.setdefault("page_index", 0)
        detail.setdefault("timezone", "Asia/Singapore")
        merged["source_detail"] = detail
        return merged

    if page2_payload is None:
        return dict(page1_payload)

    if page2_payload.get("file_id") not in (None, file_id):
        raise ValueError("page2_payload.file_id must match file_id when set")

    page2 = parse_page1_inspection_payload({**page2_payload, "file_id": file_id})
    if page2.completion_date is not None:
        detail = dict(page2.source_detail or {})
        detail["page_index"] = 1
        detail.setdefault("timezone", "Asia/Singapore")
        return {
            "file_id": file_id,
            "completion_date": page2.completion_date,
            "confidence": page2.confidence,
            "inference_model": page2.inference_model,
            "source_detail": detail,
        }

    return {
        "file_id": file_id,
        "completion_date": None,
        "confidence": None,
        "inference_model": None,
        "source_detail": {
            "timezone": "Asia/Singapore",
            "reason": REASON_NO_DATE_PAGES_1_AND_2,
            "note": "inspected page 1 then page 2; no student completion date on either",
        },
    }


def load_page1_inspection_result(work_dir: Path, file_id: str) -> Page1InspectionResult | None:
    path = page1_result_path_for(work_dir, file_id)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_page1_inspection_payload(payload)


def list_d_root_page1_cohort(
    mgr: PdfFileManager,
    *,
    student_ids: list[str] | None = None,
    doc_types: frozenset[str] | None = None,
    skip_doc_types: frozenset[str] | None = None,
    include_activity_note: bool = True,
) -> list[PdfFile]:
    """Registered completion mains under DaydreamEdu (d_root), ordered for Phase 2."""
    skip = skip_doc_types or frozenset()
    only_types = doc_types
    allowed_students = set(student_ids) if student_ids else None

    cohort: list[PdfFile] = []
    for pdf in mgr.find_files(file_type="main", is_template=False):
        if not pdf.student_id:
            continue
        if inventory_root_from_path(pdf.path) != "d_root":
            continue
        if allowed_students is not None and pdf.student_id not in allowed_students:
            continue
        if only_types is not None and pdf.doc_type not in only_types:
            continue
        if pdf.doc_type in skip:
            continue
        if not include_activity_note and pdf.doc_type in ("activity", "note"):
            continue
        cohort.append(pdf)

    cohort.sort(key=lambda f: (f.doc_type == "book", normalize_registry_path(f.path).casefold()))
    return cohort


def prepare_page1_batch(
    mgr: PdfFileManager,
    work_dir: Path,
    *,
    doc_types: frozenset[str] | None = None,
    skip_doc_types: frozenset[str] | None = None,
    include_activity_note: bool = True,
    student_ids: list[str] | None = None,
    dpi_scale: float = 2.0,
    dry_run: bool = False,
    limit: int | None = None,
) -> Page1BatchManifest:
    """Build manifest and render page-1 (and page-2 when present) PNGs for the d_root Phase 2 cohort."""
    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    skip = skip_doc_types or frozenset()

    cohort = list_d_root_page1_cohort(
        mgr,
        student_ids=student_ids,
        doc_types=doc_types,
        skip_doc_types=skip,
        include_activity_note=include_activity_note,
    )
    if limit is not None:
        cohort = cohort[: max(0, limit)]

    items: list[Page1BatchManifestItem] = []
    for pdf in cohort:
        image_path = page1_image_path_for(work_dir, pdf.id)
        page2_path: Path | None = None
        slice_name: Literal["priority", "deprioritized"] = (
            "deprioritized" if pdf.doc_type == "book" else "priority"
        )
        existing = mgr.get_completion_date(pdf.id)
        try:
            if not dry_run:
                render_page1_png(pdf.path, image_path, dpi_scale=dpi_scale)
            if pdf_page_count(pdf.path) >= 2:
                page2_path = page2_image_path_for(work_dir, pdf.id)
                if not dry_run:
                    render_page_png(
                        pdf.path, page2_path, page_index=1, dpi_scale=dpi_scale
                    )
        except (RuntimeError, ValueError, FileNotFoundError):
            page2_path = None

        level = infer_primary_level_from_path(pdf.path, name=pdf.name)
        exp_year = (
            expected_school_year(pdf.student_id, level)
            if pdf.student_id and level is not None
            else None
        )
        items.append(
            Page1BatchManifestItem(
                file_id=pdf.id,
                path=pdf.path,
                normal_name=pdf.normal_name,
                student_id=pdf.student_id or "",
                doc_type=pdf.doc_type,
                page1_image_path=str(image_path),
                slice=slice_name,
                page2_image_path=str(page2_path) if page2_path is not None else None,
                existing_completion_date=existing.completion_date if existing else None,
                path_primary_level=level,
                expected_school_year=exp_year,
            )
        )

    priority = sum(1 for item in items if item.slice == "priority")
    deprioritized = sum(1 for item in items if item.slice == "deprioritized")
    manifest = Page1BatchManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        created_at=_utc_now_iso(),
        root="d_root",
        skip_doc_types=tuple(sorted(skip)),
        items=tuple(items),
        counts={
            "total": len(items),
            "priority": priority,
            "deprioritized": deprioritized,
        },
    )
    write_batch_manifest(work_dir, manifest)
    return manifest


def write_batch_manifest(work_dir: Path, manifest: Page1BatchManifest) -> Path:
    path = manifest_path_for(work_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": manifest.schema_version,
        "created_at": manifest.created_at,
        "root": manifest.root,
        "skip_doc_types": list(manifest.skip_doc_types),
        "items": [asdict(item) for item in manifest.items],
        "counts": dict(manifest.counts),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_batch_manifest(work_dir: Path) -> Page1BatchManifest:
    path = manifest_path_for(work_dir)
    if not path.is_file():
        raise FileNotFoundError(f"Batch manifest not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = payload.get("schema_version")
    if schema not in SUPPORTED_MANIFEST_SCHEMA_VERSIONS:
        raise ValueError(f"Unsupported manifest schema: {schema!r}")
    items = tuple(
        Page1BatchManifestItem(
            file_id=item["file_id"],
            path=item["path"],
            normal_name=item["normal_name"],
            student_id=item["student_id"],
            doc_type=item["doc_type"],
            page1_image_path=item["page1_image_path"],
            slice=item["slice"],
            page2_image_path=item.get("page2_image_path"),
            existing_completion_date=item.get("existing_completion_date"),
            path_primary_level=item.get("path_primary_level"),
            expected_school_year=item.get("expected_school_year"),
        )
        for item in (payload.get("items") or [])
    )
    return Page1BatchManifest(
        schema_version=payload["schema_version"],
        created_at=str(payload["created_at"]),
        root="d_root",
        skip_doc_types=tuple(payload.get("skip_doc_types") or ()),
        items=items,
        counts=dict(payload.get("counts") or {}),
    )


def iter_page1_inspection_payloads(results_path: Path) -> Iterator[dict[str, Any]]:
    """Yield raw JSON objects from a results directory, JSONL, or single JSON file."""
    path = results_path.resolve()
    if path.is_dir():
        for child in sorted(path.glob("*.json")):
            yield json.loads(child.read_text(encoding="utf-8"))
        return

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return

    if path.suffix.lower() == ".jsonl":
        for line in text.splitlines():
            line = line.strip()
            if line:
                yield json.loads(line)
        return

    payload = json.loads(text)
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item
        return
    if isinstance(payload, dict):
        yield payload
        return
    raise ValueError(f"Unsupported results file shape: {path}")


def save_page1_inspection_result(work_dir: Path, payload: dict[str, Any]) -> Path:
    """Write agent JSON to work_dir/results/<file_id>.json."""
    parsed = parse_page1_inspection_payload(payload)
    out = page1_result_path_for(work_dir, parsed.file_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def apply_page1_inspection_result(
    mgr: PdfFileManager,
    result: Page1InspectionResult,
    *,
    force: bool = False,
    force_manual: bool = False,
    dry_run: bool = False,
    validate_school_year: bool = True,
) -> CompletionDateRecord | None:
    """Persist one agent inspection result; returns None when skipped or no date."""
    if result.completion_date is None:
        return None

    pdf = mgr.get_file(result.file_id)
    completion_date = result.completion_date
    source_detail = dict(result.source_detail) if result.source_detail else None
    if pdf is not None:
        adjusted, adjustment = adjust_page1_completion_year_for_path_context(
            completion_date,
            student_id=pdf.student_id,
            path=pdf.path,
            name=pdf.name,
            source_detail=source_detail,
        )
        if adjustment is not None:
            completion_date = adjusted
            source_detail = source_detail or {}
            source_detail["year_adjustment"] = adjustment
            result = Page1InspectionResult(
                file_id=result.file_id,
                completion_date=completion_date,
                confidence=result.confidence,
                inference_model=result.inference_model,
                source_detail=source_detail,
            )

    if validate_school_year:
        if pdf is not None:
            plausible, _detail = check_completion_date_school_year(
                completion_date,
                student_id=pdf.student_id,
                path=pdf.path,
                name=pdf.name,
            )
            if not plausible:
                return None

    existing = mgr.get_completion_date(result.file_id)
    if existing is not None:
        if existing.source == "manual" and not force_manual:
            return None
        if not force:
            return None

    if dry_run:
        return CompletionDateRecord(
            file_id=result.file_id,
            completion_date=completion_date,
            source=PAGE1_SOURCE,
            confidence=result.confidence,
            inference_model=result.inference_model,
            source_detail=result.source_detail,
            inferred_at=_utc_now_iso(),
            updated_at=_utc_now_iso(),
        )

    record = mgr.set_completion_date(
        result.file_id,
        completion_date,
        source=PAGE1_SOURCE,
        confidence=result.confidence,
        inference_model=result.inference_model,
        source_detail=source_detail,
    )
    mgr._log_operation(
        "infer_completion_date",
        file_id=result.file_id,
        after_state=json.dumps(
            {
                "method": PAGE1_SOURCE,
                "completion_date": completion_date,
                "confidence": result.confidence,
                "inference_model": result.inference_model,
            }
        ),
    )
    return record


def _merge_report(report: InferCompletionDatesReport, **kwargs: int) -> InferCompletionDatesReport:
    data = {
        "processed": report.processed,
        "written": report.written,
        "skipped_existing": report.skipped_existing,
        "skipped_manual": report.skipped_manual,
        "skipped_no_cached_result": report.skipped_no_cached_result,
        "skipped_no_date": report.skipped_no_date,
        "failed": report.failed,
        "still_undated": report.still_undated,
    }
    data.update(kwargs)
    return InferCompletionDatesReport(**data)


def apply_page1_results_from_path(
    mgr: PdfFileManager,
    results_path: Path,
    *,
    force: bool = False,
    force_manual: bool = False,
    dry_run: bool = False,
) -> InferCompletionDatesReport:
    report = InferCompletionDatesReport()
    for payload in iter_page1_inspection_payloads(results_path):
        report = _merge_report(report, processed=report.processed + 1)
        try:
            parsed = parse_page1_inspection_payload(payload)
            existing = mgr.get_completion_date(parsed.file_id)
            if parsed.completion_date is None:
                report = _merge_report(report, skipped_no_date=report.skipped_no_date + 1)
                continue
            if existing is not None:
                if existing.source == "manual" and not force_manual:
                    report = _merge_report(report, skipped_manual=report.skipped_manual + 1)
                    continue
                if not force:
                    report = _merge_report(report, skipped_existing=report.skipped_existing + 1)
                    continue
            applied = apply_page1_inspection_result(
                mgr,
                parsed,
                force=force,
                force_manual=force_manual,
                dry_run=dry_run,
            )
            if applied is not None:
                report = _merge_report(report, written=report.written + 1)
        except (ValueError, json.JSONDecodeError):
            report = _merge_report(report, failed=report.failed + 1)
    return report


def infer_completion_date_for_file_cached_page1(
    mgr: PdfFileManager,
    file_id: str,
    work_dir: Path,
    *,
    force: bool = False,
    force_manual: bool = False,
) -> CompletionDateRecord | None:
    cached = load_page1_inspection_result(work_dir, file_id)
    if cached is None:
        return None
    return apply_page1_inspection_result(
        mgr, cached, force=force, force_manual=force_manual
    )


def infer_completion_dates_cached_page1(
    mgr: PdfFileManager,
    work_dir: Path,
    *,
    student_ids: list[str] | None = None,
    doc_types: frozenset[str] | None = None,
    skip_doc_types: frozenset[str] | None = None,
    include_activity_note: bool = True,
    dry_run: bool = False,
    force: bool = False,
    force_manual: bool = False,
) -> InferCompletionDatesReport:
    """Apply cached agent results under work_dir/results for the d_root cohort."""
    cohort = list_d_root_page1_cohort(
        mgr,
        student_ids=student_ids,
        doc_types=doc_types,
        skip_doc_types=skip_doc_types,
        include_activity_note=include_activity_note,
    )
    report = InferCompletionDatesReport()
    for pdf in cohort:
        report = _merge_report(report, processed=report.processed + 1)
        cached = load_page1_inspection_result(work_dir, pdf.id)
        if cached is None:
            report = _merge_report(
                report,
                skipped_no_cached_result=report.skipped_no_cached_result + 1,
                still_undated=report.still_undated + 1,
            )
            continue

        existing = mgr.get_completion_date(pdf.id)
        if cached.completion_date is None:
            report = _merge_report(
                report,
                skipped_no_date=report.skipped_no_date + 1,
                still_undated=report.still_undated + (0 if existing else 1),
            )
            continue
        if existing is not None:
            if existing.source == "manual" and not force_manual:
                report = _merge_report(report, skipped_manual=report.skipped_manual + 1)
                continue
            if not force:
                report = _merge_report(report, skipped_existing=report.skipped_existing + 1)
                continue

        applied = apply_page1_inspection_result(
            mgr, cached, force=force, force_manual=force_manual, dry_run=dry_run
        )
        if applied is not None:
            report = _merge_report(report, written=report.written + 1)
        elif mgr.get_completion_date(pdf.id) is None:
            report = _merge_report(report, still_undated=report.still_undated + 1)
    return report
