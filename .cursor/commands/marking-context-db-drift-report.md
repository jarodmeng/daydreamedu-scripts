# Marking context DB drift report

Run a systematic drift check for marking context path coupling between `study_buddy.db` and `ai_study_buddy/context/`.

## Purpose

Report on-disk vs DB path drift for marking artifact families, with focus on:

- `marking_artifacts_missing_artifact_path`
- `marking_artifacts_missing_marking_asset`

These two checks are the core pass/fail contract used by the file-framework integrity suite for marking context drift.

## Rules

- Follow `.cursor/skills/pdf-file-manager/SKILL.md`.
- Read-only check only; do not mutate DB or files in this command.
- Run from repo root using module invocation.
- Treat nonzero drift counts as integrity findings to report first; do not auto-repair unless explicitly asked.

## What to run

Human-readable report:

```bash
python3 -m ai_study_buddy.learning_db.cli.context_db_drift_report \
  --db-path ai_study_buddy/db/study_buddy.db \
  --context-root ai_study_buddy/context
```

Machine-readable output:

```bash
python3 -m ai_study_buddy.learning_db.cli.context_db_drift_report \
  --db-path ai_study_buddy/db/study_buddy.db \
  --context-root ai_study_buddy/context \
  --json
```

CI/preflight fail mode:

```bash
python3 -m ai_study_buddy.learning_db.cli.context_db_drift_report \
  --db-path ai_study_buddy/db/study_buddy.db \
  --context-root ai_study_buddy/context \
  --fail-on-any
```

## Report format

1. State DB path and context root.
2. Show count summary.
3. Highlight these two first:
   - `marking_artifacts_missing_artifact_path`
   - `marking_artifacts_missing_marking_asset`
4. If nonzero, provide representative samples and classify likely causes (rename drift vs stale/orphan rows).
