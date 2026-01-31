#!/usr/bin/env python3
"""Tests for GET /api/pinyin-search."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app


def test_pinyin_search_tone_specific_returns_characters():
    """Valid tone-specific query (e.g. wo3) returns 200, found true, characters list."""
    with app.test_client() as client:
        r = client.get("/api/pinyin-search?q=wo3")
    assert r.status_code == 200
    data = r.get_json()
    assert data["found"] is True
    assert "characters" in data
    assert len(data["characters"]) >= 1
    chars = data["characters"]
    characters_only = [c["character"] for c in chars]
    assert "我" in characters_only
    # Sort order: strokes ASC, then zibiao_index ASC
    for i in range(len(chars) - 1):
        a, b = chars[i], chars[i + 1]
        sa, sb = a.get("strokes"), b.get("strokes")
        if sa is not None and sb is not None and sa != sb:
            assert sa <= sb
        if sa == sb:
            za, zb = a.get("zibiao_index"), b.get("zibiao_index")
            if za is not None and zb is not None:
                assert za <= zb


def test_pinyin_search_no_tone_returns_characters():
    """Valid no-tone query (e.g. wo) returns 200 and at least one character when syllable exists."""
    with app.test_client() as client:
        r = client.get("/api/pinyin-search?q=wo")
    assert r.status_code == 200
    data = r.get_json()
    assert data["found"] is True
    assert len(data["characters"]) >= 1


def test_pinyin_search_no_match():
    """Valid query with no characters returns 200, found false, error message."""
    with app.test_client() as client:
        r = client.get("/api/pinyin-search?q=xyz")
    assert r.status_code == 200
    data = r.get_json()
    assert data["found"] is False
    assert data.get("error") == "未找到该拼音的汉字"
    assert data.get("characters") == []


def test_pinyin_search_invalid_format():
    """Invalid format (e.g. mixed tone mark and digit) returns 400 and error message."""
    with app.test_client() as client:
        # nǐ3 = tone mark + trailing digit -> invalid
        r = client.get("/api/pinyin-search?q=n%C4%AB3")
    assert r.status_code == 400
    data = r.get_json()
    assert data.get("error") == "拼音输入格式错误"


def test_pinyin_search_empty_query():
    """Empty query returns 400."""
    with app.test_client() as client:
        r = client.get("/api/pinyin-search?q=")
    assert r.status_code == 400
    data = r.get_json()
    assert "error" in data


if __name__ == "__main__":
    test_pinyin_search_tone_specific_returns_characters()
    test_pinyin_search_no_tone_returns_characters()
    test_pinyin_search_no_match()
    test_pinyin_search_invalid_format()
    test_pinyin_search_empty_query()
    print("All pinyin-search API tests passed.")
