#!/usr/bin/env python3
"""
Extract target-character reading tags for HWXNet 常用词组.

This script fetches the HWXNet page for one character, reads the 常用词组 section,
captures each phrase and its displayed phrase pinyin, and derives the reading of
the target character within that phrase.

Narrow scope:
- output the target-character reading tag only
- do not build a full phrase-pronunciation dataset as the main artifact

Current derivation strategy:
- support phrases that begin with the target character
- derive the reading by matching the beginning of the displayed phrase pinyin
  against the character's allowed HWXNet readings

Usage:
  python3 extract_common_phrase_character_readings.py 行
  python3 extract_common_phrase_character_readings.py 行 --pretty
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from extract_character_hwxnet import (
    _normalize_pinyin_list,
    extract_character_info,
)

try:
    from dotenv import load_dotenv

    ENV_FILE = Path(__file__).resolve().parent.parent / "chinese_chr_app" / "backend" / ".env.local"
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
except ImportError:
    pass

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("DATABASE_URL or SUPABASE_DB_URL is not set.")
    if psycopg is None:
        raise RuntimeError("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
    return url


def _load_allowed_readings_from_db(character: str) -> List[str]:
    query = """
    SELECT pinyin
    FROM hwxnet_characters
    WHERE character = %s
    LIMIT 1
    """
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (character,))
            row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Character not found in hwxnet_characters: {character}")
    return _normalize_pinyin_list(row.get("pinyin") or [])


def _get_common_phrase_content_div(soup: BeautifulSoup):
    h1 = soup.find("h1", string=re.compile(r"常用词组"))
    if not h1:
        return None

    parent = h1.parent
    if not parent:
        return None

    for sib in parent.next_siblings:
        if hasattr(sib, "name") and sib.name == "div":
            return sib
    return None


def _extract_common_phrase_entries(content_div) -> List[Dict[str, str]]:
    """
    Extract entry rows from the 常用词组 section.

    DOM pattern:
      <p>◎ <strong>行板</strong> <span class="cpinyin">xíngbǎn</span></p>
      <p class="pgroup">...</p>
    """
    entries: List[Dict[str, str]] = []
    for p in content_div.find_all("p", recursive=False):
        classes = p.get("class") or []
        if "pgroup" in classes:
            continue
        phrase_el = p.find("strong")
        pinyin_el = p.find("span", class_="cpinyin")
        phrase = phrase_el.get_text(strip=True) if phrase_el else ""
        phrase_pinyin = pinyin_el.get_text(strip=True) if pinyin_el else ""
        if not phrase:
            continue
        entries.append(
            {
                "phrase": phrase,
                "displayed_phrase_pinyin": phrase_pinyin,
            }
        )
    return entries


def _derive_target_reading_from_phrase_pinyin(
    character: str,
    phrase: str,
    phrase_pinyin: str,
    allowed_readings: List[str],
) -> tuple[Optional[str], Optional[str]]:
    """
    Derive the reading of the target character from the displayed phrase pinyin.

    Current narrow strategy:
    - phrase must begin with the target character
    - phrase_pinyin must begin with one allowed reading

    Returns:
      (reading, note) where reading may be None if unresolved
    """
    if not phrase or not phrase_pinyin:
        return None, "missing phrase or phrase pinyin"

    if not phrase.startswith(character):
        return None, "phrase does not start with target character"

    compact_phrase_pinyin = phrase_pinyin.replace(" ", "")
    norm_phrase_pinyin = _normalize_pinyin_list([compact_phrase_pinyin])
    if not norm_phrase_pinyin:
        return None, "phrase pinyin could not be normalized"
    norm_phrase_pinyin_value = norm_phrase_pinyin[0]

    matches = [
        reading
        for reading in allowed_readings
        if norm_phrase_pinyin_value.startswith(reading)
    ]
    if not matches:
        return None, "phrase pinyin does not start with any allowed reading"

    # Prefer the longest prefix match in case readings share prefixes.
    matches.sort(key=len, reverse=True)
    best = matches[0]
    tied = [m for m in matches if len(m) == len(best)]
    if len(tied) > 1:
        return None, f"ambiguous prefix match: {tied}"
    return best, None


def extract_common_phrase_character_readings(character: str) -> Dict[str, Any]:
    """
    Fetch one HWXNet page and derive target-character readings for 常用词组 items.
    """
    if not character or len(character) != 1:
        raise ValueError("character must be a single Chinese character")

    info = extract_character_info(character)
    source_url = info.get("source_url")
    allowed_readings = _load_allowed_readings_from_db(character)

    # Re-fetch via extract_character_info's source page HTML is not exposed, so fetch by URL again
    # using the same source page through BeautifulSoup from the page text embedded in the extractor
    # path would require refactor. For now, use the page URL and BeautifulSoup directly.
    import ssl
    import urllib.request

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(source_url)
    req.add_header("User-Agent", "Mozilla/5.0 (compatible; common-phrase-reading-extractor)")
    with urllib.request.urlopen(req, context=ssl_context, timeout=30) as response:
        html_content = response.read().decode("utf-8")

    soup = BeautifulSoup(html_content, "lxml")
    content_div = _get_common_phrase_content_div(soup)

    results: List[Dict[str, Any]] = []
    if not content_div:
        return {
            "character": character,
            "source_url": source_url,
            "allowed_readings": allowed_readings,
            "common_phrase_readings": results,
            "notes": ["常用词组 section not found"],
        }

    for entry in _extract_common_phrase_entries(content_div):
        phrase = entry.get("phrase", "")
        phrase_pinyin = entry.get("displayed_phrase_pinyin", "")
        if not phrase:
            continue

        reading, note = _derive_target_reading_from_phrase_pinyin(
            character=character,
            phrase=phrase,
            phrase_pinyin=phrase_pinyin,
            allowed_readings=allowed_readings,
        )

        row: Dict[str, Any] = {
            "phrase": phrase,
            "reading": reading,
        }
        if phrase_pinyin:
            row["displayed_phrase_pinyin"] = phrase_pinyin
        if note:
            row["note"] = note
        results.append(row)

    return {
        "character": character,
        "source_url": source_url,
        "allowed_readings": allowed_readings,
        "common_phrase_readings": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract target-character reading tags for HWXNet 常用词组.",
    )
    parser.add_argument("character", help="Single Chinese character to inspect.")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    args = parser.parse_args()

    try:
        payload = extract_common_phrase_character_readings(args.character)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
