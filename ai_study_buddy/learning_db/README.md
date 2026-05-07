# AI Study Buddy Learning DB

SQLite projection layer for AI Study Buddy canonical JSON artifacts under `ai_study_buddy/context/`.

Current version: `0.1.5`

## Scope

`learning_db` provides:

- schema migrations (`core.migrate`, `migrations/*.sql`)
- JSON-to-SQLite import/backfill (`ingest.import_context_json`)
- runtime dual-write mirror (`ingest.dual_write`)
- quarantine + operation logging (`core.repository`)
- read helpers and validation utilities
- backup and retention tooling (`cli.backup_study_buddy_db`, `cli.apply_backup_tiering`)

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
python3 -m ai_study_buddy.learning_db.core.migrate

# import all families from context/
python3 -m ai_study_buddy.learning_db.ingest.import_context_json

# import one family only (example: file_question_info)
python3 -m ai_study_buddy.learning_db.ingest.import_context_json --artifact-family file_question_info

# retry quarantine entries only
python3 -m ai_study_buddy.learning_db.ingest.import_context_json \
  --artifact-family file_question_info \
  --retry-quarantine --status open

# one-shot DB backup (skips if unchanged)
python3 -m ai_study_buddy.learning_db.cli.backup_study_buddy_db --timestamp

# retention tiering (use --dry-run first)
python3 -m ai_study_buddy.learning_db.cli.apply_backup_tiering --dry-run

# install wake-triggered auto-backup fixture (learning-only; combined install is install_pdf_registry_wake.sh)
bash ai_study_buddy/utils/backup/install_learning_db_wake.sh
```

## Auto Backup on Wake

Wake backup shell lives beside other shared utilities:

- installers/runners/uninstaller: `ai_study_buddy/utils/backup/install_learning_db_wake.sh`, `run_learning_db_wake.sh`, `uninstall_learning_db_wake.sh`
- upgrade `~/.wakeup`: `bash ai_study_buddy/utils/backup/migrate_wakeup_backup_paths.sh` (`--dry-run` first)

Behavior:

- on wake, run `backup_study_buddy_db --timestamp` with retries
- skip when source DB is unchanged
- apply retention tiering (`hot-days=7`, `cold-days=60`)
- write wake logs to `~/Library/Logs/study_buddy_backup_on_wake.log`

Combined wake flow: `ai_study_buddy/utils/backup/run_wake_all.sh` invokes `run_pdf_registry_wake.sh` then `run_learning_db_wake.sh`. Installs driven by `install_pdf_registry_wake.sh` quote `run_wake_all.sh` in `~/.wakeup`.

Backup destination is controlled by `STUDY_BUDDY_DB_BACKUP_DIR` (default: `<DaydreamEdu root>/db`).

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

- `SPEC.md` — scope, contracts, env toggles, operational expectations
- `ARCHITECTURE.md` — layers, write pipelines, package layout
- `CHANGELOG.md`
- `SCHEMA.md`
- `OPERATIONS.md`
- `docs/learnings/`
