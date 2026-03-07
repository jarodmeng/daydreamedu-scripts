"""
PDF Compressor — AI Study Buddy utility.

Compresses scanned PDF files by:
  - Downsampling pages above target_dpi to target_dpi (default 150, matching Ghostscript /ebook)
  - Re-encoding JPEG pages at a lower quality (default 72)
  - Keeping 1-bit bilevel pages as 1-bit PNG (optimal format for b&w text)
  - Always preserving RGB color (teacher annotation layers use red/green)

Originals are never modified. The caller controls the output filename explicitly.

Usage (CLI — single file, output required):
    python compress_pdf.py abc.pdf --output /other/dir/abc_compressed.pdf
    python compress_pdf.py abc.pdf --output-name abc_compressed.pdf   # same dir as input
    python compress_pdf.py abc.pdf --output-name abc.pdf --force      # overwrite in place
    python compress_pdf.py abc.pdf --output out.pdf --target-dpi 300 --jpeg-quality 75
    python compress_pdf.py abc.pdf --output out.pdf --verbose
    python compress_pdf.py abc.pdf --output out.pdf --dry-run

Usage (CLI — batch mode):
    python compress_pdf.py --batch /path/to/pdfs/
    python compress_pdf.py --batch /path/to/pdfs/ --batch-prefix _c_  # custom prefix (default: _c_)

Usage (library):
    from compress_pdf import compress_pdf
    result = compress_pdf("abc.pdf", output_path="/dest/abc.pdf")
    result = compress_pdf("abc.pdf", output_name="abc_compressed.pdf")

Dependencies: pymupdf, Pillow, numpy
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pymupdf
from PIL import Image
import io


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BATCH_PREFIX = "_c_"   # used only by --batch mode when no --batch-prefix is given
DEFAULT_TARGET_DPI = 150
DEFAULT_JPEG_QUALITY = 72

# Fraction of pixels that must differ between R/G/B channels for a page to be
# considered "meaningfully colored." Used only as a diagnostic metric — we
# always preserve RGB regardless of this value.
_COLOR_SAMPLE_DIVISOR = 4  # sample at 1/16 pixels (each axis) for speed


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PageStat:
    page: int
    image_type: str       # 'bilevel_png', 'rgb_jpeg', 'gray_jpeg', 'no_image'
    original_kb: int
    compressed_kb: int
    original_dpi: int
    output_dpi: int
    color_fraction: float  # fraction of pixels with meaningful color (diagnostic)

    @property
    def savings_pct(self) -> float:
        if self.original_kb == 0:
            return 0.0
        return 100.0 * (1 - self.compressed_kb / self.original_kb)


@dataclass
class CompressResult:
    input_path: str
    output_path: str
    original_size: int        # bytes
    compressed_size: int      # bytes
    pages: int
    skipped: bool
    skip_reason: str
    page_stats: list[PageStat] = field(default_factory=list)

    @property
    def savings_pct(self) -> float:
        if self.original_size == 0:
            return 0.0
        return 100.0 * (1 - self.compressed_size / self.original_size)

    @property
    def ratio(self) -> float:
        if self.compressed_size == 0:
            return 0.0
        return self.original_size / self.compressed_size


# ---------------------------------------------------------------------------
# Core compression logic
# ---------------------------------------------------------------------------

def _color_fraction(img_rgb: Image.Image) -> float:
    """Fraction of sampled pixels with R≠G or G≠B by >20 levels."""
    w, h = img_rgb.width // _COLOR_SAMPLE_DIVISOR, img_rgb.height // _COLOR_SAMPLE_DIVISOR
    if w == 0 or h == 0:
        return 0.0
    arr = np.array(img_rgb.resize((w, h)))
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    colored = ((np.abs(r - g) > 20) | (np.abs(g - b) > 20)).sum()
    return float(colored) / (w * h)


def _compress_page(
    page: pymupdf.Page,
    doc: pymupdf.Document,
    target_dpi: int,
    jpeg_quality: int,
) -> tuple[bytes, PageStat]:
    """
    Compress a single page. Returns (compressed_image_bytes, PageStat).
    If no image is embedded, returns (b"", PageStat with type='no_image').
    """
    page_num = page.number + 1
    images = page.get_images(full=True)

    if not images:
        return b"", PageStat(
            page=page_num, image_type="no_image",
            original_kb=0, compressed_kb=0,
            original_dpi=0, output_dpi=0, color_fraction=0.0,
        )

    # Extract the primary embedded image (scanned PDFs have exactly 1 per page)
    if len(images) > 1:
        print(f"  Warning: page {page_num} has {len(images)} embedded images; using the first.",
              file=sys.stderr)

    xref = images[0][0]
    info = doc.extract_image(xref)
    orig_bytes = info["image"]
    orig_w, orig_h = info["width"], info["height"]
    is_bilevel = info["bpc"] == 1
    is_rgb = info["colorspace"] == 3

    # Compute current DPI from page dimensions (1 pt = 1/72 inch)
    page_w_pts = page.rect.width
    curr_dpi = round(orig_w / (page_w_pts / 72)) if page_w_pts > 0 else target_dpi

    img = Image.open(io.BytesIO(orig_bytes))

    # --- Downsample if above target DPI ---
    output_dpi = curr_dpi
    if curr_dpi > target_dpi:
        scale = target_dpi / curr_dpi
        new_w = round(orig_w * scale)
        new_h = round(orig_h * scale)
        resample = Image.NEAREST if is_bilevel else Image.LANCZOS
        img = img.resize((new_w, new_h), resample)
        output_dpi = target_dpi

    # --- Determine color fraction (diagnostic; does not affect output format) ---
    col_frac = 0.0
    if is_rgb:
        col_frac = _color_fraction(img.convert("RGB"))

    # --- Re-encode ---
    buf = io.BytesIO()
    if is_bilevel:
        img.convert("1").save(buf, format="PNG", optimize=True)
        image_type = "bilevel_png"
    elif is_rgb:
        # Always keep RGB — color encodes semantic layer information
        img.convert("RGB").save(buf, format="JPEG", quality=jpeg_quality,
                                optimize=True, subsampling=2)
        image_type = "rgb_jpeg"
    else:
        img.convert("L").save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
        image_type = "gray_jpeg"

    compressed = buf.getvalue()

    # Guard: if compression made it larger, keep original bytes (already optimal)
    if len(compressed) > len(orig_bytes):
        compressed = orig_bytes
        image_type += "_kept_original"

    stat = PageStat(
        page=page_num,
        image_type=image_type,
        original_kb=len(orig_bytes) // 1024,
        compressed_kb=len(compressed) // 1024,
        original_dpi=curr_dpi,
        output_dpi=output_dpi,
        color_fraction=col_frac,
    )
    return compressed, stat


def compress_pdf(
    input_path: str | os.PathLike,
    output_path: Optional[str | os.PathLike] = None,
    output_name: Optional[str] = None,
    target_dpi: int = DEFAULT_TARGET_DPI,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    force: bool = False,
) -> CompressResult:
    """
    Compress a scanned PDF and write the result to a caller-specified output path.

    Exactly one of output_path or output_name must be provided; there is no default
    output filename. This keeps naming decisions with the caller.

    Args:
        input_path:   Path to the source PDF. Never modified.
        output_path:  Full destination path for the compressed file.
        output_name:  Output filename only (no directory). The file is written next to
                      the input. Mutually exclusive with output_path.
        target_dpi:   Pages above this DPI are downsampled.
        jpeg_quality: JPEG quality for re-encoding color/grayscale pages (1–95).
        force:        If True, overwrite an existing output file.

    Returns:
        CompressResult with sizes, savings, and per-page stats.

    Raises:
        ValueError:       If neither or both of output_path/output_name are given,
                          or if the PDF is password-protected or unreadable.
        FileNotFoundError: If input_path does not exist.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # --- Resolve output path ---
    if output_path is not None and output_name is not None:
        raise ValueError("Provide output_path or output_name, not both.")
    if output_path is None and output_name is None:
        raise ValueError(
            "output_path or output_name is required. "
            "Tip: use output_name='<filename>.pdf' to write next to the input."
        )
    if output_name is not None:
        output_path = input_path.parent / output_name
    output_path = Path(output_path)

    original_size = input_path.stat().st_size

    # --- Guard: output already exists ---
    if not force and output_path.exists():
        return CompressResult(
            input_path=str(input_path),
            output_path=str(output_path),
            original_size=original_size,
            compressed_size=output_path.stat().st_size,
            pages=0,
            skipped=True,
            skip_reason=f"Output already exists: {output_path} (use force=True to override)",
        )

    # --- Open PDF ---
    try:
        doc = pymupdf.open(str(input_path))
    except Exception as exc:
        raise ValueError(f"Could not open PDF: {input_path}") from exc

    if doc.needs_pass:
        doc.close()
        raise ValueError(f"PDF is password-protected: {input_path}")

    # --- Warn if no scanned images ---
    total_images = sum(len(doc[i].get_images(full=True)) for i in range(doc.page_count))
    if total_images == 0:
        doc.close()
        import warnings
        warnings.warn(
            f"No embedded images found in {input_path}. "
            "This may be a digital (non-scanned) PDF; compression has no effect.",
            stacklevel=2,
        )
        # Still copy the file faithfully
        import shutil
        shutil.copy2(str(input_path), str(output_path))
        return CompressResult(
            input_path=str(input_path),
            output_path=str(output_path),
            original_size=original_size,
            compressed_size=original_size,
            pages=doc.page_count,
            skipped=False,
            skip_reason="No embedded images — copied as-is",
        )

    # --- Compress page by page ---
    out_doc = pymupdf.open()
    page_stats: list[PageStat] = []

    for i in range(doc.page_count):
        page = doc[i]
        compressed_bytes, stat = _compress_page(page, doc, target_dpi, jpeg_quality)
        page_stats.append(stat)

        new_page = out_doc.new_page(width=page.rect.width, height=page.rect.height)
        if compressed_bytes:
            new_page.insert_image(new_page.rect, stream=compressed_bytes)

    # --- Save ---
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_doc.save(str(output_path), garbage=4, deflate=True)
    out_doc.close()
    doc.close()

    compressed_size = output_path.stat().st_size

    return CompressResult(
        input_path=str(input_path),
        output_path=str(output_path),
        original_size=original_size,
        compressed_size=compressed_size,
        pages=len(page_stats),
        skipped=False,
        skip_reason="",
        page_stats=page_stats,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_result(result: CompressResult, verbose: bool = False) -> None:
    if result.skipped:
        print(f"  SKIPPED  {result.input_path}")
        print(f"           {result.skip_reason}")
        return

    orig_mb = result.original_size / 1024 / 1024
    comp_mb = result.compressed_size / 1024 / 1024
    print(f"  {result.input_path}")
    print(f"  → {result.output_path}")
    print(f"  {orig_mb:.1f} MB → {comp_mb:.1f} MB  "
          f"({result.savings_pct:.0f}% smaller, {result.ratio:.1f}×)  "
          f"[{result.pages} pages]")

    if verbose and result.page_stats:
        print(f"  {'Page':>4}  {'Type':<20}  {'DPI':>8}  {'Orig KB':>8}  {'Comp KB':>8}  {'Saved':>6}  {'Color':>6}")
        for s in result.page_stats:
            dpi_str = f"{s.original_dpi}→{s.output_dpi}" if s.original_dpi != s.output_dpi else str(s.output_dpi)
            print(f"  {s.page:>4}  {s.image_type:<20}  {dpi_str:>8}  {s.original_kb:>8}  "
                  f"{s.compressed_kb:>8}  {s.savings_pct:>5.0f}%  {s.color_fraction:>5.1%}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compress_pdf",
        description=(
            "Compress scanned PDF files. "
            "Single-file mode requires --output or --output-name. "
            "Batch mode uses --batch-prefix (default: _c_) to derive output names."
        ),
    )
    parser.add_argument("input", nargs="?", help="Path to the PDF to compress.")
    parser.add_argument("--output", "-o",
                        help="Full output path for the compressed file.")
    parser.add_argument("--output-name", "-n",
                        help="Output filename only; file is written next to the input.")
    parser.add_argument("--batch", "-b", metavar="DIR",
                        help="Compress all *.pdf files in DIR.")
    parser.add_argument("--batch-prefix", default=DEFAULT_BATCH_PREFIX, metavar="PREFIX",
                        help=f"Prefix prepended to each filename in batch mode "
                             f"(default: '{DEFAULT_BATCH_PREFIX}'). "
                             f"Files already starting with this prefix are skipped.")
    parser.add_argument("--target-dpi", type=int, default=DEFAULT_TARGET_DPI,
                        help=f"Downsample pages above this DPI (default: {DEFAULT_TARGET_DPI}).")
    parser.add_argument("--jpeg-quality", type=int, default=DEFAULT_JPEG_QUALITY,
                        help=f"JPEG quality for color/grayscale pages (default: {DEFAULT_JPEG_QUALITY}).")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing output file.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print projected savings without writing output.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print per-page stats.")
    return parser


def _main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.batch:
        # Batch mode: process all PDFs in a directory, deriving output name via prefix.
        batch_dir = Path(args.batch)
        if not batch_dir.is_dir():
            print(f"Error: --batch path is not a directory: {batch_dir}", file=sys.stderr)
            sys.exit(1)

        prefix = args.batch_prefix
        pdfs = sorted(p for p in batch_dir.glob("*.pdf") if not p.name.startswith(prefix))
        if not pdfs:
            print(f"No unprocessed PDFs found in {batch_dir} (none lacking prefix '{prefix}')")
            return

        total_orig = 0
        total_comp = 0
        for pdf in pdfs:
            out_name = f"{prefix}{pdf.name}"
            print(f"\n[{pdf.name}]")
            if args.dry_run:
                fd, tmp = tempfile.mkstemp(suffix=".pdf")
                os.close(fd)
                try:
                    result = compress_pdf(
                        pdf,
                        output_path=tmp,
                        target_dpi=args.target_dpi,
                        jpeg_quality=args.jpeg_quality,
                        force=True,
                    )
                    _print_result(result, verbose=args.verbose)
                    total_orig += result.original_size
                    total_comp += result.compressed_size
                finally:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
            else:
                result = compress_pdf(
                    pdf,
                    output_name=out_name,
                    target_dpi=args.target_dpi,
                    jpeg_quality=args.jpeg_quality,
                    force=args.force,
                )
                _print_result(result, verbose=args.verbose)
                total_orig += result.original_size
                total_comp += result.compressed_size

        if total_orig > 0:
            saved = 100 * (1 - total_comp / total_orig)
            print(f"\nTotal: {total_orig/1024/1024:.1f} MB → {total_comp/1024/1024:.1f} MB  ({saved:.0f}% smaller)")

    elif args.input:
        # Single file mode: --output or --output-name is required.
        if not args.output and not args.output_name:
            parser.error("Single-file mode requires --output <path> or --output-name <filename>.")

        if args.dry_run:
            fd, tmp = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            try:
                result = compress_pdf(
                    args.input,
                    output_path=tmp,
                    target_dpi=args.target_dpi,
                    jpeg_quality=args.jpeg_quality,
                    force=True,
                )
                print("(dry-run) Projected result:")
                _print_result(result, verbose=args.verbose)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        else:
            result = compress_pdf(
                args.input,
                output_path=args.output or None,
                output_name=args.output_name or None,
                target_dpi=args.target_dpi,
                jpeg_quality=args.jpeg_quality,
                force=args.force,
            )
            _print_result(result, verbose=args.verbose)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    _main()
