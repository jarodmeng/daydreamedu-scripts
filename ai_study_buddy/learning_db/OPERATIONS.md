# Operations Runbook

## 1) Apply Migrations

```bash
python3 -m ai_study_buddy.learning_db.core.migrate
```

## 2) Backfill Imports

### Full backfill

```bash
python3 -m ai_study_buddy.learning_db.ingest.import_context_json
```

### Family-specific backfill (`file_question_info`)

```bash
python3 -m ai_study_buddy.learning_db.ingest.import_context_json --artifact-family file_question_info
```

Expected summary shape:

- `scanned=<n> imported=<n|0> updated=<0|n> quarantined=<0|k> resolved=<...>`

## 3) Verify DB Counts

Use sqlite or Python to run:

```sql
SELECT COUNT(*) FROM file_question_info_runs;
SELECT COUNT(*) FROM file_question_info_sections;
SELECT COUNT(*) FROM file_question_info_items;
```

## 4) Quarantine Checks

```sql
SELECT COUNT(*)
FROM import_quarantine
WHERE artifact_family='file_question_info' AND status='open';

SELECT error_code, COUNT(*)
FROM import_quarantine
WHERE artifact_family='file_question_info'
GROUP BY error_code
ORDER BY COUNT(*) DESC;
```

## 5) Retry Quarantine

```bash
python3 -m ai_study_buddy.learning_db.ingest.import_context_json \
  --artifact-family file_question_info \
  --retry-quarantine --status open
```

Optional stage filter:

```bash
python3 -m ai_study_buddy.learning_db.ingest.import_context_json \
  --artifact-family file_question_info \
  --retry-quarantine --status open --failure-stage schema_validate
```

## 6) Dual-write Runtime Behavior

Dual-write is controlled by env toggles:

- `LEARNING_DB_ENABLE_DUAL_WRITE`
- `LEARNING_DB_STRICT_DUAL_WRITE`

When strict mode is true, dual-write failures raise to caller and may roll back/remove JSON snapshot depending on entrypoint semantics in `dual_write.py`.

## 7) file_question_info Runtime Hook

Detectors should call shared finalizer after writing `question_sections.json`:

```python
from pathlib import Path
from ai_study_buddy.marking.file_question_info import finalize_question_sections_snapshot

finalize_question_sections_snapshot(
    snapshot_path=Path("<run_folder>/question_sections.json"),
    context_root=Path("ai_study_buddy/context"),
)
```

This enforces validation and triggers DB mirror write.

## 8) Backup and Retention

### One-shot backup

```bash
python3 -m ai_study_buddy.learning_db.cli.backup_study_buddy_db --timestamp
```

Notes:

- skips if source DB is unchanged (unless `--force` is passed)
- destination is `STUDY_BUDDY_DB_BACKUP_DIR` or `<DaydreamEdu root>/db`
- writes events to `study_buddy_backup.log` in backup destination

### Tiering retention (hot/cold)

Dry-run first:

```bash
python3 -m ai_study_buddy.learning_db.cli.apply_backup_tiering --dry-run
```

Apply:

```bash
python3 -m ai_study_buddy.learning_db.cli.apply_backup_tiering --hot-days 7 --cold-days 60
```

Behavior:

- keep fresh `study_buddy_*.db` backups in hot tier
- compress older backups to `coldstorage/*.zst`
- prune backups older than `cold-days`

### Auto backup on wake (sleepwatcher fixture)

Install:

```bash
bash ai_study_buddy/utils/backup/install_learning_db_wake.sh
```

Uninstall:

```bash
bash ai_study_buddy/utils/backup/uninstall_learning_db_wake.sh
```

Verification:

```bash
launchctl list | rg study-buddy-backup-on-wake
rg -E 'utils/backup/run_(wake_all|learning_db_wake)' ~/.wakeup
```

Prefer one combined hook: run `bash ai_study_buddy/utils/backup/install_pdf_registry_wake.sh` so `~/.wakeup` runs `run_wake_all.sh`; then the learning-db–only installer usually skips (`~/.wakeup` already covered).
