#!/usr/bin/env python3
"""
Detect likely exam-set first pages from handwritten circled index marks.

This works best for scanned PDFs where each exam-set first page has a circled
index number in the top-right corner. The usual workflow is:

1. Run a broad blue-ink pass over the whole PDF.
2. Review/repair the missing gaps.
3. Run targeted grayscale or dark-ink passes only on the suspicious page range.

Example blue pass:
  python3 utility_scripts/exam_pdf_pipeline/detect_exam_boundaries.py \
    "/Users/jarodm/Desktop/Books/Chinese P2 Exams.pdf" \
    --save-review /tmp/exam_review \
    --output /tmp/exam_boundaries.json

Example targeted grayscale pass:
  python3 utility_scripts/exam_pdf_pipeline/detect_exam_boundaries.py \
    "/Users/jarodm/Desktop/Books/Chinese P2 Exams.pdf" \
    --ink-mode gray \
    --start-page 120 \
    --end-page 139 \
    --min-pixels 180 \
    --save-review /tmp/exam_gray_review
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageDraw


DIGIT_RE = re.compile(r"\d+")


@dataclass
class Component:
    x0: int
    y0: int
    x1: int
    y1: int
    area: int


@dataclass
class CandidateGroup:
    bbox: tuple[int, int, int, int]
    component_count: int
    blue_pixels: int
    mask_density: float
    aspect_ratio: float
    position_score: float
    circle_score: float
    crossout_score: float
    digit_text: Optional[str]
    digit_value: Optional[int]
    digit_confidence: float
    base_score: float
    sequence_bonus: float = 0.0
    final_score: float = 0.0
    is_crossed_out: bool = False


@dataclass
class PageAnalysis:
    pdf_page: int
    candidate_groups: list[CandidateGroup] = field(default_factory=list)
    chosen_group_index: Optional[int] = None
    chosen_digit: Optional[int] = None
    chosen_score: float = 0.0
    chosen_sequence_bonus: float = 0.0
    blue_pixel_count: int = 0
    is_boundary: bool = False
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", help="Path to the input PDF")
    parser.add_argument(
        "--ink-mode",
        choices=("blue", "gray"),
        default="blue",
        help="Ink isolation mode: broad blue pass or targeted grayscale/dark-ink pass (default: blue)",
    )
    parser.add_argument("--dpi", type=int, default=140, help="Render DPI (default: 140)")
    parser.add_argument(
        "--crop",
        default="0.70,0.00,1.00,0.24",
        help="Top-right crop as fractions x0,y0,x1,y1 (default: 0.70,0.00,1.00,0.24)",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=2,
        help="First 1-based PDF page to inspect (default: 2, assuming page 1 is a cover)",
    )
    parser.add_argument(
        "--end-page",
        type=int,
        help="Last 1-based PDF page to inspect (default: last page)",
    )
    parser.add_argument(
        "--min-pixels",
        type=int,
        default=280,
        help="Minimum ink pixels in a candidate group to consider it a boundary (default: 280)",
    )
    parser.add_argument(
        "--ambiguity-threshold",
        type=float,
        default=0.90,
        help="Mark page ambiguous when top two candidate scores differ by less than this amount (default: 0.90)",
    )
    parser.add_argument("--output", help="Optional JSON output path. Defaults to stdout only.")
    parser.add_argument(
        "--save-review",
        help="Optional directory for candidate crops, overlays, and a contact sheet.",
    )
    return parser.parse_args()


def ensure_dir(path: Optional[str]) -> None:
    if path:
        os.makedirs(path, exist_ok=True)


def parse_crop(raw: str) -> tuple[float, float, float, float]:
    parts = [float(piece.strip()) for piece in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("--crop must have 4 comma-separated numbers")
    x0, y0, x1, y1 = parts
    if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
        raise ValueError("--crop values must satisfy 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1")
    return x0, y0, x1, y1


def render_page(doc: fitz.Document, page_index0: int, dpi: int) -> np.ndarray:
    page = doc.load_page(page_index0)
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()


def crop_region(image: np.ndarray, crop: tuple[float, float, float, float]) -> np.ndarray:
    h, w = image.shape[:2]
    x0 = int(round(crop[0] * w))
    y0 = int(round(crop[1] * h))
    x1 = int(round(crop[2] * w))
    y1 = int(round(crop[3] * h))
    return image[y0:y1, x0:x1].copy()


def binary_dilate(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    result = mask.astype(bool)
    for _ in range(iterations):
        padded = np.pad(result, 1, mode="constant", constant_values=False)
        neighbors = []
        for dy in range(3):
            for dx in range(3):
                neighbors.append(padded[dy:dy + result.shape[0], dx:dx + result.shape[1]])
        result = np.logical_or.reduce(neighbors)
    return result


def binary_erode(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    result = mask.astype(bool)
    for _ in range(iterations):
        padded = np.pad(result, 1, mode="constant", constant_values=False)
        neighbors = []
        for dy in range(3):
            for dx in range(3):
                neighbors.append(padded[dy:dy + result.shape[0], dx:dx + result.shape[1]])
        result = np.logical_and.reduce(neighbors)
    return result


def binary_open(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    return binary_dilate(binary_erode(mask, iterations=iterations), iterations=iterations)


def binary_close(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    return binary_erode(binary_dilate(mask, iterations=iterations), iterations=iterations)


def make_blue_mask(crop_rgb: np.ndarray) -> np.ndarray:
    r = crop_rgb[:, :, 0].astype(np.int16)
    g = crop_rgb[:, :, 1].astype(np.int16)
    b = crop_rgb[:, :, 2].astype(np.int16)
    mask = (
        (b > 110)
        & (b - g > 10)
        & (b - r > 22)
        & (g > r - 12)
    )
    mask = binary_open(mask, iterations=1)
    mask = binary_close(mask, iterations=1)
    return mask


def make_gray_mask(crop_rgb: np.ndarray) -> np.ndarray:
    r = crop_rgb[:, :, 0].astype(np.int16)
    g = crop_rgb[:, :, 1].astype(np.int16)
    b = crop_rgb[:, :, 2].astype(np.int16)
    brightness = (r + g + b) / 3.0
    chroma = np.maximum.reduce([np.abs(r - g), np.abs(r - b), np.abs(g - b)])
    mask = (brightness < 195) & (chroma < 28)
    mask = binary_open(mask, iterations=1)
    mask = binary_close(mask, iterations=1)
    return mask


def find_components(mask: np.ndarray) -> list[Component]:
    h, w = mask.shape
    visited = np.zeros((h, w), dtype=bool)
    components: list[Component] = []
    for y in range(h):
        for x in range(w):
            if visited[y, x] or not mask[y, x]:
                continue
            stack = [(x, y)]
            visited[y, x] = True
            area = 0
            x0 = x1 = x
            y0 = y1 = y
            while stack:
                cx, cy = stack.pop()
                area += 1
                x0 = min(x0, cx)
                x1 = max(x1, cx)
                y0 = min(y0, cy)
                y1 = max(y1, cy)
                for ny in range(max(0, cy - 1), min(h, cy + 2)):
                    for nx in range(max(0, cx - 1), min(w, cx + 2)):
                        if visited[ny, nx] or not mask[ny, nx]:
                            continue
                        visited[ny, nx] = True
                        stack.append((nx, ny))
            if area < 18 or area > int(0.16 * h * w):
                continue
            components.append(Component(x0, y0, x1 + 1, y1 + 1, area))
    return components


def boxes_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int], padding: int) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (
        ax1 + padding < bx0
        or bx1 + padding < ax0
        or ay1 + padding < by0
        or by1 + padding < ay0
    )


def cluster_components(components: list[Component], padding: int = 28) -> list[list[int]]:
    groups: list[list[int]] = []
    for idx, component in enumerate(components):
        bbox = (component.x0, component.y0, component.x1, component.y1)
        matches: list[int] = []
        for group_index, group in enumerate(groups):
            if any(
                boxes_overlap(
                    bbox,
                    (components[member].x0, components[member].y0, components[member].x1, components[member].y1),
                    padding,
                )
                for member in group
            ):
                matches.append(group_index)
        if not matches:
            groups.append([idx])
            continue
        first = matches[0]
        groups[first].append(idx)
        for group_index in reversed(matches[1:]):
            groups[first].extend(groups[group_index])
            del groups[group_index]
    return groups


def estimate_circle_score(group_mask: np.ndarray) -> float:
    h, w = group_mask.shape
    if h < 8 or w < 8:
        return 0.0
    ys, xs = np.where(group_mask)
    if len(xs) < 12:
        return 0.0
    cx = xs.mean()
    cy = ys.mean()
    rx = max(1.0, (xs.max() - xs.min()) / 2.0)
    ry = max(1.0, (ys.max() - ys.min()) / 2.0)
    norm = ((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2
    ring_fraction = float(np.mean((norm > 0.45) & (norm < 1.65)))
    balanced_box = max(0.0, 1.0 - abs((w / max(1.0, h)) - 1.0))
    return min(1.5, ring_fraction * 1.5 + balanced_box * 0.5)


def detect_crossout(group_mask: np.ndarray) -> float:
    ys, xs = np.where(group_mask)
    if len(xs) < 20:
        return 0.0
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    width = max(1, x1 - x0 + 1)
    height = max(1, y1 - y0 + 1)
    xn = (xs - x0) / width
    yn = (ys - y0) / height
    dist_main = np.abs(yn - xn)
    dist_anti = np.abs(yn - (1.0 - xn))
    diag_support = max(float(np.mean(dist_main < 0.08)), float(np.mean(dist_anti < 0.08)))

    centered = np.column_stack([xs - xs.mean(), ys - ys.mean()])
    cov = np.cov(centered, rowvar=False)
    eigvals = np.linalg.eigvalsh(cov)
    eigvals = np.sort(np.maximum(eigvals, 1e-6))
    linearity = float(min(4.0, eigvals[-1] / eigvals[0])) / 4.0

    return diag_support * (0.7 + 0.6 * linearity)


def normalize_digit_text(raw_text: str) -> tuple[Optional[str], Optional[int], float]:
    if not raw_text:
        return None, None, 0.0
    groups = DIGIT_RE.findall(raw_text)
    if not groups:
        return None, None, 0.0
    groups.sort(key=len, reverse=True)
    best = groups[0]
    try:
        value = int(best)
    except ValueError:
        return None, None, 0.0
    if len(best) > 3:
        return None, None, 0.0
    confidence = min(1.0, 0.45 + 0.17 * len(best))
    return best, value, confidence


def run_tesseract_ocr(image: Image.Image, psm: str) -> tuple[Optional[str], Optional[int], float]:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        temp_path = handle.name
    try:
        image.save(temp_path)
        proc = subprocess.run(
            [
                "tesseract",
                temp_path,
                "stdout",
                "--psm",
                psm,
                "-c",
                "tessedit_char_whitelist=0123456789",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return None, None, 0.0
        return normalize_digit_text(proc.stdout.strip())
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass


def ocr_group_digit(group_mask: np.ndarray) -> tuple[Optional[str], Optional[int], float]:
    ys, xs = np.where(group_mask)
    if len(xs) < 12:
        return None, None, 0.0
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    pad = 10
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(group_mask.shape[1], x1 + pad)
    y1 = min(group_mask.shape[0], y1 + pad)

    roi = (group_mask[y0:y1, x0:x1].astype(np.uint8) * 255)
    images: list[Image.Image] = []

    full_image = Image.fromarray(255 - roi, mode="L")
    images.append(full_image.resize((full_image.width * 3, full_image.height * 3), Image.Resampling.LANCZOS))

    inner_x0 = int(round(roi.shape[1] * 0.18))
    inner_x1 = int(round(roi.shape[1] * 0.82))
    inner_y0 = int(round(roi.shape[0] * 0.16))
    inner_y1 = int(round(roi.shape[0] * 0.84))
    if inner_x1 > inner_x0 and inner_y1 > inner_y0:
        inner = roi[inner_y0:inner_y1, inner_x0:inner_x1]
        inner_image = Image.fromarray(255 - inner, mode="L")
        images.append(inner_image.resize((inner_image.width * 4, inner_image.height * 4), Image.Resampling.LANCZOS))

    best: tuple[Optional[str], Optional[int], float] = (None, None, 0.0)
    for image in images:
        for psm in ("10", "8", "7"):
            result = run_tesseract_ocr(image, psm)
            if result[2] > best[2]:
                best = result
    return best


def analyze_group(
    mask: np.ndarray,
    component_indices: Iterable[int],
    components: list[Component],
) -> CandidateGroup:
    indices = list(component_indices)
    x0 = min(components[idx].x0 for idx in indices)
    y0 = min(components[idx].y0 for idx in indices)
    x1 = max(components[idx].x1 for idx in indices)
    y1 = max(components[idx].y1 for idx in indices)
    pad = 10
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(mask.shape[1], x1 + pad)
    y1 = min(mask.shape[0], y1 + pad)

    group_mask = mask[y0:y1, x0:x1]
    blue_pixels = int(np.count_nonzero(group_mask))
    area = max(1, (x1 - x0) * (y1 - y0))
    density = blue_pixels / area
    aspect_ratio = (x1 - x0) / max(1.0, (y1 - y0))

    crop_h, crop_w = mask.shape
    group_cx = ((x0 + x1) / 2.0) / max(1.0, crop_w)
    group_cy = ((y0 + y1) / 2.0) / max(1.0, crop_h)
    position_score = (group_cx * 0.78) + ((1.0 - group_cy) * 0.22)

    circle_score = estimate_circle_score(group_mask)
    crossout_score = detect_crossout(group_mask)
    digit_text, digit_value, digit_confidence = ocr_group_digit(group_mask)

    base_score = (
        (blue_pixels / 260.0)
        + position_score
        + circle_score
        + (digit_confidence * 0.85)
        - (crossout_score * 1.8)
        - max(0.0, density - 0.18) * 3.0
    )
    return CandidateGroup(
        bbox=(x0, y0, x1, y1),
        component_count=len(indices),
        blue_pixels=blue_pixels,
        mask_density=density,
        aspect_ratio=aspect_ratio,
        position_score=position_score,
        circle_score=circle_score,
        crossout_score=crossout_score,
        digit_text=digit_text,
        digit_value=digit_value,
        digit_confidence=digit_confidence,
        base_score=base_score,
        is_crossed_out=crossout_score >= 0.72,
    )


def analyze_page(
    doc: fitz.Document,
    page_number: int,
    dpi: int,
    crop: tuple[float, float, float, float],
    min_pixels: int,
    ink_mode: str,
) -> tuple[PageAnalysis, np.ndarray]:
    image = render_page(doc, page_number - 1, dpi)
    crop_rgb = crop_region(image, crop)
    if ink_mode == "gray":
        mask = make_gray_mask(crop_rgb)
    else:
        mask = make_blue_mask(crop_rgb)
    components = find_components(mask)
    groups = cluster_components(components)

    analysis = PageAnalysis(pdf_page=page_number, blue_pixel_count=int(np.count_nonzero(mask)))
    for group_indices in groups:
        group = analyze_group(mask, group_indices, components)
        if group.blue_pixels >= min_pixels:
            analysis.candidate_groups.append(group)

    analysis.candidate_groups.sort(key=lambda item: item.base_score, reverse=True)
    return analysis, crop_rgb


def apply_sequence_scoring(pages: list[PageAnalysis], ambiguity_threshold: float) -> None:
    expected_next: Optional[int] = None
    for page in pages:
        if not page.candidate_groups:
            continue

        for candidate in page.candidate_groups:
            bonus = 0.0
            if expected_next is not None and candidate.digit_value is not None:
                delta = abs(candidate.digit_value - expected_next)
                if delta == 0:
                    bonus += 2.4
                elif delta == 1:
                    bonus += 1.1
                elif delta <= 2:
                    bonus += 0.35
                else:
                    bonus -= min(2.0, 0.32 * delta)
            if candidate.is_crossed_out:
                bonus -= 0.8
            candidate.sequence_bonus = bonus
            candidate.final_score = candidate.base_score + bonus

        page.candidate_groups.sort(key=lambda item: item.final_score, reverse=True)
        best = page.candidate_groups[0]
        page.chosen_group_index = 0
        page.chosen_digit = best.digit_value
        page.chosen_score = best.final_score
        page.chosen_sequence_bonus = best.sequence_bonus
        page.is_boundary = True

        second_score = page.candidate_groups[1].final_score if len(page.candidate_groups) > 1 else None
        if len(page.candidate_groups) > 1 and second_score is not None and (best.final_score - second_score) < ambiguity_threshold:
            page.is_ambiguous = True
            page.ambiguity_reason = "top candidate margin is small"
        elif len(page.candidate_groups) > 1:
            page.is_ambiguous = True
            page.ambiguity_reason = "multiple blue annotation groups detected"
        elif best.is_crossed_out:
            page.is_ambiguous = True
            page.ambiguity_reason = "chosen candidate still shows cross-out evidence"
        elif best.crossout_score >= 0.22:
            page.is_ambiguous = True
            page.ambiguity_reason = "candidate has moderate cross-out evidence"

        if best.digit_value is not None:
            expected_next = best.digit_value + 1


def derive_ranges(start_pages: list[int], total_pages: int) -> list[dict[str, int]]:
    if not start_pages:
        return []
    ranges: list[dict[str, int]] = []
    for idx, start in enumerate(start_pages):
        end = total_pages if idx == len(start_pages) - 1 else start_pages[idx + 1] - 1
        ranges.append({"start_page": start, "end_page": end})
    return ranges


def numpy_to_pil(image: np.ndarray) -> Image.Image:
    return Image.fromarray(image.astype(np.uint8), mode="RGB")


def draw_review_overlay(image: np.ndarray, page: PageAnalysis) -> Image.Image:
    canvas = numpy_to_pil(image)
    draw = ImageDraw.Draw(canvas)
    for idx, candidate in enumerate(page.candidate_groups):
        x0, y0, x1, y1 = candidate.bbox
        color = (255, 0, 0) if idx == page.chosen_group_index else (255, 140, 0)
        draw.rectangle((x0, y0, x1, y1), outline=color, width=3)
        label = f"{idx + 1}:{candidate.digit_text or '?'}:{candidate.final_score:.2f}"
        draw.text((x0 + 2, max(0, y0 - 14)), label, fill=color)
    return canvas


def save_review_artifacts(review_dir: str, page_to_crop: dict[int, np.ndarray], pages: list[PageAnalysis]) -> None:
    ensure_dir(review_dir)
    candidates_dir = Path(review_dir) / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)

    ambiguous_images: list[Image.Image] = []
    ambiguous_labels: list[str] = []
    for page in pages:
        if not page.candidate_groups:
            continue
        overlay = draw_review_overlay(page_to_crop[page.pdf_page], page)
        suffix = "_ambiguous" if page.is_ambiguous else ""
        overlay.save(candidates_dir / f"page_{page.pdf_page:03d}{suffix}.png")
        if page.is_ambiguous:
            ambiguous_images.append(overlay)
            ambiguous_labels.append(f"p.{page.pdf_page} {page.ambiguity_reason or ''}".strip())

    if not ambiguous_images:
        return

    tile_w = max(image.width for image in ambiguous_images)
    tile_h = max(image.height for image in ambiguous_images)
    columns = 2
    rows = math.ceil(len(ambiguous_images) / columns)
    sheet = Image.new("RGB", (columns * tile_w, rows * (tile_h + 28)), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, image in enumerate(ambiguous_images):
        row = idx // columns
        col = idx % columns
        x = col * tile_w
        y = row * (tile_h + 28)
        sheet.paste(image, (x, y))
        draw.text((x + 8, y + tile_h + 8), ambiguous_labels[idx], fill=(0, 0, 0))
    sheet.save(Path(review_dir) / "ambiguous_contact_sheet.png")


def build_result(pdf_path: str, total_pages: int, review_dir: Optional[str], pages: list[PageAnalysis]) -> dict:
    start_pages = [page.pdf_page for page in pages if page.is_boundary]
    ambiguous_pages = [page.pdf_page for page in pages if page.is_ambiguous]
    detected_sets = []
    for page in pages:
        if not page.is_boundary:
            continue
        detected_sets.append(
            {
                "set_number_hint": page.chosen_digit,
                "start_page": page.pdf_page,
            }
        )
    return {
        "pdf_path": pdf_path,
        "total_pages": total_pages,
        "start_pages": start_pages,
        "detected_sets": detected_sets,
        "ranges": derive_ranges(start_pages, total_pages),
        "ambiguous_pages": ambiguous_pages,
        "review_dir": review_dir,
        "pages": [asdict(page) for page in pages if page.candidate_groups],
    }


def main() -> int:
    args = parse_args()
    crop = parse_crop(args.crop)
    pdf_path = str(Path(args.pdf_path).expanduser())
    if not os.path.exists(pdf_path):
        raise SystemExit(f"PDF not found: {pdf_path}")

    ensure_dir(args.save_review)
    doc = fitz.open(pdf_path)
    end_page = args.end_page or doc.page_count
    if args.start_page < 1 or end_page > doc.page_count or args.start_page > end_page:
        raise SystemExit(
            f"Invalid page window: start_page={args.start_page}, end_page={end_page}, total_pages={doc.page_count}"
        )
    page_to_crop: dict[int, np.ndarray] = {}
    pages: list[PageAnalysis] = []
    for page_number in range(args.start_page, end_page + 1):
        analysis, crop_rgb = analyze_page(
            doc,
            page_number,
            args.dpi,
            crop,
            args.min_pixels,
            args.ink_mode,
        )
        page_to_crop[page_number] = crop_rgb
        if analysis.candidate_groups:
            pages.append(analysis)

    apply_sequence_scoring(pages, args.ambiguity_threshold)
    if args.save_review:
        save_review_artifacts(args.save_review, page_to_crop, pages)

    result = build_result(pdf_path, doc.page_count, args.save_review, pages)
    output_json = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output_json + "\n", encoding="utf-8")
    print(output_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
