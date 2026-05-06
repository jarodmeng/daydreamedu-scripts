# Changelog

All notable changes to `ai_study_buddy.learning_db` are documented in this file.

## [0.1.2] - 2026-05-06

Patch: strict cleanup of `learning_db` package layout with full internal migration to submodule paths.

### Changed

- Package structure:
  - added implementation subpackages: `core/`, `read/`, `ingest/`, `cli/`
  - moved implementation modules from package root into those subpackages
- Strict cleanup:
  - removed legacy root module files after migrating internal imports/tests/docs to subpackages
  - package root now keeps only `__init__.py` plus docs/directories
- Migration runner:
  - updated `core/migrate.py` to resolve SQL files from package-level `migrations/` after relocation

### Validation

- `PYTHONPATH=. python3 -m pytest ai_study_buddy/learning_db/tests` (31 passed)
- `PYTHONPATH=. python3 -m pytest ai_study_buddy/marking/tests/test_artifact_core.py ai_study_buddy/marking/tests/test_file_question_info.py` (77 passed)
- submodule entrypoint smoke checks:
  - `python3 -m ai_study_buddy.learning_db.core.migrate --help`
  - `python3 -m ai_study_buddy.learning_db.ingest.import_context_json --help`
  - `python3 -m ai_study_buddy.learning_db.cli.validate_study_buddy_db --help`

## [0.1.1] - 2026-05-05

Patch: operationalized `file_question_info` persistence rollout and documented the `learning_db` module.

### Added

- Documentation suite:
  - `README.md`
  - `SCHEMA.md`
  - `OPERATIONS.md`
  - `CHANGELOG.md`
- Migration `002_file_question_info.sql`:
  - adds `file_question_info_runs`, `file_question_info_sections`, `file_question_info_items`
  - extends `import_identity_map` and `import_quarantine` family checks with `file_question_info`

### Changed

- `import_context_json.py`:
  - adds `upsert_file_question_info_run(...)`
  - supports importing `file_question_info` family
  - adds `file_question_info` quarantine/error-code routing
- `dual_write.py`:
  - adds `family="file_question_info"` projection path

### Data Rollout

- `file_question_info` corpus imported into `study_buddy.db`:
  - scanned/imported: `23/23`
  - runs: `23`
  - sections: `105`
  - items: `760`
  - quarantine open/total: `0/0`

## [0.1.0] - 2026-04-29

Initial `learning_db` module baseline (pre-`file_question_info` family), including migration/import/dual-write foundations for marking and review artifacts.

### Added

- Migration system and base schema:
  - `migrate.py`
  - `migrations/001_initial_schema.sql`
- Core DB plumbing:
  - `connection.py` (default DB/context paths + SQLite connection helpers)
  - `config.py` (runtime toggles for reads/dual-write/json-export)
- Import pipeline:
  - `import_context_json.py` for:
    - `marking_result`
    - `marking_amendment`
    - `student_review_state`
  - identity mapping and idempotency via `import_identity_map`
  - quarantine workflow via `import_quarantine`
  - operation logging via `operation_log`
- Dual-write pipeline:
  - `dual_write.py` support for:
    - `marking_result`
    - `marking_amendment`
    - `student_review_state`
- Read/validation/ops helpers:
  - `read_marking.py`
  - `read_documents.py`
  - `validate_study_buddy_db.py`
  - `write_boundary_audit.py`
  - `dual_write_stats.py`
  - `reader_parity.py`
  - `field_coverage.py`

### Tests

- Baseline automated coverage for migrations/import/idempotency/scope/dual-write semantics and parity checks under `learning_db/tests/`.
