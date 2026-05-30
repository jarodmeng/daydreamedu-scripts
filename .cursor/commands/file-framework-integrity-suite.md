# File framework integrity suite

Run one consolidated integrity health check for the L4 file framework.

## Purpose

This suite reports one **overall PASS/FAIL** by running:

1. DaydreamEdu leaf folder vs registry check
2. GoodNotes leaf folder vs registry check (default excludes `Not completed`)
3. Completion-template link gap check (default excludes `activity`/`note`; always excludes `composition`)
4. Registry integrity audit
5. Marking context DB drift (`marking_results`/`marking_assets` path coupling)
6. Marking cardinality integrity (template/completion uniqueness)

## Rules

- Follow `.cursor/skills/pdf-file-manager/SKILL.md`.
- Do not edit the registry in this command; this is a read-only health check.
- Run from repo root with module invocation.
- Treat exit code `1` as integrity failures found (not command failure).

## What to run

Default:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.file_framework_integrity_suite
```

Include `activity` and `note` in completion-template gap check:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.file_framework_integrity_suite --include-activity-note
```

Machine-readable output:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.file_framework_integrity_suite --json
```

Custom DB:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.file_framework_integrity_suite --db /path/to/pdf_registry.db
```

## Exit codes

- `0`: overall pass
- `1`: one or more checks failed
- `2`: DB file missing

## Pass criteria

- Leaf-registry checks pass only when all included leaves fall into `scan-root + all direct PDFs registered`.
- Completion-template gap check passes when `without_template = 0` among completions that require a template link (`exam`, `exercise`, `book`; `composition` is always excluded).
- Registry integrity audit passes when all summary counters are zero.
- Marking context DB drift check passes when:
  - `marking_artifacts_missing_artifact_path = 0`
  - `marking_artifacts_missing_marking_asset = 0`
- Marking cardinality integrity check passes when:
  - `template_file_question_info_db_cardinality = 0`
  - `template_file_question_info_disk_cardinality = 0`
  - `completion_marking_family_db_cardinality = 0`
  - `completion_marking_family_disk_cardinality = 0`
- Overall suite passes only when all six checks pass.
