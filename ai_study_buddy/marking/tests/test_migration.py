from __future__ import annotations

import json
import importlib
from pathlib import Path

from ai_study_buddy.marking.workflows.migrate_learning_reports import (
    migrate_learning_reports,
    parse_legacy_learning_report,
)
from ai_study_buddy.marking.core.taxonomy import derive_skill_tags_from_embedding_label

migrate_module = importlib.import_module("ai_study_buddy.marking.workflows.migrate_learning_reports")


def _write_legacy_report(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """# Learning Report

## Result

- Student: `Emma`
- Date: `2026-04-08`
- Score: `3/4`
- Percentage: `75%`
- Overall assessment: One careless slip in Q2.

## Marking Table

Convention: `OK` = full marks, `PART` = partial credit, `X` = zero marks.

| Name | Student answer | Correct answer | Total marks | Obtained marks | Embedding |
| --- | --- | --- | ---: | ---: | --- |
| ✅ Q1 | `(2)` | `(2)` | 2 | 2 | `Forces > fair test > control variables` |
| ⚠️ Q2 | `downward force only` | `downward gravitational force and upward air resistance` | 2 | **1** | `Forces > effects of force > force direction` |

## Report Context

- Attempt file: `/tmp/c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1.pdf`
- Template book file: `/tmp/_c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1.pdf`
- Book answer file: `/tmp/_c_Science Thematic Tests and Exam Practice Primary 4 - 11 Answers.pdf`
- Answer page range for this exercise: `12-13`
- Mapping source: `manual_verified`

## Notes

- This report was produced by manual visual comparison.
""",
        encoding="utf-8",
    )
    return path


def _write_legacy_report_with_disqualified(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """# Learning Report

## Result

- Student: `Winston`
- Date: `2026-04-13`
- Score: `2/2`
- Percentage: `100%`
- Overall assessment: Q2 disqualified due to source mismatch.

## Marking Table

Convention: `OK` = full marks, `PART` = partial credit, `X` = zero marks, `DQ` = disqualified.

| Name | Student answer | Correct answer | Total marks | Obtained marks | Embedding |
| --- | --- | --- | ---: | ---: | --- |
| ✅ Q1 | `12` | `12` | 2 | 2 | `Fractions > equivalent fractions` |
| ⛔ Q2 (disqualified) | `612.5` | `N/A` | 2 | 0 | `Disqualified: source mismatch` |

## Report Context

- Attempt file: `/tmp/c_disqualified_attempt.pdf`
- Template book file: `/tmp/_c_disqualified_attempt.pdf`
- Book answer file: `/tmp/_c_disqualified_answers.pdf`
- Answer page range for this exercise: `1-2`
- Mapping source: `manual_verified`
""",
        encoding="utf-8",
    )
    return path


def test_parse_legacy_learning_report_builds_valid_artifact(tmp_path):
    report_path = _write_legacy_report(
        tmp_path
        / "learning_reports"
        / "emma"
        / "singapore_primary_science"
        / "c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1 - Marking Report.md"
    )
    artifact, warnings = parse_legacy_learning_report(report_path)
    assert artifact.context.student_id == "emma"
    assert artifact.context.subject_context == "singapore_primary_science"
    assert artifact.summary.total_marks == 4
    assert artifact.summary.earned_marks == 3
    assert artifact.question_results[0].result_id == "Q1"
    assert artifact.question_results[1].skill_tags == ("Forces", "effects of force", "force direction")
    assert warnings == []


def test_parse_legacy_learning_report_maps_disqualified_rows_and_excludes_from_totals(tmp_path):
    report_path = _write_legacy_report_with_disqualified(
        tmp_path
        / "learning_reports"
        / "winston"
        / "singapore_primary_math"
        / "c_disqualified_attempt - Marking Report.md"
    )
    artifact, warnings = parse_legacy_learning_report(report_path)
    assert warnings == []
    assert artifact.summary.total_marks == 2
    assert artifact.summary.earned_marks == 2
    assert artifact.summary.percentage == 100.0
    assert artifact.question_results[1].result_id == "Q2"
    assert artifact.question_results[1].outcome == "disqualified"
    assert artifact.question_results[1].scoring_status == "excluded_disqualified"
    assert artifact.question_results[1].skill_tags == ()


def test_parse_legacy_learning_report_backfills_file_ids_from_paths(tmp_path, monkeypatch):
    report_path = _write_legacy_report(
        tmp_path
        / "learning_reports"
        / "emma"
        / "singapore_primary_science"
        / "c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1 - Marking Report.md"
    )

    class _FakePdfFile:
        def __init__(self, file_id: str, name: str):
            self.id = file_id
            self.name = name

    class _FakeManager:
        def get_file_by_path(self, path: str):
            mapping = {
                "/tmp/c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1.pdf": "file_attempt_123",
                "/tmp/_c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1.pdf": "file_template_456",
                "/tmp/_c_Science Thematic Tests and Exam Practice Primary 4 - 11 Answers.pdf": "file_answer_321",
            }
            file_id = mapping.get(path)
            if file_id is None:
                return None
            names = {
                "file_attempt_123": "c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1.pdf",
                "file_template_456": "_c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1.pdf",
                "file_answer_321": "_c_Science Thematic Tests and Exam Practice Primary 4 - 11 Answers.pdf",
            }
            return _FakePdfFile(file_id, names[file_id])

        def get_file(self, file_id: str):
            names = {
                "file_template_456": "_c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1.pdf",
            }
            name = names.get(file_id)
            if name is None:
                return None
            return _FakePdfFile(file_id, name)

        def get_file_group_membership(self, file_id: str):
            class _Group:
                def __init__(self, group_id: str, label: str, group_type: str):
                    self.id = group_id
                    self.label = label
                    self.group_type = group_type

            if file_id == "file_template_456":
                return [_Group("group_book_789", "Science Thematic Tests and Exam Practice Primary 4", "book")]
            return []

    monkeypatch.setattr(migrate_module, "_PDF_MANAGER", None)
    monkeypatch.setattr(migrate_module, "_PDF_MANAGER_LOADED", True)
    monkeypatch.setattr(migrate_module, "_get_pdf_file_manager", lambda: _FakeManager())

    artifact, warnings = parse_legacy_learning_report(report_path)
    assert warnings == []
    assert artifact.context.attempt_file_id == "file_attempt_123"
    assert artifact.context.template_file_id == "file_template_456"
    assert artifact.context.unit_file_id == "file_template_456"
    assert artifact.context.answer_file_id == "file_answer_321"
    assert artifact.context.unit_label == "Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1"
    assert artifact.context.book_group_id == "group_book_789"
    assert artifact.context.book_label == "Science Thematic Tests and Exam Practice Primary 4"


def test_migrate_learning_reports_dry_run_respects_filters_and_limit(tmp_path):
    reports_root = tmp_path / "learning_reports"
    _write_legacy_report(
        reports_root
        / "emma"
        / "singapore_primary_science"
        / "c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1 - Marking Report.md"
    )
    _write_legacy_report(
        reports_root
        / "winston"
        / "singapore_primary_science"
        / "c_Science Practice Primary 5 and 6 - 17 Interactions - Topical Test 1 Forces - Marking Report.md"
    )

    results = migrate_learning_reports(
        reports_root=reports_root,
        context_root=tmp_path,
        student="emma",
        subject_context="singapore_primary_science",
        limit=1,
        dry_run=True,
    )
    assert len(results) == 1
    assert results[0]["status"] == "pending"
    assert results[0]["dry_run"] is True


def test_migrate_learning_reports_writes_json_and_skips_existing(tmp_path):
    reports_root = tmp_path / "learning_reports"
    _write_legacy_report(
        reports_root
        / "emma"
        / "singapore_primary_science"
        / "c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1 - Marking Report.md"
    )

    first = migrate_learning_reports(
        reports_root=reports_root,
        context_root=tmp_path,
        dry_run=False,
    )
    assert first[0]["status"] == "written"
    written_json = Path(first[0]["output_path"])
    payload = json.loads(written_json.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "marking_result.v1"

    second = migrate_learning_reports(
        reports_root=reports_root,
        context_root=tmp_path,
        dry_run=False,
    )
    assert second[0]["status"] == "skipped_existing"


def test_derive_skill_tags_strips_markdown_link_wrapper():
    tags = derive_skill_tags_from_embedding_label(
        "[Plant systems > weak stems > support and climbing for light](/tmp/example.md#L1)"
    )
    assert tags == ("Plant systems", "weak stems", "support and climbing for light")
