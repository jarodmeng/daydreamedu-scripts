"""
Helpers for HWXNet common phrase transition fields.
"""

from typing import Any, Dict, List, Set


def flatten_hwxnet_common_phrases(
    entry: Dict[str, Any],
    preserve_legacy_order: bool = True,
) -> List[str]:
    """
    Flatten 常用词组按拼音 into the legacy flat 常用词组 list.

    Prefer the legacy 常用词组 ordering when the same phrases still exist there so
    current behavior stays stable while consumers migrate to the structured field.
    Bucket order follows 拼音 order and phrase order within each bucket.
    """
    if not entry:
        return []

    phrases_by_pinyin = entry.get("常用词组按拼音")
    legacy_phrases = entry.get("常用词组") or []

    flattened: List[str] = []
    seen: Set[str] = set()

    if preserve_legacy_order and isinstance(legacy_phrases, list):
        for phrase in legacy_phrases:
            if not isinstance(phrase, str):
                continue
            phrase_text = phrase.strip()
            if phrase_text and phrase_text not in seen:
                flattened.append(phrase_text)
                seen.add(phrase_text)

    if isinstance(phrases_by_pinyin, list):
        for bucket in phrases_by_pinyin:
            if not isinstance(bucket, dict):
                continue
            phrases = bucket.get("Phrases")
            if not isinstance(phrases, list):
                continue
            for phrase in phrases:
                if not isinstance(phrase, str):
                    continue
                phrase_text = phrase.strip()
                if phrase_text and phrase_text not in seen:
                    flattened.append(phrase_text)
                    seen.add(phrase_text)

    if flattened:
        return flattened

    if isinstance(legacy_phrases, list):
        return [phrase.strip() for phrase in legacy_phrases if isinstance(phrase, str) and phrase.strip()]
    return []
