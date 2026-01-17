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
      --pdf_dir "/Users/jarodm/Library/CloudStorage/GoogleDrive-winston.ry.meng@gmail.com/My Drive/冯氏早教识字卡/" \
      --prompt_md ./chinese_character_extraction_prompt.md \
      --out_jsonl jsonl/requests.jsonl \
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
                                "You MUST extract: Index, Character, Pinyin, Radical, Strokes, Structure, Sentence(例句), Words(词组).\n"
                                "\n"
                                "⚠️ CRITICAL VALIDATION (MANDATORY - DO NOT SKIP):\n"
                                "BEFORE outputting the final table, you MUST verify that the extracted Character appears in:\n"
                                "  1. The Sentence (例句) field\n"
                                "  2. At least some of the Words (词组) field\n"
                                "\n"
                                "If the character does NOT appear in the Sentence or Words:\n"
                                "  - STOP IMMEDIATELY - This is a definite OCR error.\n"
                                "  - DO NOT OUTPUT the incorrect character.\n"
                                "  - Re-examine the image very carefully.\n"
                                "  - The character in the Sentence/Words is DEFINITELY the correct one.\n"
                                "  - Extract that character instead, even if it looks different in the main area.\n"
                                "\n"
                                "Common confusions: 要/耍 (check for 玩耍), 晴/睛 (check for 眼睛), 从/丛 (check for 丛林/丛书).\n"
                                "If your character doesn't appear in sentence/words, you have made an error - fix it before outputting.\n"
                                "\n"
                                "Output ONLY a Markdown table with exactly ONE row.\n"
                                "IMPORTANT: Both Pinyin and Words columns MUST be valid JSON arrays of strings.\n"
                                "  - Pinyin: Always output as array, e.g. [\"tā\"] for single pronunciation or [\"hé\",\"huó\",\"hú\",\"hè\"] for multiple.\n"
                                "  - Words: e.g. [\"他们\",\"他乡\"]. If no words present, output [] in the Words column.\n"
                                "Do not output any extra text outside the Markdown table.\n"
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
    parser.add_argument("--out_jsonl", default="jsonl/requests.jsonl", help="Output JSONL file")
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
    parser.add_argument(
        "--pdf_file",
        type=str,
        default=None,
        help="Process only a specific PDF file (e.g., '2861-2870.pdf')",
    )
    parser.add_argument(
        "--range",
        type=str,
        default=None,
        help="Process only PDFs containing characters in this range (e.g., '2861-2870')",
    )
    parser.add_argument(
        "--max_file_size_mb",
        type=int,
        default=190,
        help="Maximum size per JSONL file in MB (default: 190, OpenAI limit for gpt-5-mini: 200MB)",
    )

    args = parser.parse_args()
    
    # Validate that only one filtering option is used
    filter_count = sum([
        args.max_pdfs is not None,
        args.pdf_file is not None,
        args.range is not None,
    ])
    if filter_count > 1:
        raise SystemExit("Error: Can only use one of --max_pdfs, --pdf_file, or --range at a time")

    pdf_dir = Path(args.pdf_dir)
    prompt_md = Path(args.prompt_md)
    out_jsonl = Path(args.out_jsonl)
    # Create output directory if it doesn't exist
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)

    if not pdf_dir.is_dir():
        raise SystemExit(f"Not a directory: {pdf_dir}")

    if not prompt_md.exists():
        raise SystemExit(f"Prompt file not found: {prompt_md}")

    prompt_text = prompt_md.read_text(encoding="utf-8")

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    
    # Filter PDFs based on options
    if args.pdf_file:
        # Process only the specified PDF file
        pdf_path = pdf_dir / args.pdf_file
        if not pdf_path.exists():
            raise SystemExit(f"PDF file not found: {pdf_path}")
        pdf_files = [pdf_path]
    elif args.range:
        # Process only PDFs that overlap with the specified range
        range_match = re.match(r'^(\d+)-(\d+)$', args.range)
        if not range_match:
            raise SystemExit(f"Invalid range format: {args.range}. Use format like '2861-2870'")
        min_idx = int(range_match.group(1))
        max_idx = int(range_match.group(2))
        if min_idx > max_idx:
            raise SystemExit(f"Invalid range: start ({min_idx}) > end ({max_idx})")
        
        filtered_files = []
        for pdf_file in pdf_files:
            try:
                start, end = parse_index_range_from_filename(pdf_file)
                # Check if PDF range overlaps with requested range
                if not (end < min_idx or start > max_idx):
                    filtered_files.append(pdf_file)
            except ValueError:
                continue
        pdf_files = filtered_files
    elif args.max_pdfs is not None:
        pdf_files = pdf_files[: args.max_pdfs]

    if not pdf_files:
        raise SystemExit(f"No PDF files found matching the criteria in: {pdf_dir}")

    rendered_root = Path("rendered_pages")
    used_custom_ids = set()

    processed_pdfs = 0
    skipped: List[str] = []
    warnings: List[str] = []
    requests_written = 0
    
    # File splitting setup
    max_file_size_bytes = args.max_file_size_mb * 1024 * 1024
    current_file_num = 1
    current_file_size = 0
    output_files = []
    
    def get_output_file_path(file_num: int) -> Path:
        """Generate output file path with number suffix if splitting."""
        if file_num == 1:
            return out_jsonl
        else:
            # Add number suffix: requests.jsonl -> requests_002.jsonl
            stem = out_jsonl.stem
            suffix = out_jsonl.suffix
            return out_jsonl.parent / f"{stem}_{file_num:03d}{suffix}"
    
    def open_next_file():
        """Open the next output file."""
        file_path = get_output_file_path(current_file_num)
        output_files.append(file_path)
        return file_path.open("w", encoding="utf-8"), file_path
    
    f_out, current_file_path = open_next_file()
    
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

                # Serialize to JSON to check size
                line_json = json.dumps(batch_line, ensure_ascii=False) + "\n"
                line_size = len(line_json.encode('utf-8'))
                
                # Check if we need to start a new file
                if current_file_size + line_size > max_file_size_bytes and requests_written > 0:
                    f_out.close()
                    current_file_num += 1
                    f_out, current_file_path = open_next_file()
                    current_file_size = 0
                    print(f"📄 Starting new file: {current_file_path.name} (file #{current_file_num})")
                
                f_out.write(line_json)
                current_file_size += line_size
                requests_written += 1

            processed_pdfs += 1
    
    # Close the last file
    f_out.close()

    # Summary
    print("\n✅ Batch JSONL generation complete")
    print(f"PDF dir     : {pdf_dir.resolve()}")
    print(f"Model       : {args.model}")
    print(f"DPI         : {args.dpi}")
    print(f"PDFs found  : {len(sorted(pdf_dir.glob('*.pdf')))}")
    if args.max_pdfs is not None:
        print(f"PDFs limit  : {args.max_pdfs}")
    print(f"PDFs processed (matching pattern): {processed_pdfs}")
    print(f"Requests written (characters)    : {requests_written}")
    print(f"Output files created            : {len(output_files)}")
    for i, file_path in enumerate(output_files, 1):
        file_size = file_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        print(f"  {i}. {file_path.name} ({file_size_mb:.2f} MB)")
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
