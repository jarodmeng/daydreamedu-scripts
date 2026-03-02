#!/usr/bin/env python3
"""Inspect raw DOM around 常用词组 on HWXNet page for 卢."""
import re
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

url = "https://zd.hwxnet.com/search.do?keyword=" + urllib.parse.quote("卢")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(url)
req.add_header("User-Agent", "Mozilla/5.0")
with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
    html = resp.read().decode("utf-8")

soup = BeautifulSoup(html, "lxml")

# Find all h1s and show their next few siblings
for h1 in soup.find_all("h1"):
    text = h1.get_text(strip=True)
    print(f"\n=== H1: {text!r} ===")
    for i, sib in enumerate(h1.next_siblings):
        if i >= 5:
            break
        name = getattr(sib, "name", None)
        if name:
            cls = getattr(sib, "get", lambda x: None)("class")
            preview = (sib.get_text() or "")[:80].replace("\n", " ")
            print(f"  sibling {i}: <{name} class={cls}> ... {preview!r}")
        else:
            # NavigableString
            preview = str(sib).strip()[:60]
            if preview:
                print(f"  sibling {i}: text {preview!r}")

# After 常用词组 h1: list more siblings to find the content div
h1_common = soup.find("h1", string=re.compile(r"常用词组"))
if h1_common:
    print("\n=== All siblings after 常用词组 h1 (first 15) ===")
    for i, sib in enumerate(h1_common.next_siblings):
        if i >= 15:
            break
        name = getattr(sib, "name", None)
        if name:
            cls = getattr(sib, "get", lambda x: None)("class")
            text = (sib.get_text() or "").strip()[:100]
            print(f"  {i}: <{name} class={cls}> -> {text!r}")
        else:
            t = str(sib).strip()
            if t:
                print(f"  {i}: text -> {t[:80]!r}")

# Find div.view_con that appears after 常用词组 (same parent as h1?)
parent = h1_common.parent if h1_common else None
if parent:
    print("\n=== Parent of 常用词组 h1 ===")
    print(f"  <{parent.name} class={parent.get('class')}>")
    print("  Siblings of this parent (next only):")
    for i, sib in enumerate(parent.next_siblings):
        if i >= 8:
            break
        name = getattr(sib, "name", None)
        if name:
            cls = getattr(sib, "get", lambda x: None)("class")
            has_lubi = "卢比" in (sib.get_text() or "")
            print(f"    {i}: <{name} class={cls}> contains_卢比={has_lubi}")

# Also: find any div that contains "卢比"
div_with_lubi = soup.find(string=re.compile(r"卢比"))
if div_with_lubi:
    parent = div_with_lubi.parent
    for _ in range(10):
        if parent is None:
            break
        print(f"\n  Parent of '卢比': <{parent.name} class={parent.get('class')}>")
        parent = getattr(parent, "parent", None)
