"""Tests for amendment-resolved marks in report_marked_completion_fqi_stats."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = (
    _REPO_ROOT
    / "ai_study_buddy/context/student_understandings/scripts/report_marked_completion_fqi_stats.py"
)


def _load_script_module():
    spec = importlib.util.spec_from_file_location("report_marked_completion_fqi_stats", _SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_resolved_question_results_applies_amendment(tmp_path: Path):
    mod = _load_script_module()
    db_path = tmp_path / "study_buddy.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE marking_artifacts (
            artifact_id TEXT PRIMARY KEY,
            artifact_path TEXT NOT NULL,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            raw_json TEXT NOT NULL
        );
        CREATE TABLE marking_amendments (
            amendment_id TEXT PRIMARY KEY,
            artifact_id TEXT NOT NULL,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            raw_json TEXT NOT NULL
        );
        """
    )

    base = {
        "schema_version": "marking_result.v1",
        "context": {
            "student_id": "emma",
            "subject_context": "singapore_primary_math",
            "attempt_file_id": "attempt-1",
        },
        "summary": {"total_marks": 1, "earned_marks": 0, "percentage": 0},
        "question_results": [
            {
                "result_id": "Q1",
                "scoring_status": "counted",
                "outcome": "wrong",
                "max_marks": 2,
                "earned_marks": 0,
            }
        ],
    }
    amendment = {
        "schema_version": "marking_amendment.v1",
        "context": {
            "student_id": "emma",
            "subject_context": "singapore_primary_math",
            "attempt_file_id": "attempt-1",
            "marking_result_path": "marking_results/emma/singapore_primary_math/sample.json",
        },
        "summary_overrides": {},
        "question_amendments": [
            {
                "result_id": "Q1",
                "fields": {"earned_marks": 1, "outcome": "partial"},
                "reviewer_reason": "partial credit",
            }
        ],
        "question_page_map_amendments": [],
        "review_meta": {"updated_at": "2026-01-01T00:00:00Z", "updated_by": "test"},
    }
    conn.execute(
        """
        INSERT INTO marking_artifacts(artifact_id, artifact_path, raw_json)
        VALUES (?, ?, ?)
        """,
        ("art-1", "marking_results/emma/singapore_primary_math/sample.json", json.dumps(base)),
    )
    conn.execute(
        """
        INSERT INTO marking_amendments(amendment_id, artifact_id, raw_json)
        VALUES (?, ?, ?)
        """,
        ("amend-1", "art-1", json.dumps(amendment)),
    )
    conn.commit()

    rows, has_amendment = mod._load_resolved_question_results(
        conn,
        artifact_id="art-1",
        artifact_path="marking_results/emma/singapore_primary_math/sample.json",
    )
    conn.close()

    assert has_amendment is True
    assert len(rows) == 1
    assert rows[0]["earned_marks"] == 1
    assert rows[0]["outcome"] == "partial"
