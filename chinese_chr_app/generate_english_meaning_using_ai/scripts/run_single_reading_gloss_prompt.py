#!/usr/bin/env python3
"""
Run reading-level English gloss prompts for one polyphonic character.

This slices one character into reading-specific payloads using local JSON data and
optionally calls OpenAI once per reading bucket.

Usage:
  python3 run_single_reading_gloss_prompt.py --hanzi 行 --dry-run
  python3 run_single_reading_gloss_prompt.py --hanzi 行
  python3 run_single_reading_gloss_prompt.py --hanzi 参 --reading shēn
  python3 run_single_reading_gloss_prompt.py --hanzi 累 --count-tokens
"""

import argparse
import gzip
import json
import re
import sys
import unicodedata
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DEFAULT_PROMPT_MD = ROOT / "prompts" / "reading_level_english_gloss_generation_prompt.md"
DEFAULT_HWXNET_JSON = ROOT.parent / "data" / "extracted_characters_hwxnet.json"
DEFAULT_FENG_JSON = ROOT.parent / "data" / "characters.json"
DEFAULT_CEDICT_FILE = ROOT.parent / "data" / "cc_cedict" / "cedict_1_0_ts_utf-8_mdbg.txt.gz"


TONE_MARKS = {
    "ā": ("a", "1"),
    "á": ("a", "2"),
    "ǎ": ("a", "3"),
    "à": ("a", "4"),
    "ē": ("e", "1"),
    "é": ("e", "2"),
    "ě": ("e", "3"),
    "è": ("e", "4"),
    "ī": ("i", "1"),
    "í": ("i", "2"),
    "ǐ": ("i", "3"),
    "ì": ("i", "4"),
    "ō": ("o", "1"),
    "ó": ("o", "2"),
    "ǒ": ("o", "3"),
    "ò": ("o", "4"),
    "ū": ("u", "1"),
    "ú": ("u", "2"),
    "ǔ": ("u", "3"),
    "ù": ("u", "4"),
    "ǖ": ("v", "1"),
    "ǘ": ("v", "2"),
    "ǚ": ("v", "3"),
    "ǜ": ("v", "4"),
    "ü": ("v", "5"),
    "ń": ("n", "2"),
    "ň": ("n", "3"),
    "ǹ": ("n", "4"),
    "ḿ": ("m", "2"),
}


def extract_system_message(prompt_md_path: Path) -> str:
    text = prompt_md_path.read_text(encoding="utf-8")
    start_marker = "## 1. System message"
    idx = text.find(start_marker)
    if idx == -1:
        raise ValueError(f"Could not find '{start_marker}' in {prompt_md_path}")
    rest = text[idx + len(start_marker) :]
    match = re.search(r"```\s*\n(.*?)```", rest, re.DOTALL)
    if not match:
        raise ValueError("Could not find system message code block in prompt .md")
    return match.group(1).strip()


def tone_mark_to_numbered(pinyin: str) -> str:
    if not pinyin:
        return ""
    chars = []
    tone = "5"
    for ch in unicodedata.normalize("NFC", pinyin.strip().lower()):
        mapped = TONE_MARKS.get(ch)
        if mapped:
            base, detected_tone = mapped
            chars.append(base)
            if detected_tone != "5":
                tone = detected_tone
        elif ch.isalpha():
            chars.append(ch)
    return "".join(chars) + tone


def load_hwxnet(data_json: Path) -> dict:
    return json.loads(data_json.read_text(encoding="utf-8"))


def load_feng_lookup(feng_json: Path) -> dict:
    rows = json.loads(feng_json.read_text(encoding="utf-8"))
    return {
        row["Character"]: row
        for row in rows
        if isinstance(row, dict) and row.get("Character")
    }


def load_cedict_lookup(cedict_json: Path | None) -> dict:
    if cedict_json is None or not cedict_json.exists():
        return {}

    if cedict_json.suffix == ".gz" or cedict_json.name.endswith(".txt"):
        return load_cedict_text_lookup(cedict_json)

    data = json.loads(cedict_json.read_text(encoding="utf-8"))
    lookup: dict[tuple[str, str], list[dict]] = {}

    def add_entry(hanzi: str, reading_key: str, entry: dict) -> None:
        if not hanzi or not reading_key:
            return
        key = (hanzi, reading_key)
        lookup.setdefault(key, []).append(entry)

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(key, str) and "|" in key:
                hanzi, reading_key = key.split("|", 1)
                entries = value if isinstance(value, list) else [value]
                for entry in entries:
                    if isinstance(entry, dict):
                        add_entry(hanzi, reading_key, entry)
            elif isinstance(value, dict):
                for reading_key, entries in value.items():
                    if not isinstance(reading_key, str):
                        continue
                    entry_list = entries if isinstance(entries, list) else [entries]
                    for entry in entry_list:
                        if isinstance(entry, dict):
                            add_entry(key, reading_key, entry)
    elif isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            hanzi = (
                entry.get("hanzi")
                or entry.get("simplified")
                or entry.get("traditional")
                or ""
            )
            reading_key = (
                entry.get("reading_key")
                or entry.get("pinyin_numbered")
                or entry.get("pinyin")
                or ""
            )
            if isinstance(reading_key, str):
                reading_key = reading_key.strip()
            if isinstance(hanzi, str) and isinstance(reading_key, str):
                add_entry(hanzi.strip(), reading_key, entry)

    return lookup


def load_cedict_text_lookup(cedict_path: Path) -> dict:
    """
    Load a CC-CEDICT text archive (.txt or .txt.gz) into a lookup keyed by
    (hanzi, numbered_reading).
    """
    lookup: dict[tuple[str, str], list[dict]] = {}
    line_re = re.compile(
        r"^(?P<traditional>\S+)\s+(?P<simplified>\S+)\s+\[(?P<pinyin>[^\]]+)\]\s+/(?P<defs>.*)/$"
    )

    opener = gzip.open if cedict_path.suffix == ".gz" else open
    with opener(cedict_path, "rt", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = line_re.match(line)
            if not match:
                continue

            traditional = match.group("traditional").strip()
            simplified = match.group("simplified").strip()
            pinyin_numbered = match.group("pinyin").strip()
            definitions = [d.strip() for d in match.group("defs").split("/") if d.strip()]
            entry = {
                "source": "runtime_cc_cedict_lookup",
                "traditional": traditional,
                "simplified": simplified,
                "pinyin": pinyin_numbered,
                "definitions": definitions,
            }
            for hanzi in {traditional, simplified}:
                lookup.setdefault((hanzi, pinyin_numbered), []).append(entry)
    return lookup


def get_cedict_candidates(
    hanzi: str,
    reading: str,
    *,
    cedict_lookup: dict | None = None,
) -> list[dict]:
    """
    Return CC-CEDICT candidate entries for one character+reading unit.

    Today this supports an optional local JSON fixture for testing prompt shape.
    Later, the runtime CC-CEDICT query path can replace or augment this function
    without changing the rest of the prompt-building code.
    """
    reading_key = tone_mark_to_numbered(reading)
    candidates = list((cedict_lookup or {}).get((hanzi, reading_key), []))

    normalized = []
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        normalized_entry = dict(entry)
        normalized_entry.setdefault("source", "runtime_cc_cedict_lookup")
        normalized_entry.setdefault("pinyin", reading_key)
        normalized.append(normalized_entry)
    return normalized


def reading_bucket_items(buckets: list, reading: str) -> list[str]:
    items = []
    seen = set()
    for bucket in buckets or []:
        if not isinstance(bucket, dict):
            continue
        if (bucket.get("Pinyin") or "").strip() != reading:
            continue
        for item in bucket.get("Phrases") or []:
            if not isinstance(item, str):
                continue
            value = item.strip()
            if value and value not in seen:
                seen.add(value)
                items.append(value)
    return items


def basic_meanings_for_reading(entry: dict, reading: str) -> list[dict]:
    rows = []
    for sense in entry.get("基本字义解释") or []:
        if not isinstance(sense, dict):
            continue
        if (sense.get("读音") or "").strip() == reading:
            rows.append(sense)
    return rows


def basic_example_words(senses: list[dict]) -> list[str]:
    items = []
    seen = set()
    for sense in senses:
        for definition in sense.get("释义") or []:
            if not isinstance(definition, dict):
                continue
            for item in definition.get("例词") or []:
                if not isinstance(item, str):
                    continue
                value = item.strip()
                if value and value not in seen:
                    seen.add(value)
                    items.append(value)
    return items


def summarize_evidence(
    *,
    senses: list[dict],
    feng_words: list[str],
    hwxnet_common_phrases: list[str],
    cedict_candidates: list[dict],
) -> dict:
    basic_examples = basic_example_words(senses)
    return {
        "basic_meanings_count": len(senses),
        "basic_examples_count": len(basic_examples),
        "feng_phrase_count": len(feng_words),
        "common_phrase_count": len(hwxnet_common_phrases),
        "cedict_candidate_count": len(cedict_candidates),
    }


def assess_review_risk(summary: dict) -> tuple[bool, str | None]:
    basic_meanings_count = int(summary.get("basic_meanings_count") or 0)
    basic_examples_count = int(summary.get("basic_examples_count") or 0)
    feng_phrase_count = int(summary.get("feng_phrase_count") or 0)
    common_phrase_count = int(summary.get("common_phrase_count") or 0)
    cedict_candidate_count = int(summary.get("cedict_candidate_count") or 0)

    total_phrase_support = basic_examples_count + feng_phrase_count + common_phrase_count
    if basic_meanings_count == 0 and cedict_candidate_count == 0:
        return True, "No reading-specific basic_meanings or CC-CEDICT candidate entries."
    if basic_meanings_count == 0 and total_phrase_support <= 2:
        return True, "No reading-specific basic_meanings and only very sparse phrase evidence."
    if total_phrase_support <= 1 and cedict_candidate_count == 0:
        return True, "Only one or zero supporting phrases and no CC-CEDICT candidate."
    return False, None


def build_user_payload(
    hanzi: str,
    reading: str,
    hwxnet_entry: dict,
    feng_entry: dict | None,
    cedict_lookup: dict | None = None,
) -> dict:
    senses = basic_meanings_for_reading(hwxnet_entry, reading)
    reading_key = tone_mark_to_numbered(reading)
    feng_words = reading_bucket_items((feng_entry or {}).get("WordsByPinyin") or [], reading)
    hwxnet_common_phrases = reading_bucket_items(hwxnet_entry.get("常用词组按拼音") or [], reading)
    cedict_candidates = get_cedict_candidates(
        hanzi,
        reading,
        cedict_lookup=cedict_lookup,
    )
    merged_examples = []
    seen = set()
    for source_items in (
        feng_words,
        hwxnet_common_phrases,
        basic_example_words(senses),
    ):
        for item in source_items:
            if item not in seen:
                seen.add(item)
                merged_examples.append(item)

    stroke_count = hwxnet_entry.get("总笔画")
    if stroke_count is not None and not isinstance(stroke_count, int):
        try:
            stroke_count = int(stroke_count)
        except (TypeError, ValueError):
            stroke_count = None

    evidence_summary = summarize_evidence(
        senses=senses,
        feng_words=feng_words,
        hwxnet_common_phrases=hwxnet_common_phrases,
        cedict_candidates=cedict_candidates,
    )
    likely_needs_review, likely_review_reason = assess_review_risk(evidence_summary)

    return {
        "unit_id": f"{hanzi}|{reading_key}",
        "hanzi": hanzi,
        "reading": reading,
        "all_readings": hwxnet_entry.get("拼音") or [],
        "radical": hwxnet_entry.get("部首", ""),
        "stroke_count": stroke_count,
        "reading_basic_meanings": senses,
        "reading_feng_words_by_pinyin": feng_words,
        "reading_common_phrases_by_pinyin": hwxnet_common_phrases,
        "reading_example_phrases": merged_examples,
        "cedict_candidates": cedict_candidates,
        "evidence_summary": evidence_summary,
        "likely_needs_review": likely_needs_review,
        "likely_review_reason": likely_review_reason,
        "current_character_level_english_gloss": hwxnet_entry.get("英文翻译") or [],
    }


def validate_and_fix_response(parsed: dict, payload: dict) -> tuple[dict, list[str]]:
    fixes = []
    for field in ("unit_id", "hanzi", "reading"):
        expected = payload[field]
        if parsed.get(field) != expected:
            parsed[field] = expected
            fixes.append(f"Set {field} from request")

    if not parsed.get("english_gloss") or not isinstance(parsed.get("english_gloss"), str):
        parsed["english_gloss"] = "unknown"
        fixes.append("Set english_gloss to placeholder (missing)")

    short_glosses = parsed.get("short_glosses")
    if not isinstance(short_glosses, list):
        parsed["short_glosses"] = [parsed["english_gloss"]]
        fixes.append("Set short_glosses from english_gloss")
    else:
        cleaned = [str(x).strip() for x in short_glosses if str(x).strip()]
        parsed["short_glosses"] = cleaned or [parsed["english_gloss"]]
        if cleaned != short_glosses:
            fixes.append("Normalized short_glosses")

    score = parsed.get("confidence_score")
    if not isinstance(score, (int, float)):
        parsed["confidence_score"] = 0.5
        fixes.append("Set confidence_score to 0.5")
    else:
        parsed["confidence_score"] = max(0.0, min(1.0, float(score)))

    if not isinstance(parsed.get("qc_flags"), dict):
        parsed["qc_flags"] = {}
        fixes.append("Set qc_flags object")
    for key, default in (
        ("needs_human_review", False),
        ("review_reason", None),
        ("used_character_level_gloss_as_hint", False),
    ):
        if key not in parsed["qc_flags"]:
            parsed["qc_flags"][key] = default
            fixes.append(f"Set qc_flags.{key}")

    return parsed, fixes


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reading-level gloss prompt(s) for one character")
    parser.add_argument("--hanzi", required=True, help="Character to run")
    parser.add_argument("--reading", default=None, help="Optional single reading to run, e.g. shēn")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model")
    parser.add_argument("--dry-run", action="store_true", help="Print requests only")
    parser.add_argument("--count-tokens", action="store_true", help="Count prompt tokens only")
    parser.add_argument("--prompt-md", type=Path, default=DEFAULT_PROMPT_MD, help="Prompt file path")
    parser.add_argument("--hwxnet-json", type=Path, default=DEFAULT_HWXNET_JSON, help="HWXNet data JSON")
    parser.add_argument("--feng-json", type=Path, default=DEFAULT_FENG_JSON, help="Feng data JSON")
    parser.add_argument(
        "--cedict-json",
        type=Path,
        default=DEFAULT_CEDICT_FILE,
        help="Optional CC-CEDICT source: either a local JSON fixture or the official .txt/.txt.gz archive for runtime candidate lookup",
    )
    args = parser.parse_args()

    hwxnet = load_hwxnet(args.hwxnet_json)
    feng_lookup = load_feng_lookup(args.feng_json)
    cedict_lookup = load_cedict_lookup(args.cedict_json)
    if args.hanzi not in hwxnet:
        print(f"Error: character '{args.hanzi}' not found", file=sys.stderr)
        sys.exit(1)

    entry = hwxnet[args.hanzi]
    readings = [p for p in (entry.get("拼音") or []) if isinstance(p, str) and p.strip()]
    if args.reading:
        readings = [r for r in readings if r == args.reading]
        if not readings:
            print(f"Error: reading '{args.reading}' not found for '{args.hanzi}'", file=sys.stderr)
            sys.exit(1)

    system_content = extract_system_message(args.prompt_md)
    payloads = [
        build_user_payload(
            args.hanzi,
            reading,
            entry,
            feng_lookup.get(args.hanzi),
            cedict_lookup,
        )
        for reading in readings
    ]

    if args.count_tokens:
        try:
            import tiktoken
        except ImportError:
            print("Error: tiktoken required for --count-tokens. Install with: pip install tiktoken", file=sys.stderr)
            sys.exit(1)
        enc = tiktoken.encoding_for_model(args.model)
        print(f"Input tokens (model={args.model}):")
        for payload in payloads:
            user_content = json.dumps(payload, ensure_ascii=False, indent=2)
            total = len(enc.encode(system_content)) + len(enc.encode(user_content))
            print(f"  {payload['unit_id']}: {total:,}")
        return

    if args.dry_run:
        print(f"Dry run for {args.hanzi} ({len(payloads)} reading unit(s))", file=sys.stderr)
        for payload in payloads:
            print(f"\n=== {payload['unit_id']} ===", file=sys.stderr)
            print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return

    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package required. Install with: pip install openai", file=sys.stderr)
        sys.exit(1)

    client = OpenAI()
    results = []
    for payload in payloads:
        user_content = json.dumps(payload, ensure_ascii=False, indent=2)
        request = {
            "model": args.model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 256,
        }
        print(f"Calling OpenAI for {payload['unit_id']}...", file=sys.stderr)
        response = client.chat.completions.create(**request)
        content = response.choices[0].message.content
        parsed = json.loads(content)
        parsed, fixes = validate_and_fix_response(parsed, payload)
        if fixes:
            print(f"Validation fixes for {payload['unit_id']}: {', '.join(fixes)}", file=sys.stderr)
        results.append(parsed)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
