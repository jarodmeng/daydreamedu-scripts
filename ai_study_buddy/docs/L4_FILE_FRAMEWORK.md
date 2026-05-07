## Context
1) We have pdf_file_manager module for managing on-disk pdf files used in the broader ai_study_buddy project.

There are some conceptual foundations of what those files are. Having a clear framwork can help better design the tools and workflows, and better utilize those files.

## Assumptions
1. In this document, "file" always refers to a PDF file.
2. "On-disk file" means a PDF that exists physically under a root folder (e.g. DAYDREAMEDU_ROOT or GOODNOTES_ROOT), regardless of whether it is registered.
3. "Registered file" means a PDF that has a corresponding record in the pdf_file_manager registry.
4. All files in scope are main files (e.g. files with "_c_" prefix in their base names), not raw files (e.g. files with "_raw_" prefix in their base names).

## On-disk file organization

The chart below describes the on-disk PDF universe under the 2 roots and how excluded folders relate to reporting workflows.

```mermaid
flowchart LR
    D["D_ROOT (DAYDREAMEDU_ROOT)\nAll on-disk PDF files"]
    G["G_ROOT (GOODNOTES_ROOT)\nAll on-disk PDF files"]

    DEX["Excluded examples\n- root leaf '.' (when direct PDFs exist in root)"]
    DT["template subtree\ntemplate/&lt;subject&gt;/&lt;grade&gt;/&lt;type&gt;/&lt;optional book name&gt;/file.pdf"]
    DC["completion subtree\ncompletion/&lt;subject&gt;/&lt;student&gt;/&lt;grade&gt;/&lt;type&gt;/&lt;optional book name&gt;/file.pdf"]

    GEX["Coverage / leaf-report exclusions (examples)\n- root leaf '.'\n- 'Not completed' subtree (reports only; nuance ↓ Notes)\n- segment matching xUppercase... pattern (structural)"]
    GC["completion subtree\n&lt;subject&gt;/&lt;student&gt;/&lt;grade&gt;/&lt;type&gt;/&lt;optional book name&gt;/file.pdf"]

    D --> DEX
    D --> DT
    D --> DC
    G --> GEX
    G --> GC
```

Notes:
- This section is about on-disk organization only (physical files and path layout).
- Under `DAYDREAMEDU_ROOT`, the first segment is always `template` or `completion`; subject folders sit under that branch.
- Exclusions in **GEX** attach to **traversal/reporting semantics**, not ownership: those PDFs remain on-disk under `GOODNOTES_ROOT`.
- **`Not completed` segments (GoodNotes):** These folders hold **Work-in-progress** completion PDFs. **Leaf-registry reports** (`.cursor/commands/goodnotes-leaf-registry-report.md`) **exclude** those leaf folders by default so summaries target **registration-ready gaps** (`list_goodnotes_leaf_folders_under_root(..., exclude_not_completed=True)` in `ai_study_buddy.files`). **Browsing / viewers** should typically **include** them so work in progress stays visible (**`exclude_not_completed=False`**, as in **`root_pdf_browser`** / `is_goodnotes_excluded_relative_path(..., exclude_not_completed=False)`).
- **Structural x-prefix** segments (`^x[A-Z].*$`) are treated as **out of coverage** for both reports and local browse unless a tool explicitly changes that behavior.
- `<optional book name>` appears only when `type` is `book`.

## Registered file structure

In general, I divide registered files into the following hierarchical structure according to attributes. All of those attributes are stored in the pdf_file_manager registry.
1. The top-level attribute of a registered file is template vs. completion. A template registered file is basically "empty" (i.e. they haven't been worked on). Examples are cleaned school exams or exercises (we usually use the "reprocess-wa-exam-template" skill to general them from a scanned completion file). A completion registered file has been worked on (usually this means the questions in the file are answered).
   - A completion registered file is student-scoped (i.e. it must have student_id attribute set because it must belong to a particular student). A template registered file is general-scoped (i.e. it's not attached to a particular student although it might be sourced/cleaned from a student's completion file, usually by using the "reprocess-wa-exam-template" skill).
2. The following second-level attributes apply to both template and completion registered files.
   - "subject" refers to the 4 primary school subjects: chinese, english, math, and science. This attribute appears in a registered file's path as a folder name.
   - "grade" refers to the primary school grade. It can be single-grade (i.e. P1 to P6) or across-grade (i.e. PSLE). This attribute also appears in a registered file's path as a folder name.
   - "type" refers to the content type of the registered file. Template registered files should only have 3 distinct main types: "exam", "exercise", and "book". Completion registered files also have the 3 types with 2 additional types: "activity" and "note". If we tighten the definition of "completion registered file" to include only the main types, then template and completion registered files have the same "type" enums, but some of the on-disk student-scoped files are no longer categorized as "completion registered files". This attribute appears in a registered file's path as a folder name too.
3. There's 3 third-level attributes.
   - "root" refers to the root folder of the registered file path. There are 2 roots: DAYDREAMEDU_ROOT and GOODNOTES_ROOT. Template registered files are only stored in DAYDREAMEDU_ROOT while completion registered files can be stored in both DAYDREAMEDU_ROOT and GOODNOTES_ROOT. This attribute technically also appears in a registered file's path because it's the root part of the path. But this attribute is not as innate to the registered file as the second-level attributes. It's somewhat arbitrary in nature.
   - "book group" refers to the actual book a "book"-type registered file is part of. This is a third-level attribute because it only applies to a registered file whose second-level "type" attribute is "book". This attribute also appears in a registered file's path as a folder name.
   - "book unit" refers to a registered file's unit in the book. Similar to the "book group" attribute above, it only applies to a registered file whose second-level attribute "type" is "book".
4. "normal_name" is the fourth-level attribute of a registered file. This refers to the registered file's base name with prefix (e.g. "_raw_", "_c_", and "c_") and file extension stripped.

## File utilities

### `files` module (`ai_study_buddy.files`)

Use `ai_study_buddy.files` as the centralized file-utility surface for deterministic filesystem + registry-correlation logic.

- **Roots + leaf folders (registry-agnostic):**
  - `resolve_daydreamedu_root()`, `resolve_goodnotes_root()`
  - `list_leaf_folders_under_root()`, `list_daydreamedu_leaf_folders_under_root()`, `list_goodnotes_leaf_folders_under_root()`
  - `is_goodnotes_excluded_relative_path(...)` for structural GoodNotes exclusions (including optional `exclude_not_completed`)
- **Registry correlation (read-only, via `PdfFileManager` rows):**
  - `RegistryPathIndex.from_pdf_file_manager(pfm)` builds canonical resolved-path sets and row counts.
  - Leaf partition/profile helpers: `partition_daydreamedu_leaf_folders(...)`, `partition_goodnotes_leaf_folders(...)`.
  - Per-leaf helpers: `leaf_folder_registry_status(...)`, `leaf_registry_statuses_for_included_leaves(...)`, `registration_buckets(...)`.
  - Atomic per-PDF helpers: `is_pdf_registered(...)`, `pdf_file_registry_status(...)`, `leaf_pdf_file_registry_statuses(...)`.
- **Determinism rule:** callers should not hand-roll path normalization, set-difference leaf partitioning, or ad hoc `find_files()`/`list_scan_roots()` membership checks outside this module.

This module is now the default place to implement reusable “on-disk leaf ↔ registry” behavior so tools (for example command docs and later `root_pdf_browser` enhancements) can share the same semantics.

API contract and versioned details: [`ai_study_buddy/files/SPEC.md`](../files/SPEC.md).

### Unregistered on-disk files

Use these command docs to audit on-disk PDFs that are not represented in the registry:

- `.cursor/commands/daydreamedu-leaf-registry-report.md`
  - Compares DaydreamEdu leaf folders (folders with direct `*.pdf` files) against `pdf_file_manager` registered paths. Under `DAYDREAMEDU_ROOT`, registered PDFs live under `template/...` or `completion/...`; leaf and scan-root paths follow that layout.
  - Excludes the root leaf `.` from totals/tables when applicable.
  - Reports counts for scan roots vs non-scan-roots and a 4-bucket registration breakdown (`all registered` vs `some unregistered` crossed with scan-root status).
  - Surfaces unregistered basenames per leaf folder and can provide a full folder table on request.

- `.cursor/commands/goodnotes-leaf-registry-report.md`
  - Runs the same leaf-folder vs registry comparison for GoodNotes.
  - Enumerates leaf folders via **`list_goodnotes_leaf_folders_under_root(root)`** (default **`exclude_not_completed=True`**): omits **`Not completed`** subtrees plus root leaf `.` and **`^x[A-Z].*$`** segments. Other callers may set **`exclude_not_completed=False`** to list WIP completions (same module); this command keeps the default.
  - Produces the same summary/breakdown structure as the DaydreamEdu report, including unregistered basenames.

Both commands perform exact resolved-path matching (`Path.resolve()` string equality), so moved files may appear unregistered at the new location if registry paths were not updated.

Interpretation of the key output fields: `scan-root` tells you whether a leaf folder is configured as an intentional scan boundary in `PdfFileManager().list_scan_roots()`; `registered` vs `unregistered` is determined by exact resolved-path matching between each direct PDF in that leaf and `PdfFileManager().find_files()`. In practice, the 4 summary categories are:

1. scan-root + all direct PDFs registered
2. scan-root + some direct PDFs unregistered
3. non-scan-root + all direct PDFs registered
4. non-scan-root + some direct PDFs unregistered

These 4 categories are MECE (mutually exclusive and collectively exhaustive): each included leaf folder maps to exactly one category, and all included leaf folders are covered.

### Local PDF browser (`root_pdf_browser`)

[`ai_study_buddy/root_pdf_browser/README.md`](../root_pdf_browser/README.md) — small **localhost** HTTP + static UI to **view** PDFs under configured **`DAYDREAMEDU_ROOT`** and **`GOODNOTES_ROOT`** (resolved via `ai_study_buddy.files` roots helpers). Registry-agnostic browsing only; no registry reads.

- **Navigation:** a **leaf-prefix tree** computed at startup from the same PDF-leaf-folder definitions as **`ai_study_buddy.files`**: prefixes of **`list_daydreamedu_leaf_folders_under_root(daydreamedu_root)`** on DaydreamEdu and **`list_goodnotes_leaf_folders_under_root(goodnotes_root, exclude_not_completed=False)`** on GoodNotes. Directories that never ancestor a leaf folder (no direct **`*.pdf`** in that subtree per the **`files`** rules) are hidden—avoids stray top-level clutter (for example accidental **`db/`** dirs) whilst still traversing **`Not completed`** WIP subtrees where they contain PDF leaf folders.
- **`/api/pdf`** is served only when the resolved file sits in a leaf folder keyed in that snapshot; restart the server to refresh after large on-disk moves.
- **Run:** `.cursor/commands/start-root-pdf-browser.md` or `python3 -m ai_study_buddy.root_pdf_browser.spawn_background` / `serve` — see README.

### Registry integrity audit script

The `ai_study_buddy/pdf_file_manager/scripts/validate_pdf_registry_integrity.py` script is a reproducible integrity audit for the registry and on-disk state. It checks common drift and consistency issues such as missing on-disk files for registered paths, student/general scope template flag mismatches, missing `student_id` in student scope, raw/main metadata drift, raw/main relation consistency, invalid enum-like metadata values (`subject`, `metadata.grade_or_scope`, legacy `metadata.chinese_variant=foundation`), and invalid template `doc_type` values.

How to run:

- `python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity`
- `python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity --json`
- `python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity --db /path/to/pdf_registry.db`

Output behavior:

- Human-readable mode prints a summary count per check and example rows (bounded by `--limit`, default `20`).
- JSON mode emits a machine-readable object with `summary` counts and full `checks` arrays.
- Exit code is `0` when all checks pass, and `1` when any check reports issues.