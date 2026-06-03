#!/usr/bin/env python3
"""
Phase 2 tests for the Deep Consolidation queue mode + 精通项 (memorized) pool.

See docs/archive/proposals/PROPOSAL_精通项_And_Deep_Consolidation_Mode.md.
"""

import json
import os
import sys
from pathlib import Path

os.environ["IMPORT_SMOKE_TEST"] = "1"

sys.path.insert(0, str(Path(__file__).parent.parent))

import pinyin_recall


HWXNET_JSON = Path(__file__).resolve().parents[3] / "data" / "extracted_characters_hwxnet.json"

USER = "deep-consolidation-user"
DATE = "2026-06-03"


def _pick_single_unit_chars(n):
    """Pick n characters in zibiao [1,500] with exactly one enabled reading unit (deterministic unit_id)."""
    data = json.loads(HWXNET_JSON.read_text(encoding="utf-8"))
    out = []
    for ch, entry in data.items():
        if not isinstance(entry, dict):
            continue
        zi = entry.get("zibiao_index")
        if zi is None:
            continue
        try:
            zi = int(zi)
        except (TypeError, ValueError):
            continue
        if not (1 <= zi <= 500):
            continue
        units = pinyin_recall.build_reading_units_for_character(ch, entry, None)
        enabled = [u for u in units if u.get("recall_enabled")]
        if len(enabled) == 1:
            out.append((ch, entry, enabled[0]["unit_id"]))
        if len(out) >= n:
            break
    assert len(out) >= n, f"only found {len(out)} single-unit chars"
    return out


def _state(score):
    return {
        "score": score,
        "stage": 0,
        "next_due_utc": None,  # due now
        "total_correct": 3,
        "total_wrong": 0,
        "total_i_dont_know": 0,
    }


def _build(*, bands, not_tested_count, extra_state=None, total_target=20):
    """
    bands: list of (count, score). Allocates real single-unit chars to each band.
    Returns (items, mode, hwxnet_lookup, unit_ids_by_score).
    """
    total = sum(c for c, _ in bands)
    picks = _pick_single_unit_chars(total)
    hwxnet_lookup = {}
    user_state = {}
    unit_ids_by_score = {}
    idx = 0
    for count, score in bands:
        ids = []
        for _ in range(count):
            ch, entry, unit_id = picks[idx]
            idx += 1
            hwxnet_lookup[ch] = entry
            user_state[unit_id] = _state(score)
            ids.append(unit_id)
        unit_ids_by_score.setdefault(score, []).extend(ids)
    if extra_state:
        user_state.update(extra_state)
    items, mode = pinyin_recall.build_session_queue(
        USER,
        DATE,
        {USER: user_state},
        hwxnet_lookup,
        {},
        total_target=total_target,
        not_tested_count=not_tested_count,
    )
    return items, mode, unit_ids_by_score


def test_deep_consolidation_triggers_when_no_new_and_not_rescue():
    items, mode, ids = _build(
        bands=[(6, 5), (4, 15), (8, 25), (2, 45)],
        not_tested_count=0,
    )
    assert mode == "deep_consolidation"
    assert len(items) == 20
    # No 新字 served.
    assert all(item["batch_category"] != "new" for item in items)
    # Confidence-first: the two 精通项 (score 45) come first.
    memorized_ids = set(ids[45])
    assert set(i["unit_id"] for i in items[:2]) == memorized_ids
    assert items[0]["batch_category"] == "memorized"


def test_deep_consolidation_recipe_caps_and_ordering():
    items, mode, ids = _build(
        bands=[(6, 5), (4, 15), (8, 25), (2, 45)],
        not_tested_count=0,
    )
    assert mode == "deep_consolidation"
    cats = [i["batch_category"] for i in items]
    # 精通项(2) -> 掌握项(8) -> 普通已学项(4) -> 在学项(6)
    assert cats[:2] == ["memorized", "memorized"]
    assert cats[2:10] == ["mastered"] * 8
    assert cats[10:14] == ["learned_normal"] * 4
    assert cats[14:20] == ["learning_normal"] * 6


def test_deep_consolidation_redistributes_spare_into_memorized():
    # Only 精通项 available; spare slots should backfill with 精通项 up to availability.
    items, mode, ids = _build(
        bands=[(10, 45)],
        not_tested_count=0,
    )
    assert mode == "deep_consolidation"
    assert len(items) == 10
    assert all(i["batch_category"] == "memorized" for i in items)


def test_rescue_takes_precedence_over_deep_consolidation():
    # No new chars, but a heavy 难项 backlog (Total Load > 250) must stay in Rescue.
    heavy = {f"heavy-{i}|x{i}": _state(-30) for i in range(300)}
    items, mode, _ids = _build(
        bands=[(4, 25), (8, 15), (6, 5)],
        not_tested_count=0,
        extra_state=heavy,
    )
    assert mode == "rescue"


def test_no_deep_consolidation_when_new_chars_remain():
    items, mode, _ids = _build(
        bands=[(2, 25), (2, 45)],
        not_tested_count=12,
    )
    assert mode != "deep_consolidation"


def test_legacy_modes_combine_mastered_and_memorized_pool():
    # Expansion mode (new chars remain, light load); 精通项 due units feed the mastered review pool.
    items, mode, ids = _build(
        bands=[(3, 45)],
        not_tested_count=12,
        total_target=20,
    )
    assert mode == "expansion"
    served = {i["unit_id"] for i in items}
    # At least one 精通项 unit gets reviewed via the combined pool.
    assert served & set(ids[45])
