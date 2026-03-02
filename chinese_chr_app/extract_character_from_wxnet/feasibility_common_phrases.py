#!/usr/bin/env python3
"""
Feasibility check: fetch a few HWXNet pages, confirm DOM structure for 常用词组,
and report what would be extracted as 常用词组 (common phrases).

Run from extract_character_from_wxnet/: python3 feasibility_common_phrases.py
Uses characters from ../data/characters.json; randomly samples N characters.
"""

import json
import random
import re
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"
CHARACTERS_JSON = DATA_DIR / "characters.json"


def load_character_list(limit=None):
    """Load unique characters from characters.json."""
    if not CHARACTERS_JSON.exists():
        print(f"Missing {CHARACTERS_JSON}", file=sys.stderr)
        return []
    with open(CHARACTERS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    seen = set()
    chars = []
    for entry in data:
        c = (entry.get("Character") or "").strip()
        if c and c not in seen:
            seen.add(c)
            chars.append(c)
    if limit:
        chars = chars[:limit]
    return chars


def fetch_page(character: str) -> str:
    """Fetch HWXNet search page HTML for one character."""
    url = f"https://zd.hwxnet.com/search.do?keyword={urllib.parse.quote(character)}"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (compatible; feasibility-check)")
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return resp.read().decode("utf-8")


def inspect_dom_and_extract_common_phrases(soup: BeautifulSoup) -> tuple[list, str]:
    """
    Find 常用词组 section and extract phrase list.
    DOM: h1 "常用词组" is inside div.sub_label; content is in the NEXT SIBLING of that
    div: div.view_con.clearfix.
    Returns (phrases_list, dom_description).
    """
    h1 = soup.find("h1", string=re.compile(r"常用词组"))
    if not h1:
        return [], "no h1 '常用词组' found"

    # Content is in next sibling of h1's parent (parent = div.sub_label, next = div.view_con)
    parent = h1.parent
    if not parent:
        return [], "h1 has no parent"

    content_div = None
    for sib in parent.next_siblings:
        if hasattr(sib, "name") and sib.name == "div":
            content_div = sib
            break

    if not content_div:
        return [], "parent has no next sibling div"

    classes = content_div.get("class") or []
    dom_desc = f"h1 in sub_label, content div (class={classes})"

    text = content_div.get_text()
    phrases = []
    for part in re.split(r"[◎]\s+", text):
        part = part.strip()
        if not part:
            continue
        first_line = part.split("\n")[0].strip()
        match = re.match(r"([\u4e00-\u9fff]+)", first_line)
        if match:
            phrase = match.group(1)
            if phrase and phrase not in phrases:
                phrases.append(phrase)

    return phrases, dom_desc


def main():
    random.seed(42)
    chars = load_character_list()
    if not chars:
        sys.exit(1)
    # Sample 8 random characters, then ensure 卢 and 沈 are included
    sample = random.sample(chars, min(8, len(chars)))
    for c in ["卢", "沈"]:
        if c in chars and c not in sample:
            sample.append(c)

    print("Feasibility: 常用词组 extraction (DOM structure + extracted phrases)\n")
    print("Characters:", " ".join(sample), "\n")

    for character in sample:
        try:
            html = fetch_page(character)
            soup = BeautifulSoup(html, "lxml")
            phrases, dom_desc = inspect_dom_and_extract_common_phrases(soup)
            status = f"phrases={len(phrases)}" if phrases else "empty/missing"
            print(f"  {character}: {dom_desc} -> {status}")
            if phrases:
                print(f"      -> {phrases[:10]}{' ...' if len(phrases) > 10 else ''}")
        except Exception as e:
            print(f"  {character}: ERROR {e}")
    print("\nDone.")


if __name__ == "__main__":
    main()
