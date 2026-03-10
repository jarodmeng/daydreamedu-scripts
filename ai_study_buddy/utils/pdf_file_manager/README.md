# pdf_file_manager

**Version: v0.1.1**

A local utility that keeps a SQLite registry of PDF files in the study archive. It tracks exams, worksheets, book exercises, activities, notes, and templates (with optional completed variants), and keeps on-disk paths and database records in sync. You can scan one or more folders for new PDFs, optionally compress and archive originals, classify documents by type and metadata, group multi-file documents (e.g. exam booklets), and link completions to templates. Every state-mutating operation is recorded in an append-only operation log.

**Typical workflow:** Add scan roots (e.g. Google Drive folders) and students → run **scan** to discover and optionally compress new PDFs → **classify** with `doc_type`, `subject`, and metadata → use **suggest-groups** for exams, then create groups and link templates as needed. Only main files are ingested by the pipeline; raw archives are kept for traceability.

---

## Type dimensions

Every file has two independent attributes: **file_type** (main vs raw vs unknown — which file is the primary one for ingestion) and **doc_type** (exam, worksheet, book_exercise, activity, practice, notes, unknown — what kind of content). The former drives processing and naming; the latter drives metadata shape and how the ingestion pipeline routes the file.

---

## Docs

| Doc | Contents |
|-----|----------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Source folder layout, schema, file naming, metadata, integrations |
| [SPEC.md](./SPEC.md) | API, CLI, operation contract, implementation status |
| [TESTING.md](./TESTING.md) | Test levels, test data strategy, when to add tests |
| [DECISIONS.md](./DECISIONS.md) | Decision log |
| [CHANGELOG.md](./CHANGELOG.md) | Version history |

Parent: [L4_INGESTION_PIPELINE](../../docs/L4_INGESTION_PIPELINE.md) — Utilities section.

---

## Database backup

The registry DB (`ai_study_buddy/db/pdf_registry.db`) is gitignored. To back it up to the cloud **without** committing it to GitHub, copy it into a folder that syncs to the cloud (e.g. Google Drive on your Mac):

1. **Default backup location:** `~/genrong.meng@gmail.com - Google Drive/My Drive/DaydreamEdu/db`. No setup needed unless you want a different destination (set `PDF_REGISTRY_BACKUP_DIR` or use `--dest`).

2. **Run the backup script** from the repo root or from `ai_study_buddy/`:
   ```bash
   python3 ai_study_buddy/utils/pdf_file_manager/scripts/backup_pdf_registry.py
   ```
   Use `--timestamp` to keep dated copies (e.g. `pdf_registry_2025-03-10_14-30-00.db`) instead of overwriting.

Once the file is inside your Google Drive folder, it will sync to the cloud automatically.

**Run backup on wake (optional)**  
To back up automatically when the Mac wakes from sleep (only if the DB changed), use [sleepwatcher](https://formulae.brew.sh/formula/sleepwatcher):

```bash
brew install sleepwatcher
./ai_study_buddy/utils/pdf_file_manager/scripts/install_run_on_wake.sh
```

This installs a user LaunchAgent that runs the backup after each wake. The backup script still skips when unchanged. To remove: `launchctl unload ~/Library/LaunchAgents/com.daydreamedu.pdf-registry-backup-on-wake.plist` and edit or remove `~/.wakeup`.
