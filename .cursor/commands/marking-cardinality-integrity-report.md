# Marking cardinality integrity report

Run cardinality integrity checks for template/completion marking artifacts across DB and `context/`.

## Purpose

Validate these invariants:

1. **Template -> file_question_info**: each template file has at most one `file_question_info` run/folder.
2. **Completion -> marking family**: each completion file has at most one active run per marking family (`marking_results`, `marking_assets`, `learning_reports`, `marking_amendments`, `student_review_states`).

## Rules

- Follow `.cursor/skills/pdf-file-manager/SKILL.md`.
- Read-only command; do not mutate DB/files in this command.
- Run from repo root using module invocation.
- If violations exist, report IDs/counts first; do not auto-fix unless explicitly requested.

## What to run

Human-readable:

```bash
python3 -m ai_study_buddy.learning_db.cli.marking_cardinality_integrity_report \
  --registry-db-path ai_study_buddy/db/pdf_registry.db \
  --study-db-path ai_study_buddy/db/study_buddy.db \
  --context-root ai_study_buddy/context
```

Machine-readable:

```bash
python3 -m ai_study_buddy.learning_db.cli.marking_cardinality_integrity_report \
  --registry-db-path ai_study_buddy/db/pdf_registry.db \
  --study-db-path ai_study_buddy/db/study_buddy.db \
  --context-root ai_study_buddy/context \
  --json
```

Preflight fail mode:

```bash
python3 -m ai_study_buddy.learning_db.cli.marking_cardinality_integrity_report \
  --registry-db-path ai_study_buddy/db/pdf_registry.db \
  --study-db-path ai_study_buddy/db/study_buddy.db \
  --context-root ai_study_buddy/context \
  --fail-on-any
```

## Report format

1. Show count summary for:
   - `template_file_question_info_db_cardinality`
   - `template_file_question_info_disk_cardinality`
   - `completion_marking_family_db_cardinality`
   - `completion_marking_family_disk_cardinality`
2. If nonzero, list violating file IDs and counts with family labels.
