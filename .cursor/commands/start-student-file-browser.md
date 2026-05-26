# Start Student File Browser

Operator filter-first inventory on port **8771**.

Use this when you specifically want the legacy standalone inventory browser. For
the preferred unified workflow, start `buddy_console` instead.

## Foreground

```bash
cd /path/to/daydreamedu-scripts
python3 -m ai_study_buddy.student_file_browser.serve
```

## Background

```bash
python3 -m ai_study_buddy.student_file_browser.spawn_background
```

## Notes

- Requires `ai_study_buddy.files` v0.3.0+ (v0.3.1 recommended) and `pdf_registry.db` for registration enrichment.
- **View PDF** opens [`root_pdf_browser`](../../ai_study_buddy/root_pdf_browser/README.md) (port **8770**, v0.1.6+ deep links) in a new tab.
- Restart after large filesystem changes (index snapshot at startup).
- See `ai_study_buddy/student_file_browser/README.md`.
