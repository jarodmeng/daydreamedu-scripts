# pdf_file_manager — Specification

> API, operation contract, and implementation status.
>
> See [README.md](./README.md) for overview; [DATA_MODEL.md](./DATA_MODEL.md) for field-level data model reference; [ARCHITECTURE.md](./ARCHITECTURE.md) for schema and integrations.
>
> Decision log: [DECISIONS.md](./DECISIONS.md)

This document specifies the **operations** (Python API), **operation types** (for the audit log), **edge cases**, and **implementation status**. Data classes and field semantics live in [DATA_MODEL.md](./DATA_MODEL.md). All schema details are in ARCHITECTURE.md.

---

## Operations

### C — Create / Register

#### `scan_for_new_files(roots=None, min_savings_pct=10, dry_run=False) -> list[ScanResult]`

Walk configured scan roots (or override list), find direct-child `*.pdf` files in each root, compare against the registry, and process any that are new. `scan_for_new_files(...)` does **not** recurse into nested subfolders; callers that want nested folders processed must pass those folders explicitly as roots. If `dry_run=True`, no disk or database changes are made; the return value describes what would have been done for each would-be-processed file. In dry-run mode, each `ScanResult.file` is still populated with **inferred** fields (`doc_type`, `subject`, `is_template`, `metadata`, and `file_type` where applicable) so previews match a real run rather than placeholder `unknown` / empty metadata.

When `roots` is a non-empty override list, each resolved absolute path is looked up against configured `scan_roots` rows so that a matching registered root’s `student_id` is used for files under that path—the same as when scanning all configured roots without an override.

Student assignment precedence during scan:

1. explicit/configured `scan_root.student_id` (including when the root comes from the `roots=[...]` override and that path is registered as a scan root)
2. fallback inference from a registered `students.email` path segment

**Book-aware behavior:** For paths under `.../Book/<book name>/...`, scan applies path inference so files are registered with `doc_type='book'`, infers `metadata.unit` from filename where possible, and syncs a `group_type='book'` file group for that folder using `<book name>` as the group label. Only `main` files are added to the book group.

**For each unregistered file with `_c_` prefix:**
1. Register as `file_type='main'` (no compress). Apply `student_id` from the scan root when set, otherwise infer it from a registered student email segment in the path. Apply path-based inference for subject, doc_type, metadata, and **is_template**: path with no email segment and a grade/scope segment → `True`; path with email segment → `False`; **Chinese exams only:** when `subject='chinese'` and `doc_type='exam'`, `metadata.chinese_variant` is inferred from the filename: `higher` for names containing `高华` or `.hc.`, `standard` for names containing `华文` or `.chinese.` (**Standard** 华文 exams — not SEAB Foundation Chinese Language). Skip compress step.

**For each unregistered file without `_raw_` or `_c_` prefix:**
1. Call `compress_and_register(path, ...)` (see below). When the path is not yet in the registry, `compress_and_register` registers it first, then compresses.
2. Populate `student_id` from the scan root's `student_id` if set; otherwise fall back to a registered student email found in the path (on the resulting main file).

**For each unregistered file with `_raw_` prefix:**
1. Register as `file_type='raw'`.
2. Look for the corresponding main file (path `<name>` or `_c_<name>` after stripping `_raw_`) — if found in registry, create `raw_source` / `main_version` relations and set `has_raw=True` on the main file.

**Already registered files** (matched by absolute path) are skipped.

Each newly processed file produces `register` and (where applicable) `compress` + `link` entries in `operation_log`. `doc_type` defaults to `'unknown'`; classify afterwards with `update_metadata`.

#### `register_file(path, file_type=None, doc_type='unknown', student_id=None, subject=None, is_template=False, metadata=None, notes=None) -> PdfFile`

Manually register a single file without compression. Infers `file_type` from filename unless overridden: `_raw_` → `raw`, `_c_` → `main`, else `unknown`. If `student_id` is not provided, the manager attempts to infer it from a registered `students.email` path segment. Raises `FileNotFoundError` if path absent. Raises `AlreadyRegisteredError` if already registered. Writes a `register` log entry.

#### `compress_and_register(file_id_or_path, force=False, min_savings_pct=10, preserve_input=False, **compress_kwargs) -> CompressResult`

Composite: register (if needed) then compress. When given a **path** that is not yet in the registry, the file is registered first as `file_type='unknown'`, then the steps below run. When given a **file_id** or a path that is already registered, the existing record is used.

1. **Resolve to a record:** If `file_id_or_path` is a path with no matching registry row, call `register_file(path)` (creating `file_type='unknown'`), then use that record. Otherwise look up by file_id or path; raise `NotFoundError` if absent.
2. Validate `file_type == 'unknown'` (not yet processed); raise `ValueError` if already `main` or `raw`.
3. If `preserve_input=False` (default, DaydreamEdu mode):
   - Run `mv <name> _raw_<name>` (archive original before compression).
   - Call `compress_pdf.compress_pdf(input_path="_raw_<name>", output_name="_c_<name>", ...)`.
     The compressed file is written as `_c_<name>` so it is immediately clear the file is compressed.
   - **If savings ≥ `min_savings_pct`:**
     - Register `_c_<name>` as `file_type='main'`; populate `page_count`. Write `compress` log entry.
     - Register `_raw_<name>` as `file_type='raw'`; inherit `student_id`, `doc_type`, `metadata`. Write `register` log entry.
     - Create `raw_source` and `main_version` relations; set `has_raw=True` on main file. Write `link` log entry.
   - **If savings < `min_savings_pct`:**
     - Run `mv _raw_<name> <name>` (restore original; compression not worthwhile).
     - Update file's `file_type` to `'main'`; populate `page_count`. `has_raw` remains `False`.
     - Write `compress` log entry with `skipped=True` note.
4. If `preserve_input=True` (GoodNotes-safe mode):
   - Treat `<name>` as the raw source; do **not** rename or move it.
   - Call `compress_pdf.compress_pdf(input_path="<name>", output_name="_c_<name>", ...)` to create a sibling `_c_<name>` main.
   - **If savings ≥ `min_savings_pct`:**
     - Update the existing row for `<name>` to `file_type='raw'` (or insert a new raw row if the input was only ever scanned by path).
     - Register `_c_<name>` as `file_type='main'`; inherit `student_id`, `doc_type`, `metadata`; set `has_raw=True`.
     - Create `raw_source` and `main_version` relations between `<name>` and `_c_<name>`. Write `compress` and `link` log entries.
   - **If savings < `min_savings_pct`:**
     - Keep `<name>` as `file_type='main'`; do not create a persistent `_c_` file (any temporary copy is removed).
     - Write `compress` log entry with `skipped=True` note.
7. Return `CompressResult` augmented with the main file's UUID.

**Invariant metadata parity:** raw and main records created or maintained by this workflow are expected to share document-level metadata such as `subject`, `doc_type`, `student_id`, `is_template`, `metadata.grade_or_scope`, `metadata.content_folder`, and `metadata.chinese_variant` when present.

---

### R — Read / Search

> Reads do not produce `operation_log` entries.

#### `get_file(file_id) -> PdfFile`

Look up a single file by UUID.

#### `find_files(query=None, file_type=None, doc_type=None, student_id=None, subject=None, is_template=None, has_raw=None) -> list[PdfFile]`

| Parameter | Behaviour |
|-----------|-----------|
| `query` | Case-insensitive substring match on `name` |
| `file_type` | Filter to `'main'`, `'raw'`, or `'unknown'` |
| `doc_type` | Filter to a specific document type |
| `student_id` | Filter to a specific student |
| `subject` | Filter by `subject` column (`'english'`, `'math'`, `'science'`, `'chinese'`) |
| `is_template` | `True` → templates only; `False` → completions/non-templates only; `None` → no filter |
| `has_raw` | `True` → main files with a raw archive; `False` → main files without one |

#### `get_related_files(file_id) -> list[tuple[PdfFile, str]]`

Return the raw archive or main counterpart (raw_source/main_version only). Each element is `(PdfFile, relation_type)`.

#### `get_template(file_id) -> PdfFile | None`

If this file is a completion (has a `completed_from` relation), return its template. Otherwise `None`.

#### `get_completions(template_id) -> list[PdfFile]`

Return all completed files that were filled from this template (all targets of `template_for` from this file).

#### `open_file(file_id_or_path)`

Open the PDF in macOS Preview (`open <path>`). Raises `FileNotFoundError` if no longer on disk.

#### `get_operation_log(file_id=None, group_id=None, operation=None, since=None, log_id=None) -> list[OperationRecord]`

Query `operation_log`. All parameters optional. If `log_id` is set, return at most one entry with that id (empty list if not found). Otherwise results ordered `performed_at ASC`.

#### `get_book_answer_mapping(unit_file_id_or_path) -> BookAnswerMapping | None`

Return the current book-answer mapping for one registered book unit file, or `None` when no mapping exists.

#### `list_book_answer_mappings(book_group_id=None, answer_file_id_or_path=None, source=None) -> list[BookAnswerMapping]`

Return current book-answer mappings, optionally filtered by:

- `book_group_id`: must refer to a `group_type='book'` file group; filters by mapped unit membership
- `answer_file_id_or_path`: filters to mappings that point at one specific answer file
- `source`: filters by provenance such as `manual_verified` or `imported_ground_truth`

---

### U — Update

#### `rename_file(file_id_or_path, new_name) -> PdfFile`

If the registry path exists on disk: run `mv <old> <new>`. Update `name`, `path`, `updated_at`. Write `rename` log entry. Raises `ValueError` if the destination path is already occupied by another file.

If the **registry path is missing** on disk but **`<parent>/<new_name>`** already exists (external rename): update `name`, `path`, and `updated_at` only (no `mv`). When the destination is a regular file, also set **`size_bytes`** from that file. Write `rename` log entry. Does not automatically rename the paired `_raw_` archive — call separately if needed.

#### `move_file(file_id_or_path, new_dir) -> PdfFile`

Run `mv <old> <new_dir/name>`. Update `path`, `updated_at`. Write `move` log entry. Raises `ValueError` if destination exists.

#### `update_metadata(file_id_or_path, doc_type=None, student_id=None, subject=None, is_template=None, metadata=None, notes=None, file_type=None) -> PdfFile`

Update `doc_type`, `student_id`, `subject`, `is_template`, `metadata` (merged, not replaced), `notes`, and/or **`file_type`** (`'main'`, `'raw'`, or `'unknown'`) without touching disk. Primary classification method. Raises `ValueError` if `subject` is not one of the allowed values, or if `file_type` is not one of `main`, `raw`, `unknown`. Writes `update_metadata` log entry.

When any invariant document-level fields are updated on a file that is part of a linked raw/main pair, the same changes are propagated to the counterpart record to keep the pair in sync. This currently applies to:

- `doc_type`
- `student_id`
- `subject`
- `is_template`
- `metadata`

(`file_type` itself is not copied to the counterpart.) Counterpart selection for that sync uses the row’s **`file_type` after this update**, so promoting `unknown` → `main` in the same call as `doc_type` / `subject` / `metadata` still propagates those fields to the linked raw.

#### `repair_main_raw_metadata_drift() -> list[dict]`

Audit linked raw/main pairs for invariant metadata drift and repair it by copying canonical main-file values onto the linked raw record. Returns one item per repaired pair, including the raw id, main id, and the fields that were synchronized.

---

### D — Delete

#### `delete_file(file_id_or_path, keep_related=False, notes=None, deleted_by='api') -> OperationRecord`

1. Look up record.
2. Snapshot `file_relations` and `file_group_members` rows as JSON.
3. Write `delete` log entry: full record + snapshots in `before_state`.
4. Remove from any `file_group_members`. If a group's `anchor_id` pointed here, set `anchor_id=NULL` and log a warning.
5. Run `rm <path>`. If already absent, log warning and continue.
6. Delete `pdf_files` row (cascades to `file_relations`).
7. If `keep_related=False` and file was `main`: also delete the `_raw_` archive via recursive `delete_file` (`performed_by='cascade'`).
8. If `keep_related=False` and file was `raw`: clear `has_raw=False` on the corresponding main file.
9. Return `OperationRecord`.

---

### File Groups

#### `create_file_group(label, group_type='collection', anchor_id=None, notes=None) -> FileGroup`
Create empty group. Writes `group_create` log entry.

#### `add_to_file_group(group_id, file_id, role=None) -> FileGroupMember`
Only `main` files may be added (raises `ValueError` for `raw` files). `role` is accepted for backward compatibility and mapped to `metadata.unit` when the file has no unit yet; new function labels should use `metadata.unit` as the canonical location. Writes `group_add` log entry.

#### `remove_from_file_group(group_id, file_id)`
Clears `anchor_id` if pointed here. Writes `group_remove` log entry.

#### `set_file_group_anchor(group_id, file_id)`
Writes `group_anchor_set` log entry.

#### `set_book_answer_mapping(unit_file_id_or_path, answer_file_id_or_path, answer_page_start, answer_page_end, starts_mid_page=False, ends_mid_page=False, source=None, notes=None) -> BookAnswerMapping`

Create or update the current mapping for a registered book unit file. This is an upsert keyed by `unit_file_id`.

Validation:

- `answer_page_start <= answer_page_end`
- both files must exist
- both files must have `file_type='main'`
- both files must have `doc_type='book'`
- both files may come from different `group_type='book'` file groups

Writes `book_answer_mapping_set` for first insert and `book_answer_mapping_update` for later updates.

#### `delete_book_answer_mapping(unit_file_id_or_path)`

Delete the current mapping for a registered book unit file. Raises `NotFoundError` if no mapping exists. Writes `book_answer_mapping_delete`.

#### `update_file_group_notes(group_id, notes) -> FileGroup`
Writes `group_update_notes` log entry.

#### `get_file_group(group_id) -> FileGroup`
Return group with all members hydrated.

#### `list_file_groups(group_type=None) -> list[FileGroup]`
Return all groups, optionally filtered.

#### `get_file_group_membership(file_id) -> list[FileGroup]`
Return all groups the file belongs to.

#### `open_file_group(group_id)`
Open anchor file in Preview. Raises `ConfigError` if no anchor set.

#### `delete_file_group(group_id)`
Delete the group record and all `file_group_members` rows. Member files remain in the registry and on disk. Writes `group_delete` log entry with full members snapshot.

#### `suggest_groups() -> list[SuggestedGroup]`
Find candidate groups by matching `main` files on `student_id` + `subject` + `metadata.exam_date`. Returns suggestions without creating any groups. Only files with `doc_type='exam'`, `is_template=False`, and a populated `exam_date` in metadata are candidates.

---

### Raw ↔ Main Relations

#### `link_files(source_id, target_id, relation_type) -> FileRelation`
Manually create a `raw_source` or `main_version` relation. Inverse row created automatically. Updates `has_raw` on the main file. Writes `link` log entry.

#### `unlink_files(source_id, target_id)`
Remove relation pair. Updates `has_raw` if it was a raw↔main relation. Writes `unlink` log entry.

---

### Template relations

#### `link_to_template(completed_id, template_id, inherit_metadata=True) -> FileRelation`

Link a completed file to its template. Creates `template_for` (template → completed) and `completed_from` (completed → template) rows. If `inherit_metadata=True`, copies `subject`, `doc_type` (if completed has `doc_type='unknown'`), and merges `metadata` from template into completed (does not overwrite existing keys on completed). Optionally warn if `page_count` differs. **Validation:** Raises `ValueError` if the completed file already has a template; if either file is not `file_type='main'`; if the template does not have `is_template=True`; or if the completed file does not have `is_template=False`. Writes a `link_template` log entry.

#### `unlink_template(completed_id)`

Remove the completed↔template relation for this file. Writes an `unlink_template` log entry.

#### `link_goodnotes_template_for_file(main_path, auto_fix_template=True, inherit_metadata=True) -> GoodNotesTemplateLinkOutcome`

Resolve the matching DaydreamEdu `_c_` template path for one registered GoodNotes main file, optionally auto-fix `is_template=True` on that already-registered resolved target, then call `link_to_template`. Template resolution is **general-scope only**: the mirrored DaydreamEdu folder with the student-email segment removed is searched; student-scope DaydreamEdu folders are not searched. Raises `NotFoundError` if the completion is not registered or if the resolved template exists on disk but is not registered. Raises `ValueError` if the path is not under `GoodNotes/`, if the completion is not a non-template `main`, if a general-scope template path cannot be derived or found, if the resolved template is not a `main`, or if the completion is already linked to a different template.

#### `link_goodnotes_templates_for_root(root, dry_run=False, auto_fix_template=True, inherit_metadata=True) -> list[GoodNotesTemplateLinkOutcome]`

Iterate over registered GoodNotes main files under a root and apply the single-file helper. In `dry_run=True` mode, return per-file outcomes/messages without mutating the registry.

---

### Student Management

#### `add_student(id, name, email=None) -> Student`
Register a student. `id` is a short human-readable string (e.g. `'winston'`).

#### `get_student(student_id) -> Student`
#### `list_students() -> list[Student]`

---

### Configuration

#### `add_scan_root(path, student_id=None)` / `remove_scan_root(path)` / `list_scan_roots() -> list[ScanRoot]`
Manage scan roots. `student_id` links a root to a student so discovered files are auto-tagged. Config changes are not logged.

For `add_scan_root(path, student_id=None)`, `student_id` precedence is:

1. Explicit `student_id` argument (if provided)
2. Inference from a unique registered `students.email` path segment
3. `None` if no unique match exists

---

## Operation types

| `operation` | Trigger | `file_id` | `group_id` | `before_state` | `after_state` |
|-------------|---------|-----------|------------|----------------|---------------|
| `register` | `register_file` or raw archive during `compress_and_register` | ✓ | — | NULL | file record |
| `compress` | `compress_and_register` (main file) | ✓ | — | old record (`unknown`) | new record (`main`) |
| `rename` | `rename_file` | ✓ | — | old file record | new file record |
| `move` | `move_file` | ✓ | — | old file record | new file record |
| `update_metadata` | `update_metadata` | ✓ | — | old file record | new file record |
| `link` | `link_files` | ✓ (main) | — | old main record | new main record |
| `unlink` | `unlink_files` | ✓ (main) | — | old main record | new main record |
| `link_template` | `link_to_template` | ✓ (completed) | — | old completed record | new completed record (after metadata inherit) |
| `unlink_template` | `unlink_template` | ✓ (completed) | — | old completed record | new completed record |
| `delete` | `delete_file` | ✓ | — | file record + relations + group memberships | NULL |
| `group_create` | `create_file_group` | — | ✓ | NULL | group record |
| `group_add` | `add_to_file_group` | ✓ | ✓ | NULL | member record |
| `group_remove` | `remove_from_file_group` | ✓ | ✓ | member record | NULL |
| `group_anchor_set` | `set_file_group_anchor` | ✓ | ✓ | old group record | new group record |
| `group_update_notes` | `update_file_group_notes` | — | ✓ | old group record | new group record |
| `group_delete` | `delete_file_group` | — | ✓ | group record + members | NULL |
| `book_answer_mapping_set` | first `set_book_answer_mapping` for a unit | ✓ (unit) | ✓ (book group) | NULL | mapping payload |
| `book_answer_mapping_update` | later `set_book_answer_mapping` for the same unit | ✓ (unit) | ✓ (book group) | old mapping payload | new mapping payload |
| `book_answer_mapping_delete` | `delete_book_answer_mapping` | ✓ (unit) | ✓ (book group) | mapping payload | NULL |

**Reads are not logged.**

---

## Python library interface

```python
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

mgr = PdfFileManager()
mgr = PdfFileManager(db_path="/custom/path/registry.db")

# One-time setup
mgr.add_student("winston", name="Test Student A", email="<student email>")
mgr.add_student("emma",    name="Test Student B", email="<student email>")
mgr.add_scan_root(
    "/path/to/GoogleDrive-studentA@example.com/My Drive/Student A documents",
    student_id="winston"
)
mgr.add_scan_root(
    "/path/to/GoogleDrive-studentB@example.com/My Drive/Student B documents",
    student_id="emma"
)
mgr.add_scan_root(
    "/path/to/My Drive/DaydreamEdu"  # or os.environ["DAYDREAMEDU_ROOT"], or ai_study_buddy/files/roots.py::resolve_daydreamedu_root()
    # GoodNotes scan roots: os.environ["GOODNOTES_ROOT"], ai_study_buddy/local_goodnotes_root.txt, or resolve_goodnotes_root()
)

# Scan + auto-compress
results = mgr.scan_for_new_files()

# Classify
f = mgr.find_files(doc_type="unknown")[0]
f = mgr.update_metadata(f.id, doc_type="exam", subject="chinese", metadata={
    "paper_type": "eoy", "grade": "p6",
    "school": "st_gabriels", "exam_date": "2025-11-12"
})

# Suggest groups after classification
suggestions = mgr.suggest_groups()

# Create exam group
g = mgr.create_file_group("Chinese EoY P6 2025", group_type="exam")
mgr.update_metadata(p1.id,  metadata={"unit": "paper1"})
mgr.update_metadata(p2q.id, metadata={"unit": "paper2_questions"})
mgr.update_metadata(p2a.id, metadata={"unit": "paper2_answers"})
mgr.add_to_file_group(g.id, p1.id)
mgr.add_to_file_group(g.id, p2q.id)
mgr.add_to_file_group(g.id, p2a.id)
mgr.set_file_group_anchor(g.id, p2a.id)

# Search
exams     = mgr.find_files(doc_type="exam", student_id="winston")
templates = mgr.find_files(is_template=True, subject="science")
untagged  = mgr.find_files(doc_type="unknown")
no_raw    = mgr.find_files(file_type="main", has_raw=False)

# Link completed file to template (inherit subject, doc_type, metadata)
mgr.link_to_template(winston_completed.id, blank_wa2.id, inherit_metadata=True)
tpl = mgr.get_template(winston_completed.id)
all_completions = mgr.get_completions(blank_wa2.id)

# Map a book unit to pages in its answer file
mapping = mgr.set_book_answer_mapping(
    unit_file.id,
    answer_file.id,
    35,
    40,
    starts_mid_page=True,
    source="manual_verified",
)
same_book_mappings = mgr.list_book_answer_mappings(book_group_id=book_group.id)
```

For all returned data class shapes (`PdfFile`, `FileGroup`, `FileGroupMember`, and others), see [DATA_MODEL.md](./DATA_MODEL.md).

---

## Edge cases and guard rails

| Situation | Behaviour |
|-----------|-----------|
| `register_file` on a non-existent path | Raise `FileNotFoundError` |
| `register_file` on an already-registered path | Raise `AlreadyRegisteredError` |
| `set_book_answer_mapping` with a non-book file or raw file | Raise `ValueError` |
| `set_book_answer_mapping` where unit and answer do not share a `group_type='book'` group | Raise `ValueError` |
| `delete_book_answer_mapping` when no mapping exists for the unit | Raise `NotFoundError` |
| `compress_and_register` on a file with `file_type != 'unknown'` | Raise `ValueError` |
| `compress_and_register` and the `_raw_` rename destination already exists | Raise `ValueError`; abort; no changes |
| `delete_file` and file already absent from disk | Log warning; proceed with registry removal and `delete` log entry |
| `mv` / `rename` and destination path already exists (and source path still exists on disk) | Raise `ValueError`; no changes; no log entry |
| `rename_file` and source path missing but destination path already exists | DB-only sync: update `name`, `path`, `updated_at`; if destination is a file, refresh `size_bytes`; write `rename` log |
| `update_metadata` with invalid `file_type` | Raise `ValueError`; must be `main`, `raw`, or `unknown` |
| `update_metadata` promoting `unknown` → `main` with `doc_type` / `subject` / `metadata` on a linked main | Invariant fields sync to raw using the **updated** `file_type` |
| `scan_for_new_files` with no scan roots configured | Raise `ConfigError` pointing to adding a scan root programmatically or through manager configuration |
| `_raw_` file found during scan but main file not registered | Register as `file_type='raw'`; skip auto-link; warn to run `link` manually |
| Two files have the same `name` but different `path` | Both are valid distinct entries |
| Database file does not exist at startup | Auto-created with schema on first use |
| `delete_file` on the anchor of a file group | Set `anchor_id=NULL`; log warning; continue |
| `add_to_file_group` with a `raw` file | Raise `ValueError`; only `main` files may join groups |
| `add_to_file_group` on a file already in a different group | Allowed; log info |
| `open_file_group` with no anchor set | Raise `ConfigError`; suggest `group anchor` |
| `delete_file_group` | Only group record and memberships are removed; member files remain in the registry and on disk |
| `update_metadata` with partial `metadata` dict | Merges into existing metadata; unmentioned keys preserved; merged metadata is synced across linked raw/main pairs |
| `update_metadata` / `register_file` with an unrecognised `subject` value | Raise `ValueError` listing the allowed values |
| `link_to_template` with completed already linked to a template | Raise `ValueError` |
| `link_to_template` with a file that is not `file_type='main'` | Raise `ValueError` |
| `link_to_template` with template having `is_template=False` or completed having `is_template=True` | Raise `ValueError` |
| raw/main pair has drift on invariant metadata | `repair_main_raw_metadata_drift()` copies canonical main values onto raw |
| `suggest_groups` called on unclassified files | They are simply excluded from suggestions; no error |
| Any operation fails mid-way (disk op succeeds, DB update fails) | Attempt to reverse disk change; log failure with full context |

---

## Implementation status

| Step | Status |
|------|--------|
| Database schema + auto-creation (incl. `students` table) | ✅ Implemented |
| `PdfFileManager` class | ✅ Implemented |
| Student management (`add_student`, `get_student`, `list_students`) | ✅ Implemented |
| Scan root management (with `student_id`) | ✅ Implemented |
| `scan_for_new_files` (auto-compress + archive) | ✅ Implemented |
| `register_file` | ✅ Implemented |
| `compress_and_register` (compress → rename → archive) | ✅ Implemented |
| `find_files` / `get_file` / `get_file_by_path` | ✅ Implemented |
| `open_file` | ✅ Implemented |
| `rename_file` / `move_file` | ✅ Implemented |
| `update_metadata` | ✅ Implemented |
| `delete_file` | ✅ Implemented |
| Raw ↔ main relations (`link_files`, `unlink_files`) | ✅ Implemented |
| Template relations (`link_to_template`, `unlink_template`, `get_template`, `get_completions`) | ✅ Implemented |
| File group operations | ✅ Implemented |
| `suggest_groups` | ✅ Implemented |
| `operation_log` writes on all C/U/D operations | ✅ Implemented |
| `get_operation_log` query | ✅ Implemented |
| Backup utility (`backup_pdf_registry.py`) | ✅ Implemented |
| Backup tiering utility (`apply_backup_tiering.py`) | ✅ Implemented |
| Wake automation (`run_backup_on_wake.sh`) with timestamp + tiering | ✅ Implemented |
| Built-in CLI layer | ❌ Removed |
