# Proposal: Add `book` as a `doc_type` and `group_type`

> **Context:** We now have a dedicated `Book/` folder under the DaydreamEdu tree, for example `Singapore Primary Chinese/PSLE/Book/Power Pack Chinese PSLE`. The current `pdf_file_manager` model has `book_exercise` for exercise-sized extracts from a book, but no first-class way to represent a whole book or a book-organized set of book PDFs, either as a file classification or as a logical file group.
>
> **Status:** Implemented.
>
> **Historical note:** This proposal records pre-canonicalization design context and intentionally includes legacy enum names. The current canonical `doc_type` set is `exam`, `exercise`, `book`, `activity`, `note` (see `README.md` / `SPEC.md`).

---

## 1. Terminology clarification

In `pdf_file_manager`, **`file_type`** and **`doc_type`** mean different things:

- `file_type` = storage/processing role: `main`, `raw`, `unknown`
- `doc_type` = content kind: `exam`, `worksheet`, `book_exercise`, `activity`, `practice`, `notes`, `unknown`

So if we want to support a new "Book" category, it should be added as a new **`doc_type`**, not a new `file_type`. Separately, because a book is also a logical multi-file container, it should also be added as a new **`group_type`** in `file_groups`.

---

## 2. Problem

The current model handles book-related material in two imperfect ways:

1. **Whole-book or book-level PDFs have no natural `doc_type`.**
   - `book_exercise` is too narrow: it implies a bounded exercise or page range within a book.
   - `notes` and `practice` are too vague.

2. **Folder-based inference does not recognize `Book/` as an L3 content folder.**
   - Today, `Exam`, `Exercise`, `Activity`, and `Note` are recognized.
   - A new `Book/` folder currently becomes just path context, not a meaningful classification signal.

3. **Book-level grouping is currently implicit instead of explicit.**
   - The existing `file_groups.group_type` values are only `exam`, `book_exercise`, and `collection`.
   - The registry needs to distinguish:
     - a whole book or book-volume PDF
     - an exercise excerpt from a book
     - a standalone worksheet that happened to come from a book

---

## 3. Proposal

Add `book` as:

- a new `doc_type` for PDFs that represent a full book, book unit, or book-organized paper set that should be managed at the book level
- a new `group_type` for the logical group of files that belong to the same book

### Proposed meaning of `book`

Use `doc_type='book'` when the PDF is best understood as a **book artifact**, such as:

- a full textbook or workbook PDF
- a book unit PDF
- a book-organized practice-paper set kept as part of a named book collection
- an answer book that belongs to a named book set

Keep `doc_type='book_exercise'` for **exercise-level extracts** from a book, such as:

- one exercise scanned from pages 10-18
- one chapter exercise split across multiple PDFs
- one worksheet-sized segment from a larger book

### Practical rule of thumb

- If the unit you want to manage is the **book itself**, use `book`
- If the unit you want to ingest or review is a **specific exercise inside a book**, use `book_exercise`

For the `PP Chinese` materials moved into `.../PSLE/Book/Power Pack Chinese PSLE`, the intended pattern becomes:

- each file is `doc_type='book'`
- all of those files belong to one `group_type='book'` group labeled `Power Pack Chinese PSLE`
- per-file metadata stores only the file-specific `unit`

This applies both to numbered units and to supporting files in the same book folder. The proposal does **not** introduce a finer per-file semantic subtype such as `role`; that would overfit individual examples and can remain implicit in filenames/content for now.

---

## 4. Required changes

### 4.1 Schema

Extend the `pdf_files.doc_type` CHECK constraint:

```sql
CHECK(doc_type IN (
  'exam',
  'worksheet',
  'book',
  'book_exercise',
  'activity',
  'practice',
  'notes',
  'unknown'
))
```

Also extend the `file_groups.group_type` CHECK constraint:

```sql
CHECK(group_type IN (
  'exam',
  'book',
  'book_exercise',
  'collection'
))
```

### 4.2 Path inference

Recognize `Book` as an L3 folder:

| Folder | Inferred `doc_type` | Notes |
|--------|----------------------|-------|
| `Book` | `book` | Default for whole-book / book-level PDFs |

Also include `Book` in `metadata.content_folder`.

### 4.3 Grouping model

Represent each logical book as a file group:

- `group_type='book'`
- `label=<book name>` from the folder under `Book`
- member files = all book files in that folder
- `anchor_id` = optional preferred entry file for opening the group

This lets the shared book identity live in one place instead of relying only on repeated per-file metadata.

### 4.4 Documentation update plan

Update these docs:

- `README.md`
- `ARCHITECTURE.md`
- `SPEC.md`
- `DECISIONS.md`
- `CHANGELOG.md`

Planned documentation updates:

- `README.md`
  - add `book` to the `doc_type` overview
  - mention `group_type='book'` in the grouping overview
- `ARCHITECTURE.md`
  - add `Book` to the L3 folder mapping
  - document the lightweight `book` metadata shape
  - update schema snippets for `doc_type` and `group_type`
- `SPEC.md`
  - update operation/type docs so `doc_type='book'` and `group_type='book'` are accepted anywhere relevant
  - document expected `scan_for_new_files(...)` behavior for `.../Book/<book name>/...`
- `DECISIONS.md`
  - add a decision entry explaining why `book` is both a `doc_type` and a `group_type`
- `CHANGELOG.md`
  - record the feature when it is implemented

### 4.5 Lightweight metadata schema

Add a lightweight `book` metadata example:

```json
{
  "unit": "作文 1"
}
```

Recommended fields:

- `unit`

Field meanings:

- `unit`: the human-meaningful file label within that book collection, usually inferred from filename after removing technical prefixes like `_c_` / `_raw_` and any redundant leading book prefix when applicable

Not part of `book` metadata because they are already carried elsewhere:

- `subject`: first-class column
- `student_id`: first-class column
- `grade_or_scope`: inferred from the path
- `content_folder`: inferred from the path as `Book`
- `book title / shared book identity`: represented by the `book` file group label

Examples of valid `unit` values:

- `模拟考卷 3`
- `作文 2`
- `作文 范文`
- `模拟试卷 答案`
- `试卷蓝图与复习指南`

---

## 5. Why `book` is better than overloading existing types

### vs `book_exercise`

`book_exercise` already has a clear and useful meaning: a smaller, exercise-level unit from within a book. Reusing it for whole-book files would blur an important distinction in the ingestion workflow.

### vs `practice`

`practice` is too generic. A book is not just “practice”; it is a source object with stable identity, often with related answers, templates, units, and derived exercises.

### vs `notes`

Notes are reference/support material, not book artifacts.

---

## 6. Required utility changes

Most of this proposal can be implemented by extending existing utility behavior rather than inventing a new subsystem.

### 6.1 Existing functions and operations to modify

These existing surfaces should be updated to accept and handle the new types:

- `register_file(...)`
  - allow `doc_type='book'`
- `update_metadata(...)`
  - allow `doc_type='book'`
- `find_files(...)`
  - no new parameter needed, but `doc_type='book'` must work naturally
- `create_file_group(...)`
  - allow `group_type='book'`
- `list_file_groups(...)`
  - allow filtering by `group_type='book'`
- `get_file_group(...)`
  - no signature change needed, but docs/tests should include `book` groups
- `get_file_group_membership(...)`
  - no signature change needed, but docs/tests should include `book` groups
- `add_to_file_group(...)`
  - no behavior change needed, but book-group usage should be documented/tested
- `remove_from_file_group(...)`
  - no behavior change needed, but book-group usage should be documented/tested
- `set_file_group_anchor(...)`
  - no behavior change needed, but book-group usage should be documented/tested
- `scan_for_new_files(...)`
  - path inference should recognize `.../Book/<book name>/...`
  - when scanning such a folder, discovered files should be registered with `doc_type='book'`
  - file-level `metadata.unit` should be inferred from filename when possible, for both numbered and non-numbered book files
  - the scan result should leave the files ready for immediate use without requiring a separate manual classification pass for the basic `book` type

### 6.2 Schema and validation changes

The utility’s schema/bootstrap logic and any enum validation code must be updated for:

- `pdf_files.doc_type` to include `book`
- `file_groups.group_type` to include `book`

### 6.3 Path inference changes

`_infer_from_path(path)` should be extended so that:

- an L3 folder named `Book` maps to `doc_type='book'`
- `metadata.content_folder='Book'` is inferred as today’s other content folders are
- the immediate child folder under `Book` is treated as the logical book name for grouping purposes

### 6.4 Explicit scan behavior for book folders

After this proposal is implemented, `scan_for_new_files(...)` should be the primary entrypoint an agent or user uses for a folder like:

`.../Book/<book name>/`

For files discovered under that pattern, the scan should:

1. register/compress the files as usual
2. infer `doc_type='book'`
3. infer `metadata.unit` from filename where possible
4. infer that the logical shared book identity is `<book name>`

Recommended boundary for the first implementation:

- `scan_for_new_files(...)` **must** make the files themselves book-aware at registration time
- `scan_for_new_files(...)` does **not have to** create the `book` file group automatically in the same first version

That means the proposal explicitly requires scan-time support for:

- correct `doc_type`
- correct file-level metadata
- enough path-derived information to support later grouping

Automatic `book` group creation can be added either:

- directly inside `scan_for_new_files(...)` in a later iteration, or
- through a follow-up helper such as `ensure_book_group_from_path(...)`

### 6.5 Read/write behavior that does not need a new API

These existing capabilities are already sufficient once the new enum values are allowed:

- creating a logical book group via `create_file_group(label=..., group_type='book')`
- adding files to the book group via `add_to_file_group(...)`
- listing and opening book groups via existing group read APIs

So a first implementation does **not** require a brand-new book-specific CRUD interface.

### 6.6 Optional helper functions

These are not required for correctness, but would reduce manual work:

- `suggest_book_groups()`
  - find files under the same `.../Book/<book name>/...` folder and suggest one `group_type='book'` group per book folder
- `ensure_book_group(...)`
  - create the group if missing and return it
- `ensure_book_group_from_path(path)`
  - derive the book name from the folder structure, create/find the corresponding `book` group, and return it
- `link_files_in_book_folder(...)`
  - bulk-add all matching files in a folder to the corresponding book group

These should be treated as convenience helpers, not blockers for introducing `book`.

## 7. Testing plan

This proposal should include tests as part of implementation.

### 7.1 Schema and validation tests

Add or update tests to verify:

- `doc_type='book'` is accepted anywhere doc types are validated
- `group_type='book'` is accepted anywhere group types are validated
- invalid values still fail as expected

### 7.2 Path inference tests

Add tests for paths like:

- `.../Singapore Primary Chinese/PSLE/Book/Power Pack Chinese PSLE/_c_PP Chinese 模拟考卷 3.pdf`
- `.../Singapore Primary Chinese/PSLE/Book/Power Pack Chinese PSLE/_c_PP Chinese 作文 2.pdf`

Verify that inference sets:

- `doc_type='book'`
- `metadata.content_folder='Book'`
- `metadata.unit` when filename inference is available

### 7.3 Scan workflow tests

Add tests covering `scan_for_new_files(...)` on a book folder to verify:

- files are registered successfully
- `doc_type='book'` is assigned during scan
- the basic book-aware registration works without requiring a follow-up manual classification step

### 7.4 File group tests

Add tests covering:

- `create_file_group(..., group_type='book')`
- adding/removing files to/from a `book` group
- listing/filtering `book` groups
- retrieving group membership for files in a `book` group

### 7.5 MCP tests

If MCP tools cover the affected operations, update MCP-facing tests to confirm:

- book files can be found/read correctly
- book groups can be created and retrieved through the supported tool surface

## 8. Migration approach

No destructive migration is needed.

1. Add `book` to the schema and code enums/checks.
2. Add path inference for `Book/`.
3. Reclassify existing book-level PDFs from `unknown` (or other stopgap types) to `book`.
4. Leave `book_exercise` unchanged for exercise-level material.

For the newly moved `PP Chinese` files, a follow-up classification pass could set:

- `doc_type='book'`
- `subject='chinese'`
- `metadata.unit='模拟考卷 3'`, `metadata.unit='作文 2'`, `metadata.unit='作文 范文'`, etc., depending on the file
- membership in one `group_type='book'` group labeled `Power Pack Chinese PSLE`

---

## 9. Recommendation

Adopt `book` as both a new `doc_type` and a new `group_type`, and treat `Book/` as a first-class inferred content folder.

This preserves the existing meaning of `file_type`, keeps `book_exercise` precise, and makes the new DaydreamEdu `Book/` organization visible to the registry at both levels:

- per-file classification via `doc_type='book'`
- shared logical identity via `group_type='book'`
