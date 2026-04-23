from __future__ import annotations

from pathlib import Path
from typing import Sequence

from ai_study_buddy.marking.assets.layout import (
    ANSWERS_DIRNAME,
    ATTEMPT_DIRNAME,
    FULL_PAGE_IMAGE_BASENAME_RE,
)


def _import_fitz():
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover - import-time environment guard
        raise RuntimeError("PyMuPDF dependency missing: install with `pip3 install pymupdf`") from exc
    return fitz


def _normalize_image_format(image_format: str) -> str:
    ext = image_format.strip().casefold()
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        raise ValueError("image_format must be one of: png|jpg|jpeg|webp")
    return ext


def _clean_existing_full_page_images(target_dir: Path) -> None:
    if not target_dir.is_dir():
        return
    for candidate in target_dir.iterdir():
        if not candidate.is_file():
            continue
        if FULL_PAGE_IMAGE_BASENAME_RE.match(candidate.name):
            candidate.unlink()


def _resolve_page_numbers(*, page_count: int, pages_1_based: Sequence[int] | None) -> list[int]:
    if page_count <= 0:
        return []
    if pages_1_based is None:
        return list(range(1, page_count + 1))

    if len(pages_1_based) == 0:
        raise ValueError("pages_1_based must be non-empty when provided")

    resolved: list[int] = []
    for value in pages_1_based:
        if not isinstance(value, int):
            raise ValueError("pages_1_based must contain only integers")
        if value < 1 or value > page_count:
            raise ValueError(f"pages_1_based entry out of range: {value} (valid range: 1-{page_count})")
        resolved.append(value)
    return resolved


def _render_pdf_pages_to_bundle_subdir(
    *,
    pdf_path: str | Path,
    bundle_root: str | Path,
    subdir: str,
    dpi_scale: float,
    image_format: str,
    clean_existing: bool,
    pages_1_based: Sequence[int] | None,
) -> list[Path]:
    fitz = _import_fitz()
    if dpi_scale <= 0:
        raise ValueError("dpi_scale must be > 0")

    ext = _normalize_image_format(image_format)
    source_pdf = Path(pdf_path)
    if not source_pdf.is_file():
        raise FileNotFoundError(f"PDF does not exist: {source_pdf}")

    root = Path(bundle_root)
    target_dir = root / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(source_pdf))
    try:
        page_numbers = _resolve_page_numbers(page_count=doc.page_count, pages_1_based=pages_1_based)
        if clean_existing:
            _clean_existing_full_page_images(target_dir)

        written: list[Path] = []
        matrix = fitz.Matrix(dpi_scale, dpi_scale)
        for render_index, page_1_based in enumerate(page_numbers, start=1):
            page = doc[page_1_based - 1]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            out_path = target_dir / f"page-{render_index:02d}.{ext}"
            pix.save(str(out_path))
            written.append(out_path)
        return written
    finally:
        doc.close()


def render_attempt_pdf_to_bundle(
    pdf_path: str | Path,
    bundle_root: str | Path,
    *,
    dpi_scale: float = 2.0,
    image_format: str = "png",
    clean_existing: bool = True,
) -> list[Path]:
    return _render_pdf_pages_to_bundle_subdir(
        pdf_path=pdf_path,
        bundle_root=bundle_root,
        subdir=ATTEMPT_DIRNAME,
        dpi_scale=dpi_scale,
        image_format=image_format,
        clean_existing=clean_existing,
        pages_1_based=None,
    )


def render_answers_pdf_pages_to_bundle(
    pdf_path: str | Path,
    bundle_root: str | Path,
    *,
    pages_1_based: Sequence[int],
    dpi_scale: float = 2.0,
    image_format: str = "png",
    clean_existing: bool = True,
) -> list[Path]:
    return _render_pdf_pages_to_bundle_subdir(
        pdf_path=pdf_path,
        bundle_root=bundle_root,
        subdir=ANSWERS_DIRNAME,
        dpi_scale=dpi_scale,
        image_format=image_format,
        clean_existing=clean_existing,
        pages_1_based=pages_1_based,
    )
