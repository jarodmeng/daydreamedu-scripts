#!/usr/bin/env python3
"""
detect_primary_math_practice_book.py

Detect printed page numbers from scanned Primary Math practice-book PDFs (common orange footer "pill").
Designed to be batch-friendly from shell scripts.

Typical usage:
  python detect_primary_math_practice_book.py input.pdf -o page_numbers.csv
  python detect_primary_math_practice_book.py input.pdf -o page_numbers.csv --debug-dir debug_imgs

Batch example (bash):
  for f in *.pdf; do
    python detect_primary_math_practice_book.py "$f" -o "${f%.pdf}.page_numbers.csv" --infer-missing
  done

Requirements (pip):
  pip install pymupdf opencv-python numpy pytesseract pandas

Also install Tesseract OCR binary:
  - macOS: brew install tesseract
  - Ubuntu/Debian: sudo apt-get install tesseract-ocr

Notes:
- This script renders PDF pages with PyMuPDF (fitz), detects the orange "pill" region near the bottom,
  isolates white digits, and OCRs them with a digits-only whitelist.
- If some pages are missed, --infer-missing can fill gaps using a robust offset estimated from successful pages.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import json
from dataclasses import dataclass, asdict
from typing import Optional, Tuple, List, Dict

import numpy as np

try:
    import fitz  # PyMuPDF
except Exception as e:
    raise SystemExit("Missing dependency PyMuPDF. Install with: pip install pymupdf") from e

try:
    import cv2
except Exception as e:
    raise SystemExit("Missing dependency opencv-python. Install with: pip install opencv-python") from e

try:
    import pytesseract
except Exception as e:
    raise SystemExit("Missing dependency pytesseract. Install with: pip install pytesseract") from e

try:
    import pandas as pd
except Exception:
    pd = None  # optional


DIGITS_RE = re.compile(r"\d+")


@dataclass
class PageNumberResult:
    pdf_page: int                 # 1-indexed
    printed_page_raw: Optional[str]
    printed_page: Optional[int]
    method: str                   # ocr_pill_br, ocr_pill_bl, ocr_corner_br, inferred, missing
    confidence_hint: Optional[float] = None
    pill_bbox_xyxy: Optional[Tuple[int, int, int, int]] = None  # x0,y0,x1,y1 in page image pixels


def _is_plausible_page_number(val: int, *, min_page: int, max_page: int) -> bool:
    return min_page <= val <= max_page


def _parse_page_number_from_ocr(raw: str) -> Optional[int]:
    """
    Parse a page number from OCR output.

    Handles cases like "5 0" where tesseract may split digits into separate tokens.
    Does NOT apply min/max filtering; caller should do plausibility checks.
    """
    raw = (raw or "").strip()
    if not raw:
        return None

    groups = re.findall(r"\d+", raw)
    if not groups:
        return None

    candidates: List[str] = []
    candidates.extend(groups)

    # If OCR split digits with spaces (e.g., "5 0"), and all groups are single-digit,
    # allow concatenating them into a multi-digit candidate.
    if 1 < len(groups) <= 3 and all(len(g) == 1 for g in groups):
        candidates.append("".join(groups))

    # Prefer longer (more digits) candidates first (e.g., "50" over "5").
    candidates.sort(key=len, reverse=True)
    for c in candidates:
        try:
            return int(c)
        except ValueError:
            continue
    return None


def _ensure_dir(path: Optional[str]) -> None:
    if path:
        os.makedirs(path, exist_ok=True)


def _render_page(doc: fitz.Document, page_index0: int, dpi: int) -> np.ndarray:
    """Render a PDF page to BGR uint8 image."""
    page = doc.load_page(page_index0)
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    # PyMuPDF gives RGB; OpenCV uses BGR
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return img


def _crop_region(img: np.ndarray, region: Tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = region
    x0 = max(0, min(img.shape[1], x0))
    x1 = max(0, min(img.shape[1], x1))
    y0 = max(0, min(img.shape[0], y0))
    y1 = max(0, min(img.shape[0], y1))
    if x1 <= x0 or y1 <= y0:
        return img[0:1, 0:1].copy()
    return img[y0:y1, x0:x1].copy()


def _detect_orange_pill(footer_img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect the orange pill within a footer crop. Returns bbox in footer-crop coordinates (x0,y0,x1,y1).
    Robust to mild shadows by using HSV threshold + morphology + largest contour selection.
    """
    hsv = cv2.cvtColor(footer_img, cv2.COLOR_BGR2HSV)

    # Orange range tuned for the "Primary Math" footer pill.
    # May need adjustment for different scanners.
    lower = np.array([5, 70, 70])     # H,S,V
    upper = np.array([25, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    # Clean up mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Choose the largest plausible contour by area, with aspect ratio filtering
    h, w = footer_img.shape[:2]
    best = None
    best_score = 0.0
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        area = cw * ch
        if area < 0.002 * (w * h):
            continue
        ar = cw / max(1, ch)
        # pill often wide-ish but could be near-square
        if ar < 0.6 or ar > 6.0:
            continue
        # score: area with mild preference for being near bottom
        bottomness = (y + ch) / max(1, h)
        score = area * (0.5 + 0.5 * bottomness)
        if score > best_score:
            best_score = score
            best = (x, y, x + cw, y + ch)
    return best


def _extract_digits_roi(pill_img: np.ndarray) -> np.ndarray:
    """
    From the pill crop, isolate white digits.
    Strategy:
    1) Prefer HSV-based "light/low-saturation" mask (digits are white-on-orange, but scans vary).
    2) Filter connected components to keep only plausible digit blobs.
    3) Tight-crop to remaining components, upscale, binarize, and invert to black-on-white for OCR.
    """
    hsv = cv2.cvtColor(pill_img, cv2.COLOR_BGR2HSV)
    # White-ish: low saturation, high value
    s = hsv[:, :, 1].astype(np.float32)
    v = hsv[:, :, 2].astype(np.float32)

    # Slightly relaxed adaptive thresholds: scanners can tint the digits so fixed thresholds miss them.
    # Keep saturation "low-ish" and value "high-ish" within the pill crop.
    s_thresh = float(min(160.0, max(85.0, np.percentile(s, 60))))
    v_thresh = float(min(240.0, max(145.0, np.percentile(v, 78))))

    mask = ((s <= s_thresh) & (v >= v_thresh)).astype(np.uint8) * 255

    # Morphology to connect digit strokes
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    # Too much closing can merge adjacent digits (e.g., "49" becomes one blob).
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    # Connected-component filtering: keep only digit-like blobs.
    # This avoids picking up big bright areas or scanner artifacts.
    num_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    h, w = mask.shape[:2]
    kept = np.zeros_like(mask)
    for i in range(1, num_labels):
        x, y, cw, ch, area = stats[i]
        if area < 20:
            continue
        # Exclude very large components (often the circle edge / pill edge)
        if area > int(0.08 * w * h):
            continue
        ar = cw / max(1, ch)
        # Exclude very long bars (top/bottom borders) and extreme shapes
        if ar < 0.25 or ar > 3.5:
            continue
        # Digits should not touch the crop border; border-touching blobs are usually arcs/edges.
        if x <= 1 or y <= 1 or (x + cw) >= (w - 1) or (y + ch) >= (h - 1):
            continue
        # Digits shouldn't be almost as tall/wide as the whole crop.
        if cw > int(0.55 * w) or ch > int(0.80 * h):
            continue
        # digits tend to live around the center-left of the pill
        cx = x + cw / 2.0
        cy = y + ch / 2.0
        if cx < 0.05 * w or cx > 0.95 * w:
            continue
        if cy < 0.05 * h or cy > 0.95 * h:
            continue
        kept[labels == i] = 255

    # If we filtered everything out, fall back to the original mask.
    if int(np.count_nonzero(kept)) >= 10:
        mask = kept

    # Break tiny bridges between digits while keeping strokes.
    # Use a small opening on the mask (works well for "49" cases).
    small = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, small, iterations=1)

    # Tight crop around white components
    ys, xs = np.where(mask > 0)
    if len(xs) < 10:
        # fallback to full pill
        roi = mask
    else:
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        pad = 10
        x0, x1 = max(0, x0 - pad), min(mask.shape[1], x1 + pad)
        y0, y1 = max(0, y0 - pad), min(mask.shape[0], y1 + pad)
        roi = mask[y0:y1, x0:x1]

    # Upscale to help OCR
    roi = cv2.resize(roi, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC)
    # Binarize
    _, roi = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Tesseract generally prefers black text on white background.
    roi = 255 - roi
    # Add a white border to avoid edge-clipping.
    roi = cv2.copyMakeBorder(roi, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
    return roi


def _ocr_digits(
    bin_img: np.ndarray,
    *,
    min_page: int,
    max_page: int,
) -> Tuple[Optional[int], str]:
    """
    OCR digits from a binarized image. Returns (value, raw_text).
    Uses digits whitelist and a page segmentation mode that works on small snippets.
    """
    # Try a few modes; small badge digits can vary with scan quality.
    # For small numeric snippets, telling tesseract "numeric mode" helps.
    # We also try to pick the best candidate by confidence if possible.
    configs = [
        "--oem 1 --psm 10 -c tessedit_char_whitelist=0123456789 -c classify_bln_numeric_mode=1",
        "--oem 1 --psm 8  -c tessedit_char_whitelist=0123456789 -c classify_bln_numeric_mode=1",
        "--oem 1 --psm 7  -c tessedit_char_whitelist=0123456789 -c classify_bln_numeric_mode=1",
        "--oem 1 --psm 11 -c tessedit_char_whitelist=0123456789 -c classify_bln_numeric_mode=1",
    ]
    # Use a simple scoring system:
    # - Prefer candidates within min/max.
    # - Prefer longer digit strings (e.g., "50" over "5").
    # - Prefer higher tesseract confidence when available (optional).
    best_val: Optional[int] = None
    best_raw: str = ""
    best_score: float = -1.0

    def consider(val: Optional[int], raw: str, conf: Optional[float]) -> None:
        nonlocal best_val, best_raw, best_score
        if val is None:
            return
        in_range = 1.0 if _is_plausible_page_number(val, min_page=min_page, max_page=max_page) else 0.0
        digits = len(str(val))
        c = float(conf) if conf is not None else -1.0
        # Strongly prefer in-range values; then prefer more digits; then confidence.
        score = in_range * 1000.0 + digits * 10.0 + c
        if score > best_score:
            best_score = score
            best_val = val
            best_raw = raw

    for cfg in configs:
        # First: image_to_string (often better for tiny snippets than image_to_data)
        try:
            raw_s = pytesseract.image_to_string(bin_img, config=cfg).strip()
            val_s = _parse_page_number_from_ocr(raw_s)
            consider(val_s, raw_s, None)
        except Exception:
            pass

        # Second: image_to_data (may provide confidence but can fragment digits)
        try:
            d = pytesseract.image_to_data(bin_img, config=cfg, output_type=pytesseract.Output.DICT)
            texts = d.get("text", [])
            confs = d.get("conf", [])
            raw_d = " ".join(t for t in texts if t).strip()
            val_d = _parse_page_number_from_ocr(raw_d)

            cvals = []
            for t, c in zip(texts, confs):
                if not t:
                    continue
                try:
                    cf = float(c)
                except Exception:
                    continue
                if cf >= 0:
                    cvals.append(cf)
            conf = float(np.mean(cvals)) if cvals else None
            consider(val_d, raw_d, conf)
        except Exception:
            pass

    return best_val, best_raw


def _ocr_corner_fallback(corner_img: np.ndarray) -> Tuple[Optional[int], str]:
    """
    Fallback OCR for bottom-corner crop if pill detection fails.
    """
    gray = cv2.cvtColor(corner_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Invert if background is dark
    if th.mean() < 127:
        th = 255 - th
    config = "--oem 1 --psm 6 -c tessedit_char_whitelist=0123456789"
    raw = pytesseract.image_to_string(th, config=config).strip()
    m = DIGITS_RE.search(raw)
    if not m:
        return None, raw
    try:
        return int(m.group(0)), raw
    except ValueError:
        return None, raw


def _page_number_from_image(
    img: np.ndarray,
    pdf_page_1idx: int,
    debug_dir: Optional[str] = None,
    *,
    min_page: int = 1,
    max_page: int = 9999,
) -> PageNumberResult:
    """
    Detect printed page number on a rendered page image.
    Tries bottom-right pill, then bottom-left pill, then corner OCR fallback.
    """
    h, w = img.shape[:2]
    footer_h = int(h * 0.18)  # bottom ~18%
    footer = img[h - footer_h : h, :].copy()

    # Define bottom-right and bottom-left sub-crops within footer
    br = footer[:, int(w * 0.60):].copy()
    bl = footer[:, :int(w * 0.40)].copy()

    _ensure_dir(debug_dir)

    # Helpers to write debug images
    def dbg_write(name: str, im: np.ndarray) -> None:
        if not debug_dir:
            return
        out = os.path.join(debug_dir, f"p{pdf_page_1idx:03d}_{name}.png")
        cv2.imwrite(out, im)

    dbg_write("footer", footer)
    dbg_write("br", br)
    dbg_write("bl", bl)

    # Try BR pill
    pill = _detect_orange_pill(br)
    if pill:
        x0, y0, x1, y1 = pill
        pill_img = _crop_region(br, (x0, y0, x1, y1))
        dbg_write("pill_br", pill_img)
        digits_roi = _extract_digits_roi(pill_img)
        dbg_write("digits_roi_br", digits_roi)
        val, raw = _ocr_digits(digits_roi, min_page=min_page, max_page=max_page)
        if val is not None and _is_plausible_page_number(val, min_page=min_page, max_page=max_page):
            # Convert pill bbox to full-page coordinates
            bx0 = int(w * 0.60) + x0
            by0 = (h - footer_h) + y0
            bx1 = int(w * 0.60) + x1
            by1 = (h - footer_h) + y1
            return PageNumberResult(
                pdf_page=pdf_page_1idx,
                printed_page_raw=raw,
                printed_page=val,
                method="ocr_pill_br",
                pill_bbox_xyxy=(bx0, by0, bx1, by1),
            )

    # Try BL pill
    pill = _detect_orange_pill(bl)
    if pill:
        x0, y0, x1, y1 = pill
        pill_img = _crop_region(bl, (x0, y0, x1, y1))
        dbg_write("pill_bl", pill_img)
        digits_roi = _extract_digits_roi(pill_img)
        dbg_write("digits_roi_bl", digits_roi)
        val, raw = _ocr_digits(digits_roi, min_page=min_page, max_page=max_page)
        if val is not None and _is_plausible_page_number(val, min_page=min_page, max_page=max_page):
            bx0 = x0
            by0 = (h - footer_h) + y0
            bx1 = x1
            by1 = (h - footer_h) + y1
            return PageNumberResult(
                pdf_page=pdf_page_1idx,
                printed_page_raw=raw,
                printed_page=val,
                method="ocr_pill_bl",
                pill_bbox_xyxy=(bx0, by0, bx1, by1),
            )

    # Corner OCR fallback (BR then BL)
    # Use smaller crops close to page edges
    corner_h = int(h * 0.14)
    corner_w = int(w * 0.22)

    br_corner = img[h - corner_h : h, w - corner_w : w].copy()
    bl_corner = img[h - corner_h : h, 0 : corner_w].copy()
    dbg_write("corner_br", br_corner)
    dbg_write("corner_bl", bl_corner)

    val, raw = _ocr_corner_fallback(br_corner)
    if val is not None and _is_plausible_page_number(val, min_page=min_page, max_page=max_page):
        return PageNumberResult(pdf_page=pdf_page_1idx, printed_page_raw=raw, printed_page=val, method="ocr_corner_br")

    val, raw = _ocr_corner_fallback(bl_corner)
    if val is not None and _is_plausible_page_number(val, min_page=min_page, max_page=max_page):
        return PageNumberResult(pdf_page=pdf_page_1idx, printed_page_raw=raw, printed_page=val, method="ocr_corner_bl")

    return PageNumberResult(pdf_page=pdf_page_1idx, printed_page_raw=None, printed_page=None, method="missing")


def _robust_offset_infer(
    results: List[PageNumberResult],
    *,
    fix_outliers: bool,
    tolerance: int,
) -> List[PageNumberResult]:
    """
    Infer missing printed_page values assuming printed_page = pdf_page + offset
    where offset is stable across the document.

    Uses median offset from successfully OCR'd pages.
    """
    offsets = []
    for r in results:
        if r.printed_page is not None:
            offsets.append(r.printed_page - r.pdf_page)
    if len(offsets) < 3:
        return results  # not enough signal

    offset = int(np.median(np.array(offsets)))

    # Fill missing using offset, and optionally correct outliers to enforce a consistent monotonic sequence.
    filled = []
    for r in results:
        expected = r.pdf_page + offset
        if r.printed_page is None:
            filled.append(PageNumberResult(**{**asdict(r), "printed_page": expected, "method": "inferred"}))
            continue

        if fix_outliers and abs(r.printed_page - expected) > tolerance:
            # Treat as OCR outlier; replace with expected value.
            filled.append(PageNumberResult(**{**asdict(r), "printed_page": expected, "method": "corrected"}))
            continue

        filled.append(r)
    return filled


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect printed page numbers from scanned Primary Math practice-book PDFs.")
    ap.add_argument("pdf", help="Input scanned PDF")
    ap.add_argument("-o", "--output", required=True, help="Output CSV path")
    ap.add_argument("--dpi", type=int, default=200, help="Render DPI (default 200). Higher = better OCR, slower.")
    ap.add_argument("--max-pages", type=int, default=0, help="Process only first N pages (0 = all).")
    ap.add_argument("--debug-dir", default=None, help="Write debug images per page to this directory.")
    ap.add_argument("--infer-missing", action="store_true", help="Infer missing page numbers using robust offset.")
    ap.add_argument("--fix-outliers", action="store_true", help="When inferring, also correct OCR outliers to match the inferred sequence.")
    ap.add_argument("--outlier-tolerance", type=int, default=2, help="Max allowed deviation from inferred page number before correcting (default 2).")
    ap.add_argument("--min-page", type=int, default=1, help="Reject OCR values smaller than this (default 1).")
    ap.add_argument("--max-page", type=int, default=500, help="Reject OCR values larger than this (default 500).")
    ap.add_argument("--json", dest="json_out", default=None, help="Optional output JSON path with full details.")
    args = ap.parse_args()

    if not os.path.exists(args.pdf):
        print(f"File not found: {args.pdf}", file=sys.stderr)
        return 2

    try:
        doc = fitz.open(args.pdf)
    except Exception as e:
        print(f"Failed to open PDF: {e}", file=sys.stderr)
        return 2

    n_pages = doc.page_count
    if args.max_pages and args.max_pages > 0:
        n_pages = min(n_pages, args.max_pages)

    results: List[PageNumberResult] = []
    for i in range(n_pages):
        pdf_page = i + 1
        img = _render_page(doc, i, dpi=args.dpi)
        r = _page_number_from_image(
            img,
            pdf_page,
            debug_dir=args.debug_dir,
            min_page=args.min_page,
            max_page=args.max_page,
        )
        results.append(r)

        # small progress indicator for batch
        if pdf_page % 10 == 0 or pdf_page == n_pages:
            ok = sum(1 for x in results if x.printed_page is not None)
            print(f"[{os.path.basename(args.pdf)}] processed {pdf_page}/{n_pages} pages (found {ok})", file=sys.stderr)

    if args.infer_missing:
        results = _robust_offset_infer(
            results,
            fix_outliers=args.fix_outliers,
            tolerance=args.outlier_tolerance,
        )

    # Write CSV
    rows = []
    for r in results:
        rows.append({
            "pdf_page": r.pdf_page,
            "printed_page": r.printed_page if r.printed_page is not None else "",
            "printed_page_raw": r.printed_page_raw if r.printed_page_raw is not None else "",
            "method": r.method,
            "pill_bbox_xyxy": json.dumps(r.pill_bbox_xyxy) if r.pill_bbox_xyxy is not None else "",
        })

    # Use pandas if available for nicer CSV; else fallback
    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    if pd is not None:
        df = pd.DataFrame(rows)
        df.to_csv(args.output, index=False)
    else:
        import csv
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)) or ".", exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in results], f, indent=2)

    found = sum(1 for r in results if r.printed_page is not None)
    missing = len(results) - found
    print(f"Done. Pages: {len(results)}  Found: {found}  Missing: {missing}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
