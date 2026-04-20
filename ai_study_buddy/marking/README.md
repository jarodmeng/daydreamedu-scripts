# AI Study Buddy Marking Package

Canonical marking pipeline for AI Study Buddy. This package defines the
`marking_result.v1.1` artifact contract and the JSON-first workflow:

1. resolve context
2. write canonical JSON artifact
3. render markdown as a derived view
4. support human note edits in the canonical JSON

Current version: `v0.2.3`

## Package Scope

- Artifact naming and path conventions (`artifact_paths.py`)
- Singapore marking clock (`core/marking_time.py`: persisted timestamps and basename suffix use SGT)
- Schema validation and score consistency checks (`artifact_schema.py`)
- Canonical artifact writing (`artifact_writer.py`)
- Path privacy sanitization and placeholder resolution (`path_privacy.py`)
- Completion->artifact lookup helper (`artifact_lookup.py`)
- Legacy markdown migration (`migrate_learning_reports.py`)
- Markdown rendering from canonical JSON (`report_renderer.py`)
- Human note editing workflow (`edit_human_notes.py`)
- Marking taxonomy constants/helpers (`taxonomy.py`)

## Multiple attempts per template (`v0.2.3+`)

Canonical artifacts now support multiple attempts for the same student/template pair via context fields:

- `template_attempt_group_id` (deterministic group id)
- `attempt_sequence` (1-based ordering inside the group)
- `attempt_label` (optional free-text label)

Writer behavior:

- `write_marking_artifact(...)` emits `schema_version = marking_result.v1.1`.
- When `template_file_id` is present, the writer auto-populates group/sequence metadata.
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

## Directory Layout

- `api.py`: compact public API re-export surface
- `core/`: models, schema, paths, writer, taxonomy, context resolution
- `workflows/`: CLI/workflow modules for migration, rendering, and note editing
- `schemas/marking_result.v1.schema.json`: canonical JSON schema (`v1` and `v1.1` accepted; writer emits `v1.1`)
- `tests/test_artifact_core.py`: core artifact and rendering tests
- `tests/test_migration.py`: migration parser and migration flow tests

Per-run renders, answer crops, and disposable `_mark_*.py` / `_render_*.py` helpers live under `ai_study_buddy/context/.marking_scratch/<scratch_slug>/` (see `.cursor/skills/mark-goodnote-completion/SKILL.md`), not in this package root.

## Quick Start

From repository root:

```bash
# Migrate legacy markdown reports to canonical JSON artifacts
python3 -m ai_study_buddy.marking.workflows.migrate_learning_reports --dry-run

# Backfill v1.1 attempt metadata (group id / sequence / label=null)
python3 -m ai_study_buddy.marking.workflows.backfill_attempt_metadata_v1_1 --dry-run

# Render markdown from an existing canonical artifact
python3 -m ai_study_buddy.marking.workflows.report_renderer \
  ai_study_buddy/context/marking_results/<student>/<subject>/<artifact>.json

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

## Ink color interpretation policy

Default visual-marking interpretation (unless a workflow says otherwise):

- blue/black ink: student's original answers/workings; gradable
- red ink: correctness/correction marks, deductions, tally marks; non-gradable
- green ink: student corrections; non-gradable by default
- purple ink: parent remarks/notes/general learnings; non-gradable

For scoring, use only blue/black student writing (plus printed question text). Treat red/green/purple as auxiliary annotations outside default scoring scope.

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
