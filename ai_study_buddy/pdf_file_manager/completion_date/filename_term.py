# Filename term heuristics for completion_date (proposal 17 §5.2).

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..completion_date import (
    normalize_completion_date,
    school_year_expectation,
)

FILENAME_TERM_SOURCE = "filename_term"
FILENAME_TERM_CONFIDENCE = "medium"
DAYS_BEFORE_TERM_END = 14

_DATA_FILE = Path(__file__).resolve().parent / "data" / "school_term_calendar.json"

# Match order: Term 4 → 2 → 3 → 1 (first hit wins).
_TERM_PATTERN_GROUPS: tuple[tuple[int, tuple[re.Pattern[str], ...]], ...] = (
    (
        4,
        (
            re.compile(r"期末考试"),
            re.compile(r"\bEoY\b", re.IGNORECASE),
            re.compile(r"\bEOY\b", re.IGNORECASE),
            re.compile(r"\bEYE\b", re.IGNORECASE),
            re.compile(r"\bEnd\s+of\s+Year\b", re.IGNORECASE),
            re.compile(r"\bTerm\s*4\b", re.IGNORECASE),
            re.compile(r"\bT4\b", re.IGNORECASE),
        ),
    ),
    (
        2,
        (
            re.compile(r"\bWA2\b", re.IGNORECASE),
            re.compile(r"\bSA2\b", re.IGNORECASE),
            re.compile(r"\bTerm\s*2\b", re.IGNORECASE),
            re.compile(r"\bT2\b", re.IGNORECASE),
            re.compile(r"测验2"),
        ),
    ),
    (
        3,
        (
            re.compile(r"\bWA3\b", re.IGNORECASE),
            re.compile(r"\bTerm\s*3\b", re.IGNORECASE),
            re.compile(r"\bT3\b", re.IGNORECASE),
            re.compile(r"测验3"),
        ),
    ),
    (
        1,
        (
            re.compile(r"\bWA1\b", re.IGNORECASE),
            re.compile(r"\bTerm\s*1\b", re.IGNORECASE),
            re.compile(r"\bT1\b", re.IGNORECASE),
            re.compile(r"测验1"),
        ),
    ),
)

_CHINESE_PRIMARY_LEVEL = (
    (re.compile(r"六年级"), 6),
    (re.compile(r"五年级"), 5),
    (re.compile(r"四年级"), 4),
    (re.compile(r"三年级"), 3),
    (re.compile(r"二年级"), 2),
    (re.compile(r"一年级"), 1),
)


@dataclass(frozen=True)
class FilenameTermInference:
    completion_date: str
    term: int
    matched_keyword: str
    school_year: int
    primary_level: int
    student_id: str
    term_end: str
    calendar_rule_id: str
    source_detail: dict[str, Any]


@lru_cache(maxsize=1)
def load_school_term_calendar(path: Path | None = None) -> dict[str, Any]:
    calendar_path = path or _DATA_FILE
    payload = json.loads(calendar_path.read_text(encoding="utf-8"))
    if "years" not in payload:
        raise ValueError(f"invalid school term calendar: {calendar_path}")
    return payload


def infer_term_from_title(title: str) -> tuple[int, str] | None:
    """Return (term 1–4, matched keyword) from normal_name or basename."""
    text = str(title).strip()
    if not text:
        return None
    for term, patterns in _TERM_PATTERN_GROUPS:
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                return term, match.group(0)
    return None


def _infer_primary_level_from_chinese(title: str) -> int | None:
    for pattern, level in _CHINESE_PRIMARY_LEVEL:
        if pattern.search(title):
            return level
    return None


def term_end_date(calendar: dict[str, Any], school_year: int, term: int) -> str:
    year_block = calendar["years"].get(str(int(school_year)))
    if year_block is None:
        raise KeyError(f"school year {school_year} not in calendar")
    term_block = year_block["terms"].get(str(int(term)))
    if term_block is None:
        raise KeyError(f"term {term} not in school year {school_year}")
    return normalize_completion_date(term_block["end"])


def completion_date_from_term_end(term_end: str, *, days_before: int = DAYS_BEFORE_TERM_END) -> str:
    end = date.fromisoformat(normalize_completion_date(term_end))
    return (end - timedelta(days=days_before)).isoformat()


def infer_completion_date_from_filename_term(
    title: str,
    *,
    student_id: str | None,
    path: str,
    name: str | None = None,
    calendar: dict[str, Any] | None = None,
) -> FilenameTermInference | None:
    """Infer completion_date from filename/title keywords + student path grade."""
    term_match = infer_term_from_title(title)
    if term_match is None:
        return None

    term, matched_keyword = term_match
    expectation = school_year_expectation(
        student_id=student_id, path=path, name=name or title
    )
    if expectation is None:
        chinese_level = _infer_primary_level_from_chinese(title)
        if chinese_level is None or not student_id:
            return None
        from ..completion_date import SchoolYearExpectation, expected_school_year

        school_year = expected_school_year(student_id, chinese_level)
        if school_year is None:
            return None
        expectation = SchoolYearExpectation(
            student_id=str(student_id).strip(),
            primary_level=chinese_level,
            expected_school_year=school_year,
        )

    cal = calendar if calendar is not None else load_school_term_calendar()
    try:
        end = term_end_date(cal, expectation.expected_school_year, term)
    except KeyError:
        return None

    completion_date = completion_date_from_term_end(end)
    rule_id = f"{expectation.expected_school_year}-P{expectation.primary_level}-T{term}"

    source_detail = {
        "matched_keyword": matched_keyword,
        "term": term,
        "school_year": expectation.expected_school_year,
        "primary_level": expectation.primary_level,
        "term_end": end,
        "days_before_term_end": DAYS_BEFORE_TERM_END,
        "calendar_rule_id": rule_id,
        "title": title,
    }

    return FilenameTermInference(
        completion_date=completion_date,
        term=term,
        matched_keyword=matched_keyword,
        school_year=expectation.expected_school_year,
        primary_level=expectation.primary_level,
        student_id=expectation.student_id,
        term_end=end,
        calendar_rule_id=rule_id,
        source_detail=source_detail,
    )
