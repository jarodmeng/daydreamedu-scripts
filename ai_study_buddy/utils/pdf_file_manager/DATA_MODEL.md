# pdf_file_manager — Data Model

> Field-level reference for file metadata, group semantics, and returned data classes.
>
> See [README.md](./README.md) for overview; [SPEC.md](./SPEC.md) for API and operation contract; [ARCHITECTURE.md](./ARCHITECTURE.md) for schema details.

## Quick reference: unit vs groups

Use this mental model when classifying files and building groups:

- File-level metadata lives in `pdf_files.metadata` (for example `content_folder`, `grade_or_scope`, `unit`, `chinese_variant`, `exam_date`).
- Group-level identity lives in `file_groups` (`label`, `group_type`, `anchor_id`, `notes`).
- Per-member function labels are represented canonically by `pdf_files.metadata.unit`.
- For `doc_type='book'`: `metadata.unit` is the per-file chapter/unit label, while the shared book identity belongs in the `book` group's `label`.

## Exam group completeness (compulsory `metadata.unit`)

When checking whether an `exam` group has a **full** set of papers for ingestion or QA, use **compulsory** units only. Optional units may be present but must not be required for “complete.”

Collect the set of non-empty `metadata.unit` values from **`main`** members with `is_template = 0` in the group. The group is **incomplete** if any compulsory unit below is missing from that set.

| Subject | Compulsory `unit` values | Optional (do not require for completeness) |
|--------|---------------------------|---------------------------------------------|
| **chinese** (华文 and 高华) | `questions`, `answers` | `composition` |
| **math** | `Paper 1`, `Paper 2` | — |
| **english** | `Paper 1`, `Paper 2 Booklet A`, `Paper 2 Booklet B` | `Oral`, `Listening Comprehension` |
| **science** | `Booklet A`, `Booklet B` | — |

Mains with no `unit` (or empty `unit`) contribute nothing to the set until metadata is filled.

## Common metadata fields

These are common keys used in `PdfFile.metadata`:

- `content_folder` (path-derived): `Exam`, `Exercise`, `Book`, `Activity`, `Note`
- `grade_or_scope` (path-derived): `P3`, `P4`, `P5`, `P6`, `PSLE`, `Archive`
- `unit` (all grouped content): per-file function/unit label (for example `paper1`, `answers`, `Part D Topical Practice Fractions`)
- `chinese_variant` (Chinese exam files): `foundation` or `higher`
- `exam_date`, `paper_type`, `school`, `topic`: optional workflow fields

Important behavior:

- `update_metadata(..., metadata=...)` merges keys; it does not replace the full metadata object.

## Group fields

`FileGroup` records carry:

- `label`: human-readable group identity (for example exam or book name)
- `group_type`: one of `exam`, `book`, `book_exercise`, `collection`
- `anchor_id`: default member file to open
- `notes`: optional group-level notes

`FileGroupMember` rows add:

- `role`: legacy compatibility field on membership rows; prefer `PdfFile.metadata.unit` for new labeling

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
    name: str
    path: str
    file_type: str           # 'main' | 'raw' | 'unknown'
    doc_type: str            # 'exam' | 'worksheet' | 'book' | 'book_exercise' | 'activity' | 'practice' | 'notes' | 'unknown'
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
```
