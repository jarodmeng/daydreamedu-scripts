#!/usr/bin/env python3
"""
Extract (index_number, character) pairs from 冯氏早教识字卡 scanned PDFs.

Card format assumptions:
- 2 pages per character/card
- page 1: big Chinese character
- page 2: index number printed in the TOP-RIGHT corner

This script:
1) Renders each page to PNGs (via `pdftoppm`)
2) OCRs:
   - page 1 center region using tesseract + chi_sim, single-character mode
   - page 2 top-right corner using tesseract digits mode
3) Prints:
   - how many characters (cards)
   - their indices
   - their characters

Requirements (already present on your machine based on earlier checks):
- `pdftoppm` (poppler)
- `tesseract`
- Python: Pillow

We vendor `chi_sim.traineddata` under: chinese_chr_app/tessdata/chi_sim.traineddata
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional, Tuple

from PIL import Image, ImageOps


@dataclass(frozen=True)
class CardResult:
    card_idx: int  # 1-based card sequence within the PDF
    page1: int  # 1-based page number in the PDF
    page2: int  # 1-based page number in the PDF
    index_number: Optional[int]
    character: Optional[str]


def _run(cmd: List[str], *, env: Optional[dict] = None) -> str:
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  exit: {p.returncode}\n"
            f"  stderr:\n{p.stderr.strip()}\n"
        )
    return p.stdout


def pdf_page_count(pdf_path: Path) -> int:
    out = _run(["pdfinfo", str(pdf_path)])
    m = re.search(r"^Pages:\s+(\d+)\s*$", out, flags=re.MULTILINE)
    if not m:
        raise RuntimeError("Could not parse page count from pdfinfo output.")
    return int(m.group(1))


def render_page_to_png(pdf_path: Path, page_num: int, out_dir: Path, *, dpi: int = 250) -> Path:
    """
    Renders a single page to PNG using pdftoppm.
    Output filename: p{page_num}.png
    """
    out_prefix = out_dir / f"p{page_num}"
    _run(
        [
            "pdftoppm",
            "-f",
            str(page_num),
            "-l",
            str(page_num),
            "-png",
            "-r",
            str(dpi),
            str(pdf_path),
            str(out_prefix),
        ]
    )
    # pdftoppm outputs suffix like: p{page_num}-<page>.png, but for single page it's "-{page_num}.png"
    # Example: prefix "p2" with page 2 -> "p2-2.png"
    candidate = out_dir / f"p{page_num}-{page_num}.png"
    if candidate.exists():
        return candidate
    # Fallback: find any matching
    matches = sorted(out_dir.glob(f"p{page_num}-*.png"))
    if not matches:
        raise RuntimeError(f"Failed to render page {page_num} to PNG.")
    return matches[0]


def render_pdf_to_pngs(pdf_path: Path, out_dir: Path, *, dpi: int) -> Dict[int, Path]:
    """
    Render the *entire* PDF to PNGs with a single `pdftoppm` call (much faster than per-page calls).

    Produces files like: page-1.png, page-2.png, ...
    """
    prefix = out_dir / "page"
    _run(["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(prefix)])
    pages: Dict[int, Path] = {}
    for p in sorted(out_dir.glob("page-*.png")):
        m = re.search(r"page-(\d+)\.png$", p.name)
        if not m:
            continue
        pages[int(m.group(1))] = p
    if not pages:
        raise RuntimeError("Failed to render PDF pages to PNGs.")
    return pages


def _prep_for_ocr(img: Image.Image) -> Image.Image:
    # Simple preprocessing: grayscale + autocontrast.
    g = ImageOps.grayscale(img)
    g = ImageOps.autocontrast(g)
    return g


def _tight_bbox_from_dark_strokes(gray: Image.Image, *, stroke_threshold: int = 40) -> Optional[Tuple[int, int, int, int]]:
    """
    Find a tight bounding box around dark strokes.

    Strategy:
    - Invert grayscale so black strokes become bright
    - Threshold to keep only "stroke" pixels
    - getbbox() on the thresholded image
    """
    inv = ImageOps.invert(gray)
    mask = inv.point(lambda p: 255 if p > stroke_threshold else 0)
    return mask.getbbox()


def _crop_pad(gray: Image.Image, bbox: Tuple[int, int, int, int], *, pad_frac: float = 0.08) -> Image.Image:
    w, h = gray.size
    l, t, r, b = bbox
    pad = int(max(r - l, b - t) * pad_frac)
    l = max(0, l - pad)
    t = max(0, t - pad)
    r = min(w, r + pad)
    b = min(h, b + pad)
    return gray.crop((l, t, r, b))


def _binarize(gray: Image.Image, *, threshold: int = 180) -> Image.Image:
    return gray.point(lambda p: 255 if p > threshold else 0)


def _tesseract_ocr(
    img: Image.Image,
    *,
    lang: str,
    psm: int,
    extra_args: List[str],
    tessdata_dir: Optional[Path],
) -> str:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        in_png = td_path / "in.png"
        out_base = td_path / "out"
        img.save(in_png)
        env = dict(os.environ)
        # Only override tessdata location when we need a non-system language pack (e.g. chi_sim).
        # If we override it for 'eng', tesseract will fail unless eng.traineddata exists in that dir.
        if tessdata_dir is not None:
            env["TESSDATA_PREFIX"] = str(tessdata_dir)
        else:
            # Ensure we don't inherit a previously-set TESSDATA_PREFIX from the shell.
            # Explicitly point to a common system tessdata dir so 'eng' works reliably.
            env.pop("TESSDATA_PREFIX", None)
            for candidate in (
                "/usr/local/share/tessdata",
                "/opt/homebrew/share/tessdata",
                "/usr/share/tessdata",
            ):
                if Path(candidate).exists():
                    env["TESSDATA_PREFIX"] = candidate
                    break
        _run(
            [
                "tesseract",
                str(in_png),
                str(out_base),
                "-l",
                lang,
                "--psm",
                str(psm),
                *extra_args,
            ],
            env=env,
        )
        txt = (td_path / "out.txt").read_text(encoding="utf-8", errors="replace")
        return txt.strip()


OcrMode = Literal["fast", "balanced", "accurate"]


def ocr_index_number(page2_png: Path, prev_index: Optional[int], mode: OcrMode) -> Optional[int]:
    """
    OCR the top-right corner digits.
    """
    img = Image.open(page2_png)
    w, h = img.size
    def build_crop(x0: float, x1: float, y1: float) -> Image.Image:
        roi = img.crop((int(w * x0), 0, int(w * x1), int(h * y1)))
        gray = _prep_for_ocr(roi)
        bbox = _tight_bbox_from_dark_strokes(gray, stroke_threshold=35)
        crop = _crop_pad(gray, bbox, pad_frac=0.18) if bbox else gray
        # Upscale to help tesseract distinguish thin strokes in the small top-right number.
        return crop.resize((crop.size[0] * 4, crop.size[1] * 4))

    # Tight far-right crop avoids pinyin text (helps cases like "shan 54").
    crop_tight = build_crop(0.78, 0.93, 0.20)
    # More generous crop helps cases where digits sit further left.
    crop_wide = build_crop(0.62, 0.93, 0.24)

    def ocr_digits(lang: str, crop: Image.Image) -> List[int]:
        txt = _tesseract_ocr(
            crop,
            lang=lang,
            psm=7,
            extra_args=[
                "-c",
                "tessedit_char_whitelist=0123456789",
            ],
            tessdata_dir=None,
        )
        nums: List[int] = []
        for s in re.findall(r"(\d+)", txt):
            try:
                n = int(s)
            except ValueError:
                continue
            if 1 <= n <= 9999:
                nums.append(n)
        return nums

    def pick_best(cands: List[int]) -> Optional[int]:
        if not cands:
            return None
        if prev_index is None:
            return max(cands)
        target = prev_index + 1
        return min(cands, key=lambda n: (abs(n - target), n))

    # 1) Try eng on tight crop (often enough, and fast).
    best = pick_best(ocr_digits("eng", crop_tight))
    if best is not None:
        # If we have a previous index, ensure we're not wildly off; otherwise accept.
        if prev_index is None or abs(best - (prev_index + 1)) <= 3:
            return best

    # 2) Try eng on wide crop.
    best = pick_best(ocr_digits("eng", crop_wide))
    if best is not None and (prev_index is None or abs(best - (prev_index + 1)) <= 3):
        return best

    if mode == "fast":
        return best

    # 3) Fall back to snum (digits-focused) only when needed.
    best_snum = pick_best(ocr_digits("snum", crop_tight))
    if best_snum is not None:
        return best_snum
    return pick_best(ocr_digits("snum", crop_wide))


def _most_frequent_cjk(text: str) -> Optional[str]:
    counts: Dict[str, int] = {}
    for ch in re.findall(r"[\u4e00-\u9fff]", text):
        counts[ch] = counts.get(ch, 0) + 1
    if not counts:
        return None
    # Prefer highest frequency; tie-breaker by Unicode codepoint for stability.
    return max(counts.items(), key=lambda kv: (kv[1], ord(kv[0])))[0]


def _ocr_first_cjk(img: Image.Image, *, psm: int, tessdata_dir: Path) -> Optional[str]:
    txt = _tesseract_ocr(
        img,
        lang="chi_sim",
        psm=psm,
        extra_args=[],
        tessdata_dir=tessdata_dir,
    )
    m = re.search(r"([\u4e00-\u9fff])", txt)
    return m.group(1) if m else None


def _ocr_back_big_glyph(page2_png: Path, tessdata_dir: Path) -> Optional[str]:
    """
    Back page has the large glyph near the top-left (much cheaper than OCRing full back-page text).
    """
    img = Image.open(page2_png)
    w, h = img.size
    # The exact glyph placement varies a bit. Try a couple crops; prefer excluding the pinyin line.
    rois = [
        # Skip the pinyin line; includes large glyph + some repeated wordlist items.
        img.crop((0, int(h * 0.18), int(w * 0.45), int(h * 0.72))),
        # Slightly smaller ROI focusing more on the left side.
        img.crop((0, int(h * 0.18), int(w * 0.38), int(h * 0.62))),
    ]
    for roi in rois:
        # PSM=6 gives us multiple words; pick the most frequent CJK in that region
        # (the target character repeats many times, e.g. 山头/山东/高山...).
        txt = _tesseract_ocr(
            roi,
            lang="chi_sim",
            psm=6,
            extra_args=[],
            tessdata_dir=tessdata_dir,
        )
        best = _most_frequent_cjk(txt)
        if best:
            return best
    return None


def ocr_character(page1_png: Path, page2_png: Path, tessdata_dir: Path, mode: OcrMode) -> Optional[str]:
    """
    OCR the large center character.
    """
    # Important: grayscale preprocessing makes some glyphs (e.g. 飞) mis-OCR.
    # Use the raw page image and try a few PSMs (some glyphs like 儿 behave better under 6/7).
    img = Image.open(page1_png)

    # Fast path: two-pass agreement.
    ch8 = _ocr_first_cjk(img, psm=8, tessdata_dir=tessdata_dir)
    ch10 = _ocr_first_cjk(img, psm=10, tessdata_dir=tessdata_dir)
    if ch8 and ch10 and ch8 == ch10:
        return ch8
    if mode == "fast":
        return ch10 or ch8

    # If the two quick passes disagree, trust the back-page signal (repeats the target in word list).
    if ch8 and ch10 and ch8 != ch10:
        back = _ocr_back_big_glyph(page2_png, tessdata_dir)
        if back:
            return back
        # No back signal; fall back to ch10 as a default.
        return ch10

    # Balanced/accurate: try a couple more cheap PSMs to handle edge cases like 儿.
    ch6 = _ocr_first_cjk(img, psm=6, tessdata_dir=tessdata_dir)
    # Only use ch6 if it supports an existing candidate (not just agreeing with ch10 which can be wrong).
    if ch6 and ch8 and ch6 == ch8:
        return ch6
    if ch10:
        # ch10 tends to be good for most, but can still be wrong for some; validate via back glyph when available.
        back = _ocr_back_big_glyph(page2_png, tessdata_dir)
        if back and back != ch10:
            return back
        return ch10

    # If we got here, fall back to back glyph OCR.
    back = _ocr_back_big_glyph(page2_png, tessdata_dir)
    if back:
        return back
    if mode == "accurate":
        # Last resort: OCR full back page and choose most frequent CJK.
        back_img = Image.open(page2_png)
        back_txt = _tesseract_ocr(
            back_img,
            lang="chi_sim",
            psm=6,
            extra_args=[],
            tessdata_dir=tessdata_dir,
        )
        return _most_frequent_cjk(back_txt)
    return ch8


def extract_cards(pdf_path: Path, *, dpi: int, tessdata_dir: Path, mode: OcrMode) -> List[CardResult]:
    pages = pdf_page_count(pdf_path)
    if pages % 2 != 0:
        raise RuntimeError(f"Expected even page count (2 pages per card), got {pages}.")

    results: List[CardResult] = []
    prev_index: Optional[int] = None
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        pngs = render_pdf_to_pngs(pdf_path, out_dir, dpi=dpi)
        for card_i, (p1, p2) in enumerate(zip(range(1, pages + 1, 2), range(2, pages + 1, 2)), start=1):
            p1_png = pngs[p1]
            p2_png = pngs[p2]
            idx = ocr_index_number(p2_png, prev_index, mode)
            ch = ocr_character(p1_png, p2_png, tessdata_dir, mode)
            if idx is not None:
                prev_index = idx
            results.append(CardResult(card_idx=card_i, page1=p1, page2=p2, index_number=idx, character=ch))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract indices + characters from 冯氏早教识字卡 PDFs.")
    parser.add_argument("pdf", type=str, help="Path to input PDF (absolute or relative).")
    parser.add_argument("--dpi", type=int, default=300, help="Render DPI for OCR (default: 300).")
    parser.add_argument(
        "--mode",
        choices=["fast", "balanced", "accurate"],
        default="balanced",
        help="OCR mode: fast (fewer retries), balanced (default), accurate (more fallbacks).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON to stdout (default is a readable text table).",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    script_dir = Path(__file__).resolve().parent
    tessdata_dir = script_dir / "tessdata"
    if not (tessdata_dir / "chi_sim.traineddata").exists():
        raise SystemExit(f"Missing chi_sim.traineddata at: {tessdata_dir / 'chi_sim.traineddata'}")

    cards = extract_cards(pdf_path, dpi=args.dpi, tessdata_dir=tessdata_dir, mode=args.mode)

    if args.json:
        payload = {
            "pdf": str(pdf_path),
            "count": len(cards),
            "cards": [
                {
                    "card_idx": c.card_idx,
                    "page1": c.page1,
                    "page2": c.page2,
                    "index_number": c.index_number,
                    "character": c.character,
                }
                for c in cards
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"PDF: {pdf_path}")
        print(f"Cards (characters): {len(cards)}")
        print("")
        print("card_idx  index  char  pages")
        print("--------  -----  ----  -----")
        for c in cards:
            idx = "" if c.index_number is None else str(c.index_number)
            ch = "" if c.character is None else c.character
            print(f"{c.card_idx:>7}  {idx:>5}  {ch:>4}  {c.page1}-{c.page2}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

