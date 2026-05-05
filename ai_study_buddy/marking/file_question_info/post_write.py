from __future__ import annotations

from pathlib import Path

from ai_study_buddy.learning_db.dual_write import maybe_dual_write_snapshot
from ai_study_buddy.marking.file_question_info.api import load_question_sections_json, validate_question_sections_dict


def finalize_question_sections_snapshot(
    *,
    snapshot_path: Path,
    context_root: Path,
    db_path: Path | str | None = None,
) -> bool:
    """Shared post-write hook for detector workflows.

    Validates the just-written ``question_sections.json`` and mirrors it to ``study_buddy.db``
    through dual-write semantics.
    """

    payload = load_question_sections_json(snapshot_path)
    validate_question_sections_dict(payload)
    return maybe_dual_write_snapshot(
        family="file_question_info",
        snapshot_path=snapshot_path,
        context_root=context_root,
        db_path=db_path,
    )
