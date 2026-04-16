#!/usr/bin/env python3
"""
Build a one-book OpenAI Batch API JSONL file for continuation-aware page segments.
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


def slugify(text: str) -> str:
    value = text.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def render_page_to_data_url(pdf_path: Path, page_number_1_based: int, dpi: int, jpeg_quality: int) -> str:
    doc = fitz.open(str(pdf_path))
    try:
        page = doc.load_page(page_number_1_based - 1)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    finally:
        doc.close()


def build_openai_json_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "book_label": {"type": "string"},
            "answer_file": {"type": "string"},
            "unit_manifest_indices": {"type": "array", "items": {"type": "integer"}},
            "page_segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "answer_page": {"type": "integer"},
                        "continued_unit_index": {"type": ["integer", "null"]},
                        "non_registry_prefix": {
                            "type": ["object", "null"],
                            "properties": {
                                "label": {"type": "string"},
                                "visible_heading_labels": {"type": "array", "items": {"type": "string"}},
                                "notes": {"type": "string"},
                            },
                            "required": ["label", "visible_heading_labels", "notes"],
                            "additionalProperties": False,
                        },
                        "visible_heading_labels": {"type": "array", "items": {"type": "string"}},
                        "visible_unit_indices": {"type": "array", "items": {"type": "integer"}},
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
                    "additionalProperties": False,
                },
            },
            "global_notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["book_label", "answer_file", "unit_manifest_indices", "page_segments", "global_notes"],
        "additionalProperties": False,
    }


def build_request_body(
    *,
    model: str,
    system_message: str,
    user_payload: dict,
    front_matter_path: Path | None,
    answer_path: Path,
    front_matter_page_count: int,
    answer_page_numbers: list[int],
    dpi: int,
    jpeg_quality: int,
    max_output_tokens: int,
    reasoning: dict | None = None,
) -> dict:
    user_content: list[dict] = [
        {
            "type": "input_text",
            "text": (
                "Inspect each answer page and output:\n"
                "1) visible registry headings on the page as visible_unit_indices\n"
                "2) a single top-of-page continuation owner as continued_unit_index (or null)\n\n"
                f"{json.dumps(user_payload, ensure_ascii=False, indent=2)}"
            ),
        }
    ]

    if front_matter_path is not None:
        for page_num in range(1, front_matter_page_count + 1):
            user_content.append({"type": "input_text", "text": f"Front matter page {page_num}"})
            user_content.append(
                {
                    "type": "input_image",
                    "image_url": render_page_to_data_url(front_matter_path, page_num, dpi, jpeg_quality),
                }
            )

    for page_num in answer_page_numbers:
        user_content.append({"type": "input_text", "text": f"Answer page {page_num}"})
        user_content.append(
            {
                "type": "input_image",
                "image_url": render_page_to_data_url(answer_path, page_num, dpi, jpeg_quality),
            }
        )

    body: dict = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_message}],
            },
            {"role": "user", "content": user_content},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "book_answer_page_segments_continuation",
                "schema": build_openai_json_schema(),
                "strict": True,
            }
        },
        "max_output_tokens": max_output_tokens,
    }
    if reasoning:
        body["reasoning"] = reasoning
    return body


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build one-book OpenAI Batch API JSONL input for continuation-aware page segments"
    )
    parser.add_argument("--book-label", required=True, help="Exact book group label in pdf_file_manager")
    parser.add_argument("--prompt-md", type=Path, default=PROMPT_MD)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--jpeg-quality", type=int, default=90)
    parser.add_argument("--max-output-tokens", type=int, default=65536)
    parser.add_argument(
        "--reasoning-effort",
        default=None,
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
        help="OpenAI Responses API reasoning.effort (omit to leave default; gpt-5.4 defaults to none per OpenAI docs)",
    )
    parser.add_argument(
        "--reasoning-summary",
        default=None,
        choices=["auto", "concise", "detailed"],
        help="Optional reasoning.summary (only sent when --reasoning-effort is set); may require org verification",
    )
    parser.add_argument("--answer-page-start", type=int, default=1)
    parser.add_argument("--answer-page-end", type=int, default=None)
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

    reasoning: dict | None = None
    if args.reasoning_effort is not None:
        reasoning = {"effort": args.reasoning_effort}
        if args.reasoning_summary is not None:
            reasoning["summary"] = args.reasoning_summary

    request_body = build_request_body(
        model=args.model,
        system_message=system_message,
        user_payload=user_payload,
        front_matter_path=Path(front_matter_file.path) if front_matter_file is not None else None,
        answer_path=Path(answer_file.path),
        front_matter_page_count=(front_matter_file.page_count or 0) if front_matter_file is not None else 0,
        answer_page_numbers=answer_page_numbers,
        dpi=args.dpi,
        jpeg_quality=args.jpeg_quality,
        max_output_tokens=args.max_output_tokens,
        reasoning=reasoning,
    )

    answer_window = f"p{args.answer_page_start}_{answer_page_end}"
    record = {
        "custom_id": f"book:{slugify(args.book_label)}:page_segments_continuation_openai:{answer_window}",
        "method": "POST",
        "url": "/v1/responses",
        "body": request_body,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    size_mb = args.output.stat().st_size / (1024 * 1024)
    print(f"Wrote 1 OpenAI continuation page-segments batch request to {args.output}")
    print(f"custom_id: {record['custom_id']}")
    print(f"answer_pages: {args.answer_page_start}-{answer_page_end} ({len(answer_page_numbers)} rendered)")
    print(f"unit_count: {len(unit_files)}")
    print(f"size_mb: {size_mb:.2f}")
    if reasoning:
        print(f"reasoning: {json.dumps(reasoning, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
