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
        from ai_study_buddy.learning_db.read.read_documents import (
            fetch_student_review_state_raw_json,
            relative_review_state_path,
        )

        rel = relative_review_state_path(student_id, subject_context, artifact_stem)
        learns = False
        fallback_fs = True
        try:
            from ai_study_buddy.learning_db.core.config import (
                learning_db_read_fallback_filesystem,
                learning_db_reads_enabled,
            )

            learns = learning_db_reads_enabled()
            fallback_fs = learning_db_read_fallback_filesystem()
        except ImportError:
            pass

        if learns:
            raw = fetch_student_review_state_raw_json(rel)
            if raw is not None:
                return normalize_review_state(raw)
            if not fallback_fs:
                return normalize_review_state(None)

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
        actor: str = "script:ai_study_buddy.marking.review.repository",
    ) -> Path:
        path = self.review_state_path(
            student_id=student_id,
            subject_context=subject_context,
            artifact_stem=artifact_stem,
        )
        canonical = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"

        from ai_study_buddy.learning_db.core.config import learning_db_dual_write_enabled, learning_db_json_export_enabled
        from ai_study_buddy.learning_db.ingest.dual_write import maybe_dual_write_from_canonical, maybe_dual_write_snapshot
        from ai_study_buddy.learning_db.read.read_documents import relative_review_state_path
        from ai_study_buddy.learning_db.cli.write_boundary_audit import audit_write_boundary_event

        rel_posix = relative_review_state_path(student_id, subject_context, artifact_stem)

        try:
            if learning_db_json_export_enabled():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(canonical, encoding="utf-8")
                maybe_dual_write_snapshot(
                    family="student_review_state",
                    snapshot_path=path,
                    context_root=self._context_root,
                )
            else:
                if not learning_db_dual_write_enabled():
                    raise ValueError(
                        "LEARNING_DB_ENABLE_JSON_EXPORT=0 requires LEARNING_DB_ENABLE_DUAL_WRITE=1 for save_review_state "
                        "to persist into study_buddy.db"
                    )
                maybe_dual_write_from_canonical(
                    family="student_review_state",
                    rel_path=rel_posix,
                    canonical_snapshot_text=canonical,
                )
        except Exception as exc:
            audit_write_boundary_event(
                operation_type="student_review_state_write",
                entity_type="student_review_state",
                entity_id=rel_posix,
                status="failed",
                actor=actor,
                metadata={"context_root": str(self._context_root)},
                error_code=type(exc).__name__,
                error_message=str(exc),
            )
            raise
        audit_write_boundary_event(
            operation_type="student_review_state_write",
            entity_type="student_review_state",
            entity_id=rel_posix,
            status="succeeded",
            actor=actor,
            metadata={"context_root": str(self._context_root)},
        )
        return path

    def load_raw_review_state(
        self,
        *,
        student_id: str,
        subject_context: str,
        artifact_stem: str,
    ) -> dict[str, Any] | None:
        from ai_study_buddy.learning_db.read.read_documents import (
            fetch_student_review_state_raw_json,
            relative_review_state_path,
        )

        rel = relative_review_state_path(student_id, subject_context, artifact_stem)
        learns = False
        fallback_fs = True
        try:
            from ai_study_buddy.learning_db.core.config import (
                learning_db_read_fallback_filesystem,
                learning_db_reads_enabled,
            )

            learns = learning_db_reads_enabled()
            fallback_fs = learning_db_read_fallback_filesystem()
        except ImportError:
            pass

        if learns:
            raw = fetch_student_review_state_raw_json(rel)
            if raw is not None:
                return raw
            if not fallback_fs:
                return None

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
        from ai_study_buddy.learning_db.read.read_documents import (
            fetch_marking_amendment_raw_json,
            relative_amendment_path,
        )

        rel = relative_amendment_path(student_id, subject_context, artifact_stem)
        learns = False
        fallback_fs = True
        try:
            from ai_study_buddy.learning_db.core.config import (
                learning_db_read_fallback_filesystem,
                learning_db_reads_enabled,
            )

            learns = learning_db_reads_enabled()
            fallback_fs = learning_db_read_fallback_filesystem()
        except ImportError:
            pass

        if learns:
            raw = fetch_marking_amendment_raw_json(rel)
            if raw is not None:
                return raw
            if not fallback_fs:
                return None

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
        actor: str = "script:ai_study_buddy.marking.review.repository",
    ) -> Path:
        path = self.amendment_path(
            student_id=student_id,
            subject_context=subject_context,
            artifact_stem=artifact_stem,
        )
        canonical = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"

        from ai_study_buddy.learning_db.core.config import learning_db_dual_write_enabled, learning_db_json_export_enabled
        from ai_study_buddy.learning_db.ingest.dual_write import maybe_dual_write_from_canonical, maybe_dual_write_snapshot
        from ai_study_buddy.learning_db.read.read_documents import relative_amendment_path
        from ai_study_buddy.learning_db.cli.write_boundary_audit import audit_write_boundary_event

        rel_posix = relative_amendment_path(student_id, subject_context, artifact_stem)

        try:
            if learning_db_json_export_enabled():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(canonical, encoding="utf-8")
                maybe_dual_write_snapshot(
                    family="marking_amendment",
                    snapshot_path=path,
                    context_root=self._context_root,
                )
            else:
                if not learning_db_dual_write_enabled():
                    raise ValueError(
                        "LEARNING_DB_ENABLE_JSON_EXPORT=0 requires LEARNING_DB_ENABLE_DUAL_WRITE=1 for save_amendment "
                        "to persist into study_buddy.db"
                    )
                maybe_dual_write_from_canonical(
                    family="marking_amendment",
                    rel_path=rel_posix,
                    canonical_snapshot_text=canonical,
                )
        except Exception as exc:
            audit_write_boundary_event(
                operation_type="marking_amendment_write",
                entity_type="marking_amendment",
                entity_id=rel_posix,
                status="failed",
                actor=actor,
                metadata={"context_root": str(self._context_root)},
                error_code=type(exc).__name__,
                error_message=str(exc),
            )
            raise
        audit_write_boundary_event(
            operation_type="marking_amendment_write",
            entity_type="marking_amendment",
            entity_id=rel_posix,
            status="succeeded",
            actor=actor,
            metadata={"context_root": str(self._context_root)},
        )
        return path
