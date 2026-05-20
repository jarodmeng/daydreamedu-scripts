"""Registry-derived completion series for (student, template) pairs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile


def slugify_student(student_id: str | None, student_name: str | None) -> str:
    """Match ``marking.core.artifact_paths.slugify_student`` (no marking import)."""
    raw = student_id or student_name or "unknown_student"
    return re.sub(r"[^a-z0-9]+", "_", raw.strip().casefold()).strip("_") or "unknown_student"


def series_id_for(
    student_id: str | None,
    student_name: str | None,
    template_file_id: str,
) -> str:
    return f"{slugify_student(student_id, student_name)}::{template_file_id}"


def _parse_added_at_sort_key(added_at: str) -> tuple[int, ...]:
    normalized = added_at.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)


def _completion_sort_key(completion: PdfFile) -> tuple[tuple[int, ...], str]:
    resolved = Path(completion.path).expanduser().resolve(strict=False).as_posix()
    return (_parse_added_at_sort_key(completion.added_at), resolved)


@dataclass(frozen=True)
class CompletionSeriesMember:
    file_id: str
    path: str
    added_at: str
    attempt_sequence: int


@dataclass(frozen=True)
class CompletionSeries:
    series_id: str
    student_id: str
    template_file_id: str
    members: tuple[CompletionSeriesMember, ...]

    @property
    def attempt_count(self) -> int:
        return len(self.members)


def build_completion_series(
    *,
    student_id: str,
    student_name: str | None,
    template_file_id: str,
    completions: list[PdfFile],
) -> CompletionSeries | None:
    """Filter and order completion mains for one student on one template."""
    members_files = [
        c
        for c in completions
        if c.student_id == student_id and not c.is_template and c.file_type == "main"
    ]
    if not members_files:
        return None
    members_files.sort(key=_completion_sort_key)
    sid = series_id_for(student_id, student_name, template_file_id)
    members = tuple(
        CompletionSeriesMember(
            file_id=c.id,
            path=Path(c.path).expanduser().resolve(strict=False).as_posix(),
            added_at=c.added_at,
            attempt_sequence=index + 1,
        )
        for index, c in enumerate(members_files)
    )
    return CompletionSeries(
        series_id=sid,
        student_id=student_id,
        template_file_id=template_file_id,
        members=members,
    )
