from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from ai_study_buddy.marking.core.artifact_paths import slugify_student
from ai_study_buddy.marking.review.models import STATIC_ROUTE_PREFIX
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile, normalize_pdf_display_name

_REVIEW_REDO_PAGE_BASENAME_RE = re.compile(r"^page_(\d+)\.(png|jpg|jpeg|webp)$", re.IGNORECASE)


def _import_fitz():
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover - import-time environment guard
        raise RuntimeError("PyMuPDF dependency missing: install with `pip3 install pymupdf`") from exc
    return fitz


def review_redo_render_dir(
    *,
    context_root: Path,
    student_slug: str,
    subject_context: str,
    normal_name: str,
) -> Path:
    return context_root / "review_redo" / student_slug / subject_context / normal_name


def _extract_page_num(path: Path) -> int:
    match = _REVIEW_REDO_PAGE_BASENAME_RE.match(path.name)
    if not match:
        return 10_000_000
    return int(match.group(1))


def list_review_redo_images(*, context_root: Path, unit_dir: Path) -> list[dict[str, Any]]:
    resolved_root = context_root.resolve()
    rendered_dir = (unit_dir / "rendered_pages").resolve()
    if not rendered_dir.is_dir():
        return []

    candidates = [
        path
        for path in rendered_dir.iterdir()
        if path.is_file() and _REVIEW_REDO_PAGE_BASENAME_RE.match(path.name)
    ]
    out: list[dict[str, Any]] = []
    for path in sorted(candidates, key=lambda candidate: (_extract_page_num(candidate), candidate.name)):
        rel = path.resolve().relative_to(resolved_root).as_posix()
        out.append(
            {
                "name": path.name,
                "page_num": _extract_page_num(path),
                "url": f"{STATIC_ROUTE_PREFIX}/{rel}",
            }
        )
    return out


def _newest_mtime(paths: Sequence[Path]) -> float | None:
    mtimes = [path.stat().st_mtime for path in paths if path.is_file()]
    return max(mtimes) if mtimes else None


def review_redo_cache_is_stale(*, source_pdf: Path, rendered_dir: Path) -> bool:
    if not source_pdf.is_file():
        return True
    if not rendered_dir.is_dir():
        return True

    pngs = [
        path
        for path in rendered_dir.iterdir()
        if path.is_file() and _REVIEW_REDO_PAGE_BASENAME_RE.match(path.name)
    ]
    if not pngs:
        return True

    source_mtime = source_pdf.stat().st_mtime
    cache_mtime = _newest_mtime(pngs)
    if cache_mtime is None:
        return True
    return source_mtime > cache_mtime


def _clean_existing_review_redo_images(target_dir: Path) -> None:
    if not target_dir.is_dir():
        return
    for candidate in target_dir.iterdir():
        if candidate.is_file() and _REVIEW_REDO_PAGE_BASENAME_RE.match(candidate.name):
            candidate.unlink()


def render_review_redo_pages(
    *,
    source_pdf: Path,
    unit_dir: Path,
    dpi_scale: float = 2.0,
    image_format: str = "png",
    clean_existing: bool = True,
) -> list[Path]:
    fitz = _import_fitz()
    if dpi_scale <= 0:
        raise ValueError("dpi_scale must be > 0")

    ext = image_format.strip().casefold()
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        raise ValueError("image_format must be one of: png|jpg|jpeg|webp")

    pdf_path = source_pdf.expanduser().resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF does not exist: {pdf_path}")

    rendered_dir = unit_dir / "rendered_pages"
    rendered_dir.mkdir(parents=True, exist_ok=True)
    if clean_existing:
        _clean_existing_review_redo_images(rendered_dir)

    doc = fitz.open(str(pdf_path))
    try:
        matrix = fitz.Matrix(dpi_scale, dpi_scale)
        written: list[Path] = []
        for render_index in range(1, doc.page_count + 1):
            page = doc[render_index - 1]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            out_path = rendered_dir / f"page_{render_index:03d}.{ext}"
            pix.save(str(out_path))
            written.append(out_path)
        return written
    finally:
        doc.close()


def review_redo_unit_dir_for_attempt(
    *,
    context_root: Path,
    attempt: PdfFile,
    template: PdfFile,
    subject_context: str,
    student_id: str | None,
    student_name: str | None,
) -> Path:
    student_slug = slugify_student(student_id, student_name)
    normal_name = normalize_pdf_display_name(template.name)
    return review_redo_render_dir(
        context_root=context_root,
        student_slug=student_slug,
        subject_context=subject_context,
        normal_name=normal_name,
    )


def ensure_review_redo_images(
    *,
    context_root: Path,
    source_pdf: Path,
    unit_dir: Path,
    dpi_scale: float = 2.0,
) -> tuple[list[dict[str, Any]], str]:
    rendered_dir = unit_dir / "rendered_pages"
    if review_redo_cache_is_stale(source_pdf=source_pdf, rendered_dir=rendered_dir):
        render_review_redo_pages(
            source_pdf=source_pdf,
            unit_dir=unit_dir,
            dpi_scale=dpi_scale,
            clean_existing=True,
        )

    images = list_review_redo_images(context_root=context_root, unit_dir=unit_dir)
    rendered_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return images, rendered_at
