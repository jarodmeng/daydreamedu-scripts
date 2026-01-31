#!/usr/bin/env python3
"""
Extract radical → stroke count mapping from 汉文学网 (HWXNet) 按部首查字 page.

The page https://zd.hwxnet.com/bushou.html organizes radicals by stroke count
(笔画一, 笔画二, …). Each radical link has an href like .../bushou/...-N.html
where N is the radical's stroke count. This script fetches the page, parses
those links, and writes a JSON mapping for use by the Chinese character app
(e.g. for sorting the Radicals page by radical stroke count).

Output: chinese_chr_app/data/radical_stroke_counts.json
  { "一": 1, "丨": 1, "口": 3, "木": 4, ... }

Usage:
  python extract_radical_stroke_counts.py [--output PATH] [--filter-radicals PATH]

  --output PATH         Write JSON here (default: ../data/radical_stroke_counts.json).
  --filter-radicals PATH  Optional: path to a JSON array or newline-separated file
                          of radical characters; only output mappings for these.
"""

import argparse
import json
import re
import ssl
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Set

from bs4 import BeautifulSoup


BUSHOU_URL = "https://zd.hwxnet.com/bushou.html"
# Match href like .../bushou/...-3.html or bushou/...-15.html
HREF_STROKE_RE = re.compile(r"bushou/[^/]+-(\d+)\.html$", re.I)


def fetch_bushou_html() -> str:
    """Fetch the 按部首查字 page with same SSL/headers as other HWXNet scrapers."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(BUSHOU_URL)
    req.add_header(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    )
    with urllib.request.urlopen(req, context=ssl_context, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse_radical_stroke_mapping(html: str) -> Dict[str, int]:
    """
    Parse HTML and return dict: radical_char -> stroke_count.
    Uses link hrefs that end with -N.html (N = stroke count); link text = radical.
    """
    soup = BeautifulSoup(html, "lxml")
    mapping: Dict[str, int] = {}
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        m = HREF_STROKE_RE.search(href)
        if not m:
            continue
        stroke_count = int(m.group(1))
        text = (a.get_text() or "").strip()
        if not text:
            continue
        # Skip "难检字" (hard-to-index) under 其他
        if text == "难检字":
            continue
        # One radical char or a few (e.g. multi-char labels); take first char for single
        if len(text) == 1:
            mapping[text] = stroke_count
        else:
            # Some entries might be multi-char; store each char with same count
            for c in text:
                if c.strip():
                    mapping[c] = stroke_count
    return mapping


def load_filter_radicals(path: Path) -> Optional[Set[str]]:
    """Load set of radical chars to keep. File: JSON array or one radical per line."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return {str(x).strip() for x in data if str(x).strip()}
    except json.JSONDecodeError:
        pass
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines:
        return set(lines)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract radical→stroke_count from 汉文学网 按部首查字 and write JSON."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output JSON path (default: ../data/radical_stroke_counts.json)",
    )
    parser.add_argument(
        "--filter-radicals",
        type=Path,
        default=None,
        help="Optional: only output radicals in this file (JSON array or one per line)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and parse only; print mapping to stdout, do not write file",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    default_output = script_dir.parent / "data" / "radical_stroke_counts.json"
    output_path = args.output or default_output

    print(f"Fetching {BUSHOU_URL} ...")
    html = fetch_bushou_html()
    mapping = parse_radical_stroke_mapping(html)
    print(f"Parsed {len(mapping)} radical → stroke count entries.")

    filter_set = None
    if args.filter_radicals:
        filter_set = load_filter_radicals(args.filter_radicals)
        if filter_set:
            mapping = {k: v for k, v in mapping.items() if k in filter_set}
            print(f"Filtered to {len(mapping)} radicals (from {len(filter_set)} in filter).")
        else:
            print("Warning: --filter-radicals file empty or invalid; using full mapping.")

    if args.dry_run:
        print(json.dumps(mapping, ensure_ascii=False, indent=2))
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
