#!/usr/bin/env python3
"""Phase 0 contract tests for reading-level pinyin-recall units."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pinyin_recall


HWXNET_JSON = Path(__file__).resolve().parents[3] / "data" / "extracted_characters_hwxnet.json"
FENG_JSON = Path(__file__).resolve().parents[3] / "data" / "characters.json"


def _load_hwxnet_entry(character: str):
    data = json.loads(HWXNET_JSON.read_text(encoding="utf-8"))
    return data[character]


def _load_feng_entry(character: str):
    data = json.loads(FENG_JSON.read_text(encoding="utf-8"))
    return next(entry for entry in data if entry.get("Character") == character)


def test_pinyin_to_numbered_uses_tone_5_for_neutral_and_tone_digits_for_marked_readings():
    assert pinyin_recall.pinyin_to_numbered("xíng") == "xing2"
    assert pinyin_recall.pinyin_to_numbered("ma") == "ma5"
    assert pinyin_recall.pinyin_to_numbered("lü") == "lv5"


def test_build_reading_units_for_character_returns_stable_phase0_contract_for_xing():
    units = pinyin_recall.build_reading_units_for_character(
        "行",
        _load_hwxnet_entry("行"),
        _load_feng_entry("行"),
    )

    assert [unit["unit_id"] for unit in units] == ["行|xing2", "行|hang2"]
    assert [unit["reading_rank"] for unit in units] == [1, 2]
    assert [unit["is_primary"] for unit in units] == [True, False]
    assert all(unit["recall_enabled"] is True for unit in units)
    assert all(unit["enable_reason"] == "auto" for unit in units)


def test_build_reading_units_for_character_keeps_stems_and_glosses_reading_specific_for_xing():
    units = {
        unit["reading_key"]: unit
        for unit in pinyin_recall.build_reading_units_for_character(
            "行",
            _load_hwxnet_entry("行"),
            _load_feng_entry("行"),
        )
    }

    xing = units["xing2"]
    hang = units["hang2"]

    assert xing["stem_words"][:3] == ["行动", "行走", "进行"]
    assert hang["stem_words"][:3] == ["行列", "行业", "银行"]
    assert "银行" not in xing["stem_words"]
    assert "行动" not in hang["stem_words"]
    assert hang["english_translations"] == [
        "line; row",
        "line of business; trade",
        "bank; commercial firm",
        "rank among siblings",
    ]
    assert all(sense.get("读音") == "xíng" for sense in xing["basic_meanings"])
    assert all(sense.get("读音") == "háng" for sense in hang["basic_meanings"])


def test_build_reading_units_for_character_keeps_polyphonic_he_buckets_separate():
    units = {
        unit["reading_key"]: unit
        for unit in pinyin_recall.build_reading_units_for_character(
            "和",
            _load_hwxnet_entry("和"),
            _load_feng_entry("和"),
        )
    }

    assert units["he2"]["stem_words"][:3] == ["和平", "和谐", "和解"]
    assert units["huo2"]["stem_words"][:3] == ["和面", "和泥", "暖和"]
    assert units["hu2"]["stem_words"][:2] == ["和了", "和牌"]
    assert "暖和" not in units["he2"]["stem_words"]
    assert "和牌" not in units["he2"]["stem_words"]
    assert units["he2"]["english_translations"] == [
        "harmony",
        "peace",
        "calm",
        "together with",
        "sum",
    ]


def test_build_reading_units_for_character_respects_phase0_override_contract():
    units = pinyin_recall.build_reading_units_for_character(
        "参",
        _load_hwxnet_entry("参"),
        _load_feng_entry("参"),
        recall_overrides={
            "参|cen1": {
                "recall_enabled": False,
                "enable_reason": "disabled_incomplete",
            }
        },
    )

    cen = next(unit for unit in units if unit["unit_id"] == "参|cen1")
    can = next(unit for unit in units if unit["unit_id"] == "参|can1")

    assert can["is_primary"] is True
    assert cen["recall_enabled"] is False
    assert cen["enable_reason"] == "disabled_incomplete"


def test_build_reading_units_for_monophonic_character_returns_one_unit():
    units = pinyin_recall.build_reading_units_for_character(
        "甲",
        _load_hwxnet_entry("甲"),
        None,
    )

    assert len(units) == 1
    assert units[0]["unit_id"] == "甲|jia3"
    assert units[0]["reading_rank"] == 1
    assert units[0]["is_primary"] is True


def test_build_reading_unit_pool_can_exclude_disabled_units():
    hwxnet_lookup = {
        "参": _load_hwxnet_entry("参"),
        "行": _load_hwxnet_entry("行"),
    }
    character_lookup = {
        "参": _load_feng_entry("参"),
        "行": _load_feng_entry("行"),
    }

    enabled_pool = pinyin_recall.build_reading_unit_pool(
        hwxnet_lookup,
        character_lookup,
        recall_overrides={
            "参|cen1": {
                "recall_enabled": False,
                "enable_reason": "disabled_incomplete",
            }
        },
    )
    full_pool = pinyin_recall.build_reading_unit_pool(
        hwxnet_lookup,
        character_lookup,
        recall_overrides={
            "参|cen1": {
                "recall_enabled": False,
                "enable_reason": "disabled_incomplete",
            }
        },
        enabled_only=False,
    )

    assert [unit["unit_id"] for unit in enabled_pool] == [
        "参|can1",
        "参|shen1",
        "行|xing2",
        "行|hang2",
    ]
    assert [unit["unit_id"] for unit in full_pool] == [
        "参|can1",
        "参|shen1",
        "参|cen1",
        "行|xing2",
        "行|hang2",
    ]


def test_build_session_queue_emits_unit_specific_items_for_polyphonic_character():
    items, _mode = pinyin_recall.build_session_queue(
        "test-user",
        "2026-03-29",
        {},
        {"行": _load_hwxnet_entry("行")},
        {"行": _load_feng_entry("行")},
        total_target=10,
        new_count=10,
    )

    assert len(items) == 2
    by_correct = {item["correct_pinyin"]: item for item in items}

    assert set(by_correct.keys()) == {"xíng", "háng"}
    assert by_correct["xíng"]["unit_id"] == "行|xing2"
    assert by_correct["xíng"]["stem_words"][:3] == ["行动", "行走", "进行"]
    assert by_correct["xíng"]["meanings"] == [
        "to walk",
        "to travel",
        "to conduct",
        "capable",
        "to perform",
    ]
    assert by_correct["háng"]["unit_id"] == "行|hang2"
    assert by_correct["háng"]["stem_words"][:3] == ["行列", "行业", "银行"]
    assert by_correct["háng"]["meanings"] == [
        "line; row",
        "line of business; trade",
        "bank; commercial firm",
        "rank among siblings",
    ]
    assert "银行" not in by_correct["xíng"]["stem_words"]
