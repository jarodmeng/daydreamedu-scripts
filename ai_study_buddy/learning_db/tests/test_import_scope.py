from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_study_buddy.learning_db.import_context_json import (
    rel_path_matches_scope,
    run_import,
)
from ai_study_buddy.learning_db.migrate import apply_migrations

from ai_study_buddy.learning_db.tests.fixtures import _minimal_mr


@pytest.mark.parametrize(
    ("rel", "student", "subject", "prefix", "expect"),
    [
        (
            "marking_results/emma/singapore_primary_science/x.json",
            "emma",
            None,
            None,
            True,
        ),
        (
            "marking_results/noah/singapore_primary_science/x.json",
            "emma",
            None,
            None,
            False,
        ),
        (
            "marking_results/emma/singapore_primary_science/x.json",
            None,
            "singapore_primary_science",
            None,
            True,
        ),
        (
            "marking_results/emma/singapore_primary_math/x.json",
            None,
            "singapore_primary_science",
            None,
            False,
        ),
        (
            "marking_results/emma/singapore_primary_math/x.json",
            "emma",
            "singapore_primary_science",
            None,
            False,
        ),
        (
            "marking_results/emma/singapore_primary_math/x.json",
            None,
            None,
            "marking_results/emma/singapore_primary_math",
            True,
        ),
        (
            "student_review_states/winston/foo/y.json",
            "winston",
            None,
            None,
            True,
        ),
    ],
)
def test_rel_path_matches_scope(
    rel: str,
    student: str | None,
    subject: str | None,
    prefix: str | None,
    expect: bool,
) -> None:
    assert rel_path_matches_scope(rel, student_id=student, subject_context=subject, path_prefix=prefix) is expect


def test_run_import_scopes_to_student(tmp_path: Path) -> None:
    ctx = tmp_path / "context"
    db = tmp_path / "db.sqlite"
    apply_migrations(db_path=db)
    _write_json(ctx / "marking_results" / "emma" / "singapore_primary_science" / "a.json", _minimal_mr("a1", "emma", "singapore_primary_science"))
    _write_json(ctx / "marking_results" / "noah" / "singapore_primary_science" / "b.json", _minimal_mr("b1", "noah", "singapore_primary_science"))

    summaries = run_import(
        db_path=db,
        context_root=ctx,
        dry_run=False,
        limit=None,
        artifact_family="marking_result",
        retry_quarantine=False,
        retry_status="open",
        retry_failure_stage=None,
        student_id="emma",
        subject_context=None,
        path_prefix=None,
    )
    assert summaries["marking_result"].scanned == 1


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
