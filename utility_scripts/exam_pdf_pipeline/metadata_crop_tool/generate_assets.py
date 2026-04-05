#!/usr/bin/env python3
"""
Render first-page images and manifest for the generic metadata crop tool.

Input mapping CSV format:
  set_number,pdf_page

Example:
  python3 utility_scripts/exam_pdf_pipeline/metadata_crop_tool/generate_assets.py \
    --pdf "/Users/jarodm/Desktop/Books/Math P2 Exams.pdf" \
    --mapping-csv "/tmp/math_mapping.csv"
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image


ROOT = Path(__file__).resolve().parent


@dataclass
class ManifestEntry:
    set_number: int
    pdf_page: int
    image_path: str
    image_width: int
    image_height: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, help="Input PDF path")
    parser.add_argument(
        "--mapping-csv",
        required=True,
        help="CSV with set_number,pdf_page columns",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "assets"),
        help="Asset output directory (default: utility_scripts/exam_pdf_pipeline/metadata_crop_tool/assets)",
    )
    parser.add_argument("--dpi", type=int, default=180, help="Render DPI (default: 180)")
    return parser.parse_args()


def load_mapping(path: Path) -> list[tuple[int, int]]:
    rows: list[tuple[int, int]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            page_value = row.get("pdf_page") or row.get("start_page")
            if page_value is None:
                raise ValueError("Mapping CSV must include pdf_page or start_page")
            rows.append((int(row["set_number"]), int(page_value)))
    rows.sort()
    return rows


def main() -> int:
    args = parse_args()
    pdf_path = Path(args.pdf).expanduser()
    mapping_csv = Path(args.mapping_csv).expanduser()
    assets_dir = Path(args.output_dir).expanduser()
    pages_dir = assets_dir / "pages"

    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")
    if not mapping_csv.exists():
        raise SystemExit(f"Mapping CSV not found: {mapping_csv}")

    assets_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)

    mapping = load_mapping(mapping_csv)
    pdf = fitz.open(pdf_path)
    manifest: list[ManifestEntry] = []

    scale = args.dpi / 72
    for set_number, pdf_page in mapping:
        page = pdf.load_page(pdf_page - 1)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        filename = f"set_{set_number:02d}_page_{pdf_page:03d}.png"
        out_path = pages_dir / filename
        image.save(out_path)
        manifest.append(
            ManifestEntry(
                set_number=set_number,
                pdf_page=pdf_page,
                image_path=f"assets/pages/{filename}",
                image_width=image.width,
                image_height=image.height,
            )
        )

    manifest_path = assets_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "pdf_path": str(pdf_path),
                "mapping_csv": str(mapping_csv),
                "items": [asdict(item) for item in manifest],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {manifest_path}")
    print(f"Rendered {len(manifest)} first-page images into {pages_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
