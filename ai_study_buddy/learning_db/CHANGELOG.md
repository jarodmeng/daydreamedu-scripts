# Changelog

All notable changes to `ai_study_buddy.learning_db` are documented in this file.

## [0.1.7] - 2026-05-28

### Added

- New drift audit CLI: `python3 -m ai_study_buddy.learning_db.cli.context_db_drift_report`
  - Reports DB↔`context/` path consistency for marking artifacts, review states, amendments, and import identity paths.
  - Supports human-readable and `--json` output plus `--fail-on-any` for CI/preflight use.
- New missing-asset triage CLI: `python3 -m ai_study_buddy.learning_db.cli.triage_missing_marking_assets`
  - Classifies active missing `marking_asset` rows into `probable_rename_drift`, `likely_legacy_or_pruned_assets`, and `hard_inconsistency`.

### Changed

- `context_db_drift_report` now counts `marking_artifacts_missing_marking_asset` against **active rows only** (`is_deleted=0`) to avoid deleted-row noise in operational drift totals.

## [0.1.6] - 2026-05-22

### Changed

- [L4_LOCAL_LEARNING_DB.md](../docs/L4_LOCAL_LEARNING_DB.md): Phase 3 **provisional sign-off** — 660 dual-writes, 0 failures; rollback drill documented in [LEARNING_DUAL_WRITE_PHASE3.md](docs/learnings/LEARNING_DUAL_WRITE_PHASE3.md).
- `README.md`: document `dual_write_stats` CLI in Quick Commands.

## [0.1.5] - 2026-05-07

### Changed

- Wake backup for `study_buddy.db` lives only under **`ai_study_buddy/utils/backup/`** (`run_learning_db_wake.sh`, `install_learning_db_wake.sh`, `uninstall_learning_db_wake.sh`; combined pdf + study backup via **`run_wake_all.sh`** / **`install_pdf_registry_wake.sh`**).
- **`learning_db/scripts/`** wake shims (`install_run_on_wake.sh`, `run_backup_on_wake.sh`, `uninstall_run_on_wake.sh`) and that directory removed after a transitional period; installers detect only **`utils/backup`** paths.
- **`pdf_file_manager`** wake shim scripts removed the same way (see **`pdf_file_manager` CHANGELOG `[v0.3.15]`**).
- Learning-only **`install_learning_db_wake.sh`**: when `~/.wakeup` already invokes **`utils/backup/run_wake_all.sh`** and **`com.daydreamedu.pdf-registry-backup-on-wake`** is installed, skip appending another wake line and skip loading a second sleepwatcher LaunchAgent.

### Added

- **`migrate_wakeup_backup_paths.py`** and **`migrate_wakeup_backup_paths.sh`** — rewrite **`~/.wakeup`** lines from old shim paths (`pdf_file_manager/scripts/run_backup_on_wake.sh`, **`learning_db/scripts/run_backup_on_wake.sh`**) to canonical **`utils/backup`** scripts; drop redundant **`run_learning_db_wake.sh`** when **`run_wake_all.sh`** is present.

## [0.1.4] - 2026-05-06

Patch: module documentation (`SPEC.md`, `ARCHITECTURE.md`) and README version line.

### Added

- `SPEC.md` — scope, contracts, environment variables, and operational expectations.
- `ARCHITECTURE.md` — layers (`context/` vs `study_buddy.db`), batch vs dual-write pipelines, package layout, and design rules.

### Changed

- `README.md`:
  - **Current version** `0.1.4`
  - Related Docs lists `SPEC.md` and `ARCHITECTURE.md` with short descriptions.

## [0.1.3] - 2026-05-06

Patch: add wake-triggered backup fixture and retention tiering for `study_buddy.db`.

### Added

- New tiering CLI:
  - `python3 -m ai_study_buddy.learning_db.cli.apply_backup_tiering`
  - supports `--hot-days`/`--cold-days` and `--dry-run`
- Wake automation scripts under **`learning_db/scripts/`** (`run_backup_on_wake.sh`, `install_run_on_wake.sh`, `uninstall_run_on_wake.sh`); **canonical paths and migration** summarized under **[0.1.5]**.

### Changed

- `README.md`:
  - adds auto-backup-on-wake usage and backup/tiering commands
- `OPERATIONS.md`:
  - adds backup, tiering, and wake fixture install/verify runbook
- `docs/L4_LOCAL_LEARNING_DB.md`:
  - adds implementation update note for learning DB auto backup fixture

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
