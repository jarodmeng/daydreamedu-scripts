#!/usr/bin/env python3
"""
Generate OpenAI Batch JSONL (one request per character)
with custom_id as 4-digit index number (e.g. "0721").

Input PDFs are expected to be named like:
  <dddd>-<dddd>.pdf   e.g. 0721-0730.pdf

Behavior:
- Reads PDFs directly from a folder (Google Drive sync folder is fine)
- Skips PDFs that do not match <dddd>-<dddd>.pdf
- Optionally processes only the first N PDFs (sorted by filename)
- Each character uses 2 pages; we extract only the second page of each pair:
  pages 2,4,6,... in 1-based page numbering

Usage Example:
    python3 make_batch_jsonl_per_character.py \
      --pdf_dir "/Users/jarodm/Library/CloudStorage/GoogleDrive-winston.ry.meng@gmail.com/My Drive/冯式早教识字卡/" \
      --prompt_md ./chinese_character_extraction_prompt.md \
      --out_jsonl requests.jsonl \
      --dpi 250 \
      --model gpt-5-mini \
      --max_pdfs 10 \
      --save_images
"""

import re
import json
import base64
import argparse
from pathlib import Path
from typing import Tuple, Optional, List

# pip install pymupdf
import fitz  # PyMuPDF


FILENAME_PATTERN = re.compile(r"^(\d{4})-(\d{4})$")


def parse_index_range_from_filename(pdf_path: Path) -> Tuple[int, int]:
    """
    Parse index range from '<dddd>-<dddd>.pdf' filename.
    Example: '0721-0730.pdf' -> (721, 730)
    """
    m = FILENAME_PATTERN.fullmatch(pdf_path.stem)
    if not m:
        raise ValueError(f"Filename does not match '<dddd>-<dddd>.pdf': {pdf_path.name}")

    start = int(m.group(1))
    end = int(m.group(2))
    if end < start:
        raise ValueError(f"Bad range in filename: {pdf_path.name}")

    return start, end


def render_page_to_png_bytes(pdf_path: Path, page_1_based: int, dpi: int) -> bytes:
    """
    Render one PDF page (1-based) to PNG bytes.
    """
    page_index = page_1_based - 1  # 0-based in PyMuPDF
    doc = fitz.open(str(pdf_path))
    try:
        if page_index < 0 or page_index >= doc.page_count:
            raise ValueError(
                f"Page out of range: page={page_1_based}, total_pages={doc.page_count}"
            )

        page = doc.load_page(page_index)
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def png_bytes_to_data_url(png_bytes: bytes) -> str:
    """
    Convert PNG bytes to base64 data URL usable in OpenAI image inputs.
    """
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def build_batch_line(custom_id: str, model: str, prompt_text: str, image_url: str) -> dict:
    """
    One JSONL request line for POST /v1/responses.
    One character per request, output should be one-row Markdown table.
    """
    return {
        "custom_id": custom_id,  # e.g. "0721"
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": prompt_text}],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Extract the fields for this single Chinese character card.\n"
                                "This image is the SECOND page of the 2-page character set.\n"
                                "Output ONLY the Markdown table with one row.\n"
                            ),
                        },
                        {"type": "input_image", "image_url": image_url},
                    ],
                },
            ],
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate Batch JSONL (one request per character, custom_id=4-digit index) from <dddd>-<dddd>.pdf files."
    )
    parser.add_argument("--pdf_dir", required=True, help="Folder containing PDFs")
    parser.add_argument("--prompt_md", required=True, help="Path to saved prompt .md")
    parser.add_argument("--out_jsonl", default="requests.jsonl", help="Output JSONL file")
    parser.add_argument("--dpi", type=int, default=250, help="Render DPI (200–300 recommended)")
    parser.add_argument("--model", default="gpt-5-mini", help="Model name (default: gpt-5-mini)")
    parser.add_argument(
        "--save_images",
        action="store_true",
        help="Save rendered pages into ./rendered_pages/<pdf_stem>/ for inspection",
    )
    parser.add_argument(
        "--max_pdfs",
        type=int,
        default=None,
        help="Process only the first N PDFs (sorted). Example: --max_pdfs 10",
    )
    parser.add_argument(
        "--strict_pagecount",
        action="store_true",
        help=(
            "If set: enforce that each PDF has exactly 2*(end-start+1) pages. "
            "Otherwise it will warn but still attempt extraction."
        ),
    )

    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    prompt_md = Path(args.prompt_md)
    out_jsonl = Path(args.out_jsonl)

    if not pdf_dir.is_dir():
        raise SystemExit(f"Not a directory: {pdf_dir}")

    if not prompt_md.exists():
        raise SystemExit(f"Prompt file not found: {prompt_md}")

    prompt_text = prompt_md.read_text(encoding="utf-8")

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if args.max_pdfs is not None:
        pdf_files = pdf_files[: args.max_pdfs]

    if not pdf_files:
        raise SystemExit(f"No PDF files found in: {pdf_dir}")

    rendered_root = Path("rendered_pages")
    used_custom_ids = set()

    processed_pdfs = 0
    skipped: List[str] = []
    warnings: List[str] = []
    requests_written = 0

    with out_jsonl.open("w", encoding="utf-8") as f_out:
        for pdf_path in pdf_files:
            # Skip files not matching pattern
            try:
                start, end = parse_index_range_from_filename(pdf_path)
            except Exception as e:
                skipped.append(f"{pdf_path.name}  -> skipped (reason: {e})")
                continue

            expected_chars = end - start + 1
            expected_pages = expected_chars * 2

            # Read page count
            doc = fitz.open(str(pdf_path))
            total_pages = doc.page_count
            doc.close()

            if total_pages != expected_pages:
                msg = (
                    f"{pdf_path.name}: page_count={total_pages}, "
                    f"expected={expected_pages} (from range {start:04d}-{end:04d})"
                )
                if args.strict_pagecount:
                    skipped.append(msg + " -> skipped (strict_pagecount)")
                    continue
                else:
                    warnings.append("WARN " + msg)

            # Each character -> one "second page": 2,4,6,...,2*n
            for i in range(expected_chars):
                idx = start + i
                custom_id = f"{idx:04d}"

                if custom_id in used_custom_ids:
                    raise ValueError(
                        f"Duplicate custom_id={custom_id}. PDFs overlap ranges."
                    )
                used_custom_ids.add(custom_id)

                page_1_based = 2 * (i + 1)

                try:
                    png_bytes = render_page_to_png_bytes(pdf_path, page_1_based, dpi=args.dpi)
                except Exception as e:
                    warnings.append(
                        f"WARN {pdf_path.name}: failed rendering page {page_1_based} for index {custom_id} -> {e}"
                    )
                    continue

                if args.save_images:
                    out_dir = rendered_root / pdf_path.stem
                    out_dir.mkdir(parents=True, exist_ok=True)
                    (out_dir / f"{custom_id}_page_{page_1_based:02d}.png").write_bytes(png_bytes)

                image_url = png_bytes_to_data_url(png_bytes)

                batch_line = build_batch_line(
                    custom_id=custom_id,
                    model=args.model,
                    prompt_text=prompt_text,
                    image_url=image_url,
                )

                f_out.write(json.dumps(batch_line, ensure_ascii=False) + "\n")
                requests_written += 1

            processed_pdfs += 1

    # Summary
    print("\n✅ Batch JSONL generation complete")
    print(f"Output JSONL: {out_jsonl.resolve()}")
    print(f"PDF dir     : {pdf_dir.resolve()}")
    print(f"Model       : {args.model}")
    print(f"DPI         : {args.dpi}")
    print(f"PDFs found  : {len(sorted(pdf_dir.glob('*.pdf')))}")
    if args.max_pdfs is not None:
        print(f"PDFs limit  : {args.max_pdfs}")
    print(f"PDFs processed (matching pattern): {processed_pdfs}")
    print(f"Requests written (characters)    : {requests_written}")
    if args.save_images:
        print(f"Rendered PNGs saved under       : {rendered_root.resolve()}")

    if skipped:
        print("\n--- Skipped PDFs ---")
        for line in skipped[:50]:
            print(line)
        if len(skipped) > 50:
            print(f"... ({len(skipped)-50} more)")

    if warnings:
        print("\n--- Warnings ---")
        for line in warnings[:50]:
            print(line)
        if len(warnings) > 50:
            print(f"... ({len(warnings)-50} more)")


if __name__ == "__main__":
    main()
