#!/usr/bin/env python3
"""Focused tests for the HWXNet 英文解释按拼音 transition behavior."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import database
from english_translations import flatten_hwxnet_english_translations


HWXNET_JSON = Path(__file__).resolve().parents[3] / "data" / "extracted_characters_hwxnet.json"
REVIEWED_JSON = (
    Path(__file__).resolve().parents[3]
    / "generate_english_meaning_using_ai"
    / "batch_artifacts"
    / "reading_glosses.reviewed.json"
)


def test_normalize_english_translations_by_pinyin_enforces_pinyin_order_and_ignores_unknown_buckets():
    normalized = database.normalize_hwxnet_english_translations_by_pinyin(
        ["lèi", "léi", "lěi"],
        [
            {"Pinyin": "lěi", "Glosses": ["accumulate", "  ", "successive"]},
            {"Pinyin": "unknown", "Glosses": ["ignored"]},
            {"Pinyin": "léi", "Glosses": ["burden"]},
            {"Pinyin": "lèi", "Glosses": ["tired"]},
        ],
    )

    assert normalized == [
        {"Pinyin": "lèi", "Glosses": ["tired"]},
        {"Pinyin": "léi", "Glosses": ["burden"]},
        {"Pinyin": "lěi", "Glosses": ["accumulate", "successive"]},
    ]


def test_flatten_hwxnet_english_translations_keeps_reading_boundaries():
    entry = {
        "character": "累",
        "英文翻译": ["tired", "accumulate", "burden"],
        "英文解释按拼音": [
            {"Pinyin": "lèi", "Glosses": ["tired", "to tire"]},
            {"Pinyin": "léi", "Glosses": ["burden", "numerous", "cumbersome"]},
            {"Pinyin": "lěi", "Glosses": ["accumulate", "successive", "involve"]},
        ],
    }

    assert flatten_hwxnet_english_translations(entry) == [
        "tired, to tire",
        "burden, numerous, cumbersome",
        "accumulate, successive, involve",
    ]


def test_flatten_hwxnet_english_translations_uses_structured_only_without_legacy_bias():
    entry = {
        "character": "乐",
        "英文解释按拼音": [
            {"Pinyin": "lè", "Glosses": ["happy", "joy"]},
            {"Pinyin": "yuè", "Glosses": ["music", "harmonious sound"]},
        ],
    }

    assert flatten_hwxnet_english_translations(entry) == [
        "happy, joy",
        "music, harmonious sound",
    ]


def test_flatten_hwxnet_english_translations_falls_back_to_legacy_when_structured_missing():
    entry = {
        "character": "甲",
        "英文翻译": ["first", "armor shell"],
    }

    assert flatten_hwxnet_english_translations(entry) == ["first", "armor shell"]


def test_hwxnet_json_english_translations_by_pinyin_invariants_hold():
    data = json.loads(HWXNET_JSON.read_text(encoding="utf-8"))

    assert len(data) > 3000

    for entry in data.values():
        pinyin = entry.get("拼音") or []
        english_by_pinyin = entry.get("英文解释按拼音")

        if not pinyin:
            assert english_by_pinyin in (None, [])
            continue

        assert isinstance(english_by_pinyin, list)
        assert len(english_by_pinyin) == len(pinyin)

        for expected_reading, bucket in zip(pinyin, english_by_pinyin):
            assert bucket.get("Pinyin") == expected_reading
            assert isinstance(bucket.get("Glosses"), list)


def test_all_monophonic_rows_have_exactly_one_bucket():
    data = json.loads(HWXNET_JSON.read_text(encoding="utf-8"))

    for entry in data.values():
        if len(entry.get("拼音") or []) != 1:
            continue
        assert entry["英文解释按拼音"] == [
            {
                "Pinyin": entry["拼音"][0],
                "Glosses": entry.get("英文翻译") or [],
            }
        ]
