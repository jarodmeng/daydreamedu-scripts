from datetime import datetime, timezone

from ai_study_buddy.pdf_file_manager.completion_date.goodnotes import (
    completion_date_from_utc_iso,
    confidence_for_goodnotes_match_status,
    infer_completion_date_from_goodnotes_match,
)
from ai_study_buddy.pdf_file_manager.goodnotes_metadata import (
    GoodnotesDocumentMatch,
    GoodnotesDocumentTimestamps,
)


def _match(
    *,
    status: str = "matched_exact",
    last_modified: str | None = "2026-03-18T14:54:04.072Z",
    updated_at: str | None = "2026-05-20T02:59:23Z",
) -> GoodnotesDocumentMatch:
    return GoodnotesDocumentMatch(
        status=status,  # type: ignore[arg-type]
        file_id="fid",
        registered_path="/GoodNotes/x.pdf",
        backup_stem="x",
        candidate_names=("x",),
        matched_candidate_name="x",
        goodnotes_document_id="DOC1",
        goodnotes_document_name="x",
        goodnotes_folder_path="Subject / P6",
        goodnotes_folder_ids=("a", "b"),
        timestamps=GoodnotesDocumentTimestamps(
            created_at="2026-01-01T00:00:00Z",
            updated_at=updated_at,
            last_modified=last_modified,
            created_at_raw=1.0,
            updated_at_raw=2.0,
            last_modified_raw=last_modified,
        ),
    )


def test_completion_date_from_utc_iso_sgt():
    day, utc = completion_date_from_utc_iso("2026-03-18T14:54:04.072Z")
    assert day == "2026-03-18"
    assert utc.startswith("2026-03-18T14:54:04")


def test_prefers_last_modified():
    row = infer_completion_date_from_goodnotes_match(_match())
    assert row is not None
    assert row.completion_date == "2026-03-18"
    assert row.source == "goodnotes_last_modified"
    assert row.confidence == "high"
    assert row.source_detail["timestamp_field"] == "last_modified"


def test_falls_back_to_updated_at():
    row = infer_completion_date_from_goodnotes_match(
        _match(last_modified=None, updated_at="2026-05-20T02:59:23Z")
    )
    assert row is not None
    assert row.source == "goodnotes_updated_at"
    assert row.completion_date == "2026-05-20"


def test_medium_confidence_for_underscore_restore():
    assert confidence_for_goodnotes_match_status("matched_leading_underscore_restored") == "medium"
    row = infer_completion_date_from_goodnotes_match(
        _match(status="matched_leading_underscore_restored")
    )
    assert row is not None
    assert row.confidence == "medium"


def test_not_found_returns_none():
    assert infer_completion_date_from_goodnotes_match(
        GoodnotesDocumentMatch(
            status="not_found",
            file_id="f",
            registered_path="/GoodNotes/x.pdf",
            backup_stem="x",
            candidate_names=(),
            matched_candidate_name=None,
            goodnotes_document_id=None,
            goodnotes_document_name=None,
            goodnotes_folder_path=None,
            goodnotes_folder_ids=(),
            timestamps=None,
        )
    ) is None
