#!/usr/bin/env python3
"""Tests for pinyin-search behavior against legacy searchable_pinyin rows."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import database


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)

    def close(self):
        pass


def test_get_characters_by_pinyin_search_keys_matches_legacy_accented_searchable_pinyin(monkeypatch):
    rows = [
        {
            "character": "挣",
            "zibiao_index": 100,
            "index": "x1",
            "radical": "扌",
            "strokes": 9,
            "pinyin": ["zhēng", "zhèng"],
            "searchable_pinyin": ["zhèng", "zhèng0", "zhèng5", "zhēng", "zhēng0", "zhēng5"],
        },
        {
            "character": "铛",
            "zibiao_index": 200,
            "index": "x2",
            "radical": "钅",
            "strokes": 11,
            "pinyin": ["dāng", "chēng"],
            "searchable_pinyin": ["dāng", "dāng0", "dāng5", "chēng", "chēng0", "chēng5"],
        },
    ]
    monkeypatch.setattr(database, "_get_connection", lambda: _FakeConnection(rows))

    zheng_results = database.get_characters_by_pinyin_search_keys(["zheng4"])
    dang_results = database.get_characters_by_pinyin_search_keys(["dang1"])

    assert [row["character"] for row in zheng_results] == ["挣"]
    assert [row["character"] for row in dang_results] == ["铛"]


def test_get_characters_by_pinyin_search_keys_preserves_sort_order(monkeypatch):
    rows = [
        {
            "character": "政",
            "zibiao_index": 50,
            "index": "x3",
            "radical": "攵",
            "strokes": 9,
            "pinyin": ["zhèng"],
            "searchable_pinyin": ["zhèng", "zhèng0", "zhèng5"],
        },
        {
            "character": "挣",
            "zibiao_index": 100,
            "index": "x1",
            "radical": "扌",
            "strokes": 9,
            "pinyin": ["zhēng", "zhèng"],
            "searchable_pinyin": ["zhèng", "zhèng0", "zhèng5", "zhēng", "zhēng0", "zhēng5"],
        },
        {
            "character": "症",
            "zibiao_index": 300,
            "index": "x4",
            "radical": "疒",
            "strokes": 10,
            "pinyin": ["zhèng", "zhēng"],
            "searchable_pinyin": ["zhèng", "zhèng0", "zhèng5", "zhēng", "zhēng0", "zhēng5"],
        },
    ]
    monkeypatch.setattr(database, "_get_connection", lambda: _FakeConnection(rows))

    results = database.get_characters_by_pinyin_search_keys(["zheng4"])

    assert [row["character"] for row in results] == ["政", "挣", "症"]


def test_get_characters_by_pinyin_search_keys_ignores_stale_searchable_pinyin(monkeypatch):
    """Removed readings must not match via stale searchable_pinyin index keys."""
    rows = [
        {
            "character": "食",
            "zibiao_index": 100,
            "index": "x1",
            "radical": "食",
            "strokes": 9,
            "pinyin": ["shí"],
            "searchable_pinyin": ["shí", "shí0", "shí5", "yì", "yì0", "yì5", "yi", "yi4"],
        },
        {
            "character": "液",
            "zibiao_index": 200,
            "index": "x2",
            "radical": "氵",
            "strokes": 11,
            "pinyin": ["yè"],
            "searchable_pinyin": ["ye", "ye4", "yi", "yi4"],
        },
        {
            "character": "衣",
            "zibiao_index": 300,
            "index": "x3",
            "radical": "衣",
            "strokes": 6,
            "pinyin": ["yī"],
            "searchable_pinyin": ["yi", "yi1"],
        },
    ]
    monkeypatch.setattr(database, "_get_connection", lambda: _FakeConnection(rows))

    yi_results = database.get_characters_by_pinyin_search_keys(
        ["yi", "yi1", "yi2", "yi3", "yi4", "yi0", "yi5"],
    )

    assert [row["character"] for row in yi_results] == ["衣"]
