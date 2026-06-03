#!/usr/bin/env python3
"""
Phase 1 tests for 精通项 band + 0->10 在学/已学 boundary fix + scaled cooling.

See docs/archive/proposals/PROPOSAL_精通项_And_Deep_Consolidation_Mode.md.
"""

import os
import sys
from pathlib import Path

os.environ["IMPORT_SMOKE_TEST"] = "1"

sys.path.insert(0, str(Path(__file__).parent.parent))

import pinyin_recall
import database as database_module


# --- _score_band: six bands, 在学/已学 boundary at 10, 精通项 at 40 ---

def test_score_band_boundaries():
    band = pinyin_recall._score_band
    assert band(-30) == "hard"          # <= -20
    assert band(-20) == "hard"          # boundary: <= -20
    assert band(-5) == "learning_normal"
    assert band(0) == "learning_normal"   # 0 now 在学 (was learned_normal)
    assert band(5) == "learning_normal"   # boundary moved 0 -> 10
    assert band(9) == "learning_normal"
    assert band(10) == "learned_normal"   # 已学 starts at 10
    assert band(15) == "learned_normal"
    assert band(19) == "learned_normal"
    assert band(20) == "mastered"
    assert band(35) == "mastered"
    assert band(39) == "mastered"         # boundary: < 40
    assert band(40) == "memorized"        # 精通项 starts at 40
    assert band(45) == "memorized"
    assert band(100) == "memorized"


# --- _cooling_days_for_score: 1d boundary at 10, scaled 精通项 cooling ---

def test_cooling_days_boundaries_and_scaling():
    cool = database_module._cooling_days_for_score
    assert cool(-30) == 0                 # 难项
    assert cool(-20) == 0
    assert cool(-5) == 1                  # 普通在学项
    assert cool(0) == 1
    assert cool(5) == 1                   # boundary moved 0 -> 10
    assert cool(9) == 1
    assert cool(10) == 5                  # 普通已学项 starts at 10
    assert cool(15) == 5
    assert cool(19) == 5
    assert cool(20) == 22                 # 掌握项
    assert cool(35) == 22
    assert cool(39) == 22
    # 精通项 (>= 40): 60 -> 90 -> 120, capped
    assert cool(40) == 60
    assert cool(55) == 60
    assert cool(59) == 60
    assert cool(60) == 90
    assert cool(79) == 90
    assert cool(80) == 120
    assert cool(100) == 120               # cap


# --- Total Load uses the 10 boundary (score 1-9 count full weight) ---

def _hwxnet_lookup_minimal():
    # A couple of single-reading entries with zibiao_index so the queue can run.
    return {
        "一": {"拼音": ["yi1"], "zibiao_index": 1},
        "二": {"拼音": ["er4"], "zibiao_index": 2},
    }


def _learning_state_with_scores(user_id, score, count):
    state = {}
    for i in range(count):
        state[f"unit-{i}|x{i}"] = {
            "score": score,
            "next_due_utc": None,
            "total_correct": 1,
            "total_wrong": 0,
            "total_i_dont_know": 0,
        }
    return {user_id: state}


def test_total_load_counts_score_1_to_9_as_active_load():
    """100 units at score 5 -> Total Load ~= 100 (full weight) -> Consolidation (was Expansion under the old 0-split)."""
    learning_state = _learning_state_with_scores("load-active", 5, 100)
    _items, mode = pinyin_recall.build_session_queue(
        "load-active",
        "2026-06-03",
        learning_state,
        _hwxnet_lookup_minimal(),
        {},
        total_target=20,
        new_count=8,
    )
    assert mode == "consolidation"


def test_total_load_counts_score_10_to_19_at_reduced_weight():
    """100 units at score 15 (普通已学项) -> Total Load = 0.3*100 = 30 -> Expansion."""
    learning_state = _learning_state_with_scores("load-learned", 15, 100)
    _items, mode = pinyin_recall.build_session_queue(
        "load-learned",
        "2026-06-03",
        learning_state,
        _hwxnet_lookup_minimal(),
        {},
        total_target=20,
        new_count=8,
    )
    assert mode == "expansion"
