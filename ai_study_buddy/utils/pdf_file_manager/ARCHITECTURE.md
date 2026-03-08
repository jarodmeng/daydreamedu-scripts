# pdf_file_manager — Architecture

> Schema, data model, source layout, and integrations.
>
> See [README.md](./README.md) for overview; [SPEC.md](./SPEC.md) for API and CLI contract.

---

## Source folders (consolidated layout)

Scanned files may live in one or more folders (e.g. different Google Drive accounts or local paths), each added as a scan root. The layout below describes the **consolidated** structure used under the shared DaydreamEdu root; other roots can use different structures and are linked to students via `student_id` when added.

**Example root (shared):** `/Users/jarodm/Library/CloudStorage/GoogleDrive-genrong.meng@gmail.com/My Drive/DaydreamEdu`

**Hierarchy:**

| Level | Folder meaning | Examples |
|-------|----------------|----------|
| **L1** | Subject | May be short (`Chinese`, `Math`) or longer (`Singapore Primary English`, `Singapore Primary Math`). Inference matches the subject word (e.g. "English" → `english`). |
| **L2** | Student (email-named) or general scope | Student: `winston.ry.meng@gmail.com` (then has Px/PSLE inside). General: any non-email segment — `P3`, `P4`, `P5`, `P6`, `PSLE`, `Archive` — **files under general scope are templates** (`is_template=True`). |
| **L3** | Content type | `Exam`, `Exercise`, `Activity`, `Note` |

So a full path might be: `DaydreamEdu/Singapore Primary Math/winston.ry.meng@gmail.com/P6/Exam/...` or `DaydreamEdu/Singapore Primary Science/P6/Exercise/...`. Student-specific folders are named by the student's email; the file manager can map that path segment to `student_id` via the `students.email` column when present. **Shallow paths:** Some files (e.g. answer keys) sit directly under L1 with no L2/L3; for those, only subject (and optionally filename-based `source_book`) can be inferred; `content_folder`, `grade_or_scope`, and `is_template` are left unset or for human classification.

**L3 content types (folder → doc_type / metadata):**

| Folder | Description | Suggested `doc_type` | Question-level breakdown |
|--------|-------------|----------------------|---------------------------|
| **Exam** | Weighted assessments (end of term), end-of-year assessments (full year). | `exam` | Yes — can be broken into individual questions. |
| **Exercise** | Day-to-day exercises. | `worksheet` or `book_exercise` | Yes. |
| **Activity** | Topic-related study activities; often accompany a textbook or topic. | `activity` | Not necessarily by questions. |
| **Note** | Study notes; various formats. | `notes` | Not necessarily by questions. |

**Book-derived content and special prefixes:** Some content comes from named books; filenames may use a prefix to indicate source:

| Prefix | Book | Notes |
|--------|------|-------|
| **PP** | Power Pack | PSLE exam preparation; one per subject. |
| **EPO** / **English Practice 1000+** | English Practice 1000+ | English PSLE preparation exercise book. |

Content from these books may be split across multiple folders by "nature of the portions". **Answers** files (answer keys) do not roll up to a single folder — they apply to a book or set of exercises. How to treat them is discussed in **Answers files** below.

**Folder-based inference (optional):** When registering or scanning under this root, the file manager can infer: **subject** from L1 folder name — match a known subject word (e.g. `Chinese`, `Math`, `Science`, `English`), including when L1 is longer (e.g. `Singapore Primary English` → `english`); **student_id** when an L2 path segment matches `students.email` (otherwise L2 is general scope); **is_template** — `True` when the file is under a general-scope L2 folder (any non-email L2, e.g. `P3`, `P4`, `P5`, `P6`, `PSLE`, `Archive`), `False` when under a student (email-named) folder; **metadata.grade_or_scope** from L2 when not student-specific; **metadata.content_folder** from L3 (`Exam`, `Exercise`, `Activity`, `Note`); **metadata.source_book** from filename prefix when recognised (e.g. `PP`, `PP `, `EPO`, `EPO_`). For **files directly under L1** (no L2/L3, e.g. answer keys in `Subject/Answers.pdf`), only subject and optionally `source_book` from the filename are inferred; `is_template`, `content_folder`, and `grade_or_scope` are not set by path. Inference is best-effort; any inferred value can be overridden by a human. **Precedence:** When a scan root has `student_id` set, that value is used for all files discovered under that root and overrides path-based inference.

**Human-supplied metadata:** Not all metadata can be derived from folder structure, file name, or file content. Fields such as `school`, `exam_date`, `paper_type`, `chinese_variant`, `topic`, and free-form `notes` typically require a **human reviewer** to provide or confirm them. The file manager supports this via the **classify** workflow: after scan (or register), the user runs `classify` / `update_metadata` (CLI or API) to set `doc_type`, `subject`, and any metadata fields. Newly scanned files default to `doc_type='unknown'`; use `find_files(doc_type='unknown')` or `list --doc-type unknown` to surface files that still need classification. Template linking and suggest-groups are most useful once classification (and, for exams, `exam_date`) has been filled in.

**Answers files:** Answer keys (e.g. "PP Math Answers.pdf", "English Practice 1000+ Answers.pdf") apply to a book or set of exercises but do not sit under one content folder. In practice they often sit **directly under the subject folder** (L1 only), e.g. `DaydreamEdu/Singapore Primary English/English Practice 1000+ Answers.pdf`. **Recommended approach:** Register the Answers file as a normal file with `doc_type='notes'` and `metadata.source_book` so it is findable and queryable; then add it to the book's file group with `role='answers'`, alongside the question/exercise files, so opening the group shows questions and answers together. A dedicated relation type (e.g. `answer_key_for`) can be added later if the workflow demands it.

---

## Real-world alignment (DaydreamEdu drive)

The following reflects the actual structure under the shared DaydreamEdu root (as of the last review), to validate the plan and close gaps:

- **L1 names:** Folders are `Singapore Primary English`, `Singapore Primary Chinese`, `Singapore Primary Science`, `Singapore Primary Math` — not the short `English`/`Chinese`/etc. Subject inference must recognise the subject word inside the L1 name (e.g. "Singapore Primary English" → `english`).
- **L2 general scope:** In addition to P5, P6, PSLE, Archive, the drive uses **P3**, **P4** as general-scope (template) folders. Any L2 that is not a student email is treated as general scope.
- **Answers at L1:** Three answer-key PDFs sit directly under the subject folder (no L2/L3): e.g. `Singapore Primary English/English Practice 1000+ Answers.pdf`, `Singapore Primary Science/PP PSLE Science Exam Power Pack Answers.pdf`, `Singapore Primary Math/PP PSLE Math Exam Power Pack Answers.pdf`. Inference for these: subject from L1, optional `source_book` from filename; no `content_folder` or L2-based `is_template` from path.
- **Filename prefixes:** EPO exercises use the `EPO_` prefix (e.g. `EPO_Grammar_Cloze_02.pdf`). Power Pack answers use `PP ` (e.g. `PP PSLE Math Exam Power Pack Answers.pdf`). Prefix matching should treat these as `EPO` and `PP` respectively.
- **Scale:** Hundreds of PDFs under the root. First full scan will register and optionally compress all unregistered PDFs; use `dry_run=True` to preview, and consider running scan in batches or register-only then compress later if needed.
- **No `_raw_` files yet:** The drive currently has no `_raw_`-prefixed archives; the first run will treat every PDF as a new file and run the register+compress workflow (or register-only if not using scan).

**P5/P6 Math Exam filename convention:** Under `Singapore Primary Math/…/P5/Exam` (and similarly P6), files follow `p5.math.0xx.<exam name>.pdf` (or `p6.math.0xx.…`). Two optional parenthetical tags are used:

| Tag | Meaning | Registry usage |
|-----|--------|-----------------|
| ** (Paper 1)** / **(Paper 2)** | Same exam, different paper (e.g. Paper 1 + Paper 2 = one exam). | Create an **exam group** with label = exam name (strip the " (Paper 1)" / " (Paper 2)" suffix). Add both files to the group; set anchor to Paper 1 (or as desired). |
| ** (empty)** | Blank/template version (workings and markings removed). | Set **is_template=True** on the `(empty)` file; **link_to_template(completed_id, template_id)** so the non-empty file points to it. |

Examples: `p5.math.022.Mathematics Practice Paper Set 1 (Paper 1).pdf` and `p5.math.023.Mathematics Practice Paper Set 1 (Paper 2).pdf` → one exam group "Mathematics Practice Paper Set 1". `p5.math.022.Mathematics Practice Paper Set 1 (Paper 1) (empty).pdf` is the template for `p5.math.022.Mathematics Practice Paper Set 1 (Paper 1).pdf`. The same base name without ` (empty)` is the completed counterpart.

---

## Database

Registry path: `ai_study_buddy/db/pdf_registry.db` (relative to repo root). Override via `PDF_REGISTRY_PATH` environment variable or `--db` CLI flag.

### Schema

```sql
-- Students
CREATE TABLE students (
    id         TEXT PRIMARY KEY,              -- short human-readable ID, e.g. 'winston', 'emma'
    name       TEXT NOT NULL,
    email      TEXT,
    added_at   TEXT NOT NULL                  -- ISO 8601 UTC
);

-- Core file registry
CREATE TABLE pdf_files (
    id             TEXT PRIMARY KEY,             -- UUID v4
    name           TEXT NOT NULL,                -- basename, e.g. "math_wa1.pdf"
    path           TEXT NOT NULL UNIQUE,         -- absolute path on disk
    file_type      TEXT NOT NULL DEFAULT 'unknown'
                   CHECK(file_type IN ('main', 'raw', 'unknown')),
    doc_type       TEXT NOT NULL DEFAULT 'unknown'
                   CHECK(doc_type IN ('exam', 'worksheet', 'book_exercise', 'activity', 'practice', 'notes', 'unknown')),
    student_id     TEXT REFERENCES students(id),
    subject        TEXT
                   CHECK(subject IN ('english', 'math', 'science', 'chinese')),
    is_template    BOOLEAN NOT NULL DEFAULT 0,   -- True = blank/master (no student content); can have completions
    size_bytes     INTEGER,
    page_count     INTEGER,
    has_raw        BOOLEAN NOT NULL DEFAULT 0,   -- denormalised; True = main file has a _raw_ archive
    metadata       TEXT,                         -- JSON; schema varies by doc_type (see Metadata schemas)
    added_at       TEXT NOT NULL,                -- ISO 8601 UTC
    updated_at     TEXT NOT NULL,                -- ISO 8601 UTC
    notes          TEXT
);

-- Raw ↔ main pairs; template ↔ completed pairs (multi-file grouping lives in file_groups)
CREATE TABLE file_relations (
    id            TEXT PRIMARY KEY,              -- UUID v4
    source_id     TEXT NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
    target_id     TEXT NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL
                  CHECK(relation_type IN ('raw_source', 'main_version', 'template_for', 'completed_from')),
    created_at    TEXT NOT NULL,
    UNIQUE(source_id, target_id, relation_type)
);

-- Named groups of files that belong to the same logical document
CREATE TABLE file_groups (
    id         TEXT PRIMARY KEY,                 -- UUID v4
    label      TEXT NOT NULL,                    -- e.g. "Chinese EoY P6 2025", "Math 6A Ch3 Exercise 3A"
    group_type TEXT NOT NULL DEFAULT 'collection'
               CHECK(group_type IN ('exam', 'book_exercise', 'collection')),
    anchor_id  TEXT REFERENCES pdf_files(id)
               ON DELETE SET NULL,               -- file to open when opening the group
    created_at TEXT NOT NULL,
    notes      TEXT
);

-- Membership: which files belong to which group
CREATE TABLE file_group_members (
    group_id   TEXT NOT NULL REFERENCES file_groups(id) ON DELETE CASCADE,
    file_id    TEXT NOT NULL REFERENCES pdf_files(id)   ON DELETE CASCADE,
    role       TEXT,                             -- free-form booklet label within the group
    added_at   TEXT NOT NULL,
    PRIMARY KEY (group_id, file_id)
);

-- Append-only audit log: every state-mutating operation (C/U/D). Never deleted.
-- file_id and group_id are plain TEXT with no FK constraints so entries survive
-- after the referenced rows are deleted.
CREATE TABLE operation_log (
    id           TEXT PRIMARY KEY,               -- UUID v4
    operation    TEXT NOT NULL,                  -- see Operation types table
    file_id      TEXT,
    group_id     TEXT,
    performed_at TEXT NOT NULL,                  -- ISO 8601 UTC
    performed_by TEXT,                           -- 'cli' | 'api' | 'cascade' | free-form
    before_state TEXT,                           -- JSON snapshot before op (NULL for creates)
    after_state  TEXT,                           -- JSON snapshot after op (NULL for deletes)
    notes        TEXT
);

-- Configured root directories for scanning
CREATE TABLE scan_roots (
    id         TEXT PRIMARY KEY,                 -- UUID v4
    path       TEXT NOT NULL UNIQUE,
    student_id TEXT REFERENCES students(id),     -- if set, files discovered here auto-get this student_id
    added_at   TEXT NOT NULL
);
```

### Relation types

| `relation_type` | Source | Target | Meaning |
|-----------------|--------|--------|---------|
| `raw_source` | main file | raw archive | "I was compressed from this raw archive" |
| `main_version` | raw archive | main file | "my processed main version is this file" |
| `template_for` | template file | completed file | "this completion was filled from this template" (1:N) |
| `completed_from` | completed file | template file | "I was completed from this template" |

Both directions for raw↔main and template↔completed are written as separate rows. A template can have many `template_for` rows (one per student completion); a completed file has at most one `completed_from` row.

---

## File naming conventions

| Prefix | `file_type` | Role |
|--------|-------------|------|
| `_raw_` | `raw` | Archived original scan. Kept for traceability. Never ingested. |
| `_c_` | `main` | Compressed file ready for ingestion. When scan finds a `_c_*.pdf`, it registers as main only (no compress step). |
| *(none)* | `main` | Possible when compression was skipped (original kept); or legacy. |
| *(none, not yet processed)* | `unknown` | Newly registered, awaiting `compress_and_register`. |

`compress_and_register` moves the original to `_raw_<name>`, then calls `compress_pdf` with `output_name=_c_<name>`, so the compressed file is written as `_c_<name>`. If savings are below threshold, the original is restored at `<name>` and the row is updated to `file_type='main'` (no `_c_` prefix).

---

## Document types (`doc_type`)

| `doc_type` | Description | Typical source | Maps from L3 folder |
|------------|-------------|----------------|---------------------|
| `exam` | Formal school exam — WA, EoY, mid-year, weighted assessment | Scanner app, download | Exam |
| `worksheet` | Standalone practice worksheet — teacher-issued, tuition center, printed online | Scanner app | Exercise |
| `book_exercise` | Pages from a physical textbook/workbook (contiguous page range for one exercise) | Scanner app | Exercise (when from a book) |
| `activity` | Topic-related study activities; accompany a textbook or topic; not necessarily question-based | Scanner app | Activity |
| `practice` | Generic practice material not fitting above categories | Various | — |
| `notes` | Teacher notes, revision summaries, reference sheets | Scanner app or download | Note |
| `unknown` | Default; not yet classified | — | — |

---

## Templates (`is_template`)

A **template** is a blank or master version of a document — no student content yet. It can be any `doc_type` (exam, worksheet, book_exercise, etc.). Examples: a blank WA paper in the shared DaydreamEdu folder; a scanned blank book exercise. Templates typically have `student_id=NULL`. When a student completes the document (e.g. in Goodnotes), the resulting PDF is a **completion** of that template: `is_template=False`, `student_id` set, and linked via `template_for` / `completed_from` relations.

**Why a boolean, not a `doc_type` value:** "Template" describes *role* (blank vs. filled), not *content type*. An exam template and an exam completion are both `doc_type='exam'`; one has `is_template=True`, the other `is_template=False`.

**Metadata inheritance:** When linking a completed file to a template via `link_to_template`, the file manager can copy `subject`, `doc_type` (if unset), and `metadata` from the template to the completion so the completion does not need to be classified manually. Optionally warn if `page_count` differs between template and completion.

---

## Metadata schemas (per `doc_type`)

The `metadata` column stores a JSON object. `student_id` and `subject` are first-class columns on `pdf_files` and are **not** duplicated in `metadata`.

**Chinese subject only:** For `subject='chinese'`, use the optional `metadata.chinese_variant` to distinguish foundation vs. higher: `'foundation'` (default, 华文) or `'higher'` (高华). There is no separate subject value for Higher Chinese — it is a metadata variant of Chinese.

### `exam`

```json
{
  "paper_type":       "wa",
  "grade":            "p6",
  "school":           "st_gabriels",
  "exam_date":        "2025-09-15",
  "grade_or_scope":   "P6",
  "content_folder":   "Exam",
  "source_book":      "PP",
  "chinese_variant":  "higher"
}
```

`paper_type` values: `wa`, `eoy`, `mid_year`, `practice`. `chinese_variant` is used only when `subject='chinese'`. The last four fields are optional and often inferred from path or filename.

### `worksheet`

```json
{
  "topic":  "fractions",
  "source": "tuition_center"
}
```

`source` is free-form: teacher name, tuition center, website, etc.

### `book_exercise`

```json
{
  "book_title": "My Pals Are Here! Maths 6A",
  "chapter":    "Chapter 3: Fractions",
  "exercise":   "Exercise 3A",
  "page_range": "10-18"
}
```

`page_range` refers to physical page numbers in the book, not PDF page count.

### `activity`

```json
{
  "topic":       "photosynthesis",
  "source_book": "PP",
  "grade_or_scope": "P6"
}
```

Topic and source are optional; use when the activity accompanies a specific topic or book.

### `practice` and `notes`

```json
{
  "topic": "plants"
}
```

### `unknown`

No expected structure. Free-form JSON or `null`.

---

## File groups (`file_groups`)

### Group types

| `group_type` | When to use | Typical `role` values |
|--------------|-------------|----------------------|
| `exam` | Multiple booklets from one exam sitting (English: 2 PDFs, Chinese/HC: 3 PDFs) | `paper1`, `paper2_questions`, `paper2_answers` |
| `book_exercise` | One exercise scanned across multiple sessions | `part_1`, `part_2`; or `pages_10_14`, `pages_15_18` |
| `collection` | Any other manual grouping | Free-form |

Single-file documents do not need a group.

**Group membership applies to `main` files only.** Raw archives (`file_type='raw'`) are never added to file groups — they are not ingestion targets. When `compress_and_register` creates a main file from a raw scan, the main file inherits the raw file's group memberships (if any existed before compression).

### Suggest-groups heuristics

`scan --suggest-groups` (and the standalone `suggest-groups` command) identifies candidate groups by finding `main` files sharing the same `student_id` + `subject` + `metadata.exam_date`. This means files must be classified (`doc_type`, `subject`, and `exam_date` in metadata set) before suggestions are meaningful. The command outputs suggested groupings for manual confirmation — it never creates groups automatically.

---

## File type detection

When `register_file` is called directly, `file_type` is inferred from the filename:

| Condition | Assigned `file_type` |
|-----------|----------------------|
| Name starts with `_raw_` | `raw` |
| Name does not start with `_raw_` | `unknown` (becomes `main` after `compress_and_register`) |
| Explicitly overridden by caller | caller-provided value |

`doc_type` defaults to `unknown`. `student_id` is populated from the scan root's `student_id` if the file was discovered by `scan_for_new_files`.

---

## Integration with compress_pdf

`compress_and_register` delegates to `compress_pdf.compress_pdf()` via direct Python import. The file manager passes `output_name` so that the compressed output is written directly to the final main filename; no `_c_` or other intermediate prefix is used in the file manager workflow, and no extra renaming step is required.

---

## Integration with ingestion pipeline

The pipeline queries the file manager to determine:
- `doc_type` and `metadata` → infer `paper_type`, `subject`, `student_id`, `school` on the `documents` row without re-prompting
- `get_file_group_membership(file_id)` → find the exam group, set `exam_id` on all resulting `documents` rows, read `role` to infer per-booklet `paper_type`

Only `main` files are ingested. The pipeline never processes `raw` archives.

---

## Dependencies

`sqlite3` (stdlib), `uuid` (stdlib), `pathlib` (stdlib), `json` (stdlib), `pymupdf` (for `page_count`), `compress_pdf` (local utility, same repo)
