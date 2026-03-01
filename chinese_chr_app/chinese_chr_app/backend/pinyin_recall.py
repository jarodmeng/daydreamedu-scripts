"""
MVP1 Pinyin Recall: session queue, stem words, distractors, and in-memory scheduler.

Uses HWXNet (拼音 = first as correct; other pronunciations excluded from distractors)
and Feng/HWXNet for stem words. In-memory learning state keyed by user_id.
"""

import hashlib
import random
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from pinyin_search import pinyin_to_base_and_tone

# Stage ladder (days until next review): 0 = same session, 1 = +1d, 2 = +3d, 3 = +7d, 4 = +14d, 5 = +30d
STAGE_INTERVAL_DAYS = [0, 1, 3, 7, 14, 30]
MAX_STAGE = len(STAGE_INTERVAL_DAYS) - 1

I_DONT_KNOW_LABEL = "我不知道"

# Character categories for display (MECE): 新字, 巩固, 重测
CATEGORY_NEW = "新字"
CATEGORY_CONFIRM = "巩固"
CATEGORY_REVISE = "重测"


def _category_for_character(state: Dict[str, Any]) -> str:
    """
    Return category label for a character based on learning state.
    New: never tested. Confirm (巩固): tested, all correct, and 已学字 (score >= 10).
    Revise (重测): tested but has wrong/我不知道, or score < 10 (not yet 已学字).
    Falls back to stage/next_due for legacy state without count fields.
    """
    if not state:
        return CATEGORY_NEW
    try:
        score = int(state.get("score") or 0)
    except (TypeError, ValueError):
        score = 0
    total_correct = state.get("total_correct") or 0
    total_wrong = state.get("total_wrong") or 0
    total_i_dont_know = state.get("total_i_dont_know") or 0
    total_answered = total_correct + total_wrong + total_i_dont_know
    if total_answered > 0:
        if total_wrong + total_i_dont_know > 0:
            return CATEGORY_REVISE
        # 巩固 only for 已学字 (score >= 10); before that, testing is 重测
        if score >= PROFICIENCY_MIN_SCORE:
            return CATEGORY_CONFIRM
        return CATEGORY_REVISE
    # Legacy state: has state dict but no counts. Infer from stage/next_due and score.
    if (state.get("stage", 0) > 0 or state.get("next_due_utc") is not None) and score >= PROFICIENCY_MIN_SCORE:
        return CATEGORY_CONFIRM
    return CATEGORY_REVISE  # state exists, reset or not yet 已学字 => 重测


def _score_band(score: int) -> str:
    """Return five-band label: hard, learning_normal, learned_normal, mastered. Used for queue allocation."""
    if score <= HARD_MAX_SCORE:
        return "hard"
    if score <= 0:
        return "learning_normal"
    if score < MASTERED_MIN_SCORE:
        return "learned_normal"
    return "mastered"


def _batch_category_for_character(state: Dict[str, Any]) -> str:
    """Return five-band category at batch time: new, hard, learning_normal, learned_normal, mastered. For logging in item_presented."""
    if not state:
        return "new"
    try:
        score = int(state.get("score") or 0)
    except (TypeError, ValueError):
        score = 0
    return _score_band(score)


def _next_due_ts(state: Dict[str, Any], now_ts: int) -> Optional[int]:
    """Return next_due_utc as int (epoch seconds) for comparison, or None if not due."""
    nd = state.get("next_due_utc")
    if nd is None:
        return 0
    if hasattr(nd, "timestamp"):
        return int(nd.timestamp())
    try:
        return int(nd)
    except (TypeError, ValueError):
        return 0


# Expand character pool as user progresses. Mastery = score >= 10 (matches profile "已学").
# Every 200 mastered chars, add 500 more to zibiao_max. Prevents "bank run out" at 500 chars.
ZIBIAO_EXPAND_MASTERED_STEP = 200
ZIBIAO_EXPAND_POOL_STEP = 500
PROFICIENCY_MIN_SCORE = 10

# Five score bands for queue construction (Issue #12). Align with profile thresholds.
HARD_MAX_SCORE = -20          # 难字: score <= -20
MASTERED_MIN_SCORE = 20       # 掌握字: score >= 20
# Active Load = count(难字) + count(普通在学字). Modes: Expansion (< 100), Consolidation (100-250), Rescue (> 250).
ACTIVE_LOAD_EXPANSION_MAX = 99
ACTIVE_LOAD_CONSOLIDATION_MAX = 250
# Mode recipes (total_target=20): Rescue 4 掌握字 + 8 普通已学字 + 6 在学字 + 2 新字; Expansion 10 新字 + 10 review; Consolidation 5 新字 + 15 review.
RESCUE_MASTERED = 4
RESCUE_LEARNED_NORMAL = 8
RESCUE_LEARNING = 6
RESCUE_NEW = 2
EXPANSION_NEW = 10
EXPANSION_REVIEW = 10
CONSOLIDATION_NEW = 5
CONSOLIDATION_REVIEW = 15

_PINYIN_INDEX_CACHE: Tuple[
    Dict[Tuple[str, int], List[str]], List[str]
] | None = None


def get_stem_words(
    character: str,
    character_lookup: Dict[str, Any],
    hwxnet_lookup: Dict[str, Any],
    max_words: int = 3,
) -> List[str]:
    """
    Prefer Feng Words first, then HWXNet 例词. Dedupe, cap to max_words, shortest first.
    """
    feng_words: List[str] = []
    if character_lookup and character in character_lookup:
        feng_words = list(character_lookup[character].get("Words") or [])
    hwxnet_words: List[str] = []
    if hwxnet_lookup and character in hwxnet_lookup:
        entry = hwxnet_lookup[character]
        for sense in entry.get("基本字义解释") or []:
            for definition in sense.get("释义") or []:
                for ex in definition.get("例词") or []:
                    if ex and ex not in hwxnet_words:
                        hwxnet_words.append(ex)
    combined = list(feng_words)
    for w in hwxnet_words:
        if w not in combined:
            combined.append(w)
    combined = sorted(combined, key=len)[:max_words]
    return combined


def get_correct_pinyin(hwxnet_entry: Dict[str, Any]) -> str:
    """First entry in 拼音 is the correct answer for MVP1."""
    pinyin_list = hwxnet_entry.get("拼音") or []
    if isinstance(pinyin_list, str):
        pinyin_list = [pinyin_list]
    if not pinyin_list:
        return ""
    return (pinyin_list[0] or "").strip()


def get_other_pronunciations(hwxnet_entry: Dict[str, Any]) -> List[str]:
    """All pronunciations except the first (excluded from distractors)."""
    pinyin_list = hwxnet_entry.get("拼音") or []
    if isinstance(pinyin_list, str):
        pinyin_list = [pinyin_list]
    return [p.strip() for p in pinyin_list[1:] if p and p.strip()]


def _first_basic_meaning_zh(entry: Dict[str, Any]) -> Optional[str]:
    """First 解释 from 基本字义解释 (for correct-answer screen 基本解释)."""
    for sense in entry.get("基本字义解释") or []:
        for defn in (sense.get("释义") or [])[:1]:
            expl = (defn.get("解释") or "").strip()
            if expl:
                return expl
    return None


def _all_pinyin_list(entry: Dict[str, Any], fallback_primary: str = "") -> List[str]:
    """Normalized list of all 拼音; if missing/empty, return [fallback_primary] when given."""
    pinyin_list = entry.get("拼音") or []
    if isinstance(pinyin_list, str):
        pinyin_list = [pinyin_list]
    out = [p.strip() for p in pinyin_list if p and p.strip()]
    if not out and fallback_primary:
        return [fallback_primary]
    return out


def build_pinyin_index(hwxnet_lookup: Dict[str, Any]) -> Tuple[Dict[Tuple[str, int], List[str]], List[str]]:
    """
    Build (base, tone) -> list of pinyin strings, and flat list of all pinyin.
    Used for distractor generation. Each pinyin appears once per (base, tone).
    """
    by_base_tone: Dict[Tuple[str, int], List[str]] = defaultdict(list)
    all_pinyin: List[str] = []
    seen_pinyin = set()
    for _ch, entry in (hwxnet_lookup or {}).items():
        if not isinstance(entry, dict):
            continue
        pinyin_list = entry.get("拼音") or []
        if isinstance(pinyin_list, str):
            pinyin_list = [pinyin_list]
        for py in pinyin_list:
            if not py or not py.strip():
                continue
            py = py.strip()
            if py in seen_pinyin:
                continue
            seen_pinyin.add(py)
            all_pinyin.append(py)
            base, tone = pinyin_to_base_and_tone(py)
            if base is not None:
                t = tone if tone is not None and tone != 0 else 5
                if tone is None:
                    t = 5
                by_base_tone[(base, t)].append(py)
    return dict(by_base_tone), all_pinyin


def get_or_build_pinyin_index(
    hwxnet_lookup: Dict[str, Any],
) -> Tuple[Dict[Tuple[str, int], List[str]], List[str]]:
    """
    Cached wrapper around build_pinyin_index so we only build the index once per
    process (or until this module is reloaded).
    """
    global _PINYIN_INDEX_CACHE
    if _PINYIN_INDEX_CACHE is None:
        _PINYIN_INDEX_CACHE = build_pinyin_index(hwxnet_lookup)
    return _PINYIN_INDEX_CACHE


def build_distractors(
    correct_pinyin: str,
    other_pronunciations: List[str],
    pinyin_by_base_tone: Dict[Tuple[str, int], List[str]],
    all_pinyin: List[str],
    count: int = 3,
) -> List[str]:
    """
    Return `count` distractors. Exclude correct_pinyin and other_pronunciations.
    Prefer: same syllable different tone, then same tone different syllable, then fallback.
    """
    exclude = {correct_pinyin.strip().lower()}
    for p in other_pronunciations:
        exclude.add(p.strip().lower())
    result: List[str] = []
    base, tone = pinyin_to_base_and_tone(correct_pinyin)
    tone_val = tone if tone is not None and tone != 0 else 5
    if tone is None:
        tone_val = 5

    # Same syllable, different tone (primary)
    if base:
        for t in [1, 2, 3, 4, 5]:
            if t == tone_val:
                continue
            for py in pinyin_by_base_tone.get((base, t), []):
                if py.strip().lower() not in exclude and py not in result:
                    result.append(py)
                    if len(result) >= count:
                        return result

    # Same tone, different syllable (secondary)
    if tone_val is not None:
        for (b, t), py_list in pinyin_by_base_tone.items():
            if t != tone_val or b == base:
                continue
            for py in py_list:
                if py.strip().lower() not in exclude and py not in result:
                    result.append(py)
                    if len(result) >= count:
                        return result

    # Fallback: random from all
    shuffled = list(all_pinyin)
    random.shuffle(shuffled)
    for py in shuffled:
        if py.strip().lower() not in exclude and py not in result:
            result.append(py)
            if len(result) >= count:
                return result

    return result


def build_session_queue(
    user_id: str,
    date_str: str,
    learning_state: Dict[str, Dict[str, Any]],
    hwxnet_lookup: Dict[str, Any],
    character_lookup: Dict[str, Any],
    *,
    zibiao_min: int = 1,
    zibiao_max: int = 500,
    due_first: int = 8,
    due_confirm_min: int = 4,
    new_count: int = 4,
    total_target: int = 20,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Build ordered list of session items (20 per batch) using five score-based categories and
    Active Load mode (Expansion / Consolidation / Rescue). See PROPOSAL_Queue_By_Five_Score_Categories.

    Five bands: 难字 (score <= -20), 普通在学字 (-20 < score <= 0), 普通已学字 (0 < score < 20), 掌握字 (>= 20).
    Active Load = count(难字) + count(普通在学字). Mode: Expansion (< 100), Consolidation (100-250), Rescue (> 250).
    Rescue recipe: 4 掌握字 + 8 普通已学字 + 6 在学字 (难字 first) + 2 新字; confidence-first order.
    Within 在学字 slots: 难字 first (score asc), then 普通在学字 — no cap on 难字.
    """
    now_ts = int(time.time())
    user_state = learning_state.setdefault(user_id, {})

    # Expand pool based on mastered count (score >= 10)
    mastered_count = sum(
        1 for s in user_state.values()
        if isinstance(s, dict) and (s.get("score") or 0) >= PROFICIENCY_MIN_SCORE
    )
    max_zibiao_in_corpus = 0
    for entry in (hwxnet_lookup or {}).values():
        if isinstance(entry, dict):
            zi = entry.get("zibiao_index")
            if zi is not None:
                try:
                    max_zibiao_in_corpus = max(max_zibiao_in_corpus, int(zi))
                except (TypeError, ValueError):
                    pass
    tier = mastered_count // ZIBIAO_EXPAND_MASTERED_STEP
    zibiao_max_effective = min(
        max_zibiao_in_corpus or 7000,
        500 + tier * ZIBIAO_EXPAND_POOL_STEP,
    )
    zibiao_max_effective = max(zibiao_max, zibiao_max_effective)

    seed_str = f"{user_id}:{date_str}"
    rng = random.Random(hashlib.sha256(seed_str.encode()).hexdigest())

    # Candidate pool: HWXNet chars with zibiao_index in [zibiao_min, zibiao_max_effective]
    candidates: List[Tuple[str, Dict[str, Any]]] = []
    for ch, entry in (hwxnet_lookup or {}).items():
        if not isinstance(entry, dict):
            continue
        zi = entry.get("zibiao_index")
        if zi is None:
            continue
        try:
            zi_int = int(zi)
        except (TypeError, ValueError):
            continue
        if not (zibiao_min <= zi_int <= zibiao_max_effective):
            continue
        candidates.append((ch, entry))

    candidates.sort(key=lambda x: (x[1].get("zibiao_index"), x[0]))
    rng.shuffle(candidates)

    pinyin_by_base_tone, all_pinyin = get_or_build_pinyin_index(hwxnet_lookup)

    def _is_due(state: Dict[str, Any]) -> bool:
        nd = _next_due_ts(state, now_ts)
        return nd == 0 or nd <= now_ts

    due_hard: List[Tuple[str, Dict[str, Any]]] = []
    due_learning_normal: List[Tuple[str, Dict[str, Any]]] = []
    due_learned_normal: List[Tuple[str, Dict[str, Any]]] = []
    due_mastered: List[Tuple[str, Dict[str, Any]]] = []
    new_items: List[Tuple[str, Dict[str, Any]]] = []

    for ch, entry in candidates:
        state = user_state.get(ch, {})
        if not state:
            new_items.append((ch, entry))
            continue
        if not _is_due(state):
            continue
        score = int(state.get("score") or 0)
        band = _score_band(score)
        if band == "hard":
            due_hard.append((ch, entry))
        elif band == "learning_normal":
            due_learning_normal.append((ch, entry))
        elif band == "learned_normal":
            due_learned_normal.append((ch, entry))
        else:
            due_mastered.append((ch, entry))

    active_load = 0
    for state in user_state.values():
        if not isinstance(state, dict):
            continue
        s = int(state.get("score") or 0)
        if s <= HARD_MAX_SCORE or (HARD_MAX_SCORE < s <= 0):
            active_load += 1

    if active_load <= ACTIVE_LOAD_EXPANSION_MAX:
        mode = "expansion"
    elif active_load <= ACTIVE_LOAD_CONSOLIDATION_MAX:
        mode = "consolidation"
    else:
        mode = "rescue"

    def _score_key(x: Tuple[str, Dict[str, Any]]) -> int:
        return user_state.get(x[0], {}).get("score", 0)

    def _next_due_key(x: Tuple[str, Dict[str, Any]]) -> int:
        return _next_due_ts(user_state.get(x[0], {}), now_ts) or 0

    due_hard.sort(key=_score_key)
    due_learning_normal.sort(key=_score_key)
    due_learned_normal.sort(key=_next_due_key)
    due_mastered.sort(key=_next_due_key)
    rng.shuffle(new_items)

    n_mastered = len(due_mastered)
    n_learned_normal = len(due_learned_normal)
    n_learning = len(due_hard) + len(due_learning_normal)
    n_new_avail = len(new_items)

    if mode == "rescue":
        n_mastered_slots = min(RESCUE_MASTERED, n_mastered)
        n_learned_normal_slots = min(RESCUE_LEARNED_NORMAL, n_learned_normal)
        n_learning_slots = min(RESCUE_LEARNING, n_learning)
        n_new_slots = min(RESCUE_NEW, n_new_avail)
        spare = total_target - (n_mastered_slots + n_learned_normal_slots + n_learning_slots + n_new_slots)
        while spare > 0 and (n_learned_normal_slots < n_learned_normal or n_learning_slots < n_learning or n_new_slots < n_new_avail):
            if n_learned_normal_slots < n_learned_normal:
                n_learned_normal_slots += 1
                spare -= 1
            elif n_learning_slots < n_learning:
                n_learning_slots += 1
                spare -= 1
            elif n_new_slots < n_new_avail:
                n_new_slots += 1
                spare -= 1
            else:
                break
    elif mode == "expansion":
        n_new_slots = min(EXPANSION_NEW, n_new_avail, total_target)
        review_slots = min(EXPANSION_REVIEW, total_target - n_new_slots)
        n_learning_slots = min(review_slots, n_learning)
        n_learned_normal_slots = min(review_slots - n_learning_slots, n_learned_normal)
        n_mastered_slots = min(review_slots - n_learning_slots - n_learned_normal_slots, n_mastered)
        if n_learning_slots + n_learned_normal_slots + n_mastered_slots < review_slots:
            n_learned_normal_slots = min(n_learned_normal, review_slots - n_learning_slots - n_mastered_slots)
            n_mastered_slots = min(n_mastered, review_slots - n_learning_slots - n_learned_normal_slots)
    else:
        n_new_slots = min(CONSOLIDATION_NEW, n_new_avail, total_target)
        review_slots = min(CONSOLIDATION_REVIEW, total_target - n_new_slots)
        n_learning_slots = min(review_slots, n_learning)
        n_learned_normal_slots = min(review_slots - n_learning_slots, n_learned_normal)
        n_mastered_slots = min(review_slots - n_learning_slots - n_learned_normal_slots, n_mastered)
        if n_learning_slots + n_learned_normal_slots + n_mastered_slots < review_slots:
            n_learned_normal_slots = min(n_learned_normal, review_slots - n_learning_slots - n_mastered_slots)
            n_mastered_slots = min(n_mastered, review_slots - n_learning_slots - n_learned_normal_slots)

    learning_pool: List[Tuple[str, Dict[str, Any]]] = list(due_hard) + list(due_learning_normal)
    learning_pool = learning_pool[:n_learning_slots]

    mastered_queue = due_mastered[:n_mastered_slots]
    learned_normal_queue = due_learned_normal[:n_learned_normal_slots]
    new_queue: List[Tuple[str, Dict[str, Any]]] = []
    seen = {x[0] for x in mastered_queue + learned_normal_queue + learning_pool}
    for ch, entry in new_items:
        if len(new_queue) >= n_new_slots:
            break
        if ch in seen:
            continue
        new_queue.append((ch, entry))
        seen.add(ch)

    if mode == "rescue":
        queue: List[Tuple[str, Dict[str, Any]]] = mastered_queue + learned_normal_queue + learning_pool + new_queue
    else:
        learned_queue = learned_normal_queue + mastered_queue
        queue = learned_queue + learning_pool + new_queue

    items_out: List[Dict[str, Any]] = []
    for ch, entry in queue:
        correct = get_correct_pinyin(entry)
        if not correct:
            continue
        other = get_other_pronunciations(entry)
        distractors = build_distractors(
            correct, other, pinyin_by_base_tone, all_pinyin, count=3
        )
        choices = [correct] + distractors[:3]
        rng.shuffle(choices)
        stem_words = get_stem_words(ch, character_lookup or {}, hwxnet_lookup or {}, 3)
        char_state = user_state.get(ch, {})
        category = _category_for_character(char_state)
        batch_category = _batch_category_for_character(char_state)
        # For correct-answer screen (Issue #7): all pinyin, English meaning, 基本解释
        all_pinyin = _all_pinyin_list(entry, fallback_primary=correct)
        is_polyphonic = len(all_pinyin) > 1
        english = entry.get("英文翻译") or []
        if isinstance(english, list):
            meanings = [(e or "").strip() for e in english if (e or "").strip()]
        else:
            meanings = []
        meaning_zh = _first_basic_meaning_zh(entry)
        items_out.append({
            "character": ch,
            "stem_words": stem_words,
            "correct_pinyin": correct,
            "choices": choices,
            "prompt_type": "hanzi_to_pinyin",
            "category": category,
            "batch_category": batch_category,
            "all_pinyin": all_pinyin,
            "is_polyphonic": is_polyphonic,
            "meanings": meanings,
            "meaning_zh": meaning_zh,
        })
    return (items_out, mode)


def update_learning_state(
    learning_state: Dict[str, Dict[str, Any]],
    user_id: str,
    character: str,
    correct: bool,
    i_dont_know: bool,
) -> None:
    """
    Treat wrong or 我不知道 as incorrect: do not advance stage (or reset to 0).
    On correct: advance stage (cap at MAX_STAGE) and set next_due_utc.
    Tracks total_correct, total_wrong, total_i_dont_know for category (新字/巩固/重测).
    """
    import time as _time
    user_state = learning_state.setdefault(user_id, {})
    char_state = user_state.setdefault(
        character,
        {"stage": 0, "next_due_utc": None, "total_correct": 0, "total_wrong": 0, "total_i_dont_know": 0},
    )
    # Ensure counts exist for older in-memory state
    char_state.setdefault("total_correct", 0)
    char_state.setdefault("total_wrong", 0)
    char_state.setdefault("total_i_dont_know", 0)

    if correct:
        char_state["total_correct"] = char_state.get("total_correct", 0) + 1
    elif i_dont_know:
        char_state["total_i_dont_know"] = char_state.get("total_i_dont_know", 0) + 1
    else:
        char_state["total_wrong"] = char_state.get("total_wrong", 0) + 1

    if i_dont_know or not correct:
        char_state["stage"] = 0
        char_state["next_due_utc"] = None
        return

    stage = min(char_state.get("stage", 0) + 1, MAX_STAGE)
    days = STAGE_INTERVAL_DAYS[stage]
    # Same session = next_due 0 so it can reappear later in same session if we want; for v0 we set to now + 1 min so it doesn't reappear
    if days == 0:
        next_ts = int(_time.time()) + 60
    else:
        next_ts = int(_time.time()) + days * 86400
    char_state["stage"] = stage
    char_state["next_due_utc"] = next_ts
