# Completion date storage and inference helpers (proposal 17).

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

COMPLETION_DATE_SOURCES = frozenset(
    {
        "handwritten_page1",
        "filename_term",
        "drive_modified",
        "goodnotes_last_modified",
        "goodnotes_updated_at",
        "manual",
    }
)

COMPLETION_DATE_CONFIDENCE_LEVELS = frozenset({"high", "medium", "low"})

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Proposal 17 §5.2 — P1 calendar year anchors (Singapore school year = calendar year).
STUDENT_P1_CALENDAR_YEAR: dict[str, int] = {
    "winston": 2021,
    "emma": 2023,
    "abigail": 2025,
}

_PATH_PRIMARY_LEVEL_RE = re.compile(r"(?:^|[/\\])P([1-6])(?:[/\\]|$)", re.IGNORECASE)
_NAME_PRIMARY_LEVEL_RE = re.compile(
    r"\b(?:Primary|P)\s*([1-6])\b", re.IGNORECASE
)

REASON_SCHOOL_YEAR_MISMATCH = "school_year_mismatch"


@dataclass(frozen=True)
class CompletionDateRecord:
    file_id: str
    completion_date: str  # YYYY-MM-DD
    source: str
    confidence: str | None
    inference_model: str | None
    source_detail: dict | None
    inferred_at: str
    updated_at: str


@dataclass(frozen=True)
class InferCompletionDatesReport:
    """Batch inference summary (Phases 2–3)."""

    processed: int = 0
    written: int = 0
    skipped_existing: int = 0
    skipped_manual: int = 0
    skipped_no_cached_result: int = 0
    skipped_no_date: int = 0
    failed: int = 0
    still_undated: int = 0


def merge_infer_completion_dates_report(
    report: InferCompletionDatesReport, **kwargs: int
) -> InferCompletionDatesReport:
    """Return a new report with selected counters incremented or replaced."""
    data = {
        "processed": report.processed,
        "written": report.written,
        "skipped_existing": report.skipped_existing,
        "skipped_manual": report.skipped_manual,
        "skipped_no_cached_result": report.skipped_no_cached_result,
        "skipped_no_date": report.skipped_no_date,
        "failed": report.failed,
        "still_undated": report.still_undated,
    }
    data.update(kwargs)
    return InferCompletionDatesReport(**data)


def normalize_completion_date(completion_date: str) -> str:
    """Validate YYYY-MM-DD calendar date; return normalized string."""
    value = str(completion_date).strip()
    if not _ISO_DATE_RE.match(value):
        raise ValueError(
            f"completion_date must be ISO YYYY-MM-DD; got {completion_date!r}"
        )
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(
            f"completion_date must be a valid calendar date; got {completion_date!r}"
        ) from exc
    return value


def normalize_completion_date_source(source: str) -> str:
    value = str(source).strip()
    if value not in COMPLETION_DATE_SOURCES:
        raise ValueError(
            f"source must be one of {', '.join(sorted(COMPLETION_DATE_SOURCES))}; got {source!r}"
        )
    return value


def normalize_completion_date_confidence(confidence: str | None) -> str | None:
    if confidence is None:
        return None
    value = str(confidence).strip()
    if value not in COMPLETION_DATE_CONFIDENCE_LEVELS:
        raise ValueError(
            "confidence must be one of high, medium, low; "
            f"got {confidence!r}"
        )
    return value


def normalize_inference_model(inference_model: str | None) -> str | None:
    if inference_model is None:
        return None
    value = str(inference_model).strip()
    if not value:
        return None
    if value == "inherit":
        raise ValueError(
            'inference_model must be the actual detector model identifier, not "inherit"'
        )
    return value


@dataclass(frozen=True)
class SchoolYearExpectation:
    student_id: str
    primary_level: int
    expected_school_year: int


def infer_primary_level_from_path(path: str, *, name: str | None = None) -> int | None:
    """Return 1–6 from ``.../P5/...`` path segment, else from filename."""
    normalized = str(path).replace("\\", "/")
    match = _PATH_PRIMARY_LEVEL_RE.search(normalized)
    if match:
        return int(match.group(1))
    if name:
        name_match = _NAME_PRIMARY_LEVEL_RE.search(str(name))
        if name_match:
            return int(name_match.group(1))
    return None


def expected_school_year(student_id: str, primary_level: int) -> int | None:
    """``school_year = p1_year(student_id) + (primary_level - 1)`` (proposal 17 §5.2)."""
    p1_year = STUDENT_P1_CALENDAR_YEAR.get(str(student_id).strip())
    if p1_year is None:
        return None
    if not 1 <= int(primary_level) <= 6:
        return None
    return p1_year + (int(primary_level) - 1)


def school_year_expectation(
    *,
    student_id: str | None,
    path: str,
    name: str | None = None,
) -> SchoolYearExpectation | None:
    if not student_id:
        return None
    level = infer_primary_level_from_path(path, name=name)
    if level is None:
        return None
    year = expected_school_year(student_id, level)
    if year is None:
        return None
    return SchoolYearExpectation(
        student_id=str(student_id).strip(),
        primary_level=level,
        expected_school_year=year,
    )


def plausible_school_year_window(expected_school_year: int) -> tuple[int, int]:
    """Inclusive calendar-year range for a completion at this path grade."""
    year = int(expected_school_year)
    return (year - 1, year + 1)


def check_completion_date_school_year(
    completion_date: str,
    *,
    student_id: str | None,
    path: str,
    name: str | None = None,
) -> tuple[bool, dict]:
    """Quick sanity check: completion calendar year vs student + ``Pn`` in path.

    Returns ``(plausible, detail)``. When student or grade is unknown, returns
    ``(True, {"skipped": ...})`` so inference is not blocked.
    """
    normalized = normalize_completion_date(completion_date)
    completion_year = int(normalized[:4])
    expectation = school_year_expectation(
        student_id=student_id, path=path, name=name
    )
    if expectation is None:
        return True, {"skipped": "unknown_student_or_grade"}

    low, high = plausible_school_year_window(expectation.expected_school_year)
    detail: dict = {
        "student_id": expectation.student_id,
        "primary_level": expectation.primary_level,
        "expected_school_year": expectation.expected_school_year,
        "allowed_year_min": low,
        "allowed_year_max": high,
        "completion_year": completion_year,
    }
    if low <= completion_year <= high:
        return True, detail

    detail["reason"] = REASON_SCHOOL_YEAR_MISMATCH
    return False, detail


_EXAM_VINTAGE_YEAR_RE = re.compile(
    r"\b(?:EOY|EoY|EYE|PSLE|WA\s*\d|exam|paper|header|vintage)\b",
    re.IGNORECASE,
)
_YEAR_FROM_HEADER_RE = re.compile(
    r"year\s+from\s+(?:header|title|worksheet|paper|exam)",
    re.IGNORECASE,
)
_EXPLICIT_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def _date_line_has_explicit_completion_year(
    evidence: str, completion_year: int
) -> bool:
    """True when evidence quotes the completion year on the Date line itself."""
    lower = evidence.lower()
    if "date" not in lower:
        return False
    date_idx = lower.find("date")
    window = evidence[date_idx : date_idx + 60]
    for stop in (";", " header", " eoy", " psle", " wa", " —", " - "):
        pos = window.lower().find(stop)
        if pos > 0:
            window = window[:pos]
    return str(completion_year) in window


def adjust_page1_completion_year_for_path_context(
    completion_date: str,
    *,
    student_id: str | None,
    path: str,
    name: str | None = None,
    source_detail: dict | None = None,
) -> tuple[str, dict | None]:
    """Prefer path-grade school year over exam vintage in headers (proposal 17 §5.1).

    When the agent inferred ``expected_school_year - 1`` from a printed exam year
    (e.g. EOY 2024 on a P5 path in school year 2025) but the ``Date:`` line has
    month/day only, bump the calendar year to ``expected_school_year``.
  """
    normalized = normalize_completion_date(completion_date)
    expectation = school_year_expectation(
        student_id=student_id, path=path, name=name
    )
    if expectation is None:
        return normalized, None

    detail = source_detail or {}
    evidence = str(detail.get("evidence") or "")
    disambiguation = str(detail.get("disambiguation") or "")
    combined = f"{evidence} {disambiguation}"

    completion_year = int(normalized[:4])
    expected = expectation.expected_school_year
    if completion_year != expected - 1:
        return normalized, None

    if _date_line_has_explicit_completion_year(evidence, completion_year):
        return normalized, None

    used_exam_vintage = bool(
        _YEAR_FROM_HEADER_RE.search(combined)
        or _EXAM_VINTAGE_YEAR_RE.search(combined)
    )
    if not used_exam_vintage:
        return normalized, None

    adjusted = f"{expected}-{normalized[5:]}"
    return adjusted, {
        "from_year": completion_year,
        "to_year": expected,
        "reason": "path_grade_school_year_over_exam_header_vintage",
        "primary_level": expectation.primary_level,
        "expected_school_year": expected,
    }


def validate_inferred_completion_date_provenance(
    *,
    source: str,
    confidence: str | None,
    inference_model: str | None,
) -> None:
    """Require confidence (and model for page-1) when persisting automated detections."""
    if source == "manual":
        return
    if confidence is None:
        raise ValueError(f"confidence is required when source={source!r}")
    if source == "handwritten_page1" and inference_model is None:
        raise ValueError(
            "inference_model is required when source='handwritten_page1'"
        )
