from __future__ import annotations

import importlib.util
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ai_study_buddy.learning_db.core.connection import default_context_root, default_db_path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FQI_STATS_SCRIPT = (
    _REPO_ROOT / "ai_study_buddy/context/student_understandings/scripts/report_marked_completion_fqi_stats.py"
)

PICKER_TO_CONTEXTS: dict[str, tuple[str, ...]] = {
    "english": ("singapore_primary_english",),
    "chinese": ("singapore_primary_chinese", "singapore_primary_higher_chinese"),
    "math": ("singapore_primary_math",),
    "science": ("singapore_primary_science",),
}

SUBJECT_CONTEXT_LABELS: dict[str, str] = {
    "singapore_primary_english": "English",
    "singapore_primary_chinese": "Chinese",
    "singapore_primary_higher_chinese": "Higher Chinese",
    "singapore_primary_math": "Math",
    "singapore_primary_science": "Science",
}

VALID_SUBJECT_PICKERS = frozenset(PICKER_TO_CONTEXTS.keys())

# Higher Chinese FQI/marking often lives under singapore_primary_chinese (high-chinese-v*).
# Split by FQI schema prefix — same flags as report_marked_completion_fqi_stats.py CLI.
_HIGH_CHINESE_FQI_PREFIX = "high-chinese"

_CHINESE_COMPUTE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "subject_context": "singapore_primary_chinese",
        "marking_contexts": ("singapore_primary_chinese",),
        "exclude_fqi_schema_prefixes": (_HIGH_CHINESE_FQI_PREFIX,),
        "include_fqi_schema_prefixes": (),
    },
    {
        "subject_context": "singapore_primary_higher_chinese",
        "marking_contexts": ("singapore_primary_chinese", "singapore_primary_higher_chinese"),
        "exclude_fqi_schema_prefixes": (),
        "include_fqi_schema_prefixes": (_HIGH_CHINESE_FQI_PREFIX,),
    },
)

_EMPTY_MESSAGE = "No counted markings in scope for this subject."


def _fqi_stats_script_path() -> Path:
    return _FQI_STATS_SCRIPT


def _load_fqi_stats_module():
    name = "report_marked_completion_fqi_stats"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    script = _fqi_stats_script_path()
    spec = importlib.util.spec_from_file_location(name, script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load FQI stats script at {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _portal_context_root() -> Path:
    raw = os.environ.get("AI_STUDY_BUDDY_CONTEXT_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return default_context_root()


def _marks_type_order(by_type: dict[str, Any]) -> list[str]:
    mod = _load_fqi_stats_module()
    ordered = mod._ordered_question_types(
        Counter({k: int(v.get("question_count", 0)) for k, v in by_type.items()})
    )
    return list(ordered)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _compute_specs_for_picker(picker: str) -> tuple[dict[str, Any], ...]:
    if picker == "chinese":
        return _CHINESE_COMPUTE_SPECS
    return [
        {
            "subject_context": ctx,
            "marking_contexts": (ctx,),
            "exclude_fqi_schema_prefixes": (),
            "include_fqi_schema_prefixes": (),
        }
        for ctx in PICKER_TO_CONTEXTS[picker]
    ]


def _append_subject_block(
    subjects_out: list[dict[str, Any]],
    *,
    subject_context: str,
    marks: dict[str, Any],
) -> None:
    if not marks or int(marks.get("question_count") or 0) <= 0:
        return
    by_type = marks.get("by_type") or {}
    subjects_out.append(
        {
            "subject_context": subject_context,
            "display_label": SUBJECT_CONTEXT_LABELS[subject_context],
            "type_order": _marks_type_order(by_type),
            "marks_by_question_type": marks,
        }
    )


def build_marks_by_question_type_response(
    *,
    student_id: str,
    subject: str,
    build_stats: Callable[..., dict[str, Any]] | None = None,
    study_db: Path | None = None,
    context_root: Path | None = None,
) -> dict[str, Any]:
    """Serve-time marks-by-type payload for one student × subject picker."""

    student_slug = student_id.strip()
    picker = subject.strip().lower()
    if not student_slug:
        raise ValueError("student_id is required")
    if picker not in VALID_SUBJECT_PICKERS:
        raise ValueError(f"subject must be one of: {', '.join(sorted(VALID_SUBJECT_PICKERS))}")

    resolved_db = (study_db or default_db_path()).expanduser().resolve()
    if not resolved_db.is_file():
        raise StudyDatabaseUnavailableError("Study database unavailable")

    resolved_context = (context_root or _portal_context_root()).expanduser().resolve()
    if not resolved_context.is_dir():
        raise StudyDatabaseUnavailableError("Context root unavailable")

    compute = build_stats
    if compute is None:
        compute = _load_fqi_stats_module().build_marked_completion_fqi_stats

    subjects_out: list[dict[str, Any]] = []
    for spec in _compute_specs_for_picker(picker):
        report = compute(
            student_slug=student_slug,
            subject_contexts=tuple(spec["marking_contexts"]),
            study_db=resolved_db,
            context_root=resolved_context,
            include_fqi_schema_prefixes=tuple(spec["include_fqi_schema_prefixes"]),
            exclude_fqi_schema_prefixes=tuple(spec["exclude_fqi_schema_prefixes"]),
        )
        _append_subject_block(
            subjects_out,
            subject_context=str(spec["subject_context"]),
            marks=report.get("marking_marks_by_type") or {},
        )

    payload: dict[str, Any] = {
        "student_id": student_slug,
        "subject": picker,
        "generated_at": _now_iso(),
        "subjects": subjects_out,
    }
    if not subjects_out:
        payload["message"] = _EMPTY_MESSAGE
    return payload


class StudyDatabaseUnavailableError(Exception):
    """Raised when study DB or context root cannot be used for serve-time compute."""
