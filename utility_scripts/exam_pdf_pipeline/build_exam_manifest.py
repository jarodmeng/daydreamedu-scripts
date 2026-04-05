#!/usr/bin/env python3
"""
Build a manifest from a set/page mapping CSV and a metadata CSV.

Mapping CSV format:
  set_number,pdf_page

Metadata CSV format:
  set_number,metadata
  or
  set_number,pdf_page,metadata
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import fitz  # PyMuPDF


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, help="Input PDF path")
    parser.add_argument("--mapping-csv", required=True, help="CSV with set_number,pdf_page")
    parser.add_argument("--metadata-csv", required=True, help="CSV with set_number,metadata")
    parser.add_argument("--output-csv", required=True, help="Output manifest CSV")
    parser.add_argument("--output-json", required=True, help="Output manifest JSON")
    parser.add_argument("--split-dir", help="Optional split output dir to prefill split_pdf paths")
    parser.add_argument(
        "--file-prefix",
        default="p2.exam.set",
        help="Optional filename prefix used when split_dir is set (default: p2.exam.set)",
    )
    return parser.parse_args()


def load_mapping(path: Path) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            page_value = row.get("pdf_page") or row.get("start_page")
            if page_value is None:
                raise ValueError("Mapping CSV must include pdf_page or start_page")
            rows.append({"set_number": int(row["set_number"]), "start_page": int(page_value)})
    rows.sort(key=lambda item: item["set_number"])
    return rows


def load_metadata(path: Path) -> dict[int, str]:
    result: dict[int, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            result[int(row["set_number"])] = (row.get("metadata") or "").strip()
    return result


def main() -> int:
    args = parse_args()
    pdf_path = Path(args.pdf).expanduser()
    mapping_csv = Path(args.mapping_csv).expanduser()
    metadata_csv = Path(args.metadata_csv).expanduser()
    output_csv = Path(args.output_csv).expanduser()
    output_json = Path(args.output_json).expanduser()
    split_dir = Path(args.split_dir).expanduser() if args.split_dir else None

    with fitz.open(pdf_path) as doc:
        total_pages = doc.page_count
    mapping = load_mapping(mapping_csv)
    metadata = load_metadata(metadata_csv)

    rows: list[dict[str, str | int]] = []
    for index, item in enumerate(mapping):
        set_number = item["set_number"]
        start_page = item["start_page"]
        end_page = total_pages if index == len(mapping) - 1 else mapping[index + 1]["start_page"] - 1
        record: dict[str, str | int] = {
            "set_number": set_number,
            "start_page": start_page,
            "end_page": end_page,
            "page_count": end_page - start_page + 1,
            "metadata": metadata.get(set_number, ""),
            "source_pdf": str(pdf_path),
        }
        if split_dir:
            record["split_pdf"] = str(split_dir / f"{args.file_prefix}{set_number}.{record['metadata']}.pdf")
        rows.append(record)

    fieldnames = ["set_number", "start_page", "end_page", "page_count", "metadata", "source_pdf"]
    if split_dir:
        fieldnames.append("split_pdf")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    output_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_csv}")
    print(f"Wrote {output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
