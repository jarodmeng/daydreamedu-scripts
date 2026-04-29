from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_study_buddy.marking.review.models import normalize_review_state


class StudentReviewRepository:
    def __init__(self, *, context_root: Path):
        self._context_root = context_root
        self._review_states_root = context_root / "student_review_states"
        self._marking_amendments_root = context_root / "marking_amendments"

    def review_state_path(self, *, student_id: str, subject_context: str, artifact_stem: str) -> Path:
        return self._review_states_root / student_id / subject_context / f"{artifact_stem}.json"

    def load_review_state(
        self,
        *,
        student_id: str,
        subject_context: str,
        artifact_stem: str,
    ) -> dict[str, Any]:
        path = self.review_state_path(
            student_id=student_id,
            subject_context=subject_context,
            artifact_stem=artifact_stem,
        )
        if not path.exists():
            return normalize_review_state(None)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return normalize_review_state(None)
        return normalize_review_state(payload)

    def save_review_state(
        self,
        *,
        student_id: str,
        subject_context: str,
        artifact_stem: str,
        payload: dict[str, Any],
    ) -> Path:
        path = self.review_state_path(
            student_id=student_id,
            subject_context=subject_context,
            artifact_stem=artifact_stem,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        return path

    def load_raw_review_state(
        self,
        *,
        student_id: str,
        subject_context: str,
        artifact_stem: str,
    ) -> dict[str, Any] | None:
        path = self.review_state_path(
            student_id=student_id,
            subject_context=subject_context,
            artifact_stem=artifact_stem,
        )
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def amendment_path(self, *, student_id: str, subject_context: str, artifact_stem: str) -> Path:
        return self._marking_amendments_root / student_id / subject_context / f"{artifact_stem}.json"

    def load_raw_amendment(
        self,
        *,
        student_id: str,
        subject_context: str,
        artifact_stem: str,
    ) -> dict[str, Any] | None:
        path = self.amendment_path(
            student_id=student_id,
            subject_context=subject_context,
            artifact_stem=artifact_stem,
        )
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def save_amendment(
        self,
        *,
        student_id: str,
        subject_context: str,
        artifact_stem: str,
        payload: dict[str, Any],
    ) -> Path:
        path = self.amendment_path(
            student_id=student_id,
            subject_context=subject_context,
            artifact_stem=artifact_stem,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        return path
