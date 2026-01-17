#!/usr/bin/env python3
"""
Generate a single JSONL request entry for reprocessing a specific character index.
"""

import json
import base64
import argparse
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF (fitz) is required. Install it with: pip3 install pymupdf")
    exit(1)


def build_batch_line(char_index: int, pdf_path: Path, prompt_md_path: Path, dpi: int = 250, model: str = "gpt-5-mini"):
    """Build a single JSONL request line for one character."""
    
    # Read prompt
    with open(prompt_md_path, 'r', encoding='utf-8') as f:
        prompt_text = f.read()
    
    # Open PDF
    doc = fitz.open(str(pdf_path))
    
    try:
        # Calculate page number (2nd page of the character pair)
        # Find which character in the PDF range this is
        pdf_start = ((char_index - 1) // 10) * 10 + 1
        char_idx_in_pdf = char_index - pdf_start  # 0-based within this PDF
        # Page 2 of the character pair (0-based: pages 1, 3, 5, ...)
        page2_idx = char_idx_in_pdf * 2 + 1
        
        if page2_idx >= doc.page_count:
            raise ValueError(f"Page {page2_idx} not found in PDF (has {doc.page_count} pages)")
        
        # Render page to PNG
        page = doc[page2_idx]
        pix = page.get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes("png")
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        image_url = f"data:image/png;base64,{img_b64}"
    finally:
        doc.close()
    
    # Build request (matching format from make_batch_jsonl_per_character.py)
    request_line = {
        "custom_id": f"{char_index:04d}",
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
    
    return request_line


def main():
    parser = argparse.ArgumentParser(
        description="Generate a single JSONL request entry for reprocessing."
    )
    parser.add_argument(
        "--index",
        type=int,
        required=True,
        help="Character index to extract (e.g., 1298)",
    )
    parser.add_argument(
        "--pdf_dir",
        type=Path,
        required=True,
        help="Directory containing PDF files",
    )
    parser.add_argument(
        "--prompt_md",
        type=Path,
        default=Path("chinese_character_extraction_prompt.md"),
        help="Path to prompt markdown file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=250,
        help="DPI for PNG rendering (default: 250)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5-mini",
        help="OpenAI model name (default: gpt-5-mini)",
    )
    
    args = parser.parse_args()
    
    # Find the PDF file containing this index
    # Each PDF contains 10 characters
    pdf_start = ((args.index - 1) // 10) * 10 + 1
    pdf_end = pdf_start + 9
    pdf_name = f"{pdf_start:04d}-{pdf_end:04d}.pdf"
    pdf_path = args.pdf_dir / pdf_name
    
    if not pdf_path.exists():
        raise SystemExit(f"PDF file not found: {pdf_path}")
    
    print(f"📄 Processing index {args.index} from {pdf_name}")
    print(f"   PDF: {pdf_path}")
    
    # Build request line
    request_line = build_batch_line(
        args.index,
        pdf_path,
        args.prompt_md,
        args.dpi,
        args.model,
    )
    
    # Write to output file
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(json.dumps(request_line, ensure_ascii=False) + '\n')
    
    print(f"✅ Generated request entry: {args.output}")
    print(f"   custom_id: {request_line['custom_id']}")


if __name__ == "__main__":
    main()
