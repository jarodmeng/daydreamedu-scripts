"""
Pinyin search: parse user query and produce search keys for lookup.

Used by GET /api/pinyin-search. Accepts:
- Tone marks (e.g. nǐ, kě) -> one key e.g. ni3, ke3
- Numeric tone (e.g. ke3, ma0) -> one key
- No tone (e.g. ke, lv) -> keys for any tone: base, base1, base2, base3, base4, base0, base5
Invalid: empty, both tone mark and trailing digit, or malformed.
"""
from typing import List, Optional, Tuple

# Accented vowel -> (base_letter, tone). Tone 1-4, 0 = neutral. ü/ǖ/ǘ/ǚ/ǜ -> v
_ACCENT_TO_BASE_AND_TONE = {
    "ā": ("a", 1), "á": ("a", 2), "ǎ": ("a", 3), "à": ("a", 4), "ă": ("a", 3),
    "ē": ("e", 1), "é": ("e", 2), "ě": ("e", 3), "è": ("e", 4), "ĕ": ("e", 3),
    "ī": ("i", 1), "í": ("i", 2), "ǐ": ("i", 3), "ì": ("i", 4), "ĭ": ("i", 3),
    "ō": ("o", 1), "ó": ("o", 2), "ǒ": ("o", 3), "ò": ("o", 4), "ŏ": ("o", 3),
    "ū": ("u", 1), "ú": ("u", 2), "ǔ": ("u", 3), "ù": ("u", 4), "ŭ": ("u", 3),
    "ǖ": ("v", 1), "ǘ": ("v", 2), "ǚ": ("v", 3), "ǜ": ("v", 4),
    "ü": ("v", 0),
}
_PLAIN_VOWELS = set("aeiouv")
_TONE_MARK_CHARS = set(_ACCENT_TO_BASE_AND_TONE.keys())


def parse_pinyin_query(raw: str) -> Tuple[bool, Optional[str], Optional[List[str]]]:
    """
    Parse user pinyin input for search.
    Returns (is_valid, error_message, search_keys).
    If valid, search_keys is a list of keys to match (e.g. ["ke3"] or ["ke", "ke1", "ke2", "ke3", "ke4", "ke0", "ke5"]).
    If invalid, error_message is the Chinese error string and search_keys is None.
    """
    if not raw or not raw.strip():
        return False, "拼音输入格式错误", None
    s = raw.strip().lower()
    # Reject if contains space (multiple syllables)
    if " " in s:
        return False, "拼音输入格式错误", None

    has_tone_mark = any(c in _TONE_MARK_CHARS for c in s)
    # Trailing digit 0-5 (numeric tone)
    if len(s) >= 2 and s[-1] in "012345":
        digit = s[-1]
        base_part = s[:-1]
        if has_tone_mark:
            return False, "拼音输入格式错误", None  # both tone mark and numeric
        base_part = _normalize_ü_to_v(base_part)
        if not base_part or not _is_valid_syllable_base(base_part):
            return False, "拼音输入格式错误", None
        tone = 0 if digit in "05" else int(digit)
        key = f"{base_part}{tone}" if tone else f"{base_part}0"
        return True, None, [key]

    if has_tone_mark:
        base_chars = []
        tone = 0
        for c in s:
            if c in _ACCENT_TO_BASE_AND_TONE:
                b, t = _ACCENT_TO_BASE_AND_TONE[c]
                base_chars.append(b)
                tone = t
            elif c in _PLAIN_VOWELS or c == "v":
                base_chars.append(c)
            else:
                base_chars.append(c)
        base = "".join(base_chars)
        if not base or not _is_valid_syllable_base(base):
            return False, "拼音输入格式错误", None
        key = f"{base}{tone}" if tone else f"{base}0"
        return True, None, [key]

    # No tone: base only (e.g. ke, lv)
    base = _normalize_ü_to_v(s)
    if not base or not _is_valid_syllable_base(base):
        return False, "拼音输入格式错误", None
    keys = [base, f"{base}1", f"{base}2", f"{base}3", f"{base}4", f"{base}0", f"{base}5"]
    return True, None, keys


def _normalize_ü_to_v(s: str) -> str:
    """Replace ü with v for search key."""
    return s.replace("ü", "v")


def _is_valid_syllable_base(s: str) -> bool:
    """Basic check: only allow lowercase letters a-z and v (for ü)."""
    if not s:
        return False
    return all(c.isalpha() and c.islower() for c in s)


def pinyin_to_base_and_tone(s: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Normalize stored pinyin (e.g. 'bà') to (base, tone).
    Returns (syllable_base, tone 1-4 or 0 for neutral). Used for search keys and distractor logic.
    """
    return _pinyin_to_base_and_tone_impl(s)


def _pinyin_to_base_and_tone_impl(s: str) -> Tuple[Optional[str], Optional[int]]:
    """Normalize stored pinyin (e.g. 'bà') to (base, tone). Used for building searchable keys."""
    if not s or not s.strip():
        return None, None
    s = s.strip().lower()
    base_chars = []
    tone = 0
    for c in s:
        if c in _ACCENT_TO_BASE_AND_TONE:
            b, t = _ACCENT_TO_BASE_AND_TONE[c]
            base_chars.append(b)
            tone = t
        elif c in _PLAIN_VOWELS or c == "v":
            base_chars.append(c)
        else:
            base_chars.append(c)
    base = "".join(base_chars)
    return base if base else None, tone


def pinyin_to_searchable_forms(pinyin_str: str) -> List[str]:
    """Convert one stored pinyin string (e.g. 'bà') to list of searchable keys."""
    base, tone = _pinyin_to_base_and_tone_impl(pinyin_str)
    if base is None:
        return []
    out = [base]
    if tone == 0:
        out.append(f"{base}0")
        out.append(f"{base}5")
    else:
        out.append(f"{base}{tone}")
    return out


def compute_searchable_pinyin_for_entry(pinyin_list: list) -> List[str]:
    """Given 拼音 list for an entry, return sorted unique searchable keys."""
    if not pinyin_list:
        return []
    seen = set()
    for s in pinyin_list:
        if isinstance(s, str):
            for key in pinyin_to_searchable_forms(s):
                seen.add(key)
    return sorted(seen)
