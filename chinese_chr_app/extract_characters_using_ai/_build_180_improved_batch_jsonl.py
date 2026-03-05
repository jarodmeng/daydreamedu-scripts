#!/usr/bin/env python3
"""
One-off: Build Batch API JSONL for the 180 character indices using the improved
prompt (Words must contain Character; keep full idioms as single items).

Reads indices from /tmp/fix_bad_words_batch.json and PNGs from
chinese_chr_app/data/png/<Index>/page2.png. Writes jsonl/requests_180_improved.jsonl.

Usage (from repo root or chinese_chr_app/extract_characters_using_ai):
    python3 _build_180_improved_batch_jsonl.py
"""
import base64
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CHINESE_CHR_APP = SCRIPT_DIR.parent  # chinese_chr_app/
PROMPT_MD = SCRIPT_DIR / "chinese_character_extraction_prompt.md"
PNG_ROOT = CHINESE_CHR_APP / "data" / "png"
BATCH_JSON = Path("/tmp/fix_bad_words_batch.json")
OUT_JSONL = SCRIPT_DIR / "jsonl" / "requests_180_improved.jsonl"

IMPROVED_USER_MESSAGE = (
    "Extract the fields for this single Chinese character card (second page).\n"
    "Output only a Markdown table with one row. Pinyin and Words must be JSON arrays.\n"
    "Every Words item must contain the Character; keep full idioms as single items.\n"
    "Do not split idioms and drop parts.\n"
)


def build_batch_line(custom_id: str, model: str, prompt_text: str, image_url: str) -> dict:
    """One JSONL request for POST /v1/responses (improved Words rules)."""
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": prompt_text}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": IMPROVED_USER_MESSAGE},
                        {"type": "input_image", "image_url": image_url},
                    ],
                },
            ],
        },
    }


def main() -> None:
    if not BATCH_JSON.exists():
        print(f"Missing {BATCH_JSON}", file=sys.stderr)
        sys.exit(1)
    with open(BATCH_JSON, encoding="utf-8") as f:
        batch_entries = json.load(f)
    indices = [e["Index"] for e in batch_entries]
    if len(indices) != 180:
        print(f"Expected 180 indices, got {len(indices)}", file=sys.stderr)
        sys.exit(1)

    if not PROMPT_MD.exists():
        print(f"Prompt not found: {PROMPT_MD}", file=sys.stderr)
        sys.exit(1)
    prompt_text = PROMPT_MD.read_text(encoding="utf-8")

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    model = "gpt-5-mini"
    written = 0
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for idx in indices:
            png_path = PNG_ROOT / idx / "page2.png"
            if not png_path.exists():
                print(f"Skip {idx}: missing {png_path}", file=sys.stderr)
                continue
            img_b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
            image_url = f"data:image/png;base64,{img_b64}"
            line = build_batch_line(idx, model, prompt_text, image_url)
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
            written += 1
    print(f"Wrote {written} requests to {OUT_JSONL}")


if __name__ == "__main__":
    main()
