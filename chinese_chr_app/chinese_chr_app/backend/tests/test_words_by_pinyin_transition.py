#!/usr/bin/env python3
"""Focused tests for the WordsByPinyin transition behavior."""

import importlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import database
import pinyin_recall
from common_phrases import flatten_hwxnet_common_phrases


CHARACTERS_JSON = Path(__file__).resolve().parents[3] / "data" / "characters.json"


def _import_app_with_smoke_test_bypass(monkeypatch):
    monkeypatch.setenv("IMPORT_SMOKE_TEST", "1")
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_normalize_words_by_pinyin_enforces_pinyin_order_and_ignores_unknown_buckets():
    normalized = database.normalize_words_by_pinyin(
        ["dí", "de", "dì"],
        [
            {"Pinyin": "de", "Phrases": ["好的", "  ", "是的"]},
            {"Pinyin": "unknown", "Phrases": ["ignored"]},
            {"Pinyin": "dì", "Phrases": ["众矢之的"]},
            {"Pinyin": "dí", "Phrases": ["的确"]},
        ],
    )

    assert normalized == [
        {"Pinyin": "dí", "Phrases": ["的确"]},
        {"Pinyin": "de", "Phrases": ["好的", "是的"]},
        {"Pinyin": "dì", "Phrases": ["众矢之的"]},
    ]


def test_flatten_words_by_pinyin_prefers_legacy_order_and_appends_missing():
    flattened = database.flatten_words_by_pinyin(
        [
            {"Pinyin": "de", "Phrases": ["好的", "是的", "新的"]},
            {"Pinyin": "dí", "Phrases": ["的确"]},
        ],
        preferred_order=["的确", "好的", "是的"],
    )

    assert flattened == ["的确", "好的", "是的", "新的"]


def test_flatten_feng_words_preserves_current_legacy_order_behavior():
    entry = {
        "Character": "的",
        "Words": ["的确", "好的", "是的", "真的"],
        "WordsByPinyin": [
            {"Pinyin": "de", "Phrases": ["好的", "是的", "真的"]},
            {"Pinyin": "dí", "Phrases": ["的确"]},
        ],
    }

    assert pinyin_recall.flatten_feng_words(entry) == ["的确", "好的", "是的", "真的"]


def test_flatten_feng_words_falls_back_to_bucket_order_without_legacy_words():
    entry = {
        "Character": "漂",
        "WordsByPinyin": [
            {"Pinyin": "piāo", "Phrases": ["漂流", "漂泊"]},
            {"Pinyin": "piào", "Phrases": ["漂亮"]},
        ],
    }

    assert pinyin_recall.flatten_feng_words(entry) == ["漂流", "漂泊", "漂亮"]


def test_flatten_hwxnet_common_phrases_preserves_current_legacy_order_behavior():
    entry = {
        "character": "累",
        "常用词组": ["累臣", "累次", "累累"],
        "常用词组按拼音": [
            {"Pinyin": "lèi", "Phrases": ["累乏"]},
            {"Pinyin": "léi", "Phrases": ["累臣", "乱石累累"]},
            {"Pinyin": "lěi", "Phrases": ["累次", "罪行累累"]},
        ],
    }

    assert flatten_hwxnet_common_phrases(entry) == [
        "累臣",
        "累次",
        "累累",
        "累乏",
        "乱石累累",
        "罪行累累",
    ]


def test_flatten_hwxnet_common_phrases_falls_back_to_bucket_order_without_legacy_phrases():
    entry = {
        "character": "琢",
        "常用词组按拼音": [
            {"Pinyin": "zhuó", "Phrases": ["琢磨", "琢石"]},
            {"Pinyin": "zuó", "Phrases": ["琢磨"]},
        ],
    }

    assert flatten_hwxnet_common_phrases(entry) == ["琢磨", "琢石"]


def test_get_stem_words_still_returns_flat_words_for_polyphonic_character():
    character_lookup = {
        "的": {
            "Character": "的",
            "Words": ["的确", "好的", "是的", "真的"],
            "WordsByPinyin": [
                {"Pinyin": "de", "Phrases": ["好的", "是的", "真的"]},
                {"Pinyin": "dí", "Phrases": ["的确"]},
            ],
        }
    }

    result = pinyin_recall.get_stem_words("的", character_lookup, {}, max_words=4)

    assert len(result) == 4
    assert set(result) == {"的确", "好的", "是的", "真的"}


def test_get_stem_words_prefers_hwxnet_common_phrases_by_pinyin_over_legacy_list():
    hwxnet_lookup = {
        "累": {
            "character": "累",
            "常用词组": ["累臣", "累次", "累累"],
            "常用词组按拼音": [
                {"Pinyin": "lèi", "Phrases": ["累乏"]},
                {"Pinyin": "léi", "Phrases": ["累臣", "乱石累累"]},
                {"Pinyin": "lěi", "Phrases": ["累次", "罪行累累"]},
            ],
            "基本字义解释": [],
        }
    }

    result = pinyin_recall.get_stem_words("累", {}, hwxnet_lookup, max_words=6)

    assert result == ["累臣", "累次", "累累", "累乏", "乱石累累", "罪行累累"]


def test_get_stem_words_falls_back_to_legacy_hwxnet_common_phrases_when_structured_missing():
    hwxnet_lookup = {
        "阿": {
            "character": "阿",
            "常用词组": ["阿爸", "阿鼻", "阿房宫"],
            "基本字义解释": [],
        }
    }

    result = pinyin_recall.get_stem_words("阿", {}, hwxnet_lookup, max_words=3)

    assert result == ["阿爸", "阿鼻", "阿房宫"]


def test_validate_field_value_accepts_valid_words_by_pinyin(monkeypatch):
    app = _import_app_with_smoke_test_bypass(monkeypatch)

    ok, error = app.validate_field_value(
        "WordsByPinyin",
        [
            {"Pinyin": "de", "Phrases": ["好的", "是的"]},
            {"Pinyin": "dí", "Phrases": ["的确"]},
        ],
    )

    assert ok is True
    assert error is None


def test_validate_field_value_rejects_invalid_words_by_pinyin(monkeypatch):
    app = _import_app_with_smoke_test_bypass(monkeypatch)

    ok, error = app.validate_field_value(
        "WordsByPinyin",
        [{"Pinyin": "", "Phrases": "not-a-list"}],
    )

    assert ok is False
    assert error == "WordsByPinyin.Pinyin must be a non-empty string"


def test_characters_json_words_by_pinyin_invariants_hold():
    data = json.loads(CHARACTERS_JSON.read_text(encoding="utf-8"))

    assert len(data) == 3000

    for entry in data:
        pinyin = entry.get("Pinyin") or []
        words_by_pinyin = entry.get("WordsByPinyin")

        assert isinstance(words_by_pinyin, list)
        assert len(words_by_pinyin) == len(pinyin)

        for expected_reading, bucket in zip(pinyin, words_by_pinyin):
            assert bucket.get("Pinyin") == expected_reading
            assert isinstance(bucket.get("Phrases"), list)


def test_monophonic_empty_words_row_still_has_one_empty_bucket():
    data = json.loads(CHARACTERS_JSON.read_text(encoding="utf-8"))

    empty_monophonic = next(
        entry
        for entry in data
        if len(entry.get("Pinyin") or []) == 1 and not (entry.get("Words") or [])
    )

    assert empty_monophonic["WordsByPinyin"] == [
        {
            "Pinyin": empty_monophonic["Pinyin"][0],
            "Phrases": [],
        }
    ]
