"""
Helpers for HWXNet English transition fields.
"""

from typing import Any, Dict, List, Set


def normalize_hwxnet_english_translations_by_pinyin(
    pinyin_list: List[Any],
    english_by_pinyin: Any,
) -> List[Dict[str, Any]]:
    """Normalize 英文解释按拼音 into one bucket per pinyin, preserving pinyin order."""
    ordered_pinyin = [
        str(reading).strip()
        for reading in (pinyin_list or [])
        if isinstance(reading, str) and str(reading).strip()
    ]
    if not ordered_pinyin:
        return []

    bucket_map: Dict[str, List[str]] = {reading: [] for reading in ordered_pinyin}
    seen_per_bucket: Dict[str, Set[str]] = {reading: set() for reading in ordered_pinyin}
    if isinstance(english_by_pinyin, list):
        for item in english_by_pinyin:
            if not isinstance(item, dict):
                continue
            reading = (item.get("Pinyin") or "").strip()
            if reading not in bucket_map:
                continue
            glosses = item.get("Glosses")
            if not isinstance(glosses, list):
                continue
            for gloss in glosses:
                if not isinstance(gloss, str):
                    continue
                gloss_text = gloss.strip()
                if not gloss_text or gloss_text in seen_per_bucket[reading]:
                    continue
                seen_per_bucket[reading].add(gloss_text)
                bucket_map[reading].append(gloss_text)

    return [{"Pinyin": reading, "Glosses": bucket_map[reading]} for reading in ordered_pinyin]


def flatten_english_translations_by_pinyin(
    english_by_pinyin: Any,
) -> List[str]:
    """
    Flatten 英文解释按拼音 into one display string per reading bucket.

    This preserves reading boundaries for polyphonic characters so current flat
    consumers can render a clear `|` split between readings.
    """
    if not isinstance(english_by_pinyin, list):
        return []

    flattened: List[str] = []
    for bucket in english_by_pinyin:
        if not isinstance(bucket, dict):
            continue
        glosses = bucket.get("Glosses")
        if not isinstance(glosses, list):
            continue
        cleaned: List[str] = []
        seen: Set[str] = set()
        for gloss in glosses:
            if not isinstance(gloss, str):
                continue
            gloss_text = gloss.strip()
            if gloss_text and gloss_text not in seen:
                seen.add(gloss_text)
                cleaned.append(gloss_text)
        if cleaned:
            flattened.append(", ".join(cleaned))

    return flattened


def flatten_hwxnet_english_translations(
    entry: Dict[str, Any],
) -> List[str]:
    """
    Flatten 英文解释按拼音 into the legacy flat 英文翻译 list.

    Prefer the structured field when present. Fall back to legacy 英文翻译 only
    when the structured field is missing or empty.
    """
    if not entry:
        return []

    english_by_pinyin = entry.get("英文解释按拼音")
    flattened = flatten_english_translations_by_pinyin(english_by_pinyin)
    if flattened:
        return flattened

    legacy_english = entry.get("英文翻译") or []
    if isinstance(legacy_english, list):
        return [gloss.strip() for gloss in legacy_english if isinstance(gloss, str) and gloss.strip()]
    return []
