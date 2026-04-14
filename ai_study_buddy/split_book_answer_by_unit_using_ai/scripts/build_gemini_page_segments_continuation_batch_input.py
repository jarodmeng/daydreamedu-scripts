#!/usr/bin/env python3
"""
Build a one-book Gemini Batch API JSONL file for continuation-aware page segments.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import re
import sys
from pathlib import Path

import fitz
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
PROMPT_MD = ROOT / "prompts" / "book_answer_page_segments_continuation_prompt.md"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from book_context import (  # noqa: E402
    build_unit_list,
    build_user_payload,
    extract_system_message,
    find_book_group,
    identify_answer_file,
    identify_front_matter,
    select_daydreamedu_files,
)

CONTINUATION_PAGE_SEGMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "book_label": {"type": "string"},
        "answer_file": {"type": "string"},
        "unit_manifest_indices": {
            "type": "array",
            "items": {"type": "integer"},
        },
        "page_segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "answer_page": {"type": "integer"},
                    "continued_unit_index": {
                        "nullable": True,
                        "type": "integer",
                    },
                    "non_registry_prefix": {
                        "nullable": True,
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "visible_heading_labels": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "notes": {"type": "string"},
                        },
                        "required": ["label", "visible_heading_labels", "notes"],
                        "propertyOrdering": ["label", "visible_heading_labels", "notes"],
                    },
                    "visible_heading_labels": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "visible_unit_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "notes": {"type": "string"},
                },
                "required": [
                    "answer_page",
                    "continued_unit_index",
                    "non_registry_prefix",
                    "visible_heading_labels",
                    "visible_unit_indices",
                    "notes",
                ],
                "propertyOrdering": [
                    "answer_page",
                    "continued_unit_index",
                    "non_registry_prefix",
                    "visible_heading_labels",
                    "visible_unit_indices",
                    "notes",
                ],
            },
        },
        "global_notes": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["book_label", "answer_file", "unit_manifest_indices", "page_segments", "global_notes"],
    "propertyOrdering": ["book_label", "answer_file", "unit_manifest_indices", "page_segments", "global_notes"],
}


def slugify(text: str) -> str:
    value = text.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def render_page_to_inline_data(pdf_path: Path, page_number_1_based: int, dpi: int, jpeg_quality: int) -> dict:
    doc = fitz.open(str(pdf_path))
    try:
        page = doc.load_page(page_number_1_based - 1)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
        return {
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": base64.b64encode(buf.getvalue()).decode("ascii"),
            }
        }
    finally:
        doc.close()


def build_request_object(
    *,
    system_message: str,
    user_payload: dict,
    front_matter_path: Path,
    answer_path: Path,
    front_matter_page_count: int,
    answer_page_numbers: list[int],
    dpi: int,
    jpeg_quality: int,
    max_output_tokens: int,
    thinking_budget: int | None,
    include_thoughts: bool = True,
) -> dict:
    parts = [
        {
            "text": (
                "Inspect each answer page and output:\n"
                "1) visible registry headings on the page as visible_unit_indices\n"
                "2) a single top-of-page continuation owner as continued_unit_index (or null)\n\n"
                f"{json.dumps(user_payload, ensure_ascii=False, indent=2)}"
            )
        }
    ]

    for page_num in range(1, front_matter_page_count + 1):
        parts.append({"text": f"Front matter page {page_num}"})
        parts.append(render_page_to_inline_data(front_matter_path, page_num, dpi, jpeg_quality))

    for page_num in answer_page_numbers:
        parts.append({"text": f"Answer page {page_num}"})
        parts.append(render_page_to_inline_data(answer_path, page_num, dpi, jpeg_quality))

    generation_config = {
        "responseMimeType": "application/json",
        "responseJsonSchema": CONTINUATION_PAGE_SEGMENT_SCHEMA,
        "maxOutputTokens": max_output_tokens,
    }
    thinking_cfg: dict = {}
    if thinking_budget is not None:
        thinking_cfg["thinkingBudget"] = thinking_budget
    if include_thoughts:
        thinking_cfg["includeThoughts"] = True
    if thinking_cfg:
        generation_config["thinkingConfig"] = thinking_cfg

    return {
        "systemInstruction": {
            "parts": [{"text": system_message}],
        },
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ],
        "generationConfig": generation_config,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build one-book Gemini Batch API JSONL input for continuation-aware page segments"
    )
    parser.add_argument("--book-label", required=True, help="Exact book group label in pdf_file_manager")
    parser.add_argument("--prompt-md", type=Path, default=PROMPT_MD)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--jpeg-quality", type=int, default=90)
    parser.add_argument("--max-output-tokens", type=int, default=65536)
    parser.add_argument("--thinking-budget", type=int, default=None, help="Gemini thinking budget; -1 for dynamic")
    parser.add_argument(
        "--include-thoughts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Ask Gemini to return thought summaries in response parts.",
    )
    parser.add_argument("--answer-page-start", type=int, default=1)
    parser.add_argument("--answer-page-end", type=int, default=None)
    parser.add_argument(
        "--unit-include-substring",
        action="append",
        default=[],
        help="Only include unit files whose unit label or filename contains this substring. Repeatable.",
    )
    parser.add_argument(
        "--unit-exclude-substring",
        action="append",
        default=[],
        help="Exclude unit files whose unit label or filename contains this substring. Repeatable.",
    )
    parser.add_argument(
        "--answer-file-substring",
        default=None,
        help="Select the answer file by substring match on filename or unit label.",
    )
    parser.add_argument(
        "--omit-front-matter",
        action="store_true",
        help="Do not include front matter pages in the request or payload.",
    )
    args = parser.parse_args()

    system_message = extract_system_message(args.prompt_md)
    group = find_book_group(args.book_label)
    files = select_daydreamedu_files(group)
    if not files:
        raise SystemExit(f"No DaydreamEdu files found for book group: {args.book_label}")

    if args.answer_file_substring:
        needle = args.answer_file_substring.lower()
        filtered_files = []
        for file in files:
            unit = file.metadata.get("unit") if isinstance(file.metadata, dict) else ""
            hay = f"{file.name}\n{unit}".lower()
            if needle in hay:
                filtered_files.append(file)
                continue
            include_match = not args.unit_include_substring or any(
                s.lower() in hay for s in args.unit_include_substring
            )
            exclude_match = any(s.lower() in hay for s in args.unit_exclude_substring)
            if include_match and not exclude_match:
                filtered_files.append(file)
        files = filtered_files
        if not files:
            raise SystemExit("Error: answer/unit filtering removed every file")

    try:
        front_matter_file = identify_front_matter(files)
    except ValueError:
        front_matter_file = None
    if args.answer_file_substring:
        needle = args.answer_file_substring.lower()
        candidates = []
        for file in files:
            unit = file.metadata.get("unit") if isinstance(file.metadata, dict) else ""
            hay = f"{file.name}\n{unit}".lower()
            if needle in hay:
                candidates.append(file)
        if len(candidates) != 1:
            raise SystemExit(
                f"Error: Expected exactly one answer file matching substring '{args.answer_file_substring}', "
                f"found {len(candidates)}: {[c.name for c in candidates]}"
            )
        answer_file = candidates[0]
    else:
        answer_file = identify_answer_file(files)

    unit_files = build_unit_list(files, front_matter_file, answer_file)
    if args.unit_include_substring:
        needles = [s.lower() for s in args.unit_include_substring]
        unit_files = [
            item
            for item in unit_files
            if any(needle in f"{item['unit_file']}\n{item['unit_label']}".lower() for needle in needles)
        ]
    if args.unit_exclude_substring:
        needles = [s.lower() for s in args.unit_exclude_substring]
        unit_files = [
            item
            for item in unit_files
            if not any(needle in f"{item['unit_file']}\n{item['unit_label']}".lower() for needle in needles)
        ]
    if not unit_files:
        raise SystemExit("Error: Unit filtering removed every unit file")

    if args.omit_front_matter:
        front_matter_file = None

    answer_page_total = answer_file.page_count or 0
    answer_page_end = args.answer_page_end or answer_page_total
    if args.answer_page_start < 1 or answer_page_end > answer_page_total or args.answer_page_start > answer_page_end:
        raise SystemExit(
            f"Error: Invalid answer page window {args.answer_page_start}-{answer_page_end} for total page count {answer_page_total}"
        )
    answer_page_numbers = list(range(args.answer_page_start, answer_page_end + 1))

    user_payload = build_user_payload(args.book_label, front_matter_file, answer_file, unit_files)
    user_payload["answer_page_start"] = args.answer_page_start
    user_payload["answer_page_end"] = answer_page_end
    user_payload["answer_page_count"] = len(answer_page_numbers)
    user_payload["global_answer_page_count"] = answer_page_total
    user_payload["unit_manifest_indices"] = [int(item["unit_index"]) for item in unit_files]

    request_object = build_request_object(
        system_message=system_message,
        user_payload=user_payload,
        front_matter_path=Path(front_matter_file.path) if front_matter_file is not None else Path(),
        answer_path=Path(answer_file.path),
        front_matter_page_count=(front_matter_file.page_count or 0) if front_matter_file is not None else 0,
        answer_page_numbers=answer_page_numbers,
        dpi=args.dpi,
        jpeg_quality=args.jpeg_quality,
        max_output_tokens=args.max_output_tokens,
        thinking_budget=args.thinking_budget,
        include_thoughts=args.include_thoughts,
    )

    answer_window = f"p{args.answer_page_start}_{answer_page_end}"
    record = {
        "key": f"book:{slugify(args.book_label)}:page_segments_continuation_gemini:{answer_window}",
        "request": request_object,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    size_mb = args.output.stat().st_size / (1024 * 1024)
    print(f"Wrote 1 Gemini continuation page-segments batch request to {args.output}")
    print(f"key: {record['key']}")
    print(f"answer_pages: {args.answer_page_start}-{answer_page_end} ({len(answer_page_numbers)} rendered)")
    print(f"unit_count: {len(unit_files)}")
    print(f"size_mb: {size_mb:.2f}")


if __name__ == "__main__":
    main()
