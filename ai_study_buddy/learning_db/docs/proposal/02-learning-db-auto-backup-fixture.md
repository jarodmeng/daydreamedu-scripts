# Proposal 2: Add auto-backup fixture for `learning_db` database

## Status

Implemented (2026-05-06).
Decision updates (2026-05-06):
- Option B accepted — include tiering in the initial implementation.
- Keep a separate `learning_db` backup fixture for now.
- Use the same tiering defaults as `pdf_registry` for now.
- Add `--dry-run` to tiering CLI.

Operational update (2026-05-07):
- Wake shell scripts are canonical under `ai_study_buddy/utils/backup/` (`run_learning_db_wake.sh`, `install_learning_db_wake.sh`, `uninstall_learning_db_wake.sh`; combined pdf+study flow via `run_wake_all.sh`).
- Older `pdf_file_manager/scripts/*` / `learning_db/scripts/*` wake shims **removed** — after pulling, run `bash ai_study_buddy/utils/backup/migrate_wakeup_backup_paths.sh` when `~/.wakeup` still quotes legacy paths (use `--dry-run` first).

## Goal

Add an operational fixture for automatic backups of `study_buddy.db`, aligned with (and hosted alongside) the wake-backup tooling for `pdf_registry.db` under `ai_study_buddy/utils/backup/`.

The fixture should:

- run a backup when the Mac wakes from sleep,
- skip copies when the source DB is unchanged,
- append timestamped logs for auditability,
- support lightweight retention/tiering so backups do not grow unbounded.

## Motivation

`learning_db` now stores production-adjacent projection state used by marking and review workflows. Manual backup commands exist, but backup reliability currently depends on humans remembering to run them.

Wake-triggered backup uses the same machinery (`sleepwatcher` + `~/.wakeup` + LaunchAgent pattern), now centralized under `utils/backup/` for both SQLite DBs (`run_wake_all.sh` backs up both sequentially).

## Current state

- Existing one-shot CLI exists:
  - `python3 -m ai_study_buddy.learning_db.cli.backup_study_buddy_db`
- Existing behavior includes:
  - destination resolution (`STUDY_BUDDY_DB_BACKUP_DIR` or `DaydreamEdu/db`),
  - unchanged-since-last-backup skip checks,
  - optional timestamped file mode,
  - append-only backup log (`study_buddy_backup.log`).
- Missing piece (historic):
  - ~~no wake installer comparable to the pdf-registry path~~ superseded — see `ai_study_buddy/utils/backup/`.

## Proposed solution (historical checklist)

Wake scripts ultimately live under `ai_study_buddy/utils/backup/` (not `learning_db/scripts/`).

### 1) Shell scripts — canonical paths

Implemented as:

- `ai_study_buddy/utils/backup/run_learning_db_wake.sh`
- `ai_study_buddy/utils/backup/install_learning_db_wake.sh`
- `ai_study_buddy/utils/backup/uninstall_learning_db_wake.sh`

Behavior:

- `run_learning_db_wake.sh` (wake runner)
  - sets deterministic `PATH`/`PYTHONPATH` for launchd context,
  - appends logs to `~/Library/Logs/study_buddy_backup_on_wake.log`,
  - retries backup command with bounded attempts (for transient mount/sync timing),
  - runs timestamped backup:
    - `python3 -m ai_study_buddy.learning_db.cli.backup_study_buddy_db --timestamp`,
  - applies retention tiering (see section below).

- `install_learning_db_wake.sh`
  - verifies `sleepwatcher` exists,
  - appends wake hook to `~/.wakeup` (idempotent),
  - ensures `~/.sleep` exists,
  - installs user launch agent plist (dedicated label for learning DB),
  - unload/load cycle for immediate activation.

- `uninstall_learning_db_wake.sh`
  - unloads and removes plist,
  - removes fixture line from `~/.wakeup`,
  - preserves unrelated user wake hooks.

### 2) Retention/tiering strategy (selected)

Selected approach: implement Option B now so the fixture is complete and maintenance-free.

- add:
  - `ai_study_buddy/learning_db/cli/apply_backup_tiering.py`,
- policy mirrors `pdf_registry`:
  - keep raw `.db` backups in hot window (`--hot-days`, default 7),
  - move older backups to `coldstorage/` as `.zst` through `zstd`,
  - prune backups older than cold window (`--cold-days`, default 60),
  - support `--dry-run` to print planned actions without mutating files.

### 3) Naming and defaults

- launch agent label:
  - `com.daydreamedu.study-buddy-backup-on-wake`
- wake log:
  - `~/Library/Logs/study_buddy_backup_on_wake.log`
- backup event log in destination:
  - `study_buddy_backup.log` (already implemented in backup CLI)
- destination env:
  - continue using `STUDY_BUDDY_DB_BACKUP_DIR`

## Safety and idempotency requirements

- installer must be repeat-safe (no duplicate wake lines, no duplicate plist writes that break launchctl),
- wake script should fail fast on repeated errors and return non-zero after final retry,
- backup skip-when-unchanged logic remains source of truth in Python CLI,
- no destructive behavior to source DB; only copy/read operations.

## Documentation changes

Update the following after implementation:

- `ai_study_buddy/learning_db/README.md`
  - add "Auto backup on wake" section with install/uninstall commands.
- `ai_study_buddy/learning_db/OPERATIONS.md`
  - add periodic verification and troubleshooting flow.
- `ai_study_buddy/docs/L4_LOCAL_LEARNING_DB.md`
  - add cross-reference to `learning_db` auto-backup fixture.
- `ai_study_buddy/learning_db/CHANGELOG.md`
  - record feature in next release entry.

## Implementation Plan

### Phase 0 - Baseline and alignment

- **Todos (checklist)**
  - [ ] Confirm current `backup_study_buddy_db.py` behavior still matches this proposal (default destination, skip logic, timestamp mode, log file naming).
  - [ ] Confirm parity targets from `utils/backup` pdf-registry installers for wake flow and retry behavior.
  - [ ] Confirm canonical script names, launch agent label, and log paths for `learning_db`.
- **Tests/checks (checklist)**
  - [ ] `python3 -m ai_study_buddy.learning_db.cli.backup_study_buddy_db --timestamp --force --dest <tmp-dir>`
  - [ ] Run `python3 -m ai_study_buddy.learning_db.cli.backup_study_buddy_db --timestamp --dest <tmp-dir>` twice (second run should skip if unchanged)
- **Success criteria**
  - Baseline behavior is validated and no naming/path ambiguity remains before adding new scripts.

### Phase 1 - Add tiering CLI

- **Todos (checklist)**
  - [ ] Add `ai_study_buddy/learning_db/cli/apply_backup_tiering.py`.
  - [ ] Implement hot/cold retention policy (`hot-days=7`, `cold-days=60` defaults).
  - [ ] Add `--dry-run` mode that reports actions without mutating files.
  - [ ] Ensure dependency checks are explicit (`zstd` required for real compression paths).
- **Tests/checks (checklist)**
  - [ ] Run `--dry-run` on a synthetic backup directory and verify planned action output.
  - [ ] Run real mode on synthetic files and verify:
    - hot-to-cold compression occurs,
    - cold-window pruning occurs,
    - summary counters are accurate.
- **Success criteria**
  - Tiering command is deterministic, safe-by-default via `--dry-run`, and mirrors `pdf_registry` retention semantics.

### Phase 2 - Add wake runner and installer fixture

- **Todos (checklist)**
  - [x] Add `ai_study_buddy/utils/backup/run_learning_db_wake.sh`.
  - [x] Add `ai_study_buddy/utils/backup/install_learning_db_wake.sh`.
  - [x] Add `ai_study_buddy/utils/backup/uninstall_learning_db_wake.sh`.
  - [ ] Ensure wake runner uses bounded retries, invokes timestamped backup, then invokes tiering.
  - [ ] Ensure installer is idempotent for `~/.wakeup`, `~/.sleep`, and launch agent installation.
- **Tests/checks (checklist)**
  - [ ] `bash ai_study_buddy/utils/backup/install_learning_db_wake.sh`
  - [ ] `launchctl list | rg study-buddy-backup-on-wake`
  - [ ] `rg utils/backup/run_learning_db_wake ~/.wakeup` (single match when using learning-only hook)
  - [ ] `bash ai_study_buddy/utils/backup/run_learning_db_wake.sh`
  - [ ] Verify backup and logs:
    - timestamped `study_buddy_*.db` appears in backup directory,
    - `study_buddy_backup.log` appends an event,
    - `~/Library/Logs/study_buddy_backup_on_wake.log` records run lifecycle.
- **Success criteria**
  - Wake-trigger fixture is installable, repeat-safe, and executes backup+tiering reliably outside interactive shell context.

### Phase 3 - Documentation and operations updates

- **Todos (checklist)**
  - [ ] Update `ai_study_buddy/learning_db/README.md` with install/uninstall and manual run commands.
  - [ ] Update `ai_study_buddy/learning_db/OPERATIONS.md` with verification/troubleshooting and dry-run tiering examples.
  - [ ] Update `ai_study_buddy/docs/L4_LOCAL_LEARNING_DB.md` with cross-reference to this fixture.
  - [ ] Update `ai_study_buddy/learning_db/CHANGELOG.md` with the feature note.
- **Tests/checks (checklist)**
  - [ ] `rg "migrate_wakeup|install_learning_db_wake|apply_backup_tiering|utils/backup" ai_study_buddy/learning_db -g "*.md"`
  - [ ] Validate all documented commands run as written on one machine.
- **Success criteria**
  - Operational docs are complete and consistent with implemented paths/commands; no stale references remain.

### Phase 4 - Final verification and closeout

- **Todos (checklist)**
  - [ ] Execute end-to-end smoke test with install -> direct wake script run -> uninstall.
  - [ ] Confirm no regressions to existing one-shot backup CLI behavior.
  - [ ] Mark proposal status as Implemented with date and any deviations.
- **Tests/checks (checklist)**
  - [ ] `bash ai_study_buddy/utils/backup/install_learning_db_wake.sh`
  - [ ] `bash ai_study_buddy/utils/backup/run_learning_db_wake.sh`
  - [ ] `bash ai_study_buddy/utils/backup/uninstall_learning_db_wake.sh`
  - [ ] Re-run one-shot backup CLI in both normal and `--force` modes.
- **Success criteria**
  - Fixture is production-ready for local developer machines, and proposal state is fully reconciled with implementation.

## Non-goals

- Continuous background sync or daemonized backup beyond wake-triggered runs.
- Encrypting backup files at rest (delegated to destination storage policy).
- Replacing manual on-demand backup CLI.

## Resolved decisions

- Keep `learning_db` and `pdf_registry` as separate backup fixtures for now.
- Use the same tiering defaults as `pdf_registry` for now (`hot-days=7`, `cold-days=60`).
- Add `--dry-run` to `apply_backup_tiering.py`.

## References

- Combined wake fixture (recommended):
  - `ai_study_buddy/utils/backup/install_pdf_registry_wake.sh`
  - `ai_study_buddy/utils/backup/run_wake_all.sh`
- Learning-only hooks:
  - `ai_study_buddy/utils/backup/install_learning_db_wake.sh`
  - `ai_study_buddy/utils/backup/run_learning_db_wake.sh`
- Existing backup CLIs:
  - `ai_study_buddy/pdf_file_manager/scripts/backup_pdf_registry.py`
  - `ai_study_buddy/learning_db/cli/backup_study_buddy_db.py`
