#!/usr/bin/env python3
"""
Cut selected metadata regions, OCR them, and write a review CSV.

Example:
  python3 utility_scripts/exam_pdf_pipeline/extract_metadata_from_crops.py \
    --tool-dir utility_scripts/exam_pdf_pipeline/metadata_crop_tool \
    --export-json ~/Downloads/metadata_crops.json \
    --output-csv /tmp/metadata_detected.csv \
    --review-dir /tmp/metadata_review
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


WHITESPACE_RE = re.compile(r"\s+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tool-dir",
        required=True,
        help="Path to utility_scripts/exam_pdf_pipeline/metadata_crop_tool",
    )
    parser.add_argument("--export-json", required=True, help="Exported crop JSON from the review tool")
    parser.add_argument("--output-csv", required=True, help="Output CSV with detected metadata")
    parser.add_argument(
        "--review-dir",
        help="Optional directory to save extracted crop images and a contact sheet",
    )
    return parser.parse_args()


def normalize_text(raw: str) -> str:
    return WHITESPACE_RE.sub(" ", raw.replace("\x0c", " ")).strip()


def run_tesseract(image: Image.Image) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        temp_path = handle.name
    try:
        image.save(temp_path)
        proc = subprocess.run(
            ["tesseract", temp_path, "stdout", "--psm", "6"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return ""
        return normalize_text(proc.stdout)
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass


def crop_bounds(selection: dict, image: Image.Image) -> tuple[int, int, int, int]:
    width, height = image.size
    if all(k in selection for k in ("x_norm", "y_norm", "width_norm", "height_norm")):
        x0 = int(round(selection["x_norm"] * width))
        y0 = int(round(selection["y_norm"] * height))
        x1 = int(round((selection["x_norm"] + selection["width_norm"]) * width))
        y1 = int(round((selection["y_norm"] + selection["height_norm"]) * height))
    else:
        x0 = int(round(selection["x"]))
        y0 = int(round(selection["y"]))
        x1 = int(round(selection["x"] + selection["width"]))
        y1 = int(round(selection["y"] + selection["height"]))
    x0 = max(0, min(width - 1, x0))
    y0 = max(0, min(height - 1, y0))
    x1 = max(x0 + 1, min(width, x1))
    y1 = max(y0 + 1, min(height, y1))
    return x0, y0, x1, y1


def save_contact_sheet(review_dir: Path, first_regions: list[tuple[int, Image.Image]]) -> None:
    if not first_regions:
        return
    tile_w = max(img.width for _, img in first_regions)
    tile_h = max(img.height for _, img in first_regions)
    cols = 2
    rows = (len(first_regions) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile_w, rows * (tile_h + 28)), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, (set_number, image) in enumerate(first_regions):
        row = idx // cols
        col = idx % cols
        x = col * tile_w
        y = row * (tile_h + 28)
        sheet.paste(image, (x, y))
        draw.text((x + 8, y + tile_h + 8), f"set {set_number}", fill=(0, 0, 0))
    sheet.save(review_dir / "contact_sheet_region1.png")


def main() -> int:
    args = parse_args()
    tool_dir = Path(args.tool_dir).expanduser()
    export_json = Path(args.export_json).expanduser()
    output_csv = Path(args.output_csv).expanduser()
    review_dir = Path(args.review_dir).expanduser() if args.review_dir else None

    manifest = json.loads((tool_dir / "assets" / "manifest.json").read_text(encoding="utf-8"))
    export = json.loads(export_json.read_text(encoding="utf-8"))
    items = {int(item["set_number"]): item for item in manifest["items"]}
    selections = export["selections"]

    if review_dir:
        review_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str | int]] = []
    first_regions: list[tuple[int, Image.Image]] = []

    for set_number in sorted(items):
        item = items[set_number]
        image_path = tool_dir / item["image_path"]
        image = Image.open(image_path).convert("RGB")
        set_selections = selections.get(str(set_number), [])
        if not set_selections:
            rows.append({"set_number": set_number, "pdf_page": item["pdf_page"], "metadata": ""})
            continue

        region_texts: list[str] = []
        set_dir = review_dir / f"set_{set_number:02d}" if review_dir else None
        if set_dir:
            set_dir.mkdir(parents=True, exist_ok=True)

        for index, selection in enumerate(set_selections, start=1):
            x0, y0, x1, y1 = crop_bounds(selection, image)
            region = image.crop((x0, y0, x1, y1))
            if index == 1 and review_dir:
                first_regions.append((set_number, region))
            if set_dir:
                region.save(set_dir / f"region_{index}.png")
            text = run_tesseract(region)
            if text:
                region_texts.append(text)

        rows.append(
            {
                "set_number": set_number,
                "pdf_page": item["pdf_page"],
                "metadata": " || ".join(region_texts),
            }
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["set_number", "pdf_page", "metadata"])
        writer.writeheader()
        writer.writerows(rows)

    if review_dir:
        save_contact_sheet(review_dir, first_regions)

    print(f"Wrote {output_csv}")
    if review_dir:
        print(f"Saved review crops to {review_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
