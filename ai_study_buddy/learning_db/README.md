# AI Study Buddy Learning DB

SQLite projection layer for AI Study Buddy canonical JSON artifacts under `ai_study_buddy/context/`.

## Scope

`learning_db` provides:

- schema migrations (`migrate.py`, `migrations/*.sql`)
- JSON-to-SQLite import/backfill (`import_context_json.py`)
- runtime dual-write mirror (`dual_write.py`)
- quarantine + operation logging (`repository.py`)
- read helpers and validation utilities

Canonical JSON files remain source-of-truth. `study_buddy.db` is a queryable mirror.

## Current Coverage

Artifact families currently supported:

- `marking_result`
- `marking_amendment`
- `student_review_state`
- `file_question_info`

## Paths and Environment

Defaults (unless overridden):

- DB path: `ai_study_buddy/db/study_buddy.db`
- context root: `ai_study_buddy/context`

Environment variables:

- `STUDY_BUDDY_DB_PATH`
- `STUDY_BUDDY_CONTEXT_ROOT`
- `LEARNING_DB_ENABLE_DUAL_WRITE` (default: true)
- `LEARNING_DB_STRICT_DUAL_WRITE` (default: false)
- `LEARNING_DB_ENABLE_JSON_EXPORT` (default: true)
- `LEARNING_DB_ENABLE_READS` (default: true)
- `LEARNING_DB_READ_FALLBACK_FILESYSTEM` (default: false)

## Quick Commands

From repo root:

```bash
# apply pending migrations
python3 -m ai_study_buddy.learning_db.migrate

# import all families from context/
python3 -m ai_study_buddy.learning_db.import_context_json

# import one family only (example: file_question_info)
python3 -m ai_study_buddy.learning_db.import_context_json --artifact-family file_question_info

# retry quarantine entries only
python3 -m ai_study_buddy.learning_db.import_context_json \
  --artifact-family file_question_info \
  --retry-quarantine --status open
```

## file_question_info Notes

For `file_question_info` imports:

- importer scans `context/file_question_info/**/question_sections.json`
- payloads are validated via `marking.file_question_info.validate_question_sections_dict`
- latest detector schemas require run-level `created_at` and `updated_at`
- importer writes into:
  - `file_question_info_runs`
  - `file_question_info_sections`
  - `file_question_info_items`

Runtime detector workflows should call the shared post-write helper:

```python
from pathlib import Path
from ai_study_buddy.marking.file_question_info import finalize_question_sections_snapshot

finalize_question_sections_snapshot(
    snapshot_path=Path("<run_folder>/question_sections.json"),
    context_root=Path("ai_study_buddy/context"),
)
```

## Related Docs

- `CHANGELOG.md`
- `SCHEMA.md`
- `OPERATIONS.md`
- `docs/learnings/`
