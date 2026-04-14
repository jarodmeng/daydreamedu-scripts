# GoodNotes Exam Files: Registration Proposal & pdf_file_manager Assessment

> **Context:** Winston's GoodNotes backup folder contains PDFs produced by different workflows (attempt-only, reviewed, attempt+review, reviewed-from-compressed). This doc proposes how to register them in the pdf_file_manager registry and eventually feed the L4 ingestion pipeline, and assesses whether current pdf_file_manager capabilities are sufficient.

---

## 1. GoodNotes folder and file categories (recap)

**Location:** `.../GoodNotes/Singapore Primary Math/winston.ry.meng@gmail.com/P6/Exam`

**Mirrored structure:** Same hierarchy under `.../DaydreamEdu/Singapore Primary Math/winston.ry.meng@gmail.com/P6/Exam` (and under `.../DaydreamEdu/.../P6/Exam` for template-only paths) holds the **source** files (templates, scored papers, compressed combined). GoodNotes outputs sync **into** the GoodNotes tree.

| Category | Example GoodNotes file | Source (DaydreamEdu) | Workflow |
|----------|------------------------|----------------------|----------|
| **1. Attempt only** | `P6 WA1 practice paper 1 (empty) (attempt).pdf` | `_c_P6 WA1 practice paper 1 (empty).pdf` (template) | Import empty template → Winston attempts → GoodNotes backup |
| **2. Reviewed only** | `P6 WA1 practice paper 1 (reviewed).pdf` | `_c_P6 WA1 practice paper 1.pdf` (scored paper) | Import scored paper → Jarod reviews (purple) → GoodNotes backup |
| **3. Attempt + review** | `p6.math.wa1.1 (empty) (attempt).pdf` | `_c_p6.math.wa1.1.pdf` (template under P6/Exam) | Import template → attempt + review in one doc → backup |
| **4. Reviewed from combined** | `c_P6 Math WA1 (reviewed).pdf` | `_c_P6 Math WA1.pdf` (compressed combined) | Import _c_ file → review → backup |

For ingestion, the **canonical “completion” to ingest** is the GoodNotes PDF: it carries student handwriting and (where applicable) parent/teacher feedback. The DaydreamEdu side holds templates and pre-compressed sources we use for **metadata and template linking** only.

---

## 2. Proposal: How to register GoodNotes files in the database

### 2.1 Principles

- **GoodNotes outputs = main files (completions) for ingestion.** The file that the pipeline ingests is always the **main** file (the one used for question extraction). On the DaydreamEdu side that main is usually `_c_<name>.pdf`; on the GoodNotes side it may appear as `c_<name>.pdf` (GoodNotes / Drive can drop the leading underscore).
- **One-way GoodNotes → Drive sync.** GoodNotes only ever writes into the `GoodNotes/` tree; it never reads back name changes. If the registry renames or moves PDFs inside `GoodNotes/`, GoodNotes will simply create *new* files on the next backup. To avoid duplicate backups and broken links, **pdf_file_manager must not rename or move the original GoodNotes-exported PDFs under the `GoodNotes/` tree.**
- **Use existing compress-and-register only under DaydreamEdu.** The raw/→`_c_` compression workflow (`compress_and_register`) *renames* the input file to `_raw_<name>` before writing `_c_<name>`, so it is safe only in the DaydreamEdu tree (templates, school scans, etc.). We must **not** run `compress_and_register` directly on GoodNotes files. If we later want compressed mains for GoodNotes content, that should use a GoodNotes-safe helper that **creates `_c_` copies without touching the original GoodNotes file**, and registers those copies as mains while leaving the originals unchanged.
- **File relations are on the main file.** Template linking (`completed_from` / `template_for`) is always set on the DaydreamEdu **main** file (`_c_<name>.pdf`) as the source, with the GoodNotes completion registered separately and linked to it. `link_template_by_paths(completed_path, template_path)` should use a **GoodNotes main path** on the completed side and a **DaydreamEdu `_c_` path** on the template side.
- **Link each completion (main) to its source.** Use the existing template relation to link the GoodNotes completion file to the DaydreamEdu file that was imported into GoodNotes. That gives metadata inheritance and traceability.
- **Support both naming styles and prefixes.** Category 1/2 use human names; category 3/4 use `p6.math.wa1.x` or `c_P6 Math WA1`. Template resolution works on the **main file’s basename** after normalising any leading `_c_` or `c_` prefix (see §4).

### 2.2 Where GoodNotes files live vs registry

- **DaydreamEdu** is already (or will be) a scan root; this is where we run full **compress-and-register** with the current semantics:
  - Non-`_c_` / non-`_raw_` PDFs under DaydreamEdu → `compress_and_register(..., preserve_input=False)` → `_raw_<name>` + `_c_<name>`, raw↔main relations created. The ingestion main is `_c_<name>`.
  - `_c_`-prefixed PDFs under DaydreamEdu → register as main only; do not compress again.
  - `_raw_` PDFs under DaydreamEdu → register as raw; if a corresponding main exists, create raw↔main relations.
- **GoodNotes** folder is a **second scan root with register-only semantics for the original exports**, plus an optional GoodNotes-safe compression path:
  - Files under a `GoodNotes/` segment are **never renamed or moved**. Their on-disk basenames remain exactly what GoodNotes wrote (including `c_` prefixes and “(attempt)/(reviewed)” tags).
  - If we want compressed mains for GoodNotes content, we use a **GoodNotes-safe variant** of compression (`compress_and_register(..., preserve_input=True)` or a dedicated helper) that:
    - reads the original GoodNotes file at `<name>` without renaming it,
    - writes a new `_c_<name>` compressed copy next to it (or under DaydreamEdu),
    - registers `<name>` as `file_type='raw'` and `_c_<name>` as `file_type='main'`, and
    - links them with raw↔main relations.
  - The ingestion pipeline and template-linking logic always target the `_c_` versions as the templates/sources; original GoodNotes filenames are only used for **template resolution** and as immutable raw sources.

### 2.3 Recommended registration flow (minimal manual work)

1. **Ensure DaydreamEdu sources are registered.**  
   All relevant templates and main files under `DaydreamEdu/.../P6/Exam` and `DaydreamEdu/.../winston.ry.meng/.../P6/Exam` should already be in the registry. Mark templates with `is_template=True`, completions (if any) with `is_template=False`.

2. **Add GoodNotes folder as a register-only scan root** (or handle it via a dedicated registration script) with `student_id` set if desired. For this root:
   - GoodNotes files are **only registered** (`register_file` + `_infer_from_path`); **no `compress_and_register`** and no renames/moves under `GoodNotes/`.
   - Their basenames (including `c_` prefixes and attempt/reviewed tags) remain exactly as written by GoodNotes.

3. **Link each GoodNotes completion to its DaydreamEdu source** using `link_template_by_paths(completed_path, template_path, inherit_metadata=True)`:
   - `completed_path` is a **GoodNotes main file** (whatever name GoodNotes produced).
   - `template_path` is the corresponding DaydreamEdu `_c_` file, obtained by calling `resolve_goodnotes_template_path(completed_path)` (see §4 and the helper in `pdf_file_manager.py`).

   Internally, template resolution:
   - Normalises the GoodNotes basename by stripping a leading `_c_` or `c_`.
   - Strips a trailing ` (attempt)` or ` (reviewed)`.
   - Uses the remaining core name as the DaydreamEdu template/base name (which already includes `(empty)` where applicable).

4. **Pipeline consumption.**  
   The ingestion pipeline (L4) uses main files and template for metadata. GoodNotes mains are no different. No schema change required.

### 2.4 “Template” for category 2 and 4 (reviewed-from-scored)

Conceptually, the **template** for a “reviewed” GoodNotes file is the document that was **imported into GoodNotes** before review — i.e. the scored/main file in DaydreamEdu. The pdf_file_manager currently defines template as “blank/master” and completion as “filled from that blank”. Here we reuse the same relation to mean “this GoodNotes PDF was produced from that DaydreamEdu PDF (import → annotate → export).” So:

- **completed_from** = “my content derives from this source file (template or scored).”
- Metadata inheritance still makes sense: the reviewed file inherits subject, exam metadata, etc., from the source.

No change to the relation type is required; we only broaden the semantic of “template” to “source document that was imported into GoodNotes to produce this completion.”

---

## 3. Assessment: Is pdf_file_manager sufficient?

### 3.1 What’s already sufficient

- **Scan + compress on DaydreamEdu.** The existing `scan_for_new_files` + `compress_and_register` behaviour is a good fit for the DaydreamEdu tree (where we *do* want `_raw_` archives and `_c_` mains, and renames are safe).
- **Register-only on GoodNotes.** For the GoodNotes tree we can already choose to **only call `register_file`** (either by treating it as a special scan root or via a dedicated script) and *not* call `compress_and_register` there, satisfying the “no rename under GoodNotes” constraint.
- **Register and classify:** `register_file`, `update_metadata` — used by scan and for any manual classification on both trees.
- **Template linking:** `link_to_template`, `link_template_by_paths` — enough to link each GoodNotes completion to the DaydreamEdu `_c_` source once we know the DaydreamEdu path.
- **Path-based inference:** `_infer_from_path` works for any path with the same L1/L2/L3 structure; GoodNotes root gets subject/student from path like DaydreamEdu.
- **No new relation types.** Template/completion is enough; “reviewed from scored” is just completion-from-source.
- **Ingestion:** Pipeline uses main files and template for metadata; GoodNotes mains are compatible.

### 3.2 Gaps and options to minimize manual work

| Gap | Option A — Better functions | Option B — Organize files / naming |
|-----|-----------------------------|------------------------------------|
| **Register-only semantics for GoodNotes tree** | Treat any path containing a `GoodNotes` segment as “no-compress”: in scan logic, call `register_file` + `_infer_from_path` but never `compress_and_register` there (or equivalently, expose a `register_only` flag on scan roots). | Keep GoodNotes-only content under a clearly named `GoodNotes/` segment so the rule is easy to apply. |
| **Resolving template path from main file basename** | Use the helper `PdfFileManager.resolve_goodnotes_template_path(main_path)` (or MCP wrapper) to normalise `_c_`/`c_`, strip `(attempt)/(reviewed)`, and return the DaydreamEdu `_c_` path; caller then uses `link_template_by_paths(completed_path, template_path)`. | Keep the mirrored folder structure and strict naming convention so the mapping is deterministic and documentable. |
| **Linking many pairs after scan** | **Batch link by convention:** e.g. `link_goodnotes_completions(goodnotes_dir)` or a script that (1) finds GoodNotes mains that have no `completed_from` yet, (2) calls `resolve_goodnotes_template_path` for each, (3) calls `link_template_by_paths(main_path, template_path)`. Run after each scan or on demand. | Same naming/organization as above so the resolver is reliable. |

### 3.3 Recommended direction

- **Scan:** Continue using full scan + compress on the DaydreamEdu tree. For the GoodNotes tree, either:
  - Treat it as a **register-only scan root** (scan calls `register_file` but skips `compress_and_register` under any `GoodNotes/` segment), or
  - Use a small **GoodNotes registration script** that enumerates PDFs under `GoodNotes/...`, calls `register_file` + `_infer_from_path`, and never renames/moves them.
- **After scan/registration:** Run a **template-linking step** that targets GoodNotes mains (under the GoodNotes root, `file_type='main'`, no `completed_from` yet). For each, call `resolve_goodnotes_template_path(main_path)` to get the DaydreamEdu `_c_` path, then `link_template_by_paths(main_path, template_path)`.
- **Implementation:** Either a small script that uses the Python API, or an MCP-backed tool that wraps `resolve_goodnotes_template_path` + `link_template_by_paths`. This keeps disk mutations (compress/rename) confined to the DaydreamEdu side while still giving full linkage between GoodNotes completions and their sources.

### 3.4 Summary table

| Goal | Current pdf_file_manager | Sufficient? | To minimize manual work |
|------|---------------------------|------------|---------------------------|
| Discover and register/compress GoodNotes PDFs | Normal scan (_c_ → main only; else compress_and_register) | Yes | Add GoodNotes as a normal scan root. |
| Set subject/student from path | `_infer_from_path` during scan | Yes | Same L1/L2 structure under GoodNotes. |
| Raw↔main relations after compress | Created by `compress_and_register` | Yes | No change. |
| Link completion (main) → source | `link_template_by_paths(completed_path, template_path)` | Yes | Naming-based resolver (script or helper) so template path is derived from **main** file basename. |
| Batch link after scan | No single API | No | Script or `link_goodnotes_completions(...)` that finds unlinked mains, resolves template, calls `link_template_by_paths`. |
| Pipeline uses GoodNotes mains | Main files + template relation | Yes | No change. |

Overall: **Current scan and register/compress behaviour is sufficient for the DaydreamEdu tree.** For the GoodNotes tree, we layer a **register-only, no-rename convention** on top, plus **convention-based template resolution** and a **post-scan linking step** (script or helper) so that each GoodNotes main is linked to its DaydreamEdu `_c_` source with minimal manual work and without disrupting GoodNotes’ one-way backup flow.

---

## 4. Implementation plan

### 4.1 Code changes (pdf_file_manager)

- **GoodNotes-aware compression**
  - Extend `compress_and_register` with a `preserve_input: bool = False` flag.
  - When `preserve_input=False` (default), keep current behaviour (rename to `_raw_<name>`, write `_c_<name>`, set main/raw as today).
  - When `preserve_input=True`:
    - Do **not** rename or move `<name>`.
    - Register `<name>` as `file_type='raw'` (or update from `'unknown'` to `'raw'` if already registered).
    - Run `compress_pdf` with `input_path=<name>`, `output_name="_c_<name>"` to create a sibling compressed copy.
    - Register `_c_<name>` as `file_type='main'`, copying `student_id`, `subject`, `doc_type`, `metadata` from `<name>` (or inferring via `_infer_from_path` if needed).
    - Create `file_relations` (`raw_source` / `main_version`) between `<name>` and `_c_<name>`, and set `has_raw=True` on the main.

- **GoodNotes-safe scan behaviour**
  - In `scan_for_new_files`, detect paths containing a `GoodNotes` segment.
  - For such paths:
    - Skip the rename-based `compress_and_register(..., preserve_input=False)` call.
    - Prefer the GoodNotes-safe `compress_and_register(..., preserve_input=True)` so that originals are kept as `raw` and compressed `_c_<name>` copies are registered as mains with raw↔main relations.
  - For DaydreamEdu paths, continue to call `compress_and_register(..., preserve_input=False)` as today.

- **Template resolution helper (already implemented)**
  - Use `PdfFileManager.resolve_goodnotes_template_path(main_path)` to:
    - Normalise leading `_c_`/`c_` prefixes.
    - Strip `(attempt)` / `(empty) (attempt)` / `(reviewed)` tags.
    - Map to the DaydreamEdu `_c_` path by replacing the `GoodNotes` segment with `DaydreamEdu`.

### 4.2 Batch-linking helper / script

- Implement a small script (or method) `link_goodnotes_completions(goodnotes_root, *, dry_run=False)` that:
  - Enumerates all PDFs under `goodnotes_root` (e.g. Winston’s `P6/Exam`).
  - For each file:
    - Ensure it is registered (and optionally compressed with `preserve_input=True` if a `_c_` copy is desired).
    - Look up the corresponding `PdfFile` for the GoodNotes main.
    - If it already has a `completed_from` relation, skip.
    - Call `resolve_goodnotes_template_path(main_path)` to compute the DaydreamEdu `_c_` template path.
    - Look up or register the DaydreamEdu `_c_` file.
    - Call `link_template_by_paths(main_path, template_path, inherit_metadata=True)`.
  - When `dry_run=True`, log the intended links without modifying the DB.

### 4.3 Migration / rollout steps

1. **Introduce `preserve_input` and GoodNotes detection** in `compress_and_register` + `scan_for_new_files`, with tests covering:
   - DaydreamEdu paths (existing behaviour unchanged).
   - GoodNotes paths with `preserve_input=True` (no rename of originals).
2. **Verify helper on real data**:
   - Run the existing dry-run script that prints `GoodNotes basename → DaydreamEdu template path` using `resolve_goodnotes_template_path`, and confirm all mappings look correct (as already done for Winston’s P6 WA1 files).
3. **Add batch-linking script** and run it in dry-run, then live mode, on Winston’s GoodNotes P6 Exam folder.
4. **Document GoodNotes scan root configuration**:
   - Add a short “GoodNotes scan root” note to `MCP.md` / `ARCHITECTURE.md` indicating that any `GoodNotes/` path should use register-only semantics (no rename of originals) and optionally GoodNotes-safe compression.

---

## 4. Naming rules for template resolution (reference)

Template resolution uses the **main file’s basename** (the file that is the completion). On the DaydreamEdu side this is usually `_c_<name>.pdf`; on the GoodNotes side it may appear as `c_<name>.pdf` (GoodNotes/Drive can drop the leading underscore). For pattern matching, strip a leading `_c_` **or** `c_` from the basename, then apply the rules below.

| Main file basename (after stripping `_c_`/`c_`) | DaydreamEdu template/source basename |
|-------------------------------------------------|--------------------------------------|
| `P6 WA1 practice paper N (empty) (attempt).pdf`  | `_c_P6 WA1 practice paper N (empty).pdf` (same N) |
| `P6 WA1 practice paper N (reviewed).pdf`   | `_c_P6 WA1 practice paper N.pdf` |
| `p6.math.wa1.K (empty) (attempt).pdf`           | `_c_p6.math.wa1.K.pdf` (same K) |
| `P6 Math WA1 (reviewed).pdf` or `c_P6 Math WA1 (reviewed).pdf` | `_c_P6 Math WA1.pdf` |

Path: DaydreamEdu base path is the same hierarchy under the DaydreamEdu root (e.g. `.../DaydreamEdu/Singapore Primary Math/winston.ry.meng@gmail.com/P6/Exam` for category 1/2/4, and `.../DaydreamEdu/Singapore Primary Math/P6/Exam` for category 3). Resolver takes the **main** file path (in GoodNotes tree), strips `_c_` from basename for matching, maps to template basename, then builds the DaydreamEdu path by replacing the “GoodNotes” path segment with “DaydreamEdu”.
