"""Stable read API for `study_buddy.db` (Proposal L4 Phase 2).

Call sites may use this façade instead of importing ``read_*`` helpers directly.

Marking lookups return the same logical ordering as filesystem scans behind
:class:`~ai_study_buddy.marking.core.artifact_lookup.MarkingArtifactRef`.
"""

from __future__ import annotations

from typing import Any

from ai_study_buddy.learning_db.read.read_documents import (
    fetch_marking_amendment_raw_json as _fetch_amendment,
    fetch_student_review_state_raw_json as _fetch_review,
)
from ai_study_buddy.learning_db.read.read_marking import find_marking_artifact_refs_from_db as _find_refs


class LearningDbReadRepository:
    """Read-only accessors; env flags still gate product integration via marking/repository."""

    find_marking_artifact_refs_from_db = staticmethod(_find_refs)

    @staticmethod
    def fetch_student_review_state_raw(json_relative_path_under_context: str) -> dict[str, Any] | None:
        """e.g. ``student_review_states/emma/foo.json``."""

        return _fetch_review(json_relative_path_under_context)

    @staticmethod
    def fetch_marking_amendment_raw(json_relative_path_under_context: str) -> dict[str, Any] | None:
        """e.g. ``marking_amendments/emma/foo.json``."""

        return _fetch_amendment(json_relative_path_under_context)
