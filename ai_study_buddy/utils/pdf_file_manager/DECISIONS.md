# pdf_file_manager — Decision Log

Decisions that shaped the design of this utility. Each entry records what was decided, what was considered, and why. Newest decision first.

---

## D-010 — Prefer MCP over a built-in CLI; remove the partial CLI layer

**Date:** 2026-03-10
**Status:** Decided
**Affects:** `SPEC.md`, `README.md`, `TESTING.md`, `CHANGELOG.md`, MCP wrapper/server modules, `pdf_file_manager.py`

### Context

The Python library had grown into the real contract for the utility, while the built-in CLI remained a partial surface. That created maintenance debt: every new capability either had to be duplicated in argparse handlers and human-oriented output, or left out of the CLI entirely. The new MCP layer provides a structured machine interface with JSON-safe returns, explicit error mapping, and a better fit for agent use than shelling out to a text CLI.

### Decision

1. **Treat the Python API plus MCP server as the supported interfaces.**  
   `PdfFileManager` remains the source of truth for business logic. The MCP wrapper and FastMCP server are the preferred machine-facing contract.

2. **Remove the built-in CLI layer from `pdf_file_manager.py`.**  
   The CLI offered limited benefit relative to its upkeep cost and duplicated a weaker form of the machine interface.

3. **Record MCP-specific tests as the interface-level verification.**  
   Wrapper and server-registration tests are now part of the supported testing story.

### Consequences

- The argparse entrypoint and CLI smoke tests are removed.
- Current-facing docs describe Python + MCP as the present contract.
- Machine-interface validation now focuses on `test_mcp_tools.py` and `test_mcp_server.py` in addition to the manager integration tests.
- If a human-facing CLI is needed again later, it should be justified as a separate product surface rather than maintained by accident.

---

## D-009 — Consolidated folder layout, `activity` doc_type, folder inference, book prefixes, Answers files

**Date:** 2026-03-06
**Status:** Decided
**Affects:** `SPEC.md` — Source folders section, doc_type enum, metadata schemas, folder-based inference

### Context

All scanned files were consolidated into a single root: `DaydreamEdu` (Google Drive). The hierarchy is: **L1** = subject (Chinese, Math, Science, English); **L2** = student folder (email-named) or general scope (P5, P6, PSLE, Archive); **L3** = content type (Exam, Exercise, Activity, Note). Some content comes from named books (prefixes PP = Power Pack, EPO = English Practice 1000+). "Answers" files (answer keys) do not sit under one folder and need a consistent treatment.

### Decisions

1. **Source folders** — Document the single consolidated root and the L1/L2/L3 structure in the spec. Treat the previous multi-root setup (Winston/Emma separate drives) as superseded by this layout; one scan root (DaydreamEdu) with path-based inference covers the hierarchy.

2. **`activity` doc_type** — Add `activity` to the `doc_type` CHECK. It corresponds to the L3 "Activity" folder: topic-related study activities that accompany a textbook or topic and are not necessarily organised by questions. Distinct from `worksheet` / `book_exercise` (question-based) and `notes` (notes).

3. **Folder-based inference** — When scanning under the consolidated root, infer: **subject** from L1; **student_id** by matching an L2 path segment to `students.email`; **metadata.grade_or_scope** (P5, P6, PSLE, Archive) from L2 when not student-specific; **metadata.content_folder** (Exam, Exercise, Activity, Note) from L3; **metadata.source_book** (PP, EPO) from filename prefix. All inference is best-effort and overridable via `classify` / `update_metadata`.

4. **Book prefixes** — Document PP and EPO in the spec. Store book origin in `metadata.source_book` when present. No separate "books" table for MVP.

5. **Answers files** — Treat as normal files with `metadata.source_book` and optional `doc_type='notes'`, or add them to a file group for the book with `role='answers'`. Defer a dedicated relation type (e.g. `answer_key_for`) until needed.

6. **General-scope folders = templates** — Files under L2 general-scope folders (P5, P6, PSLE, Archive) are blank/master copies with no student content. Set `is_template=True` when inferring from path; files under student (email-named) folders get `is_template=False`.

7. **Higher Chinese is not a separate subject** — Do not add `higher_chinese` to the subject enum. Subject remains `chinese` for both foundation (华文) and higher (高华). For Chinese files, use optional `metadata.chinese_variant`: `'foundation'` or `'higher'`. This keeps subject as a single dimension and treats foundation vs. higher as Chinese-specific metadata.

### Consequences

- Source folders section rewritten for the single DaydreamEdu root and L1/L2/L3 table; L2 general scope explicitly defined as templates.
- Folder-based inference includes **is_template** from L2 (general scope → true, student folder → false).
- Subject CHECK has four values only: `english`, `math`, `science`, `chinese`. Metadata schemas document `chinese_variant` for Chinese files.
- `doc_type` CHECK and Document types table include `activity`; metadata schema for `activity` added.
- Exam metadata schema extended with optional `grade_or_scope`, `content_folder`, `source_book` for path/book inference.
- New subsection on folder-based inference and on Answers files (options + MVP recommendation).
- `PdfFile` dataclass `doc_type` comment updated to include `activity`.

---

## D-008 — Blank vs. completed: `is_template` boolean and template relations; remove `past_year` from `doc_type`

**Date:** 2026-03-06
**Status:** Decided
**Affects:** `SPEC.md` — `pdf_files` schema (`is_template` column, removal of `past_year` from `doc_type`), `file_relations` (new relation types), operations and CLI

### Context

Blank exam papers (e.g. `p6.science.wa2.1.pdf` in the shared DaydreamEdu folder) have subject and exam metadata but no student. When a student completes the paper in Goodnotes, the resulting PDF is a variant: same structure, different content (workings, markings). The same blank can spawn multiple completions (Winston, Emma, etc.). An initial proposal was to add `doc_type='template'` to represent blanks; the user pointed out that this conflates *type* (exam, worksheet, book_exercise) with *role* (blank vs. filled). A blank exam and a completed exam are both exams.

Separately, `past_year` was a `doc_type` value. Past-year papers are a *kind* of exam or practice material, not a distinct content type; they can be represented via `doc_type='exam'` or `doc_type='practice'` with metadata (e.g. `paper_type` or a flag in metadata) if needed. Removing `past_year` from the enum simplifies the model.

### Decision 1 — `is_template` boolean, not a `doc_type` value

Add `is_template BOOLEAN NOT NULL DEFAULT 0` to `pdf_files`. When `True`, the file is a blank or master (no student content); it may have completions linked to it. When `False`, the file is a concrete instance (completion or a non-template document). A template can be any `doc_type` (exam, worksheet, book_exercise, etc.). This keeps "what kind of document" (`doc_type`) orthogonal to "is it a blank or a filled instance?" (`is_template`).

### Decision 2 — Template↔completed relation types

Add to `file_relations.relation_type`: `'template_for'` (source = template, target = completed) and `'completed_from'` (source = completed, target = template). Both directions are stored. One template can have many completions (1:N). Operations: `link_to_template(completed_id, template_id, inherit_metadata=True)` (with optional metadata inheritance and page_count sanity check), `unlink_template(completed_id)`, `get_template(file_id)`, `get_completions(template_id)`.

### Decision 3 — Remove `past_year` from `doc_type`

Drop `past_year` from the `doc_type` CHECK constraint. The allowed values become: `exam`, `worksheet`, `book_exercise`, `practice`, `notes`, `unknown`. Past-year papers are registered as `exam` or `practice` with metadata distinguishing them if needed.

### Consequences

- `pdf_files.is_template` added; `doc_type` CHECK no longer includes `past_year`.
- `file_relations.relation_type` CHECK extended with `'template_for'`, `'completed_from'`.
- New operations and CLI: `link_to_template`, `unlink_template`, `get_template`, `get_completions`; `template link` / `template unlink` subcommands.
- `find_files`, `register_file`, `update_metadata` gain `is_template` parameter; CLI gains `--is-template`, `list --templates`.
- `suggest_groups` candidate filter: `doc_type='exam'`, `is_template=False`, and `exam_date` in metadata.
- Document types table and metadata schemas: `past_year` removed; exam metadata schema no longer shares a heading with past_year.
- Operation log: `link_template`, `unlink_template` operation types.
- `PdfFile` dataclass gains `is_template: bool`.

---

## D-007 — `subject` as a first-class column with a CHECK constraint

**Date:** 2026-03-06
**Status:** Decided
**Affects:** `SPEC.md` — `pdf_files` schema (new `subject` column), metadata schemas, `find_files`, `update_metadata`, `register_file`, `PdfFile` dataclass, CLI

### Context

`subject` was previously a field inside the `metadata` JSON column (e.g. `"subject": "math"`). Every doc type in the archive carries a subject — it is as universally applicable as `student_id`. The allowed values form a closed, enumerated set: `english`, `math`, `science`, `chinese`. (Higher Chinese is not a separate subject; it is represented as `subject='chinese'` with `metadata.chinese_variant='higher'`.)

### Decision

Promote `subject` to a **first-class `TEXT` column** on `pdf_files`, enforced with a `CHECK` constraint over the allowed values. Remove it from all `metadata` JSON schemas.

**Why a column and not a separate `subjects` table (unlike `student_id`):** Subjects have no additional structured attributes at this stage — no email, no display name beyond the string itself. A CHECK constraint on the column provides the same referential integrity with less schema overhead. If subjects later need extra attributes (e.g. display names, curriculum metadata), a `subjects` table can be introduced and the column converted to a FK at that point.

**Why nullable:** Files may be registered before their subject is known (especially during bulk scans). `NULL` signals "not yet classified" without blocking registration. The `find_files(doc_type='unknown')` workflow surfaces unclassified files for follow-up `classify` calls.

**One file = one subject.** The 1:1 constraint is enforced by the single column (as opposed to a junction table). A file that covers multiple subjects (rare in this archive) should be split or classified by its primary subject.

### Consequences

- `pdf_files.subject TEXT CHECK(subject IN ('english', 'math', 'science', 'chinese'))` added (nullable).
- `subject` removed from all `metadata` JSON schemas.
- `find_files(subject=...)` now filters on the column directly (`WHERE subject = ?`) instead of `json_extract`.
- `update_metadata` and `register_file` gain a `subject` parameter; invalid values raise `ValueError`.
- `suggest_groups` uses the `subject` column (not `metadata.subject`) when matching candidate groups.
- `PdfFile` dataclass gains `subject: str | None`.
- CLI: `classify` and `register` gain `--subject`; `list` gains `--subject` filter.

---

## D-006 — Student identity: `student_id` column + `students` table

**Date:** 2026-03-06
**Status:** Decided
**Affects:** `SPEC.md` — `pdf_files` schema (new `student_id` column replacing `child` in `metadata`), new `students` table, `scan_roots` schema, `find_files` parameters, metadata schemas, Python dataclasses, CLI

### Context

All metadata schemas had a `child` field (e.g. `"child": "winston"`) in the JSON `metadata` column. This is universally applicable across all doc types — every file in the archive belongs to a student. The name `child` is also imprecise for a system that may eventually serve students of any age.

### Decision

1. **Rename `child` → `student_id`** for clarity and generality.
2. **Promote `student_id` to a first-class column** on `pdf_files` rather than keeping it in `metadata` JSON. Rationale: querying "all of Emma's files" is a fundamental operation that should be a simple `WHERE student_id = 'emma'` rather than `WHERE json_extract(metadata, '$.child') = 'emma'`. It also enables a proper foreign key.
3. **Create a `students` table** (`id`, `name`, `email`, `added_at`) to store student identity information and give `student_id` a referential target.
4. **Add `student_id` to `scan_roots`** so that files discovered under a student-specific Google Drive root are auto-tagged with that student's ID, eliminating the need for manual `update_metadata` calls for the most common case.
5. **Remove `child` / `student_id` from all `metadata` JSON schemas** — it is now captured at the column level.

### Consequences

- `pdf_files.student_id TEXT REFERENCES students(id)` added (nullable — allows for shared/unassigned files).
- `scan_roots.student_id TEXT REFERENCES students(id)` added.
- `students` table created.
- All `metadata` schema examples updated to remove `child`/`student_id` field.
- `find_files` gains `student_id` filter parameter.
- CLI: `student add` / `student list` subcommands; `config add-root` gains `--student-id` flag; `list` gains `--student` flag; `classify` gains `--student-id`.
- `Student` and `ScanRoot` dataclasses added to the Python library.

---

## D-005 — File processing workflow: compressed file as main, `_raw_` prefix for archives

**Date:** 2026-03-06
**Status:** Decided
**Affects:** `SPEC.md` — file naming conventions, `file_type` values, `file_relations` relation types, `scan_for_new_files` behaviour, `compress_and_register` behaviour, `has_compressed` → `has_raw`, Python dataclasses, CLI

### Context

The initial design treated the raw scan as the primary file and the `_c_` compressed derivative as a secondary entry. The ingestion pipeline, however, always operates on the compressed version. This meant the "important" file (compressed) had a less prominent role in the registry and a visually cluttered `_c_` prefix name.

### Decision

**The compressed file is the main file.** It takes the original clean filename. The raw scan is archived with a `_raw_` prefix and kept purely for traceability.

**Processing workflow on discovering a new PDF `abc.pdf`:**
1. Attempt compression.
2. If worthwhile (savings ≥ `min_savings_pct`, default 10%): rename `abc.pdf` → `_raw_abc.pdf`, rename `_c_abc.pdf` → `abc.pdf`. Register `abc.pdf` as `file_type='main'` and `_raw_abc.pdf` as `file_type='raw'`. Link them.
3. If not worthwhile (already optimal): `abc.pdf` stays as-is, becomes `file_type='main'` with no raw archive. `has_raw=False`.

**Naming convention:**
- `_raw_` prefix = archived original scan. Never ingested.
- No prefix = main file. The ingestion target.
- `_c_` prefix = internal compress_pdf artifact only. Never persists in the registry.

**`scan_for_new_files` becomes active:** Instead of just registering files, scan now automatically compresses new files as part of the discovery workflow. This is intentional — every new file should be ready for ingestion as soon as it is scanned.

### Why this is better than the original design

- **Clean names for important files.** The file you open, view, and ingest has the human-readable name (`math_wa1.pdf`). The archive copy has the prefix (`_raw_math_wa1.pdf`), visually subordinate.
- **Pipeline alignment.** The ingestion pipeline always uses `main` files. There is no ambiguity about which file to pass.
- **`has_raw` is more useful than `has_compressed`.** The meaningful question is "does this main file have a traceable origin?" not "does this raw scan have a compressed copy?"
- **`unknown` is now a transient state.** A file is `unknown` only briefly between discovery and compression. After `compress_and_register`, it is always either `main` or `raw`.

### Consequences

- `file_type` values: `'raw' | 'compressed' | 'unknown'` → `'main' | 'raw' | 'unknown'`.
- `file_relations.relation_type`: `'compressed_version' | 'raw_source'` → `'raw_source' | 'main_version'`.
  - `raw_source`: source=main, target=raw archive ("I was processed from this raw scan").
  - `main_version`: source=raw archive, target=main ("my processed version is this file").
- `has_compressed` → `has_raw` (True = main file has a `_raw_` archive).
- `compress_and_register` now performs the rename dance: compress → rename original to `_raw_` → rename output to clean name.
- `scan_for_new_files` calls `compress_and_register` automatically for each new unregistered file (not `_raw_`-prefixed).
- `scan --dry-run` added to preview what scan would do without making any changes.
- `add_to_file_group` restricted to `main` files only; `raw` files cannot be group members.
- `ScanResult` dataclass gains `raw_archive` field (the `_raw_` file, if created) and `compressed` boolean.

---

## D-004 — Accommodating diverse PDF types: `doc_type` + `metadata` JSON + generalising `exam_groups` → `file_groups`

**Date:** 2026-03-06
**Status:** Decided
**Affects:** `SPEC.md` — `pdf_files` schema (new `doc_type` and `metadata` columns), `exam_groups` → `file_groups` rename with new `group_type` field, `find_files` filters, `update_metadata` operation, Python dataclasses, CLI

### Context

The initial design was implicitly exam-centric: the `exam_groups` table name, the member `role` examples, and the metadata discussion all centred on multi-booklet exam sittings. In practice the archive contains three distinct source types:

1. **Scanned exam booklets** — formal school exams (WA, EoY, mid-year) and past-year papers.
2. **Scanned worksheets** — standalone practice sheets from teachers, tuition centres, or printed online resources.
3. **Scanned book exercise pages** — a contiguous page range from a physical textbook or workbook (e.g. pages 10–18 of *My Pals Are Here! Maths 6A*, corresponding to Exercise 3A).

Each type carries completely different structured attributes. A book exercise needs `book_title`, `chapter`, `exercise`, `page_range`. A worksheet needs `topic`, `source`. An exam needs `paper_type`, `school`, `exam_date`. These attributes are meaningless for the other types.

### Decision 1 — Add `doc_type` as a first-class column

Add `doc_type TEXT NOT NULL DEFAULT 'unknown'` to `pdf_files` with a CHECK constraint over: `exam`, `worksheet`, `book_exercise`, `practice`, `notes`, `unknown`.

**Why not fold it into the existing `file_type` column?** `file_type` (`raw` / `compressed`) describes the *derivative nature* of the file — is it an original scan or a processed version? `doc_type` describes the *content* of the file. These dimensions are orthogonal: a `compressed` file can be an `exam` or a `worksheet`. Conflating them would make filtering and compression logic inconsistent. Two separate columns with clear, distinct semantics is the right design.

### Decision 2 — Type-specific metadata: JSON column vs. nullable columns vs. separate tables

Three options for storing type-specific attributes:

**Option A — Nullable columns on `pdf_files`** (e.g. `subject`, `child`, `paper_type`, `book_title`, `page_range`, …)

- Pro: queryable without JSON parsing.
- Con: extremely sparse — a worksheet row has `NULL` in `book_title`, `page_range`, `chapter`; a book exercise row has `NULL` in `paper_type`, `school`. Adding a new doc type requires a schema migration.

**Option B — `metadata TEXT` JSON column** ✅ CHOSEN

A single `metadata` column stores a JSON object whose schema varies by `doc_type`. SQLite's `json_extract()` enables structured queries when needed (e.g. `WHERE json_extract(metadata, '$.subject') = 'math'`).

- Pro: extensible without schema changes — new doc types and new attributes are added by updating the application code, not the database schema.
- Pro: no sparse nulls — each row's `metadata` contains only the fields relevant to its `doc_type`.
- Pro: `before_state` / `after_state` in `operation_log` captures the full metadata JSON snapshot automatically.
- Con: less queryable than columns for ad-hoc SQL; mitigated by `find_files(subject=...)` helper that wraps `json_extract`.

**Option C — Separate per-doc-type tables** (e.g. `exam_metadata`, `worksheet_metadata`, `book_exercise_metadata`)

- Pro: fully normalised, strongly typed per type.
- Con: three extra tables, joins on every fetch, migrations required for new types. Over-engineered for a local personal tool.

**Decision: Option B** (JSON column). The tool is a local personal archive manager, not an analytics database. Extensibility without schema migrations outweighs the modest queryability loss.

### Decision 3 — Rename `exam_groups` → `file_groups`, add `group_type`

`exam_groups` was a misnomer: the grouping concept applies to any multi-file logical document, not only exams. A book exercise scanned across two sessions is equally a group.

Rename to `file_groups` (and `exam_group_members` → `file_group_members`) throughout. Add `group_type TEXT NOT NULL DEFAULT 'collection'` with values: `exam`, `book_exercise`, `collection`.

`group_type` enables:
- Filtering groups by purpose (`list_file_groups(group_type='exam')`)
- The ingestion pipeline to handle exam groups differently from book exercise groups
- Clearer CLI output (`list --grouped` shows group type alongside label)

### Consequences

- `pdf_files` gains `doc_type` and `metadata` columns.
- `exam_groups` / `exam_group_members` renamed to `file_groups` / `file_group_members`; `group_type` added to `file_groups`.
- `compress_and_register` inherits `doc_type` and `metadata` from raw source to the compressed output.
- `update_metadata` replaces `update_notes` as the primary classification method; merges partial metadata dicts rather than overwriting.
- `find_files` gains `doc_type` and `subject` filter parameters.
- CLI: `register` and `scan` gain `--doc-type`; new `classify` subcommand for post-hoc classification.
- All `ExamGroup*` references in Python dataclasses and CLI renamed to `FileGroup*`.
- `operation_log` operation type `update_notes` renamed `update_metadata` (covers notes + doc_type + metadata in one operation).

---

## D-003 — Logging scope: deletion-only vs. all state-mutating operations

**Date:** 2026-03-06
**Status:** Decided
**Affects:** `SPEC.md` — database schema (replaces `deletion_log` with `operation_log`), all C/U/D operation descriptions, Python dataclasses, CLI

### Context

The initial draft had a specialized `deletion_log` table that permanently recorded deleted files. The question arose: should logging be extended to cover all CRUD operations, with the goal of being able to "replay" all operations on a file?

### Option A — Deletion-only log (initial design)

Keep `deletion_log` as a specialized table capturing only file deletions — full record snapshot, relations, and group memberships at time of deletion.

**Pros:**
- Simple. Only the most destructive operation (irreversible deletion) is audited.
- Low overhead — log entries are infrequent.

**Cons:**
- Cannot reconstruct a file's history. If a file was registered, renamed twice, moved, then deleted, you can only see the final state at deletion — not the sequence of changes.
- "Replay" is not possible. You know a file was deleted but cannot trace what happened to it before that.
- Creates a parallel table with a different structure from what any general log would look like, making it harder to extend later.
- Update operations (rename, move) leave no trace at all.

### Option B — Unified `operation_log` covering all C/U/D operations ✅ CHOSEN

Replace `deletion_log` with a single `operation_log` table. Every state-mutating operation — file creates, updates, deletes, and all group operations — writes one row. Reads are explicitly excluded.

**Schema pattern:** Each entry captures `before_state` (JSON snapshot before the operation) and `after_state` (JSON snapshot after):
- Creates: `before_state = NULL`, `after_state = {new record}`
- Updates: `before_state = {old record}`, `after_state = {new record}` — diff is visible
- Deletes: `before_state = {full record + relations + group memberships}`, `after_state = NULL`

**Pros:**
- **Full history reconstruction.** `WHERE file_id = ?` returns every state a file passed through — from first registration through every rename and move to eventual deletion.
- **Replay is meaningful.** You can re-derive the current state from the log alone for any file.
- **Renames and moves are audited.** You can answer "what was this file called three months ago?" or "where was it stored before it was moved?"
- **Subsumes `deletion_log`.** A `delete` operation entry with `before_state` captures everything `deletion_log` did — plus you also have all prior history entries for the same `file_id`.
- **Single query pattern** for all history questions: filter `operation_log` by `file_id`, `group_id`, `operation`, or `since`.
- **No FK constraints on `file_id` / `group_id`.** Log entries survive after referenced rows are deleted — the log is the permanent record, the working tables are transient state.

**Cons:**
- More writes per operation (each C/U/D writes one log row). For a local personal tool managing hundreds of files, this is negligible.
- Slightly more complex log schema than `deletion_log`.

**Why reads are excluded:** Reads do not mutate state and cannot be replayed to produce a different registry state. `open_file` and `open_exam_group` produce no log entries. If "last accessed" surfacing is needed in the future, an `accessed_at` column on `pdf_files` is the right mechanism — not log entries.

### Decision

**Option B** (unified `operation_log`). The cost is trivial (one extra row per mutation on a low-volume local tool). The benefit — complete, replayable history for every file — is the entire point of having a log at all.

### Consequences

- `deletion_log` table is removed from the schema.
- `operation_log` table is added with columns: `id`, `operation`, `file_id`, `group_id`, `performed_at`, `performed_by`, `before_state`, `after_state`, `notes`.
- `DeletionRecord` Python dataclass is replaced by `OperationRecord`.
- Every C/U/D operation in the spec (`register_file`, `compress_and_register`, `rename_file`, `move_file`, `update_notes`, `link_files`, `unlink_files`, `delete_file`, and all `*exam_group*` operations) is documented to write a log entry.
- `get_operation_log(file_id, group_id, operation, since)` is added as a query method.
- CLI `log` command gains `--file`, `--group`, `--operation`, `--since`, and `--id` filters.
- The operation types table in `SPEC.md` enumerates all 14 operation values and the contents of `before_state` / `after_state` for each.

---

## D-002 — Exam group data model: pairwise relations vs. dedicated group table

**Date:** 2026-03-06
**Status:** Decided
**Affects:** `SPEC.md` — database schema (replaces the initial `same_exam` `file_relations` design)

### Context

Having decided to link files (D-001), the question is how to represent the grouping in the database. The initial draft used `same_exam` as a third `relation_type` value in the `file_relations` table alongside `compressed_version` and `raw_source`.

### Option A — Pairwise relations in `file_relations`

Add `'same_exam'` to the `file_relations.relation_type` CHECK constraint. A 3-file Chinese exam is represented as 6 rows: (P1→P2Q, P1→P2A, P2Q→P1, P2Q→P2A, P2A→P1, P2A→P2Q) — one row per directed pair per direction.

**Pros:**
- Simpler schema — one table for all inter-file relationships.
- Same query pattern for all relation types.

**Cons:**
- **Scales poorly.** A 3-file group requires O(n²) = 6 rows for full bidirectional coverage. For a 4-file group: 12 rows. Membership queries require finding the transitive closure of a graph, not a simple join.
- **No group-level metadata.** There is nowhere to store a human-readable group label, an anchor file designation, or notes — these would have to be attached to an arbitrary "primary" file's `notes` column.
- **No single group identity.** "The Chinese exam" has no UUID. To reference the group, you must enumerate its members — fragile if files are added or removed.
- **Mixes two conceptually different relationship types** in one table: file-to-file derivative relationships (raw↔compressed) and group memberships (same exam). These have different semantics, different cardinalities, and different lifecycle rules.

### Option B — Dedicated `exam_groups` + `exam_group_members` tables ✅ CHOSEN

A separate `exam_groups` table holds one row per exam group (with a UUID, label, anchor_id, and notes). A junction table `exam_group_members` maps files to groups, with an optional `role` column describing each file's booklet function.

**Pros:**
- **Group has a stable identity (UUID).** Operations like "open the Chinese exam," "ingest this exam," and "delete this exam group" all refer to a single ID.
- **Group-level metadata is first class.** `label`, `anchor_id`, and `notes` live on the group row, not on a member file.
- **Simple membership queries.** `SELECT * FROM exam_group_members WHERE group_id = ?` gives all members in one query. No graph traversal.
- **Scales cleanly.** N members = N rows in `exam_group_members`, regardless of N. No combinatorial blowup.
- **`role` column** captures each file's booklet function (`paper1`, `paper2_questions`, `paper2_answers`) in a well-defined place, readable by the ingestion pipeline.
- **Clean separation of concerns.** `file_relations` handles only derivative file relationships (raw↔compressed). `exam_groups` / `exam_group_members` handles grouping. Different semantics, different tables.

**Cons:**
- Slightly more complex schema (two more tables).
- Group operations require joins across three tables (`exam_groups`, `exam_group_members`, `pdf_files`).

### Decision

**Option B** (dedicated `exam_groups` + `exam_group_members` tables). The schema overhead is minimal and the benefits — stable group identity, first-class metadata, clean role labeling, and simple membership queries — are substantial.

### Consequences

- `file_relations.relation_type` CHECK constraint is restricted to `('compressed_version', 'raw_source')` only.
- `exam_groups` and `exam_group_members` are added to the schema.
- `DeletionRecord` gains an `exam_groups_snapshot` field (JSON) alongside the existing `relations_snapshot`, so the deletion log captures which groups a deleted file belonged to. (Note: `DeletionRecord` is later superseded by `OperationRecord` — see D-003.)
- The CLI gains a `group` subcommand family: `group create`, `group add`, `group remove`, `group anchor`, `group show`, `group list`, `group open`, `group delete`.
- The pipeline integration section of `SPEC.md` is updated to document how `get_file_exam_group()` feeds `exam_id` and `paper_type` during ingestion.

---

## D-001 — How to handle multi-file exams: merge vs. link

**Date:** 2026-03-06
**Status:** Decided
**Affects:** `SPEC.md` — database schema, exam group operations, CLI

### Context

Several exam types in Winston's archive consist of multiple physically separate PDF files that together constitute one exam sitting:

| Exam | Files |
|------|-------|
| English EoY | Paper 1 (writing, 14 pp) + Paper 2 (language & comprehension, 26 pp) |
| Chinese EoY | Paper 1 answer booklet (8 pp) + Paper 2 questions booklet (17 pp) + Paper 2 answers booklet (10 pp) |
| Higher Chinese EoY | Same 3-file structure as Chinese |

When the file manager needs to represent "the Chinese exam," there are two architectural options.

### Option A — Merge: combine constituent PDFs into one file before registration

The file manager (or a pre-step) concatenates the constituent PDFs into a single file. The exam entity maps 1:1 to one file on disk.

**Pros:**
- Simplest mental model — one exam = one file = one path.
- No link resolution needed; a single file can be passed to the ingestion pipeline directly.
- Easy to copy, move, or share the complete exam as a single artifact.

**Cons:**
- **Destroys provenance.** Each constituent file maps to one physical booklet scanned in a discrete session. The merged file is a synthetic artifact that never existed. If a rescan is needed for one booklet, the merged file must be recreated.
- **Creates a new derivative type.** The existing `_c_` prefix convention handles compressed derivatives. A merged file would require a third derivative type (e.g. `_m_`), a new naming scheme, and a new operation in the file manager. Complexity grows.
- **Compression is coupled.** The three source files may have been scanned and compressed at different times with different settings. Merging forces a single compression pass over mixed-quality sources, or requires merging before compression (meaning pre-compressed originals are not the inputs) — either way is awkward.
- **Blocks incremental workflows.** In practice, you scan Paper 1 on Monday and Paper 2 on Tuesday. Merging requires all parts to be in hand before anything is registered.
- **Loses booklet-level semantics.** The physical booklet boundary is semantically meaningful: the Answers booklet contains the cover page (with total scores), OAS, and all student handwriting; the Questions booklet is printed content only. Merging buries this distinction inside a flat page sequence unless it is re-encoded in the filename.

### Option B — Link: keep files separate, group them with an explicit association ✅ CHOSEN

Files remain as distinct disk files and registry entries. Membership in the same exam is recorded in a dedicated `exam_groups` table.

**Pros:**
- **Preserves the archival record exactly.** Each file maps to the scanner output for one physical booklet.
- **Aligned with the pipeline.** `L4_INGESTION_PIPELINE.md` already uses `exam_id` in the `documents` table to link multiple PDF documents to one exam. The file manager's group concept is the pre-ingestion, disk-level analog — the two layers are consistent, not in conflict.
- **Incremental workflow.** Files are registered and compressed as they arrive. The exam group is assembled by adding memberships — no blocking "all parts must be in hand" step.
- **Granular reprocessing.** Replacing or rescanning one booklet touches only that file; the rest of the group is unaffected.
- **Preserves booklet-level semantics.** The `role` field on `exam_group_members` explicitly encodes each file's function (`paper1`, `paper2_questions`, `paper2_answers`). The ingestion pipeline can read this to infer `paper_type` and know which file to look at for the OAS.

**Cons:**
- **Higher cognitive load when browsing.** A flat `list` shows 3 entries for Chinese where Math has 1. Addressed by a `list --grouped` view that nests members under their group label.
- **Link maintenance.** Files can be registered without being grouped. Addressed by (a) a `scan --suggest-groups` flag that offers auto-detected groupings for confirmation, and (b) `list --no-group` to surface ungrouped files.
- **"Which file is canonical?" ambiguity.** Addressed by the explicit `anchor_id` field on `exam_groups`. The anchor (typically the Answers booklet) is the entry point for `open_exam_group` and the primary document for pipeline ingestion.

### Decision

**Option B** (keep separate, link with relations). The cons of Option A are structural — they cannot be resolved without keeping the original files anyway. The cons of Option B are UX problems that are all solvable with well-designed group views and tooling.
