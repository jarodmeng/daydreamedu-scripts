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
