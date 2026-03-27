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


def test_all_polyphonic_buckets_match_reviewed_final_glosses():
    data = json.loads(HWXNET_JSON.read_text(encoding="utf-8"))
    reviewed = json.loads(REVIEWED_JSON.read_text(encoding="utf-8"))

    tone_marks = {
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

    def to_numbered(pinyin: str) -> str:
        import unicodedata

        chars = []
        tone = "5"
        for ch in unicodedata.normalize("NFC", pinyin.strip().lower()):
            mapped = tone_marks.get(ch)
            if mapped:
                base, detected_tone = mapped
                chars.append(base)
                if detected_tone != "5":
                    tone = detected_tone
            elif ch.isalpha():
                chars.append(ch)
        return "".join(chars) + tone

    for character, entry in data.items():
        pinyin = entry.get("拼音") or []
        if len(pinyin) <= 1:
            continue
        buckets = entry.get("英文解释按拼音") or []
        for reading, bucket in zip(pinyin, buckets):
            unit_id = f"{character}|{to_numbered(reading)}"
            reviewed_row = reviewed[unit_id]
            assert bucket["Glosses"] == reviewed_row["short_glosses"]
