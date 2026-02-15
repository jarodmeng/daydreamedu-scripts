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
    New: never tested. Confirm: tested, all correct. Revise: tested, at least one wrong/我不知道.
    Falls back to stage/next_due for legacy state without count fields.
    """
    if not state:
        return CATEGORY_NEW
    total_correct = state.get("total_correct") or 0
    total_wrong = state.get("total_wrong") or 0
    total_i_dont_know = state.get("total_i_dont_know") or 0
    total_answered = total_correct + total_wrong + total_i_dont_know
    if total_answered > 0:
        if total_wrong + total_i_dont_know > 0:
            return CATEGORY_REVISE
        return CATEGORY_CONFIRM
    # Legacy state: has state dict but no counts. Infer from stage/next_due.
    # state exists => was tested. stage>0 or next_due set => last was correct => 巩固
    if state.get("stage", 0) > 0 or state.get("next_due_utc") is not None:
        return CATEGORY_CONFIRM
    return CATEGORY_REVISE  # state exists, reset => was wrong


# Expand character pool as user progresses. Mastery = score >= 10 (matches profile "已学").
# Every 200 mastered chars, add 500 more to zibiao_max. Prevents "bank run out" at 500 chars.
ZIBIAO_EXPAND_MASTERED_STEP = 200
ZIBIAO_EXPAND_POOL_STEP = 500
PROFICIENCY_MIN_SCORE = 10

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
    new_count: int = 4,
    total_target: int = 12,
) -> List[Dict[str, Any]]:
    """
    Build ordered list of session items: due items first (up to due_first), then new (up to new_count),
    until total_target. Each item: { character, stem_words, correct_pinyin, choices, prompt_type }.

    Character pool expands as user masters more: every 200 mastered (score >= 10), add 500 to zibiao_max.
    Prevents "bank run out" when user has mastered the initial 500-character pool.
    """
    now_ts = int(time.time())
    user_state = learning_state.setdefault(user_id, {})

    # Expand pool based on mastered count (score >= 10, matches profile "已学")
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

    # Sort for deterministic order, then shuffle with seed
    candidates.sort(key=lambda x: (x[1].get("zibiao_index"), x[0]))
    rng.shuffle(candidates)

    pinyin_by_base_tone, all_pinyin = get_or_build_pinyin_index(hwxnet_lookup)

    due_items: List[Tuple[str, Dict[str, Any]]] = []
    new_items: List[Tuple[str, Dict[str, Any]]] = []

    for ch, entry in candidates:
        state = user_state.get(ch, {})
        next_due = state.get("next_due_utc")
        if next_due is not None and next_due > now_ts:
            continue
        if state and (next_due is None or next_due <= now_ts):
            due_items.append((ch, entry))
        else:
            new_items.append((ch, entry))

    # Due items: sort by score ascending (weakest first), then shuffle among same score
    due_items.sort(key=lambda x: user_state.get(x[0], {}).get("score", 0))
    rng.shuffle(new_items)

    # Take due first, then new, up to total_target
    queue: List[Tuple[str, Dict[str, Any]]] = due_items[:due_first]
    need = total_target - len(queue)
    for ch, entry in new_items:
        if need <= 0:
            break
        if ch in {x[0] for x in queue}:
            continue
        queue.append((ch, entry))
        need -= 1

    # Build session items with stem, correct pinyin, choices (4 pinyin + 我不知道)
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
        items_out.append({
            "character": ch,
            "stem_words": stem_words,
            "correct_pinyin": correct,
            "choices": choices,
            "prompt_type": "hanzi_to_pinyin",
            "category": category,
        })
    return items_out


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
