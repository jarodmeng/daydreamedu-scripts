# Validate PDF registry integrity

Run the reproducible **pdf_file_manager registry integrity audit** described in `ai_study_buddy/docs/L4_FILE_FRAMEWORK.md`.

## Rules

- Follow `.cursor/skills/pdf-file-manager/SKILL.md`.
- Do **not** query or edit the SQLite registry directly for this command.
- Run from the repository root (`daydreamedu-scripts` workspace folder).
- Use the module invocation, not a filesystem-relative script path, so package imports resolve consistently.
- Treat exit code `1` as "integrity issues were found", not as a command execution failure. Report the findings; do not repair anything unless the user explicitly asks.

## What to run

Default human-readable audit:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity
```

If the user asks for machine-readable output:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity --json
```

If the user provides a custom registry DB path:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity --db /path/to/pdf_registry.db
```

Optional human-readable example limit:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity --limit 50
```

## Report format

Default response:

1. State the registry DB path used if it appears in output or was provided.
2. Summarize whether the audit passed or failed.
3. If there are issues, list each nonzero check with its count and a few representative examples from the command output.
4. Mention that the validator checks exact registered paths against on-disk files and path-derived registry fields, so moved files or stale rows may surface as integrity drift.

Do not dump the full output if it is long. Keep the key counts and examples visible, and offer to investigate or repair specific failing checks only after reporting the audit result.
