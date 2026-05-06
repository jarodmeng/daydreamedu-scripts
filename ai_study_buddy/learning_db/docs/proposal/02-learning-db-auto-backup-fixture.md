# Proposal 2: Add auto-backup fixture for `learning_db` database

## Status

Implemented (2026-05-06).
Decision updates (2026-05-06):
- Option B accepted — include tiering in the initial implementation.
- Keep a separate `learning_db` backup fixture for now.
- Use the same tiering defaults as `pdf_registry` for now.
- Add `--dry-run` to tiering CLI.

## Goal

Add an operational fixture for automatic backups of `study_buddy.db`, similar to the existing `pdf_file_manager/scripts` wake-backup setup for `pdf_registry.db`.

The fixture should:

- run a backup when the Mac wakes from sleep,
- skip copies when the source DB is unchanged,
- append timestamped logs for auditability,
- support lightweight retention/tiering so backups do not grow unbounded.

## Motivation

`learning_db` now stores production-adjacent projection state used by marking and review workflows. Manual backup commands exist, but backup reliability currently depends on humans remembering to run them.

The `pdf_file_manager` package already uses a practical wake-triggered mechanism (`sleepwatcher` + `~/.wakeup` + user launch agent) that has proven low-friction. Reusing that pattern for `study_buddy.db` lowers operational risk and avoids inventing a second operational model.

## Current state

- Existing one-shot CLI exists:
  - `python3 -m ai_study_buddy.learning_db.cli.backup_study_buddy_db`
- Existing behavior includes:
  - destination resolution (`STUDY_BUDDY_DB_BACKUP_DIR` or `DaydreamEdu/db`),
  - unchanged-since-last-backup skip checks,
  - optional timestamped file mode,
  - append-only backup log (`study_buddy_backup.log`).
- Missing piece:
  - no native auto-trigger fixture comparable to `pdf_file_manager/scripts/install_run_on_wake.sh`.

## Proposed solution

Create a small script fixture under `learning_db/scripts/` that mirrors the established `pdf_file_manager/scripts/` setup.

### 1) New scripts

Add:

- `ai_study_buddy/learning_db/scripts/run_backup_on_wake.sh`
- `ai_study_buddy/learning_db/scripts/install_run_on_wake.sh`
- `ai_study_buddy/learning_db/scripts/uninstall_run_on_wake.sh`

Behavior:

- `run_backup_on_wake.sh`
  - sets deterministic `PATH`/`PYTHONPATH` for launchd context,
  - appends logs to `~/Library/Logs/study_buddy_backup_on_wake.log`,
  - retries backup command with bounded attempts (for transient mount/sync timing),
  - runs timestamped backup:
    - `python3 -m ai_study_buddy.learning_db.cli.backup_study_buddy_db --timestamp`,
  - applies retention tiering (see section below).

- `install_run_on_wake.sh`
  - verifies `sleepwatcher` exists,
  - appends wake hook to `~/.wakeup` (idempotent),
  - ensures `~/.sleep` exists,
  - installs user launch agent plist (dedicated label for learning DB),
  - unload/load cycle for immediate activation.

- `uninstall_run_on_wake.sh`
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
  - [ ] Confirm parity targets from `pdf_file_manager/scripts` for installer/wake flow and retry behavior.
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
  - [ ] Add `ai_study_buddy/learning_db/scripts/run_backup_on_wake.sh`.
  - [ ] Add `ai_study_buddy/learning_db/scripts/install_run_on_wake.sh`.
  - [ ] Add `ai_study_buddy/learning_db/scripts/uninstall_run_on_wake.sh`.
  - [ ] Ensure wake runner uses bounded retries, invokes timestamped backup, then invokes tiering.
  - [ ] Ensure installer is idempotent for `~/.wakeup`, `~/.sleep`, and launch agent installation.
- **Tests/checks (checklist)**
  - [ ] `bash ai_study_buddy/learning_db/scripts/install_run_on_wake.sh`
  - [ ] `launchctl list | rg study-buddy-backup-on-wake`
  - [ ] `rg "learning_db/scripts/run_backup_on_wake.sh" ~/.wakeup` (single match)
  - [ ] `bash ai_study_buddy/learning_db/scripts/run_backup_on_wake.sh`
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
  - [ ] `rg "run_backup_on_wake|install_run_on_wake|apply_backup_tiering" ai_study_buddy/learning_db -g "*.md"`
  - [ ] Validate all documented commands run as written on one machine.
- **Success criteria**
  - Operational docs are complete and consistent with implemented paths/commands; no stale references remain.

### Phase 4 - Final verification and closeout

- **Todos (checklist)**
  - [ ] Execute end-to-end smoke test with install -> direct wake script run -> uninstall.
  - [ ] Confirm no regressions to existing one-shot backup CLI behavior.
  - [ ] Mark proposal status as Implemented with date and any deviations.
- **Tests/checks (checklist)**
  - [ ] `bash ai_study_buddy/learning_db/scripts/install_run_on_wake.sh`
  - [ ] `bash ai_study_buddy/learning_db/scripts/run_backup_on_wake.sh`
  - [ ] `bash ai_study_buddy/learning_db/scripts/uninstall_run_on_wake.sh`
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

- Existing wake fixture scripts:
  - `ai_study_buddy/pdf_file_manager/scripts/install_run_on_wake.sh`
  - `ai_study_buddy/pdf_file_manager/scripts/run_backup_on_wake.sh`
- Existing backup CLIs:
  - `ai_study_buddy/pdf_file_manager/scripts/backup_pdf_registry.py`
  - `ai_study_buddy/learning_db/cli/backup_study_buddy_db.py`
