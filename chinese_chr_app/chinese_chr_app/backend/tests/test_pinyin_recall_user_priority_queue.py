#!/usr/bin/env python3
"""Phase 1 tests for user-prioritized 新字 selection in Pinyin Recall."""

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


def _build_queue(*, prioritized_characters=None, learning_state=None, total_target=10):
    return pinyin_recall.build_session_queue(
        "phase1-user",
        "2026-04-06",
        learning_state or {},
        {
            "甲": _load_hwxnet_entry("甲"),
            "乐": _load_hwxnet_entry("乐"),
            "参": _load_hwxnet_entry("参"),
        },
        {
            "乐": _load_feng_entry("乐"),
            "参": _load_feng_entry("参"),
        },
        prioritized_characters=prioritized_characters,
        total_target=total_target,
        new_count=10,
        zibiao_min=1,
        zibiao_max=500,
    )


def test_phase1_no_priority_rows_keeps_queue_unchanged():
    baseline_items, baseline_mode = _build_queue(prioritized_characters=None)
    explicit_empty_items, explicit_empty_mode = _build_queue(prioritized_characters=[])

    assert baseline_mode == explicit_empty_mode
    assert [item["unit_id"] for item in baseline_items] == [
        item["unit_id"] for item in explicit_empty_items
    ]


def test_phase1_prioritized_new_items_are_front_loaded_before_non_priority_new_items():
    items, _mode = _build_queue(
        prioritized_characters=[
            {"character": "参", "priority": 0},
            {"character": "甲", "priority": 1},
        ],
    )

    assert [item["unit_id"] for item in items[:2]] == ["参|can1", "甲|jia3"]
    assert len(items) == 4


def test_phase1_character_wide_priority_uses_reading_rank_when_slots_are_tight():
    items, _mode = _build_queue(
        prioritized_characters=[
            {"character": "乐", "priority": 0},
        ],
        total_target=1,
    )

    assert [item["unit_id"] for item in items] == ["乐|le4"]


def test_phase1_reading_specific_priority_outranks_character_wide_for_same_character():
    items, _mode = _build_queue(
        prioritized_characters=[
            {"character": "乐", "priority": 0},
            {"character": "乐", "reading": "yuè", "priority": 0},
        ],
        total_target=2,
    )

    assert [item["unit_id"] for item in items] == ["乐|yue4", "乐|le4"]


def test_phase1_priority_can_override_candidate_window_for_explicit_new_target():
    items, _mode = _build_queue(
        prioritized_characters=[
            {"character": "参", "priority": 0},
        ],
        total_target=2,
    )

    assert items[0]["unit_id"] == "参|can1"
    assert len(items) == 2
    assert "参|can1" in [item["unit_id"] for item in items]


def test_phase1_already_banked_priority_unit_does_not_reenter_new_queue():
    items, _mode = _build_queue(
        prioritized_characters=[
            {"character": "参", "reading": "cān", "priority": 0},
        ],
        learning_state={
            "phase1-user": {
                "参|can1": {
                    "score": 0,
                    "stage": 0,
                    "next_due_utc": None,
                    "total_correct": 0,
                    "total_wrong": 0,
                    "total_i_dont_know": 0,
                }
            }
        },
        total_target=2,
    )

    unit_ids = [item["unit_id"] for item in items]

    assert "参|can1" not in unit_ids
    assert len(items) == 2


def test_priority_label_fields_are_included_for_priority_matched_items():
    items, _mode = _build_queue(
        prioritized_characters=[
            {
                "character": "乐",
                "reading": "yuè",
                "priority": 0,
                "label": "听写二",
                "source": "dictation_list",
            },
        ],
        total_target=2,
    )

    priority_item = next(item for item in items if item["unit_id"] == "乐|yue4")

    assert priority_item["priority_label"] == "听写二"
    assert priority_item["priority_source"] == "dictation_list"
    assert priority_item["from_user_priority"] is True


def test_due_queue_boosts_weak_prioritized_units_before_non_priority_peers():
    items, _mode = pinyin_recall.build_session_queue(
        "phase1-user",
        "2026-04-06",
        {
            "phase1-user": {
                "甲|jia3": {
                    "score": 0,
                    "stage": 0,
                    "next_due_utc": None,
                    "total_correct": 0,
                    "total_wrong": 1,
                    "total_i_dont_know": 0,
                },
                "乐|le4": {
                    "score": 0,
                    "stage": 0,
                    "next_due_utc": None,
                    "total_correct": 0,
                    "total_wrong": 1,
                    "total_i_dont_know": 0,
                },
                "乐|yue4": {
                    "score": 20,
                    "stage": 2,
                    "next_due_utc": 9999999999,
                    "total_correct": 2,
                    "total_wrong": 0,
                    "total_i_dont_know": 0,
                },
            }
        },
        {
            "甲": _load_hwxnet_entry("甲"),
            "乐": _load_hwxnet_entry("乐"),
        },
        {
            "乐": _load_feng_entry("乐"),
        },
        prioritized_characters=[
            {"character": "乐", "reading": "lè", "priority": 0},
        ],
        total_target=2,
        new_count=0,
        zibiao_min=1,
        zibiao_max=500,
    )

    assert [item["unit_id"] for item in items[:2]] == ["乐|le4", "甲|jia3"]


def test_mastered_due_items_do_not_receive_priority_boost():
    items, _mode = pinyin_recall.build_session_queue(
        "phase1-user",
        "2026-04-06",
        {
            "phase1-user": {
                "甲|jia3": {
                    "score": 20,
                    "stage": 2,
                    "next_due_utc": 1,
                    "total_correct": 2,
                    "total_wrong": 0,
                    "total_i_dont_know": 0,
                },
                "乐|le4": {
                    "score": 20,
                    "stage": 2,
                    "next_due_utc": 2,
                    "total_correct": 2,
                    "total_wrong": 0,
                    "total_i_dont_know": 0,
                },
            }
        },
        {
            "甲": _load_hwxnet_entry("甲"),
            "乐": _load_hwxnet_entry("乐"),
        },
        {
            "乐": _load_feng_entry("乐"),
        },
        prioritized_characters=[
            {"character": "乐", "reading": "lè", "priority": 0},
        ],
        total_target=2,
        new_count=0,
        zibiao_min=1,
        zibiao_max=500,
    )

    assert [item["unit_id"] for item in items[:2]] == ["甲|jia3", "乐|le4"]
