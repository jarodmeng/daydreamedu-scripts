# Operations Runbook

## 1) Apply Migrations

```bash
python3 -m ai_study_buddy.learning_db.migrate
```

## 2) Backfill Imports

### Full backfill

```bash
python3 -m ai_study_buddy.learning_db.import_context_json
```

### Family-specific backfill (`file_question_info`)

```bash
python3 -m ai_study_buddy.learning_db.import_context_json --artifact-family file_question_info
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
python3 -m ai_study_buddy.learning_db.import_context_json \
  --artifact-family file_question_info \
  --retry-quarantine --status open
```

Optional stage filter:

```bash
python3 -m ai_study_buddy.learning_db.import_context_json \
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
