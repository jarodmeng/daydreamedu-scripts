# Registry integrity audit script

Run the reproducible **pdf_file_manager registry integrity audit** described in `ai_study_buddy/docs/L4_FILE_FRAMEWORK.md`.

## Rules

- Follow `.cursor/skills/pdf-file-manager/SKILL.md`.
- Do **not** query or edit the SQLite registry directly for this command.
- Run from the repository root (`daydreamedu-scripts` workspace folder).
- Use the module invocation, not a filesystem-relative script path, so package imports resolve consistently.
- Treat exit code `1` as "integrity issues were found", not as a command execution failure. Report findings; do not repair unless explicitly asked.

## What to run

Default human-readable audit:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity
```

Machine-readable output:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity --json
```

Custom DB path:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity --db /path/to/pdf_registry.db
```

Optional example limit:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity --limit 50
```

## Report format

1. State the registry DB path used.
2. Summarize pass/fail.
3. If there are issues, list each nonzero check with count and representative examples.
4. Mention that checks are exact-path and path-derived; moved files or stale rows can appear as integrity drift.
