#!/usr/bin/env python3
"""
Split a scanned worksheet/exam PDF into per-question outputs.

Key outputs:
- pdf/Q###_<label>.pdf (multi-page PDFs if needed)
- png/Q###_<label>_pN.png (one image per segment page)
- segments_index.csv (all crop rectangles used)
- manifest.json (run settings + detected markers)

Heuristics:
- Detect question starts via OCR near the left margin
- Build vertical segments between consecutive starts
- Add top/bottom padding (configurable)
- STEM reassignment:
  If top-of-page content references "Questions X and Y", that content is duplicated
  into those questions instead of being attached to the previous question.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
import pandas as pd
import pytesseract
from PIL import Image, ImageEnhance, ImageOps
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


# ---------------------------
# Rendering
# ---------------------------
def render_pdf_to_images(pdf_path: str, out_pages_dir: str, dpi: int) -> List[str]:
    os.makedirs(out_pages_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    page_paths: List[str] = []
    for i in range(len(doc)):
        pix = doc.load_page(i).get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        path = os.path.join(out_pages_dir, f"page-{i+1:03d}.png")
        img.save(path)
        page_paths.append(path)
    return page_paths


# ---------------------------
# OCR helpers
# ---------------------------
def ocr_data(img: Image.Image) -> pd.DataFrame:
    """OCR to a dataframe of word boxes."""
    g = img.convert("L")
    g = ImageOps.autocontrast(g)
    g = ImageEnhance.Contrast(g).enhance(1.5)
    df = pytesseract.image_to_data(
        g,
        output_type=pytesseract.Output.DATAFRAME,
        config="--psm 6",
    )
    df = df.dropna(subset=["text"]).copy()
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"] != ""]
    return df


@dataclass
class Marker:
    page0: int          # 0-based page index
    key: Tuple[int, str]  # (number, suffix) where suffix '' or 'a'/'b'/...
    label: str          # e.g. '13.' or '19a'
    x: int
    y: int
    conf: float
    style: str          # dot/plain/sub


def detect_markers_on_page(img: Image.Image, page0: int) -> List[Marker]:
    """
    Detect question start markers on a page.

    Supports:
    - 'n.' at the left margin
    - 'n' (two+ digits) at the left margin
    - 'na' (e.g. 19a, 19b) at the left margin
    """
    w, _ = img.size
    df = ocr_data(img)

    line_cols = ["block_num", "par_num", "line_num"]
    markers: List[Marker] = []

    for _, g in df.groupby(line_cols):
        g2 = g.sort_values("left")
        for _, row in g2.iterrows():
            txt = str(row["text"]).strip()
            left = int(row["left"])
            top = int(row["top"])
            height = int(row["height"])
            conf = float(row.get("conf", 0))

            if not (10 <= height <= 220):
                continue

            # A: n. (match prefix; OCR may include trailing chars)
            m = re.match(r"^0*([1-9]\d{0,2})\.", txt)
            if m and left <= 0.22 * w:
                n = int(m.group(1))
                markers.append(Marker(page0, (n, ""), f"{n}.", left, top, conf, "dot"))
                break

            # C: na (subparts)
            m = re.match(r"^0*([1-9]\d{1,2})([a-zA-Z])", txt)
            if m and left <= 0.20 * w:
                n = int(m.group(1))
                s = m.group(2).lower()
                markers.append(Marker(page0, (n, s), f"{n}{s}", left, top, conf, "sub"))
                break

            # B: plain n (two+ digits) used in some sections
            m = re.match(r"^0*([1-9]\d{1,2})\b", txt)
            if m and left <= 0.16 * w:
                n = int(m.group(1))
                markers.append(Marker(page0, (n, ""), f"{n}", left, top, conf, "plain"))
                break

    # Dedup by close y (keep higher conf)
    markers.sort(key=lambda m: (m.y, m.x))
    dedup: List[Marker] = []
    for m in markers:
        hit = next((e for e in dedup if abs(e.y - m.y) < 25), None)
        if hit:
            if m.conf > hit.conf:
                hit.x, hit.y, hit.conf, hit.label, hit.key, hit.style = m.x, m.y, m.conf, m.label, m.key, m.style
        else:
            dedup.append(m)

    return dedup


def monotonic_filter(markers: List[Marker]) -> List[Marker]:
    """
    Drop non-monotonic marker keys (often false positives).
    Example: if we already saw 14., a later '3.' on the next page is likely an option number.
    """
    markers = sorted(markers, key=lambda m: (m.page0, m.y, m.x))
    out: List[Marker] = []
    prev: Optional[Tuple[int, str]] = None
    for m in markers:
        if prev is None or m.key >= prev:
            if out and out[-1].key == m.key:
                continue
            out.append(m)
            prev = m.key
        else:
            continue
    return out


def collapse_subpart_markers(markers: List[Marker], *, split_subparts: bool) -> List[Marker]:
    """
    If split_subparts is False, treat subparts like 20a/20b as part of one question 20:
    - keep only the first marker for each main question number (n)
    - normalize keys to (n, '') so subparts do not become segmentation boundaries
    """
    if split_subparts:
        return markers

    markers = sorted(markers, key=lambda m: (m.page0, m.y, m.x))
    out: List[Marker] = []
    seen_n: set[int] = set()
    for m in markers:
        n = m.key[0]
        if n in seen_n:
            # drop subsequent subpart markers (20b, 20c, ...)
            continue
        seen_n.add(n)
        # normalize marker to main question key
        m.key = (n, "")
        # normalize label too (so manifest/CSV labels don't show '20a' when it's treated as '20')
        m.label = f"{n}."
        out.append(m)
    return out


# ---------------------------
# STEM reassignment
# ---------------------------
_STEM_RE = re.compile(
    r"(?i)\b(?:for|refer to|use|based on|with reference to)\b.*?\bquestions?\b\s+([0-9]{1,3}[a-zA-Z]?)\s*(?:and|&|to|-)\s*([0-9]{1,3}[a-zA-Z]?)"
)

def ocr_text(img: Image.Image) -> str:
    g = img.convert("L")
    g = ImageOps.autocontrast(g)
    g = ImageEnhance.Contrast(g).enhance(1.6)
    return pytesseract.image_to_string(g, config="--psm 6") or ""


def parse_question_ref(text: str) -> Optional[List[Tuple[int, str]]]:
    """
    Return list of referenced question keys [(13,''), (14,'')] if text contains 'Questions 13 and 14' etc.
    """
    m = _STEM_RE.search(text)
    if not m:
        return None

    def parse_one(tok: str) -> Tuple[int, str]:
        tok = tok.strip()
        mm = re.match(r"^(\d+)([a-zA-Z]?)$", tok)
        if not mm:
            return (0, "")
        return (int(mm.group(1)), mm.group(2).lower() if mm.group(2) else "")

    a = parse_one(m.group(1))
    b = parse_one(m.group(2))
    if a[0] == 0 or b[0] == 0:
        return None

    # expand ranges e.g. 13 to 15
    if a[1] == "" and b[1] == "" and a[0] <= b[0]:
        return [(n, "") for n in range(a[0], b[0] + 1)]
    return [a, b]


# ---------------------------
# Export
# ---------------------------
def image_to_pdf_pages(image_paths: List[str], out_pdf: str) -> None:
    c = None
    for img_path in image_paths:
        img = Image.open(img_path).convert("RGB")
        w, h = img.size
        if c is None:
            c = canvas.Canvas(out_pdf, pagesize=(w, h))
        else:
            c.setPageSize((w, h))
        c.drawImage(ImageReader(img), 0, 0, width=w, height=h)
        c.showPage()
    if c is None:
        raise ValueError("No images to write")
    c.save()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="Input scanned PDF")
    ap.add_argument("--out", required=True, help="Output directory")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--top-pad", type=int, default=40)
    ap.add_argument("--bottom-pad", type=int, default=20)
    ap.add_argument("--keep-pages", action="store_true", help="Keep rendered page images")
    ap.add_argument(
        "--split-subparts",
        action="store_true",
        help="If set, keep subparts (e.g., 19a, 19b) as separate outputs. Default groups them under Q019_19.pdf.",
    )
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out)
    png_dir = os.path.join(out_dir, "png")
    pdf_dir = os.path.join(out_dir, "pdf")
    pages_dir = os.path.join(out_dir, "_pages")

    if os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    os.makedirs(png_dir, exist_ok=True)
    os.makedirs(pdf_dir, exist_ok=True)

    # 1) render
    page_paths = render_pdf_to_images(args.pdf, pages_dir, args.dpi)
    page_imgs = [Image.open(p).convert("RGB") for p in page_paths]

    # 2) markers
    markers: List[Marker] = []
    for i, img in enumerate(page_imgs):
        markers.extend(detect_markers_on_page(img, i))
    markers = monotonic_filter(markers)
    markers = collapse_subpart_markers(markers, split_subparts=args.split_subparts)

    if not markers:
        raise RuntimeError("No question markers detected. Try increasing DPI or adjusting patterns.")

    # 3) build segments
    # segments_by_qkey: map question key -> list of per-page segments (page0, x0,y0,x1,y1, role, order)
    segments_by_qkey: Dict[Tuple[int, str], List[dict]] = {}
    records: List[dict] = []

    def group_key(qkey: Tuple[int, str]) -> Tuple[int, str]:
        """
        Group subparts (e.g., (19,'a'), (19,'b')) into the same main question key (19,'')
        unless --split-subparts is enabled.
        """
        if args.split_subparts:
            return qkey
        n, _s = qkey
        return (n, "")

    def add_segment(qkey: Tuple[int, str], label: str, page0: int, x0: int, y0: int, x1: int, y1: int, role: str) -> None:
        gkey = group_key(qkey)
        seg = {"page0": page0, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "role": role, "label": label}
        segments_by_qkey.setdefault(gkey, []).append(seg)
        records.append({
            "q_index": f"{gkey[0]}{gkey[1]}",
            "label": label,
            "page": page0 + 1,
            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "width": x1 - x0, "height": y1 - y0,
            "role": role,
        })

    # Build "body" segments between consecutive markers
    for idx, m in enumerate(markers):
        start_page0 = m.page0
        start_y = m.y
        if idx < len(markers) - 1:
            n = markers[idx + 1]
            end_page0 = n.page0
            end_y = n.y
        else:
            end_page0 = len(page_imgs) - 1
            end_y = None

        qkey = m.key
        label = m.label

        for p in range(start_page0, end_page0 + 1):
            img = page_imgs[p]
            w, h = img.size
            if p == start_page0:
                y0 = max(0, start_y - (args.top_pad if start_y > 0 else 0))
            else:
                y0 = 0
            if p == end_page0:
                y1 = h if end_y is None else max(y0 + 50, end_y - args.bottom_pad)
            else:
                y1 = h
            add_segment(qkey, label, p, 0, y0, w, y1, "body")

    # 4) STEM reassignment:
    # If a page has content above its first marker, we inspect that block. If it references "Questions X and Y",
    # we attach that block to those questions (duplicated) and remove it from the previous question.
    # Implementation:
    # - For each page, find first marker start_y (if any).
    # - If start_y is reasonably below the top, crop [0..start_y-bottom_pad] and OCR text.
    # - If it references questions, we:
    #   a) Create a STEM segment for each referenced qkey using that crop.
    #   b) Remove any previous-question segment that covered that same crop area.
    #
    # NOTE: this is conservative and designed for the specific worksheet pattern you showed.
    page_first_marker: Dict[int, Marker] = {}
    for m in markers:
        if m.page0 not in page_first_marker or m.y < page_first_marker[m.page0].y:
            page_first_marker[m.page0] = m

    for p0, first in page_first_marker.items():
        if first.y <= (args.top_pad + 30):
            continue  # nothing meaningful above
        img = page_imgs[p0]
        w, h = img.size
        stem_bottom = max(0, first.y - args.bottom_pad)
        if stem_bottom < 80:
            continue

        stem_crop = img.crop((0, 0, w, stem_bottom))
        text = ocr_text(stem_crop)
        refs = parse_question_ref(text)
        if not refs:
            continue

        # Add stem segments for referenced questions
        for qkey in refs:
            add_segment(qkey, "STEM", p0, 0, 0, w, stem_bottom, "stem")

        # Remove from previous question: find any segment on page p0 that starts at y0==0 and y1==stem_bottom-ish
        # and belongs to some other qkey; it was likely assigned as continuation.
        for qkey, segs in list(segments_by_qkey.items()):
            new_segs = []
            for seg in segs:
                if seg["page0"] == p0 and seg["role"] == "body" and seg["y0"] == 0 and abs(seg["y1"] - stem_bottom) <= 40:
                    # drop this segment
                    continue
                new_segs.append(seg)
            segments_by_qkey[qkey] = new_segs

        # Also drop corresponding records rows
        records = [r for r in records if not (r["page"] == p0 + 1 and r["role"] == "body" and r["y0"] == 0 and abs(r["y1"] - stem_bottom) <= 40)]

    # 5) Export images + PDFs per qkey
    def safe_label(s: str) -> str:
        return re.sub(r"[^0-9A-Za-z]+", "", s)[:20] or "Q"

    for qkey, segs in segments_by_qkey.items():
        # order: stem first then body, each by page then y0
        segs = sorted(segs, key=lambda s: (0 if s["role"] == "stem" else 1, s["page0"], s["y0"]))
        segments_by_qkey[qkey] = segs

        # qkey is already grouped if --split-subparts is not set
        q_index_str = f"{qkey[0]}{qkey[1]}"
        base = f"Q{qkey[0]:03d}_{q_index_str}"

        png_paths: List[str] = []
        for j, seg in enumerate(segs, start=1):
            img = page_imgs[seg["page0"]]
            crop = img.crop((seg["x0"], seg["y0"], seg["x1"], seg["y1"]))
            role = seg["role"]
            if role == "stem":
                png_name = f"{base}_stem_p{j}.png"
            else:
                png_name = f"{base}_p{j}.png"
            out_png = os.path.join(png_dir, png_name)
            crop.save(out_png, "PNG")
            png_paths.append(out_png)

        out_pdf = os.path.join(pdf_dir, f"{base}.pdf")
        image_to_pdf_pages(png_paths, out_pdf)

    # 6) Write CSV + manifest
    df_out = pd.DataFrame(records)
    df_out = df_out.sort_values(["q_index", "page", "role", "y0"]).reset_index(drop=True)
    df_out.to_csv(os.path.join(out_dir, "segments_index.csv"), index=False)

    manifest = {
        "source_pdf": os.path.abspath(args.pdf),
        "dpi": args.dpi,
        "top_pad_px": args.top_pad,
        "bottom_pad_px": args.bottom_pad,
        "markers": [
            {
                "page": m.page0 + 1,
                "key": [m.key[0], m.key[1]],
                "label": m.label,
                "x": m.x,
                "y": m.y,
                "conf": m.conf,
                "style": m.style,
            }
            for m in markers
        ],
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    if not args.keep_pages:
        shutil.rmtree(pages_dir, ignore_errors=True)

    print(f"Done. Output in: {out_dir}")


if __name__ == "__main__":
    main()
