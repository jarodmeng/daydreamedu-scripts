#!/usr/bin/env python3
"""
Split a PDF into multiple files using a manifest with page ranges and metadata.

Example:
  python3 utility_scripts/exam_pdf_pipeline/split_pdf_by_manifest.py \
    --pdf "/Users/jarodm/Desktop/Books/Chinese P2 Exams.pdf" \
    --manifest "utility_scripts/exam_pdf_pipeline/exam_manifest.csv" \
    --output-dir "/Users/jarodm/Desktop/Books/Chinese P2 Exams Manifest Split"
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF


@dataclass(frozen=True)
class ManifestRow:
    set_number: int
    start_page: int
    end_page: int
    page_count: int
    metadata: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, help="Input PDF path")
    parser.add_argument(
        "--manifest",
        required=True,
        help="CSV manifest with set_number,start_page,end_page,page_count,metadata columns",
    )
    parser.add_argument("--output-dir", required=True, help="Destination folder for split PDFs")
    parser.add_argument(
        "--file-prefix",
        default="p2.chinese.set",
        help="Filename prefix before the set number (default: p2.chinese.set)",
    )
    return parser.parse_args()


def sanitize_metadata_for_filename(value: str) -> str:
    cleaned = value.strip()
    replacements = {
        "/": "-",
        "\\": "-",
        ":": " -",
        "*": "",
        "?": "",
        '"': "",
        "<": "",
        ">": "",
        "|": "",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.rstrip(". ")
    return cleaned or "untitled"


def load_manifest(manifest_path: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                parsed = ManifestRow(
                    set_number=int(row["set_number"]),
                    start_page=int(row["start_page"]),
                    end_page=int(row["end_page"]),
                    page_count=int(row["page_count"]),
                    metadata=(row.get("metadata") or "").strip(),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid manifest row: {row!r}") from exc
            if not parsed.metadata:
                raise ValueError(f"Missing metadata for set {parsed.set_number}")
            rows.append(parsed)

    if not rows:
        raise ValueError("Manifest CSV is empty")

    rows.sort(key=lambda row: row.set_number)
    set_numbers = [row.set_number for row in rows]
    if set_numbers != sorted(set(set_numbers)):
        raise ValueError("Manifest set_number values must be unique")

    return rows


def main() -> int:
    args = parse_args()
    pdf_path = Path(args.pdf).expanduser()
    manifest_path = Path(args.manifest).expanduser()
    output_dir = Path(args.output_dir).expanduser()

    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")
    if not manifest_path.exists():
        raise SystemExit(f"Manifest CSV not found: {manifest_path}")

    rows = load_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    src = fitz.open(pdf_path)
    total_pages = src.page_count
    created_files: list[Path] = []

    for row in rows:
        expected_count = row.end_page - row.start_page + 1
        if expected_count != row.page_count:
            raise ValueError(
                f"Manifest page_count mismatch for set {row.set_number}: "
                f"{row.start_page}-{row.end_page} implies {expected_count}, got {row.page_count}"
            )
        if row.start_page < 1 or row.end_page > total_pages or row.start_page > row.end_page:
            raise ValueError(
                f"Invalid page range for set {row.set_number}: {row.start_page}-{row.end_page}"
            )

        dst = fitz.open()
        dst.insert_pdf(src, from_page=row.start_page - 1, to_page=row.end_page - 1)
        metadata_name = sanitize_metadata_for_filename(row.metadata)
        out_path = output_dir / f"{args.file_prefix}{row.set_number}.{metadata_name}.pdf"
        dst.save(out_path)
        dst.close()
        created_files.append(out_path)

    print(f"Created {len(created_files)} files in {output_dir}")
    print(f"First file by set number: {created_files[0]}")
    print(f"Last file by set number: {created_files[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
