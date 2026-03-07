# pdf_file_manager

**Version: v0.1.0**

A local utility that keeps a SQLite registry of PDF files in the study archive. It tracks exams, worksheets, book exercises, activities, notes, and templates (with optional completed variants), and keeps on-disk paths and database records in sync. You can scan one or more folders for new PDFs, optionally compress and archive originals, classify documents by type and metadata, group multi-file documents (e.g. exam booklets), and link completions to templates. Every change is recorded in an append-only operation log.

**Typical workflow:** Add scan roots (e.g. Google Drive folders) and students → run **scan** to discover and optionally compress new PDFs → **classify** with `doc_type`, `subject`, and metadata → use **suggest-groups** for exams, then create groups and link templates as needed. Only `main` files are ingested by the pipeline; `_raw_` archives are kept for traceability.

---

## Docs

| Doc | Contents |
|-----|----------|
| [VISION.md](./VISION.md) | Purpose, type dimensions, scan → compress → archive workflow |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Source folder layout, schema, metadata, integrations |
| [SPEC.md](./SPEC.md) | API, CLI, operation contract, implementation status |
| [TESTING.md](./TESTING.md) | Test levels, test data strategy, when to add tests |
| [DECISIONS.md](./DECISIONS.md) | Decision log |
| [CHANGELOG.md](./CHANGELOG.md) | Version history; v0.1.0 and the 5-phase build plan |

Parent: [L4_INGESTION_PIPELINE](../../docs/L4_INGESTION_PIPELINE.md) — Utilities section.
