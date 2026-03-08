# pdf_file_manager — Specification

> API, CLI, operation contract, and implementation status.
>
> See [VISION.md](./VISION.md) for purpose and workflow; [ARCHITECTURE.md](./ARCHITECTURE.md) for schema, data model, and integrations.
>
> Decision log: [DECISIONS.md](./DECISIONS.md)

This document specifies the **operations** (Python API and CLI), **operation types** (for the audit log), **data classes**, **edge cases**, and **implementation status**. All schema and metadata details are in ARCHITECTURE.md.

---

## Operations

### C — Create / Register

#### `scan_for_new_files(roots=None, min_savings_pct=10, dry_run=False) -> list[ScanResult]`

Walk configured scan roots (or override list), find every `*.pdf`, compare against registry, and process any that are new. If `dry_run=True`, no disk or database changes are made; the return value describes what would have been done for each would-be-processed file.

**For each unregistered file with `_c_` prefix:**
1. Register as `file_type='main'` (no compress). Apply scan root `student_id` and path-based inference. Skip compress step.

**For each unregistered file without `_raw_` or `_c_` prefix:**
1. Call `compress_and_register(path, ...)` (see below). When the path is not yet in the registry, `compress_and_register` registers it first, then compresses.
2. Populate `student_id` from the scan root's `student_id` if set (on the resulting main file).

**For each unregistered file with `_raw_` prefix:**
1. Register as `file_type='raw'`.
2. Look for the corresponding main file (path `<name>` or `_c_<name>` after stripping `_raw_`) — if found in registry, create `raw_source` / `main_version` relations and set `has_raw=True` on the main file.

**Already registered files** (matched by absolute path) are skipped.

Each newly processed file produces `register` and (where applicable) `compress` + `link` entries in `operation_log`. `doc_type` defaults to `'unknown'`; classify afterwards with `update_metadata`.

#### `register_file(path, file_type=None, doc_type='unknown', student_id=None, subject=None, is_template=False, metadata=None, notes=None) -> PdfFile`

Manually register a single file without compression. Infers `file_type` from filename unless overridden: `_raw_` → `raw`, `_c_` → `main`, else `unknown`. Raises `FileNotFoundError` if path absent. Raises `AlreadyRegisteredError` if already registered. Writes a `register` log entry.

#### `compress_and_register(file_id_or_path, force=False, min_savings_pct=10, **compress_kwargs) -> CompressResult`

Composite: register (if needed) then compress. When given a **path** that is not yet in the registry, the file is registered first as `file_type='unknown'`, then the steps below run. When given a **file_id** or a path that is already registered, the existing record is used.

1. **Resolve to a record:** If `file_id_or_path` is a path with no matching registry row, call `register_file(path)` (creating `file_type='unknown'`), then use that record. Otherwise look up by file_id or path; raise `NotFoundError` if absent.
2. Validate `file_type == 'unknown'` (not yet processed); raise `ValueError` if already `main` or `raw`.
3. Run `mv <name> _raw_<name>` (archive original before compression).
4. Call `compress_pdf.compress_pdf(input_path="_raw_<name>", output_name="_c_<name>", ...)`.
   The compressed file is written as `_c_<name>` so it is immediately clear the file is compressed.
5. **If savings ≥ `min_savings_pct`:**
   - Register `_c_<name>` as `file_type='main'`; populate `page_count`. Write `compress` log entry.
   - Register `_raw_<name>` as `file_type='raw'`; inherit `student_id`, `doc_type`, `metadata`. Write `register` log entry.
   - Create `raw_source` and `main_version` relations; set `has_raw=True` on main file. Write `link` log entry.
6. **If savings < `min_savings_pct`:**
   - Run `mv _raw_<name> <name>` (restore original; compression not worthwhile).
   - Update file's `file_type` to `'main'`; populate `page_count`. `has_raw` remains `False`.
   - Write `compress` log entry with `skipped=True` note.
7. Return `CompressResult` augmented with the main file's UUID.

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

---

### U — Update

#### `rename_file(file_id_or_path, new_name) -> PdfFile`

Run `mv <old> <new>`. Update `name`, `path`, `updated_at`. Write `rename` log entry. Raises `ValueError` if destination exists. Does not automatically rename the paired `_raw_` archive — call separately if needed.

#### `move_file(file_id_or_path, new_dir) -> PdfFile`

Run `mv <old> <new_dir/name>`. Update `path`, `updated_at`. Write `move` log entry. Raises `ValueError` if destination exists.

#### `update_metadata(file_id_or_path, doc_type=None, student_id=None, subject=None, is_template=None, metadata=None, notes=None) -> PdfFile`

Update `doc_type`, `student_id`, `subject`, `is_template`, `metadata` (merged, not replaced), and/or `notes` without touching disk. Primary classification method. Raises `ValueError` if `subject` is not one of the allowed values. Writes `update_metadata` log entry.

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
Only `main` files may be added (raises `ValueError` for `raw` files). Writes `group_add` log entry.

#### `remove_from_file_group(group_id, file_id)`
Clears `anchor_id` if pointed here. Writes `group_remove` log entry.

#### `set_file_group_anchor(group_id, file_id)`
Writes `group_anchor_set` log entry.

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

**Reads are not logged.**

---

## Python library interface

```python
from pdf_file_manager import PdfFileManager

mgr = PdfFileManager()
mgr = PdfFileManager(db_path="/custom/path/registry.db")

# One-time setup
mgr.add_student("winston", name="Winston Meng", email="winston.ry.meng@gmail.com")
mgr.add_student("emma",    name="Emma Meng",    email="emma.rs.meng@gmail.com")
mgr.add_scan_root(
    "/Users/jarodm/Library/CloudStorage/GoogleDrive-winston.ry.meng@gmail.com/My Drive/Winston Primary School documents",
    student_id="winston"
)
mgr.add_scan_root(
    "/Users/jarodm/Library/CloudStorage/GoogleDrive-emma.rs.meng@gmail.com/My Drive/Emma Primary School Documents",
    student_id="emma"
)
mgr.add_scan_root(
    "/Users/jarodm/Library/CloudStorage/GoogleDrive-genrong.meng@gmail.com/My Drive/DaydreamEdu"
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
mgr.add_to_file_group(g.id, p1.id,  role="paper1")
mgr.add_to_file_group(g.id, p2q.id, role="paper2_questions")
mgr.add_to_file_group(g.id, p2a.id, role="paper2_answers")
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
```

### Data classes

```python
@dataclass
class Student:
    id: str
    name: str
    email: str | None
    added_at: str

@dataclass
class ScanRoot:
    id: str
    path: str
    student_id: str | None
    added_at: str

@dataclass
class PdfFile:
    id: str
    name: str
    path: str
    file_type: str           # 'main' | 'raw' | 'unknown'
    doc_type: str            # 'exam' | 'worksheet' | 'book_exercise' | 'activity' | 'practice' | 'notes' | 'unknown'
    student_id: str | None
    subject: str | None      # 'english' | 'math' | 'science' | 'chinese'
    is_template: bool        # True = blank/master; False = completion or non-template
    size_bytes: int | None
    page_count: int | None
    has_raw: bool            # True = main file has a _raw_ archive
    metadata: dict | None
    added_at: str
    updated_at: str
    notes: str | None

@dataclass
class FileRelation:
    id: str
    source_id: str
    target_id: str
    relation_type: str       # 'raw_source' | 'main_version'
    created_at: str

@dataclass
class FileGroup:
    id: str
    label: str
    group_type: str          # 'exam' | 'book_exercise' | 'collection'
    anchor_id: str | None
    created_at: str
    notes: str | None
    members: list[FileGroupMember]

@dataclass
class FileGroupMember:
    group_id: str
    file_id: str
    role: str | None
    added_at: str
    file: PdfFile

@dataclass
class SuggestedGroup:
    group_type: str
    candidate_files: list[PdfFile]
    match_basis: dict        # e.g. {"student_id": "winston", "subject": "chinese", "exam_date": "2025-11-12"}  (subject from column, exam_date from metadata)

@dataclass
class OperationRecord:
    id: str
    operation: str
    file_id: str | None
    group_id: str | None
    performed_at: str
    performed_by: str | None
    before_state: dict | None
    after_state: dict | None
    notes: str | None

@dataclass
class ScanResult:
    file: PdfFile            # the main file
    raw_archive: PdfFile | None   # the _raw_ archive created during compression, if any
    compressed: bool         # True = compression was performed; False = file was already optimal
```

---

## CLI interface

```bash
# --- Student management ---
python pdf_file_manager.py student add winston "Winston Meng" --email winston.ry.meng@gmail.com
python pdf_file_manager.py student list

# --- Config ---
python pdf_file_manager.py config add-root /path/to/drive --student-id winston
python pdf_file_manager.py config remove-root /path/to/drive
python pdf_file_manager.py config list-roots

# --- Scan ---
python pdf_file_manager.py scan                    # discovers, compresses, and archives new files
python pdf_file_manager.py scan --dry-run          # show what would happen without writing
python pdf_file_manager.py scan --roots /path/to/drive
python pdf_file_manager.py scan --suggest-groups   # after scan, print grouping suggestions

# --- Register (manual, no compression) ---
python pdf_file_manager.py register /path/to/file.pdf [--doc-type exam] [--student-id winston] [--subject math] [--is-template]

# --- Compress (manual, single file) ---
python pdf_file_manager.py compress <id|path> [--force] [--min-savings 10]

# --- Classify / update metadata ---
python pdf_file_manager.py classify <id|path> --doc-type exam --student-id winston \
    --subject math --metadata '{"paper_type":"wa","exam_date":"2025-09-15"}'
python pdf_file_manager.py classify <id|path> --is-template
python pdf_file_manager.py classify <id|path> --notes "scored by teacher"

# --- List / Show ---
python pdf_file_manager.py list
python pdf_file_manager.py list --student winston
python pdf_file_manager.py list --subject math
python pdf_file_manager.py list --templates          # is_template=True only
python pdf_file_manager.py list --doc-type exam
python pdf_file_manager.py list --doc-type unknown          # unclassified
python pdf_file_manager.py list --type main --no-raw        # main files without a raw archive
python pdf_file_manager.py list --query "math"
python pdf_file_manager.py list --grouped
python pdf_file_manager.py show <id|path>

# --- Open ---
python pdf_file_manager.py open <id|path>                   # opens in Preview

# --- Rename / Move ---
python pdf_file_manager.py rename <id|path> <new_name.pdf>
python pdf_file_manager.py mv <id|path> /new/directory/

# --- Delete ---
python pdf_file_manager.py rm <id|path> [--keep-related] [--notes "reason"]

# --- Template link (completed → template) ---
python pdf_file_manager.py template link <completed_id|path> <template_id|path> [--no-inherit]
python pdf_file_manager.py template unlink <completed_id|path>

# --- File groups ---
python pdf_file_manager.py group create "Chinese EoY P6 2025" --type exam
python pdf_file_manager.py group create "Math 6A Ch3 Exercise 3A" --type book_exercise
python pdf_file_manager.py group add <group_id> <file_id|path> [--role paper2_answers]
python pdf_file_manager.py group remove <group_id> <file_id|path>
python pdf_file_manager.py group anchor <group_id> <file_id|path>
python pdf_file_manager.py group show <group_id>
python pdf_file_manager.py group list [--type exam]
python pdf_file_manager.py group open <group_id>
python pdf_file_manager.py group delete <group_id>
python pdf_file_manager.py group suggest               # suggest groups based on metadata overlap

# --- Operation log ---
python pdf_file_manager.py log
python pdf_file_manager.py log --file <id|path>
python pdf_file_manager.py log --group <group_id>
python pdf_file_manager.py log --operation delete
python pdf_file_manager.py log --since 2025-01-01
python pdf_file_manager.py log --id <log_entry_uuid>

# --- Global flags ---
python pdf_file_manager.py --db /custom/path/registry.db <command>
python pdf_file_manager.py --verbose <command>
```

---

## Edge cases and guard rails

| Situation | Behaviour |
|-----------|-----------|
| `register_file` on a non-existent path | Raise `FileNotFoundError` |
| `register_file` on an already-registered path | Raise `AlreadyRegisteredError` |
| `compress_and_register` on a file with `file_type != 'unknown'` | Raise `ValueError` |
| `compress_and_register` and the `_raw_` rename destination already exists | Raise `ValueError`; abort; no changes |
| `delete_file` and file already absent from disk | Log warning; proceed with registry removal and `delete` log entry |
| `mv` / `rename` and destination path already exists | Raise `ValueError`; no changes; no log entry |
| `scan_for_new_files` with no scan roots configured | Raise `ConfigError` pointing to `config add-root` |
| `_raw_` file found during scan but main file not registered | Register as `file_type='raw'`; skip auto-link; warn to run `link` manually |
| Two files have the same `name` but different `path` | Both are valid distinct entries |
| Database file does not exist at startup | Auto-created with schema on first use |
| `delete_file` on the anchor of a file group | Set `anchor_id=NULL`; log warning; continue |
| `add_to_file_group` with a `raw` file | Raise `ValueError`; only `main` files may join groups |
| `add_to_file_group` on a file already in a different group | Allowed; log info |
| `open_file_group` with no anchor set | Raise `ConfigError`; suggest `group anchor` |
| `delete_file_group` | Only group record and memberships are removed; member files remain in the registry and on disk |
| `update_metadata` with partial `metadata` dict | Merges into existing metadata; unmentioned keys preserved |
| `update_metadata` / `register_file` with an unrecognised `subject` value | Raise `ValueError` listing the allowed values |
| `link_to_template` with completed already linked to a template | Raise `ValueError` |
| `link_to_template` with a file that is not `file_type='main'` | Raise `ValueError` |
| `link_to_template` with template having `is_template=False` or completed having `is_template=True` | Raise `ValueError` |
| `suggest_groups` called on unclassified files | They are simply excluded from suggestions; no error |
| Any operation fails mid-way (disk op succeeds, DB update fails) | Attempt to reverse disk change; log failure with full context |

---

## Implementation status

| Step | Status |
|------|--------|
| Database schema + auto-creation (incl. `students` table) | ⬜ Not started |
| `PdfFileManager` class | ⬜ Not started |
| Student management (`add_student`, `list_students`) | ⬜ Not started |
| Scan root management (with `student_id`) | ⬜ Not started |
| `scan_for_new_files` (auto-compress + archive) | ⬜ Not started |
| `register_file` | ⬜ Not started |
| `compress_and_register` (compress → rename → archive) | ⬜ Not started |
| `find_files` / `get_file` (with `student_id`, `doc_type`, `subject` filters) | ⬜ Not started |
| `open_file` | ⬜ Not started |
| `rename_file` / `move_file` | ⬜ Not started |
| `update_metadata` | ⬜ Not started |
| `delete_file` | ⬜ Not started |
| Raw ↔ main relations (`link_files`, `unlink_files`) | ⬜ Not started |
| Template relations (`link_to_template`, `unlink_template`, `get_template`, `get_completions`) | ⬜ Not started |
| File group operations | ⬜ Not started |
| `suggest_groups` | ⬜ Not started |
| `operation_log` writes on all C/U/D operations | ⬜ Not started |
| `get_operation_log` query | ⬜ Not started |
| CLI | ⬜ Not started |
