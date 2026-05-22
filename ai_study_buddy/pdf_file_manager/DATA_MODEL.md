# pdf_file_manager — Data Model

> Field-level reference for file metadata, group semantics, and returned data classes.
>
> See [README.md](./README.md) for overview; [SPEC.md](./SPEC.md) for API and operation contract; [ARCHITECTURE.md](./ARCHITECTURE.md) for schema details.

## Quick reference: unit vs groups

Use this mental model when classifying files and building groups:

- File-level metadata lives in `pdf_files.metadata` (for example `content_folder`, `grade_or_scope`, `unit`, `chinese_variant`, `exam_date`).
- Group-level identity lives in `file_groups` (`label`, `group_type`, `anchor_id`, `notes`).
- Book-answer coverage lives in `book_answer_mappings` (unit file, answer file, inclusive page range, split-page flags, provenance).
- `metadata.unit` is enforced as **book-only** metadata.
- For `doc_type='book'`: `metadata.unit` is the per-file chapter/unit label, while the shared book identity belongs in the `book` group's `label`.
- For `doc_type='book'` answer coverage: the shared book identity still belongs to the `book` group, while page-level answer coverage belongs in `book_answer_mappings`.

## Common metadata fields

These are common keys used in `PdfFile.metadata`:

- `content_folder` (path-derived): `Exam`, `Exercise`, `Book`, `Activity`, `Note`
- `grade_or_scope` (path-derived): `P1`, `P2`, `P3`, `P4`, `P5`, `P6`, `PSLE`
- `unit` (book-only): per-file unit label for `doc_type='book'` files
- `chinese_variant` (Chinese exam files): `standard` (**Standard** 华文 / non-HC) or `higher` (高华) — not the same as SEAB “Foundation Chinese Language”. The legacy spelling `foundation` is **invalid** and must not appear in stored JSON (`InvalidMetadataError` on load/persist).
- `exam_date`, `paper_type`, `school`, `topic`: optional workflow fields

Important behavior:

- `update_metadata(..., metadata=...)` merges keys; it does not replace the full metadata object.
- `register_file(..., metadata=...)` and `update_metadata(..., metadata=...)` reject non-empty `metadata.unit` unless `doc_type='book'` (`InvalidMetadataError`).
- `update_metadata(..., file_type=...)` can set or repair `pdf_files.file_type` (`main`, `raw`, `unknown`) without touching disk; use with `rename_file` when the on-disk main was renamed (for example to `_c_…`) but the registry path was not updated.

## Group fields

`FileGroup` records carry:

- `label`: human-readable group identity (for example exam or book name)
- `group_type`: one of `exam`, `book`, `book_exercise`, `collection`
- `anchor_id`: default member file to open
- `notes`: optional group-level notes

`FileGroupMember` rows add:

- `role`: legacy compatibility field on membership rows; when passed to `add_to_file_group(..., role=...)`, it is only allowed for `doc_type='book'` files

## Returned data classes

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
    name: str                # exact on-disk basename, including technical prefix + extension
    normal_name: str         # computed (not persisted): normalized display stem
    path: str
    file_type: str           # 'main' | 'raw' | 'unknown'
    doc_type: str            # 'exam' | 'exercise' | 'book' | 'activity' | 'note'
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
    relation_type: str       # 'raw_source' | 'main_version' | 'template_for' | 'completed_from'
    created_at: str

@dataclass
class FileGroup:
    id: str
    label: str
    group_type: str          # 'exam' | 'book' | 'book_exercise' | 'collection'
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
class BookAnswerMapping:
    id: str
    unit_file_id: str
    answer_file_id: str
    answer_page_start: int
    answer_page_end: int
    starts_mid_page: bool
    ends_mid_page: bool
    source: str | None
    notes: str | None
    created_at: str
    updated_at: str
    unit_file: PdfFile
    answer_file: PdfFile

@dataclass
class SuggestedGroup:
    group_type: str
    candidate_files: list[PdfFile]
    match_basis: dict        # e.g. {"student_id": "winston", "subject": "chinese", "exam_date": "2025-11-12"}

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
    file: PdfFile
    raw_archive: PdfFile | None
    compressed: bool
    template_link: GoodNotesTemplateLinkOutcome | None = None  # v0.3.20+ GoodNotes auto-link preview/outcome
```

`PdfFile.normal_name` is derived from `name` using canonical normalization in `pdf_file_manager`:

- iterative prefix stripping: `_raw_`, `_c_`, `raw_`, `c_`
- extension removal via `Path(...).stem`

This value is computed at runtime and is **not** stored as a DB column.
