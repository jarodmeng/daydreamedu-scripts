# AI Study Buddy Marking Package

Canonical marking pipeline for AI Study Buddy. This package defines the
`marking_result.v1.6` artifact contract and the JSON-first workflow:

1. resolve context
2. write canonical JSON artifact
3. render markdown as a derived view
4. support human note edits in the canonical JSON

Current version: `v0.3.10`

## Package Scope

- Artifact naming and path conventions (`artifact_paths.py`)
- Marking asset bundle paths/layout validation helpers (`assets/`)
- Singapore marking clock (`core/marking_time.py`: persisted timestamps and basename suffix use SGT)
- Schema validation and score consistency checks (`artifact_schema.py`)
- Canonical artifact writing (`artifact_writer.py`)
- Partial-marking scope inference helper (`core/partial_marking.py`)
- Path privacy sanitization and placeholder resolution (`path_privacy.py`)
- Completion->artifact lookup helper (`artifact_lookup.py`)
- Run-level artifact removal helper (`artifact_cleanup.py`)
- Legacy markdown migration (`migrate_learning_reports.py`)
- Markdown rendering from canonical JSON (`report_renderer.py`)
- Human note editing workflow (`edit_human_notes.py`)
- Marking taxonomy constants/helpers (`taxonomy.py`)
- Review-domain backend services for marked-attempt review workflows (`review/`)
- File-question-info helpers for deterministic `context/file_question_info/...` run folders, page renders, and `question_sections.json` validation (`file_question_info/`)
- Completion registry audit exclusions for GoodNotes Science revision guide book folders (`core/completion_registry_audit.py`; see `../docs/notes/completion_files_registry_audit.md`)

## Multiple attempts per template (`v0.2.3+`)

Normative completion ↔ marking identity (one run per `file_id`, `attempt_sequence` intent): [L4_COMPLETION_MARKING_FRAMEWORK](../docs/L4_COMPLETION_MARKING_FRAMEWORK.md).

Canonical artifacts now support multiple attempts for the same student/template pair via context fields:

- `template_attempt_group_id` (deterministic group id)
- `attempt_sequence` (1-based ordering inside the group)
- `attempt_label` (optional free-text label)

Writer behavior:

- `write_marking_artifact(...)` emits `schema_version = marking_result.v1.6`.
- When `template_file_id` is present, the writer sets `template_attempt_group_id` and `attempt_sequence` from **`PdfFileManager` completion series** (`completion_series_id`, `next_attempt_sequence_for_completion`) — not from a scan of prior marking JSONs. Re-mark on the same completion `file_id` keeps the same sequence.
- **Backfill (registry):** `python3 -m ai_study_buddy.marking.workflows.backfill_attempt_sequence_from_registry --dry-run`
- Learning report rendering shows `Attempt #<n>` when `attempt_sequence` is present.

Example `context` snippet:

```json
{
  "template_file_id": "689c5325-8d60-4da4-b00b-99eb26ecec9e",
  "template_attempt_group_id": "winston::689c5325-8d60-4da4-b00b-99eb26ecec9e",
  "attempt_sequence": 2,
  "attempt_label": "retake"
}
```

## Question-to-attempt-page mapping (`v0.2.9+`)

Canonical artifacts now include question page anchors in `context.question_page_map`:

- required in `marking_result.v1.6` (may be empty array)
- one entry per mapped `question_results[].result_id`
- includes:
  - `result_id`
  - `attempt_page_start` (int >= 1)
  - `confidence` (`high|medium|low`)
  - `source` (`manual_visual|ai_visual_backfill|script_inferred`)
  - optional `evidence_image`, optional `note`

Example `context` snippet:

```json
{
  "question_page_map": [
    {
      "result_id": "Q1",
      "attempt_page_start": 1,
      "confidence": "high",
      "source": "manual_visual",
      "evidence_image": "attempt/page-01.png",
      "note": null
    }
  ]
}
```

## Directory Layout

- `api.py`: compact public API re-export surface
- `core/`: models, schema, paths, writer, taxonomy, context resolution
- `file_question_info/`: helpers for detector `question_sections.json` artifacts (run-folder resolution, rasterization, load/validate, CLI validator)
- `workflows/`: CLI/workflow modules for migration, rendering, and note editing
- `ai_study_buddy/schemas/marking/marking_result.v1.6.schema.json`: canonical JSON schema for `marking_result.v1.6` (strict, closed contract)
- `ai_study_buddy/schemas/marking/marking_amendment.v1.schema.json`: companion amendment overlay schema contract (`marking_amendment.v1`)
- `review/`: review-domain APIs/services (attempt list/detail shaping, review-state and amendment writes)
- `tests/test_artifact_core.py`: core artifact and rendering tests
- `tests/test_migration.py`: migration parser and migration flow tests

Per-run renders, answer crops, and disposable `_mark_*.py` / `_render_*.py` helpers live under the standardized bundle root in `context.marking_asset` (for example `ai_study_buddy/context/marking_assets/<student>/<subject>/<artifact_stem>/`), not in this package root.

## File Question Info Helpers (`v0.3.2+`)

Detectors for Chinese/English/Higher Chinese/Math/Science write `question_sections.json` under:

`ai_study_buddy/context/file_question_info/<subject_scope>/<grade>/<slug>/question_sections.json`

with corresponding rendered pages under:

`ai_study_buddy/context/file_question_info/<subject_scope>/<grade>/<slug>/rendered_pages/page_%03d.png`

The canonical structural validator (used by detector agents as a terminal gate) is:

```bash
python3 -m ai_study_buddy.marking.file_question_info.validate <run_folder>/question_sections.json
```

Detector post-write workflows now use a shared finalizer hook to enforce
validation and dual-write mirroring:

```python
from pathlib import Path
from ai_study_buddy.marking import finalize_question_sections_snapshot

finalize_question_sections_snapshot(
    snapshot_path=Path("<run_folder>/question_sections.json"),
    context_root=Path("ai_study_buddy/context"),
)
```

Reader/consumer helpers for v3 readiness:

```python
from ai_study_buddy.marking.file_question_info import (
    get_latest_question_sections_for_file_id,
    iter_sections_ordered,
    iter_questions_ordered,
    question_page_map_from_question_sections,
    section_hint_strings_for_context,
)

source = get_latest_question_sections_for_file_id(template_file_id)
payload = source["payload"]  # runtime-validated when require_valid=True (default)
sections = iter_sections_ordered(payload)
questions = iter_questions_ordered(payload)
page_map_rows = list(question_page_map_from_question_sections(payload).values())
section_hints = section_hint_strings_for_context(payload)
```

READ-flag behavior for lookup helpers:

- `LEARNING_DB_ENABLE_READS=1` (default): prefer DB-backed lookup.
- `LEARNING_DB_READ_FALLBACK_FILESYSTEM=1`: allow filesystem fallback on DB miss.
- Divergence guard (default `detect_divergence=True`): when DB and filesystem artifacts both exist and differ for the same file, lookup raises `QuestionSectionsLookupError`.

## Quick Start

From repository root:

```bash
# Migrate legacy markdown reports to canonical JSON artifacts
python3 -m ai_study_buddy.marking.workflows.migrate_learning_reports --dry-run

# Backfill v1.1 attempt metadata (group id / sequence / label=null)
python3 -m ai_study_buddy.marking.workflows.backfill_attempt_metadata_v1_1 --dry-run

# Backfill v1.3 partial-marking metadata and re-render reports
python3 -m ai_study_buddy.marking.workflows.backfill_is_partial_v1_3 --dry-run

# Render markdown from an existing canonical artifact
python3 -m ai_study_buddy.marking.workflows.report_renderer \
  ai_study_buddy/context/marking_results/<student>/<subject>/<artifact>.json

# Validate marking asset bundle for one artifact
python3 -m ai_study_buddy.marking.workflows.validate_bundle \
  ai_study_buddy/context/marking_results/<student>/<subject>/<artifact>.json \
  --strict

# Remove one marking run's artifacts (JSON + report + bundle)
python3 -m ai_study_buddy.marking.workflows.remove_run_artifacts \
  ai_study_buddy/context/marking_results/<student>/<subject>/<artifact>.json \
  --dry-run

# Render attempt pages to standardized MAB naming under attempt/page-{nn}.png
python3 - <<'PY'
from ai_study_buddy.marking import render_attempt_pdf_to_bundle
render_attempt_pdf_to_bundle(
    "path/to/attempt.pdf",
    "ai_study_buddy/context/marking_assets/<student>/<subject>/<artifact_stem>",
)
PY

# Update human notes in a canonical artifact
python3 -m ai_study_buddy.marking.workflows.edit_human_notes \
  ai_study_buddy/context/marking_results/<student>/<subject>/<artifact>.json \
  --summary-note "Reviewed with parent" \
  --updated-by "tutor"
```

## Marking timestamps (Singapore)

Persisted `created_at` / `updated_at` use **Singapore civil time** with a **`+08:00` ISO offset**. When constructing artifacts in code, prefer:

```python
from ai_study_buddy.marking import now_marking_iso

created_at = updated_at = now_marking_iso()
```

`write_marking_artifact` still accepts UTC (`Z`) or other offsets and **normalizes to SGT** before writing. The `__YYYYMMDD_HHMMSS` file suffix is the **SGT wall-clock** time for that instant.

## Resolver-Only Context Contract (`v0.2.16+`)

- Canonical `marking_result` writes are resolver-only:
  - resolve context via `resolve_marking_context(...)`
  - pass resolver-produced context into `MarkingArtifact`
  - write via `write_marking_artifact(...)`
- Manual context assembly is unsupported for canonical writes.
- Writer enforcement is fail-closed and unconditional:
  - `context.context_resolution` is required
  - `context.context_resolution.method` must be `resolve_marking_context`
  - `context.context_resolution.mode` must be one of:
    - `standard_mapped_answer`
    - `embedded_answer_override`
    - `teacher_annotated`
  - `context.unit_label` must be a non-empty string.
- Backward compatibility note:
  - readers/parsers remain backward-compatible for legacy `marking_result.v1.5` artifacts,
  - new writes default to `marking_result.v1.6`.

## Ink color interpretation policy

Default visual-marking interpretation (unless a workflow says otherwise):

- blue/black ink: student's original answers/workings; gradable
- red ink: correctness/correction marks, deductions, tally marks; non-gradable
- green ink: student corrections; non-gradable by default
- purple ink: parent remarks/notes/general learnings; non-gradable

For scoring, use only blue/black student writing (plus printed question text). Treat red/green/purple as auxiliary annotations outside default scoring scope.

## Diagnosis text localization in markdown reports

When rendering markdown learning reports, diagnosis cells are subject-aware:

- Chinese / Higher Chinese subjects render mistake-type labels in Chinese (for example, `概念不清`).
- Other subjects keep the default `mistake_type: reasoning` format.
- If only reasoning is present, the renderer outputs reasoning text directly.

## Path Privacy Behavior (`v0.1.2+`)

- Canonical JSON remains the source of truth, but path fields are now persisted in a PII-safe form.
- During artifact write, context path fields are sanitized:
  - GoodNotes absolute prefix -> `GOODNOTES_ROOT`
  - DaydreamEdu absolute prefix -> `DAYDREAMEDU_ROOT`
  - email segments -> `<student_email>`
- During markdown render, placeholders are resolved back when possible:
  - roots are resolved from env/config via `ai_study_buddy.files.roots`
  - `<student_email>` is resolved from `context.student_id` via `PdfFileManager`
- If resolution data is unavailable, placeholders are preserved (render still succeeds).

## Context Resolver Usage

Path-first resolver entry point:

```python
from ai_study_buddy.marking import resolve_marking_context
```

Standard mapped-answer flow (already registered + linked + mapped):

```python
context = resolve_marking_context(
    attempt_file_id_or_path="/abs/path/to/GoodNotes/.../c_unit_attempt.pdf",
)
```

First-touch onboarding flow (auto-register + auto-link):

```python
context = resolve_marking_context(
    attempt_file_id_or_path="/abs/path/to/GoodNotes/.../c_unit_attempt.pdf",
    auto_register_attempt=True,
    auto_link_template=True,
)
```

Embedded-answer flow (weighted assessment papers with answer pages in the same paper):

```python
context = resolve_marking_context(
    attempt_file_id_or_path="/abs/path/to/GoodNotes/.../c_weighted_assessment.pdf",
    auto_register_attempt=True,
    auto_link_template=True,
    self_answer_pages=(9, 10),
)
```

Artifact lookup by completion (JSON-only default, optionally require report file):

```python
from ai_study_buddy.marking import find_marking_artifacts_for_attempt

# Default: json_only
refs = find_marking_artifacts_for_attempt(
    "attempt_file_id_here",
    manager=manager,
)

# Require both JSON + derived markdown report to exist
refs_with_report = find_marking_artifacts_for_attempt(
    "attempt_file_id_here",
    match_condition="json_and_report",
    manager=manager,
)
```

## Documentation Index

- `ARCHITECTURE.md`: package architecture, context resolver contract, and implementation plan
- `CHANGELOG.md`: package release history
- `SPEC.md`: functional and data contract specification
- `TESTING.md`: test strategy, commands, and quality gates
