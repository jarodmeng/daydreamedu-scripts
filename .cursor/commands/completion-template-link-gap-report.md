# Completion template link gap report

Run the **registry-only** report for **completion mains** that still have **no** template link (`completed_from` relation), grouped by **root** (`d_root` / `g_root`), **doc_type**, **student**, **grade**, and **subject**.

Documented in `ai_study_buddy/docs/L4_FILE_FRAMEWORK.md` (template vs completion and this utility).

## Rules

- Follow `.cursor/skills/pdf-file-manager/SKILL.md`.
- Do **not** hand-edit the SQLite registry for this command unless the user explicitly asks for repairs.
- Run from the repository root (`daydreamedu-scripts` workspace folder).
- Use the **module** invocation below so package imports resolve consistently.
- **Exit code:** `0` when **no** completions are missing a template under the filter; `1` when at least one gap row exists; `2` when the DB file is missing.

## What to run

Default (excludes `activity` and `note` doc_types — focuses on exam / exercise / book):

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.completion_template_link_gap_report
```

Include activity and note completions in the counts and gap table:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.completion_template_link_gap_report --include-activity-note
```

Custom registry path:

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.completion_template_link_gap_report --db /path/to/pdf_registry.db
```

Machine-readable JSON (includes `summary` and `gaps` array):

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.completion_template_link_gap_report --json
```

## Report format (human)

When responding to the user:

1. State the registry DB path from the script output (or `--db` if provided).
2. Repeat the filter line (default excludes activity/note).
3. Give the **summary** line: completion mains total, with template, without template, gap bucket count.
4. If there are gap rows, paste the **table** (or the top buckets if very long) — same columns as the script: `cnt`, `root`, `doc_type`, `student`, `grade`, `subject`.
5. Briefly interpret **root**: `d_root` means the stored path contains `/DaydreamEdu/`; `g_root` means `/GoodNotes/`. `(unknown)` means neither segment matched (unusual for in-scope Drive layouts).
6. If the user wants to **fix** gaps, point them at `PdfFileManager.link_goodnotes_template_for_file` / `link_goodnotes_templates_for_root` for GoodNotes-shaped paths, and `link_template_by_paths` for explicit pairs — do not run linking unless the user asks.

Do not dump huge JSON in chat unless the user asked for `--json` output.
