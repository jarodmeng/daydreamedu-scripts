# pdf_file_manager — Vision

> Status: **Draft**
>
> Parent doc: [L4_INGESTION_PIPELINE](../../docs/L4_INGESTION_PIPELINE.md) — Utilities section.
>
> Decision log: [DECISIONS.md](./DECISIONS.md)
>
> See also: [ARCHITECTURE.md](./ARCHITECTURE.md) (schema, data model), [SPEC.md](./SPEC.md) (API, CLI, contract).

**Purpose:** Maintain a local SQLite registry of all PDF files in the study archive. The archive contains diverse document types — scanned exam booklets, worksheets, book exercise pages, and blank templates (with optional completed variants). The file manager tracks main vs. raw-archive variants, file group memberships, student and type-specific metadata, and provides CRUD operations that keep on-disk state and database records in sync. Every state-mutating operation is recorded in an append-only `operation_log`, enabling full history reconstruction for any file or group.

---

## Two orthogonal type dimensions

Every file has two independent type attributes:

| Attribute | Column | Purpose | Values |
|-----------|--------|---------|--------|
| Processing state | `file_type` | Is this the primary file for ingestion, or an archived original? | `main`, `raw`, `unknown` |
| Content type | `doc_type` | What kind of document does the file contain? | `exam`, `worksheet`, `book_exercise`, `activity`, `practice`, `notes`, `unknown` |

`file_type` drives file processing and naming conventions. `doc_type` drives metadata structure, ingestion routing, and grouping semantics. A `main` file can be any `doc_type`.

---

## File processing workflow

The file manager's primary workflow on discovering a new PDF is **scan → compress → archive**:

1. `scan_for_new_files` discovers an unregistered PDF (e.g., `math_wa1.pdf`).
2. For an unregistered PDF **without** a `_c_` prefix, `compress_and_register` is called automatically:
   - Renames the original to `_raw_math_wa1.pdf` (the raw archive).
   - Attempts compression via the `compress_pdf` utility.
   - **If compression is worthwhile** (savings ≥ `min_savings_pct`, default 10%):
     - Writes the compressed output as `_c_math_wa1.pdf` (main file; `_c_` prefix = compressed).
     - Registers both; links them with `raw_source` / `main_version` relations; populates `page_count`.
   - **If compression is not worthwhile**: restores the original at `math_wa1.pdf` as main (no `_c_`), no `_raw_`; `has_raw = False`.
3. For an unregistered PDF **with** a `_c_` prefix, the file is registered as `main` only (no compress step).
4. The resulting main file (`file_type='main'`) is what the ingestion pipeline operates on. `_raw_` files are kept for traceability only; they are not ingested.

**`page_count` value:** Captured during compress at no extra cost (PyMuPDF is already invoked). Used for: list-view display, sanity-checking scans (e.g., flagging a 2-page file where 16 pages were expected), and pipeline cost estimation (LLM call count scales with page count).
