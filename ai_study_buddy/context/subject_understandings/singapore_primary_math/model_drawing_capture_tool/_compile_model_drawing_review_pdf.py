#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent
CAPTURE_ROOT = ROOT / "output" / "model_drawing_captures"
OUT_PDF = ROOT / "output" / "model_drawing_review_compiled.pdf"

# Used only to read MediaBox from one chapter PDF (same book folder as browser "Open folder").
DEFAULT_CHAPTER_PDF_DIR = Path(
    "/Users/jarodm/Library/CloudStorage/GoogleDrive-genrong.meng@gmail.com/My Drive/DaydreamEdu/template/Singapore Primary Math/P6/Book/Model Drawing Made Easy and Inspiring for P5 and P6"
)

OUTPUT_DPI = 300
MARGIN_X = 36
MARGIN_Y = 30
GAP = 18
HEADER_TO_BODY_GAP = 20


def unit_sort_key(p: Path) -> tuple[int, str]:
    m = re.match(r"^(\d+)", p.name)
    return (int(m.group(1)) if m else 999999, p.name)


def load_png(path: Path) -> Image.Image:
    img = Image.open(path)
    return img.convert("RGB")


def pt_to_px(value_pt: float) -> int:
    return round(value_pt * OUTPUT_DPI / 72.0)


def resolve_source_pdf_root() -> Path:
    if len(sys.argv) > 1:
        p = Path(sys.argv[1]).expanduser().resolve()
        if not p.is_dir():
            raise SystemExit(f"Not a directory: {p}")
        return p
    env = os.environ.get("MODEL_DRAWING_CHAPTER_PDF_DIR", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if not p.is_dir():
            raise SystemExit(f"$MODEL_DRAWING_CHAPTER_PDF_DIR is not a directory: {p}")
        return p
    if DEFAULT_CHAPTER_PDF_DIR.is_dir():
        return DEFAULT_CHAPTER_PDF_DIR
    raise SystemExit(
        "Need the book folder that contains chapter PDFs (for page size).\n"
        "  python3 _compile_model_drawing_review_pdf.py /path/to/book/folder\n"
        "  or: MODEL_DRAWING_CHAPTER_PDF_DIR=/path/to/book/folder\n"
        f"  Default tried: {DEFAULT_CHAPTER_PDF_DIR}"
    )


def get_reference_page_size_px(src_root: Path | None = None) -> tuple[int, int]:
    root = src_root if src_root is not None else resolve_source_pdf_root()
    pdfs = sorted(root.glob("_c_*.pdf"))
    if not pdfs:
        pdfs = sorted(root.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in: {root}")

    reader = PdfReader(str(pdfs[0]))
    if not reader.pages:
        raise SystemExit(f"Reference PDF has no pages: {pdfs[0]}")
    mb = reader.pages[0].mediabox
    # Convert PDF points (1/72 inch) to output pixels at OUTPUT_DPI.
    w_pt = float(mb.right) - float(mb.left)
    h_pt = float(mb.top) - float(mb.bottom)
    return max(1, pt_to_px(w_pt)), max(1, pt_to_px(h_pt))


def render_page_one(unit_name: str, stem_img: Image.Image, page_size: tuple[int, int]) -> Image.Image:
    font = ImageFont.load_default()
    margin_x = pt_to_px(MARGIN_X)
    margin_y = pt_to_px(MARGIN_Y)
    header_gap = pt_to_px(HEADER_TO_BODY_GAP)
    header_probe = Image.new("RGB", (10, 10), "white")
    probe_draw = ImageDraw.Draw(header_probe)
    header_bbox = probe_draw.textbbox((0, 0), f"Unit {unit_name}", font=font)
    header_h = header_bbox[3] - header_bbox[1]

    w, h = page_size
    page = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(page)
    draw.text((margin_x, margin_y), f"Unit {unit_name}", fill=(0, 0, 0), font=font)
    y = margin_y + header_h + header_gap
    # Paste at native resolution without scaling; any overflow is intentionally clipped.
    page.paste(stem_img, (margin_x, y))
    return page


def render_page_two(unit_name: str, example_imgs: list[Image.Image], page_size: tuple[int, int]) -> Image.Image:
    font = ImageFont.load_default()
    title = f"Unit {unit_name} — Example model(s)"
    margin_x = pt_to_px(MARGIN_X)
    margin_y = pt_to_px(MARGIN_Y)
    header_gap = pt_to_px(HEADER_TO_BODY_GAP)
    gap_px = pt_to_px(GAP)

    header_probe = Image.new("RGB", (10, 10), "white")
    probe_draw = ImageDraw.Draw(header_probe)
    header_bbox = probe_draw.textbbox((0, 0), title, font=font)
    header_h = header_bbox[3] - header_bbox[1]

    w, h = page_size
    page = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(page)
    draw.text((margin_x, margin_y), title, fill=(0, 0, 0), font=font)

    y = margin_y + header_h + header_gap
    for img in example_imgs:
        # Paste at native resolution (no resizing).
        page.paste(img, (margin_x, y))
        y += img.height + gap_px
    return page


def main() -> None:
    if not CAPTURE_ROOT.exists():
        raise SystemExit(f"Capture folder not found: {CAPTURE_ROOT}")

    src_root = resolve_source_pdf_root()
    print(f"Reference PDF folder: {src_root}")
    page_size = get_reference_page_size_px(src_root)
    print(
        "Using fixed page size at "
        f"{OUTPUT_DPI} dpi (px): {page_size[0]} x {page_size[1]}"
    )

    unit_dirs = sorted([p for p in CAPTURE_ROOT.iterdir() if p.is_dir()], key=unit_sort_key)
    pages: list[Image.Image] = []
    skipped = []

    for unit_dir in unit_dirs:
        stems = sorted(unit_dir.glob("stem*.png"))
        examples = sorted(unit_dir.glob("example_*.png"))
        if not stems:
            skipped.append((unit_dir.name, "no stem"))
            continue
        if not examples:
            skipped.append((unit_dir.name, "no examples"))
            continue

        stem_img = load_png(stems[0])
        example_imgs = [load_png(p) for p in examples]

        pages.append(render_page_one(unit_dir.name, stem_img, page_size))
        pages.append(render_page_two(unit_dir.name, example_imgs, page_size))

    if not pages:
        raise SystemExit("No pages generated. Check capture folders.")

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(OUT_PDF, save_all=True, append_images=pages[1:], resolution=OUTPUT_DPI)

    print(f"Wrote: {OUT_PDF}")
    print(f"Units included: {len(pages) // 2}")
    if skipped:
        print(f"Units skipped: {len(skipped)}")
        for name, reason in skipped[:20]:
            print(f"  - {name}: {reason}")
        if len(skipped) > 20:
            print(f"  ... and {len(skipped) - 20} more")


if __name__ == "__main__":
    main()

