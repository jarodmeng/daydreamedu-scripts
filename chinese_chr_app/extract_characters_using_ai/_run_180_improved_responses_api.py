#!/usr/bin/env python3
"""
One-off: Run the 180 character indices through the Responses API (sync) with the
improved prompt. Saves results to JSON; no merge into characters.json.

Usage (from repo root):
    python3 chinese_chr_app/extract_characters_using_ai/_run_180_improved_responses_api.py
"""
import base64
import json
import re
import sys
import time
from pathlib import Path

from openai import OpenAI

SCRIPT_DIR = Path(__file__).resolve().parent
CHINESE_CHR_APP = SCRIPT_DIR.parent
PROMPT_MD = SCRIPT_DIR / "chinese_character_extraction_prompt.md"
PNG_ROOT = CHINESE_CHR_APP / "data" / "png"
BATCH_JSON = Path("/tmp/fix_bad_words_batch.json")
OUT_JSON = SCRIPT_DIR / "jsonl" / "improved_180_results.json"

IMPROVED_USER_MESSAGE = (
    "Extract the fields for this single Chinese character card (second page).\n"
    "Output only a Markdown table with one row. Pinyin and Words must be JSON arrays.\n"
    "Every Words item must contain the Character; keep full idioms as single items.\n"
    "Do not split idioms and drop parts.\n"
)


def extract_table_from_response(response_text: str):
    table_start = response_text.find(
        "| Index | Character | Pinyin | Radical | Strokes | Structure | Sentence | Words |"
    )
    if table_start == -1:
        table_start = response_text.find("| Index | Character |")
    if table_start == -1:
        return None
    lines = response_text[table_start:].split("\n")
    table_lines = []
    for line in lines:
        if line.strip() and ("|" in line or not table_lines):
            table_lines.append(line)
        elif table_lines and not line.strip():
            break
    return "\n".join(table_lines)


def parse_markdown_table(table_text: str):
    lines = [line.strip() for line in table_text.strip().split("\n") if line.strip()]
    if len(lines) < 2:
        return None
    for line in lines[1:]:
        if re.match(r"^\|[\s\-:]+\|", line):
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 8:
            return {
                "Index": parts[0],
                "Character": parts[1],
                "Pinyin": parts[2],
                "Radical": parts[3],
                "Strokes": parts[4],
                "Structure": parts[5],
                "Sentence": parts[6],
                "Words": parts[7],
            }
    return None


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

    client = OpenAI()
    model = "gpt-5-mini"
    results = []
    errors = []

    for i, idx in enumerate(indices):
        png_path = PNG_ROOT / idx / "page2.png"
        if not png_path.exists():
            errors.append({"Index": idx, "error": f"Missing {png_path}"})
            print(f"  [{i+1}/180] {idx} skip (no PNG)")
            continue
        img_b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
        image_url = f"data:image/png;base64,{img_b64}"

        try:
            resp = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": prompt_text}],
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": IMPROVED_USER_MESSAGE},
                            {"type": "input_image", "image_url": image_url},
                        ],
                    },
                ],
            )
        except Exception as e:
            errors.append({"Index": idx, "error": str(e)})
            print(f"  [{i+1}/180] {idx} API error: {e}")
            continue

        text = ""
        for item in resp.output:
            if getattr(item, "type", None) == "message" and getattr(item, "status", None) == "completed":
                for c in getattr(item, "content", []):
                    if getattr(c, "type", None) == "output_text":
                        text = getattr(c, "text", "") or ""
                        break
                if text:
                    break

        table_text = extract_table_from_response(text)
        if not table_text:
            errors.append({"Index": idx, "error": "No table in response"})
            print(f"  [{i+1}/180] {idx} no table")
            continue
        row = parse_markdown_table(table_text)
        if not row:
            errors.append({"Index": idx, "error": "Parse failed"})
            print(f"  [{i+1}/180] {idx} parse failed")
            continue

        row["Index"] = f"{int(row['Index']):04d}"
        try:
            row["Pinyin"] = json.loads(row["Pinyin"]) if row.get("Pinyin") else []
        except json.JSONDecodeError:
            row["Pinyin"] = []
        try:
            row["Words"] = json.loads(row["Words"]) if row.get("Words") else []
        except json.JSONDecodeError:
            row["Words"] = []

        results.append(row)
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  [{i+1}/180] {idx} {row.get('Character', '?')} ok")
        time.sleep(0.2)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(results)} results to {OUT_JSON}")
    if errors:
        print(f"Errors: {len(errors)}")
        err_path = OUT_JSON.parent / "improved_180_errors.json"
        with open(err_path, "w", encoding="utf-8") as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)
        print(f"Errors saved to {err_path}")


if __name__ == "__main__":
    main()
