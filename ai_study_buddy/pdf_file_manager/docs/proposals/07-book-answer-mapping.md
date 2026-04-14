# Proposal 7: Book unit to answer-page mapping

**Happy path item:** [Book answer mapping] — Represent the mapping from a registered book unit file to its covering page range inside a registered answer file as a first-class registry relation, instead of storing it ad hoc in external JSON or overloading per-file metadata.

---

## Implementation status

**Baseline:** [`pdf_file_manager` v0.2.7](../../CHANGELOG.md) (see changelog entry *Book answer mappings*). This section is the source of truth for **proposal vs shipped**.

| Area | Status |
| --- | --- |
| `book_answer_mappings` table + invariants (same book group, `doc_type='book'`, `file_type='main'`, upsert by unit) | **Implemented** |
| Operation log: `book_answer_mapping_set`, `book_answer_mapping_update`, `book_answer_mapping_delete` | **Implemented** |
| Python: `set` / `get` / `list` / `delete` / `import_book_answer_mappings_from_json` | **Implemented** |
| MCP: `pdf_set_book_answer_mapping`, `pdf_get_book_answer_mapping`, `pdf_list_book_answer_mappings`, `pdf_delete_book_answer_mapping` | **Implemented** |
| MCP: `pdf_import_book_answer_mappings_from_json` | **Not implemented** (still “potential future” below) |
| Python: `list_unmapped_book_units` | **Not implemented** |
| CLI `pdf_file_manager book-answer …` | **Not implemented** |
| Companion table / flag for “known unmapped by design” | **Not implemented** (v1 uses *no row*) |
| Phase 3: model runs writing directly to registry | **Not implemented** |

**Ground-truth JSON:** Bulk import is supported via **`import_book_answer_mappings_from_json`** (Python only). The pilot files under `ai_study_buddy/split_book_answer_by_unit_using_ai/pilot_ground_truth/` used in v0.2.7 are listed in [Phase 2](#phase-2) below; **`power_pack_english_psle_situational_writing_ground_truth.json`** is an additional validated artifact in the same format and can be imported the same way once the answer and unit PDFs are registered in the book group.

**Docs:** [Documentation update plan](#documentation-update-plan) — most items were done for v0.2.7; this proposal file was not originally toggled to “done”; this section records that.

---

## Motivation

We now have several successful pilot runs that can map:

- a registered `doc_type='book'` unit file
- to a registered answer / worked-solutions PDF in the same `group_type='book'`
- with an inclusive answer-page range
- plus split-page boundary flags for starts/ends that happen mid-page

Examples already validated in `ai_study_buddy/split_book_answer_by_unit_using_ai/` include:

- `Science Practice Primary 5 and 6`
- `Power Pack Science PSLE`
- `Power Pack Chinese PSLE`
- `Power Pack Math PSLE`
- `Power Pack English PSLE` (main practice-answer subset)

Today, these mappings live only as external JSON artifacts and pilot ground-truth files. That is enough for experimentation, but not ideal for long-term registry-backed workflows.

The mapping is not intrinsic metadata of either file alone:

- it is not just a property of the unit file
- it is not just a property of the answer file
- it is a relation between two registered files

So the best long-term home is a dedicated relation layer in `pdf_file_manager`.

---

## Problem

The current registry already supports:

- per-file classification and metadata in `pdf_files`
- logical book identity in `file_groups` with `group_type='book'`
- file-to-file relations such as template linking

But it does **not** support a structured way to say:

> “This specific book unit file is covered by pages 35–40 of this specific answer file, starts mid-page, and ends at the end of the page.”

Without a first-class place for that mapping:

1. Scripts must keep sidecar JSON files and re-resolve filenames back to registry rows.
2. Provenance such as “model-generated” vs “manually verified” cannot be queried through the registry.
3. Consumers cannot ask simple questions like:
   - “Given this book unit file, what answer pages cover it?”
   - “List all verified answer mappings for this book.”
   - “Which units in this book still have no verified answer mapping?”
4. Putting the mapping into `pdf_files.metadata` would be awkward because it creates cross-file coupling inside a blob field.

---

## Proposal

Add a first-class **book answer mapping** relation to the registry.

**Status:** The storage model, invariants, and core Python API below are **implemented** (v0.2.7). See [Implementation status](#implementation-status) for MCP/CLI/import gaps.

### Concept

Each mapping row links:

- one registered `unit_file`
- to one registered `answer_file`
- with a page range and split-page flags

This should be treated as a new relation type for book-specific answer coverage, separate from:

- template/completion linking
- raw/main file relations
- group membership

### Recommended storage model

Add a dedicated table, for example:

`book_answer_mappings`

Suggested columns:

- `id`
- `unit_file_id`
- `answer_file_id`
- `answer_page_start`
- `answer_page_end`
- `starts_mid_page`
- `ends_mid_page`
- `source`
- `notes`
- `created_at`
- `updated_at`

Suggested invariants:

- exactly one current row per `unit_file_id`
- `answer_page_start <= answer_page_end`
- `unit_file_id` and `answer_file_id` must both exist in `pdf_files`
- both files must be `file_type='main'`
- both files must be `doc_type='book'`
- both files must belong to the same `group_type='book'` group

### Why a dedicated table is better than metadata

This mapping should **not** live in `pdf_files.metadata` because:

- metadata blobs are file-local, while this mapping is relational
- the answer file id/path would have to be duplicated into each unit file’s JSON
- queries become harder and less reliable
- provenance and verification state are harder to normalize

This mapping should also **not** be represented only as a `file_group`, because:

- groups express shared identity or loose membership
- they do not naturally encode page ranges and boundary flags

So the clean model is:

- `file_groups.group_type='book'` stores the shared book identity
- `book_answer_mappings` stores per-unit answer coverage inside that book

---

## Suggested API surface

*Cross-check [Implementation status](#implementation-status) above.*

### Python API

**Implemented (v0.2.7):**

- `set_book_answer_mapping(unit_file_id_or_path, answer_file_id_or_path, answer_page_start, answer_page_end, starts_mid_page=False, ends_mid_page=False, source=None, notes=None)`
- `get_book_answer_mapping(unit_file_id_or_path)`
- `list_book_answer_mappings(book_group_id=None, answer_file_id_or_path=None, source=None)`
- `delete_book_answer_mapping(unit_file_id_or_path)`
- `import_book_answer_mappings_from_json(json_path, *, source='imported_ground_truth')` — reads the same shape as pilot ground-truth JSON (`book_label`, `answer_file`, `mappings[]`).

**Not implemented:**

- `list_unmapped_book_units(book_group_id)` (optional higher-level helper; callers can diff group members against `list_book_answer_mappings` today).

### MCP tool surface

**Implemented (v0.2.7):**

- `pdf_set_book_answer_mapping`
- `pdf_get_book_answer_mapping`
- `pdf_list_book_answer_mappings`
- `pdf_delete_book_answer_mapping`

**Not implemented:**

- `pdf_import_book_answer_mappings_from_json` — no MCP wrapper yet; use Python `import_book_answer_mappings_from_json` or repeated `pdf_set_book_answer_mapping`.

### CLI

**Not implemented** (optional but helpful):

- `pdf_file_manager book-answer set ...`
- `pdf_file_manager book-answer get ...`
- `pdf_file_manager book-answer list ...`

---

## Provenance and verification

The mapping layer should explicitly preserve provenance.

For v1, the table is a **current-state** view rather than a historical ledger:

- `set_book_answer_mapping(...)` should upsert by `unit_file_id`
- updates and deletes should be recorded in `operation_log`

Suggested `source` values (free-form `TEXT` in DB; **no enum enforcement** in v0.2.7):

- `model_generated`
- `model_generated_gpt54`
- `model_generated_gemini25pro`
- `manual_verified`
- `manual_corrected`
- `imported_ground_truth`

This would let downstream tools distinguish:

- unreviewed model output
- model output that was manually accepted
- manually corrected ground truth

---

## Scope rules and edge cases

The mapping layer should support these cases cleanly:

1. **Normal unit -> answer-file mapping**
   - one unit file
   - one answer file
   - contiguous page range

2. **Mid-page boundaries**
   - `starts_mid_page`
   - `ends_mid_page`

3. **Book subsets with separate answer files**
   - e.g. `Power Pack English PSLE`
   - main `Practice 1-18` maps to `Practice Answers`
   - `Situational Writing Practice 1-5` maps to `Situational Writing Practice Answers`
   - this is a strong reason the mapping should point directly to a specific answer file

4. **Intentional exclusions**
   - e.g. `Concept Maps` in `Power Pack Science PSLE`
   - some unit files may intentionally have no answer mapping

To support intentional exclusions, consider either:

- no row at all plus a separate review note elsewhere
- or a future companion table/flag for “known unmapped by design”

For v1, no row is the intended representation.

---

## Migration / adoption plan

### Phase 1

**Done (v0.2.7).** Table `book_answer_mappings`, CRUD + upsert-by-unit, operation-log entries for create, update, and delete.

### Phase 2

**Partially done.** Python `import_book_answer_mappings_from_json` is **implemented**; loading each file into a given registry is an **operational** step (files must exist in the book group with matching basenames).

Validated ground-truth JSON under `ai_study_buddy/split_book_answer_by_unit_using_ai/pilot_ground_truth/`:

- `science_practice_primary_5_and_6_ground_truth.json` — used in v0.2.7 rollout
- `power_pack_science_psle_ground_truth.json` — used in v0.2.7 rollout
- `power_pack_chinese_psle_ground_truth.json` — used in v0.2.7 rollout
- `power_pack_math_psle_ground_truth.json` — used in v0.2.7 rollout
- `power_pack_english_psle_practice_ground_truth.json` — used in v0.2.7 rollout
- `power_pack_english_psle_situational_writing_ground_truth.json` — same import path; **not** called out in the v0.2.7 changelog list (added later)

Mark imported mappings with:

- `source='imported_ground_truth'` (default for `import_book_answer_mappings_from_json`)

### Phase 3

**Not done.** Have future model runs write first-pass mappings into the registry directly, then promote them to verified/corrected after manual review.

---

## Documentation update plan

**Status:** Core product docs were updated for **v0.2.7** as planned. This proposal was left as the design record; [Implementation status](#implementation-status) above reconciles it with what shipped.

| Doc | Status (v0.2.7) |
| --- | --- |
| `README.md` | **Done** — book answer mappings, MCP tool list |
| `ARCHITECTURE.md` | **Done** — table and placement vs groups/relations |
| `SPEC.md` | **Done** — API contract for CRUD mappings |
| `DECISIONS.md` | **Done** — decision entry for dedicated table |
| `CHANGELOG.md` | **Done** — v0.2.7 entry |
| `MCP.md` | **Done** — four mapping tools (**not** import MCP) |
| `07-book-answer-mapping.md` (this file) | **Updated** — implementation status section |

Planned content (original intent — largely reflected in the updated docs above):

- `README.md` — book units linked to answer files via page-range mappings; query via API/MCP
- `ARCHITECTURE.md` — `book_answer_mappings`; mixed books with multiple answer files
- `SPEC.md` — data model, invariants, unmapped = no row
- `DECISIONS.md` — why not `pdf_files.metadata`
- `CHANGELOG.md` — version history
- `MCP.md` — machine-facing CRUD; import remains Python-only until a fifth tool exists

---

## Test plan

**Automated coverage (v0.2.7):** See `tests/test_book_answer_mappings.py` and MCP tests in `tests/test_mcp_tools.py` / `tests/test_mcp_server.py` for CRUD, filters, upsert logging, validation errors, **`import_book_answer_mappings_from_json`**, and the four MCP mapping tools.

### Data model tests

- Create one valid mapping row between a unit file and answer file in the same book group. **Covered** (synthetic fixtures).
- Reject invalid page ranges where `start > end`. **Enforced** in `set_book_answer_mapping` (`ValueError`); **no dedicated pytest** in `test_book_answer_mappings.py` at time of writing.
- Reject mapping rows for missing file ids. **Partially** (NotFound / wrong group paths).
- Reject duplicate rows for the same `unit_file_id` if uniqueness is enforced. **Covered** via upsert behavior (same unit updates one row).

### API tests

- `set_book_answer_mapping(...)` creates a row. **Covered**
- Repeating the same call updates the row if the API is upsert-style. **Covered**
- `get_book_answer_mapping(...)` returns the correct row. **Covered**
- `list_book_answer_mappings(...)` filters by book group and answer file correctly. **Covered**
- `delete_book_answer_mapping(...)` removes the row. **Covered**

### Registry consistency tests

- Mapping unit and answer files in the same `group_type='book'` works. **Covered**
- Mapping files across unrelated books is rejected or flagged clearly. **Covered** (`ValueError`)
- Mapping to a non-book file is rejected or flagged clearly. **Covered** (`ValueError`)

### Real-example fixture tests

**Not required by current test suite** (uses temp DBs and small PDFs). Optional follow-up: fixture-backed tests using real pilot filenames.

Pilot books with validated JSON:

- `Science Practice Primary 5 and 6`
- `Power Pack Science PSLE`
- `Power Pack Chinese PSLE`
- `Power Pack Math PSLE`
- `Power Pack English PSLE` practice subset
- `Power Pack English PSLE` situational-writing subset (`power_pack_english_psle_situational_writing_ground_truth.json`)

---

## Recommendation

Implement this as a dedicated registry relation table.

That gives us:

- normalized storage
- queryable provenance
- compatibility with mixed-book structures that have multiple answer files
- a clean bridge from model-generated output to manually verified registry truth

This is the most natural extension of the current `pdf_file_manager` design, which already treats:

- files as first-class rows
- books as first-class groups
- certain cross-file relationships as first-class structured relations

Book answer-page coverage should follow the same design philosophy.
