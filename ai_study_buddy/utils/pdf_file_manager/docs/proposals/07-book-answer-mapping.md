# Proposal 7: Book unit to answer-page mapping

**Happy path item:** [Book answer mapping] — Represent the mapping from a registered book unit file to its covering page range inside a registered answer file as a first-class registry relation, instead of storing it ad hoc in external JSON or overloading per-file metadata.

---

## Motivation

We now have several successful pilot runs that can map:

- a registered `doc_type='book'` unit file
- to a registered answer / worked-solutions PDF in the same `group_type='book'`
- with an inclusive answer-page range
- plus split-page boundary flags for starts/ends that happen mid-page

Examples already validated in `split_book_answer_by_unit_using_ai/` include:

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

### Python API

Add helper methods such as:

- `set_book_answer_mapping(unit_file_id_or_path, answer_file_id_or_path, answer_page_start, answer_page_end, starts_mid_page=False, ends_mid_page=False, source=None, notes=None)`
- `get_book_answer_mapping(unit_file_id_or_path)`
- `list_book_answer_mappings(book_group_id=None, answer_file_id_or_path=None, source=None)`
- `delete_book_answer_mapping(unit_file_id_or_path)`

Optional higher-level helpers:

- `list_unmapped_book_units(book_group_id)`

### MCP tool surface

Expose structured tools such as:

- `pdf_set_book_answer_mapping`
- `pdf_get_book_answer_mapping`
- `pdf_list_book_answer_mappings`
- `pdf_delete_book_answer_mapping`

Potential future tool:

- `pdf_import_book_answer_mappings_from_json`

### CLI

Optional but helpful:

- `pdf_file_manager book-answer set ...`
- `pdf_file_manager book-answer get ...`
- `pdf_file_manager book-answer list ...`

---

## Provenance and verification

The mapping layer should explicitly preserve provenance.

For v1, the table is a **current-state** view rather than a historical ledger:

- `set_book_answer_mapping(...)` should upsert by `unit_file_id`
- updates and deletes should be recorded in `operation_log`

Suggested `source` values:

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

Add the table and basic CRUD API with upsert-by-unit behavior and operation-log entries for create, update, and delete.

### Phase 2

Import already validated ground-truth mappings from:

- `science_practice_primary_5_and_6_ground_truth.json`
- `power_pack_science_psle_ground_truth.json`
- `power_pack_chinese_psle_ground_truth.json`
- `power_pack_math_psle_ground_truth.json`
- `power_pack_english_psle_practice_ground_truth.json`

Mark imported mappings with:

- `source='imported_ground_truth'`

### Phase 3

Have future model runs write first-pass mappings into the registry directly, then promote them to verified/corrected after manual review.

---

## Documentation update plan

Update these docs if the proposal is implemented:

- `README.md`
- `ARCHITECTURE.md`
- `SPEC.md`
- `DECISIONS.md`
- `CHANGELOG.md`
- `MCP.md`

Planned documentation updates:

- `README.md`
  - mention that book units can now be linked to answer files through page-range mappings
  - add a short example of querying a unit’s answer coverage
- `ARCHITECTURE.md`
  - document the new `book_answer_mappings` relation/table
  - explain how it sits alongside `pdf_files`, `file_groups`, and existing file relations
  - note that mixed books can map different unit subsets to different answer files
- `SPEC.md`
  - describe the new mapping data model and invariants
  - define accepted CRUD operations
  - document expected behavior for unmapped units and intentionally excluded units
- `DECISIONS.md`
  - add a short decision entry explaining why book answer-page coverage is stored as a dedicated relation table instead of file metadata
- `CHANGELOG.md`
  - record the addition of book answer mapping support
- `MCP.md`
  - add the new MCP tools
  - document the machine-facing contract for querying and updating book answer mappings

---

## Test plan

### Data model tests

- Create one valid mapping row between a unit file and answer file in the same book group.
- Reject invalid page ranges where `start > end`.
- Reject mapping rows for missing file ids.
- Reject duplicate rows for the same `unit_file_id` if uniqueness is enforced.

### API tests

- `set_book_answer_mapping(...)` creates a row.
- Repeating the same call updates the row if the API is upsert-style.
- `get_book_answer_mapping(...)` returns the correct row.
- `list_book_answer_mappings(...)` filters by book group and answer file correctly.
- `delete_book_answer_mapping(...)` removes the row.

### Registry consistency tests

- Mapping unit and answer files in the same `group_type='book'` works.
- Mapping files across unrelated books is rejected or flagged clearly.
- Mapping to a non-book file is rejected or flagged clearly.

### Real-example fixture tests

Use at least one known mapping from each validated pilot:

- `Science Practice Primary 5 and 6`
- `Power Pack Science PSLE`
- `Power Pack Chinese PSLE`
- `Power Pack Math PSLE`
- `Power Pack English PSLE` practice subset

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
