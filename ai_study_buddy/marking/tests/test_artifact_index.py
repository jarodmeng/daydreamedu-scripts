"""Tests for batch marking artifact index."""

from __future__ import annotations

import json
from pathlib import Path

from ai_study_buddy.marking.core.artifact_lookup import (
    MarkingArtifactIndex,
    build_marking_artifact_index,
    find_marking_artifacts_for_attempt,
)


def _write_marking_json(
    path: Path,
    *,
    attempt_file_id: str,
    created_at: str = "2026-05-01T10:00:00+08:00",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "created_at": created_at,
                "context": {"attempt_file_id": attempt_file_id},
            }
        ),
        encoding="utf-8",
    )


def test_build_marking_artifact_index_groups_by_completion_id(tmp_path: Path) -> None:
    ctx = tmp_path / "context"
    results = ctx / "marking_results" / "winston" / "singapore_primary_math"
    _write_marking_json(
        results / "older.json",
        attempt_file_id="file-1",
        created_at="2026-05-01T10:00:00+08:00",
    )
    _write_marking_json(
        results / "newer.json",
        attempt_file_id="file-1",
        created_at="2026-05-02T10:00:00+08:00",
    )

    index = build_marking_artifact_index(context_root=ctx)
    refs = index.by_completion_id["file-1"]
    assert len(refs) == 2
    assert refs[0].marking_result_json.name == "newer.json"


def test_find_marking_artifacts_uses_prebuilt_index(monkeypatch, tmp_path: Path) -> None:
    from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile

    ctx = tmp_path / "context"
    results = ctx / "marking_results" / "winston"
    _write_marking_json(results / "run.json", attempt_file_id="file-9")

    completion = PdfFile(
        id="file-9",
        name="_c_x.pdf",
        path=str(tmp_path / "_c_x.pdf"),
        file_type="main",
        doc_type="exam",
        student_id="winston",
        subject="math",
        is_template=False,
        size_bytes=1,
        page_count=1,
        has_raw=False,
        metadata=None,
        added_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        notes=None,
    )
    from types import SimpleNamespace

    class FakeManager:
        def get_file(self, file_id: str):
            return completion if file_id == "file-9" else None

        def get_student(self, student_id: str):
            return SimpleNamespace(name="Winston", email=None)

    manager = FakeManager()
    index = build_marking_artifact_index(context_root=ctx)

    def fail_scan(*_args, **_kwargs):
        raise AssertionError("filesystem scan should not run when index hits")

    monkeypatch.setattr(
        "ai_study_buddy.marking.core.artifact_lookup._find_via_filesystem",
        fail_scan,
    )
    refs = find_marking_artifacts_for_attempt(
        "file-9",
        manager=manager,  # type: ignore[arg-type]
        context_root=ctx,
        artifact_index=index,
    )
    assert len(refs) == 1
    assert refs[0].marking_result_json.name == "run.json"
