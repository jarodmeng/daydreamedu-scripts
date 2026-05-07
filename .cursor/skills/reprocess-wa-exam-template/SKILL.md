---
name: reprocess-wa-exam-template
description: >-
  Reprocesses student scanned weighted assessment/exam PDFs into cleaned
  general-scope templates and links student completion files to those templates.
  Use when school-returned papers are scanned with writing, usually as `_raw_`
  files, and the user wants one merged handoff PDF for external cleanup followed by
  split/template placement and registry linking—even when list lines span multiple
  student-scope leaf folders.
---

# Reprocess WA/Exam Template (MVP)

## When this skill applies

- Student scanned school papers (weighted assessments or exams) include handwriting and must be cleaned.
- Files are currently student completion files and should end with template-linked completion records.
- User wants to clean one merged file externally, not multiple files.

## Required inputs (ask if missing)

1. Path to the list txt file (absolute paths, one PDF per line; `#` comments allowed).
2. Confirmation of external-cleaning handoff path (default output convention is used unless user overrides).
3. **When the batch spans more than one unique `(subject, grade, doc_type)` template-branch triple** across list rows (multi-leaf-folder batch): an explicit `<doc label>` for the Phase A merged file and the Phase B cleaned default (`<doc label> - merged.pdf` / `<doc label> - cleaned.pdf` at `DAYDREAMEDU_ROOT`), or an explicit full path override for both artifacts. If ambiguous and missing, stop and ask—the default label `<subject> <grade> <doc_type>` applies only when that triple is the same for every row.

## Input conventions and derivation rules

- Do not ask for student email as a required input in MVP.
- Derive student scope and destination paths **per row** from each listed path.
- The doc type folder name is inferred from the same folder structure as that row’s student-scope file (for example `Exam` or `Weighted Assessment`) and defines that row’s template destination root `DAYDREAMEDU_ROOT/template/<subject>/<grade>/<doc_type>/`.
- **Multi-leaf-folder batches are allowed**: list lines may resolve to different `(subject, student_email, grade, doc_type)` tuples. Phase A still produces **exactly one** merged PDF at the repo root for external cleanup; Phase B consumes **that same** cleaned PDF once, splits it in original list order, and routes each segment to **that row’s** template folder and links against **that row’s** completion folder.
- Canonical source layout for each listed path is:
  - `DAYDREAMEDU_ROOT/completion/<subject>/<student_email>/<grade>/<doc_type>/<filename>.pdf`
  - with `<grade>` in `P1`-`P6` or `PSLE`.
- Canonical template destination layout is:
  - `DAYDREAMEDU_ROOT/template/<subject>/<grade>/<doc_type>/<filename_without_raw_prefix>.pdf`
- If any listed path does not match the canonical source layout exactly, stop and ask; do not infer by guesswork.
- Derive `<doc label>` for merged/cleaned artifacts at `DAYDREAMEDU_ROOT`:
  - When **every** row shares one `(subject, grade, doc_type)` triple: default `<subject> <grade> <doc_type>` unless the user overrides.
  - When **more than one** distinct `(subject, grade, doc_type)` appears across rows: **no default**—require an explicit `<doc label>` or explicit merged/cleaned path override from the user before Phase A (see Required inputs).
- If list lines name `_c_<name>.pdf` (completion mains), **do not merge those files for Phase A**. Resolve the sibling `_raw_<name>.pdf` in the same directory, require that it exists, and merge `_raw_` PDFs in list order. Basename and collision checks use the resolved `_raw_` paths (working basename = strip one leading `_raw_`).
- **Per-row folders** (for Phase B boundaries, placement, scan, link): From each normalized list path, `student_dir` = dirname of that PDF (the `…/<doc_type>` folder); template directory for that row = `DAYDREAMEDU_ROOT/template/<subject>/<grade>/<doc_type>/` parsed from the same path.

## Fail-fast validation (run before Phase A actions)

1. Parse and normalize all list entries (`expanduser().resolve()`), preserving txt order.
2. Reject immediately if any item:
   - is not under `DAYDREAMEDU_ROOT`;
   - is not a `.pdf`;
   - does not exist as a file;
   - does not match the canonical source layout above.
3. For each row, parse `(subject, student_email, grade, doc_type)` and `student_dir` from the canonical path. Collect the set of distinct `(subject, grade, doc_type)` triples:
   - if `|triples| > 1` and the user has not supplied an explicit `<doc label>` (or explicit merged/cleaned path override), stop and ask.
4. After resolving Phase A merge sources (`_c_` list → `_raw_` sibling when applicable), reject **duplicate** normalized paths (the same PDF must not appear twice in merge order).
5. **Planned template path uniqueness** (replaces “global working basename must differ”): For each row, canonical output basename = working basename with at most one leading `_raw_` stripped (same as today). Planned template file path = `DAYDREAMEDU_ROOT/template/<subject>/<grade>/<doc_type>/<canonical_basename>.pdf` using that row’s parsed components. If any two rows produce the **same** planned path, stop and ask (filesystem/registry collision). Rows in **different** template folders may share the same filename (same canonical basename under different `<subject>/<grade>/<doc_type>`) — that is allowed.
6. Compute destination collision checks before moving (evaluate **every** row’s intended student-scope paths **and** every **planned split template path** from step 5 against existing files/registry):
   - any existing destination completion/template file path that would block Phase B placement => stop and ask;
   - any existing merged/cleaned artifact at intended path => stop and ask (or require explicit replacement instruction).
7. Only proceed to Phase A after all checks pass.

## Prerequisites

- Read and follow [`pdf-file-manager`](../pdf-file-manager/SKILL.md) for registry operations.
- Resolve DaydreamEdu root via `resolve_daydreamedu_root()` from [`ai_study_buddy/files/roots.py`](../../../ai_study_buddy/files/roots.py).
- For path-changing moves, keep disk + registry in sync:
  - If source is already registered, move with `PdfFileManager.move_file(...)` (preferred; updates DB and path-derived scope fields).
  - If source is not registered, use shell `mv`.
  - If an on-disk move happened first (external/manual), run immediate reconciliation so registry path matches final location before continuing.
- For deletions, move to Trash (`mv <path> ~/.Trash/`), never `rm`.

## Workflow

### Phase A — Prepare, move, and merge (mandatory)

1. Validate list file:
   - Read lines in order, skip blank/comment lines.
   - Apply all rules from "Fail-fast validation"; do not continue on partial validity.
2. Derive normalized target metadata **per list row** (preserve row order end-to-end: merge order, split order, segment-to-folder routing):
   - Subject, student segment, grade, doc type, `student_dir`, and basename.
   - Basename convention: if file starts with `_raw_`, strip one `_raw_` only for canonical matching keys; do not use this to rename student-side files on disk.
3. Move completion files into the canonical student-scope destination if needed:
   - Decide move method per file:
     - If file is registered at source path, call `PdfFileManager.move_file(file_id_or_path=<source>, new_dir=<dest_dir>)`.
     - Otherwise use shell `mv`.
   - Stop on collisions; do not overwrite silently.
   - Do not rewrite technical prefixes during this move (`_raw_` / `_c_` must be preserved).
   - If a source file is `_raw_<name>.pdf`, destination must remain `_raw_<name>.pdf` (never rename to plain `<name>.pdf` in this workflow).
   - Mandatory reconciliation check after each move batch:
     - For every intended destination path, verify `PdfFileManager.get_file_by_path(dest_path)` resolves.
     - If missing but old source path is still the registered path, stop and reconcile before Phase A proceeds.
4. Merge all **Phase A source** PDFs in list order into one PDF (mandatory)—use `_raw_` siblings when the list lines are `_c_` paths (see Input conventions).
   - Output: `DAYDREAMEDU_ROOT/<doc label> - merged.pdf` (or user-provided override).
   - Verify merged page count equals sum of source page counts.
5. Stop for external cleanup:
   - User cleans the merged file outside this workflow.
   - Expected cleaned artifact default: `DAYDREAMEDU_ROOT/<doc label> - cleaned.pdf`.

### Phase B — Split cleaned output, place templates, scan, and link

1. Validate cleaned PDF exists and page count matches expected merged total.
2. Derive per-segment split boundaries from student completion files in **original txt list order**, using **each row’s** `student_dir` (see Input conventions):
   - For row *i*, let `<name>.pdf` be that row’s canonical basename (same key used after Phase A `_raw_` resolution).
   - In **that row’s** `student_dir` only, check main candidates in this order:
     1. `_c_<name>.pdf`
     2. `<name>.pdf`
   - Use the first existing candidate to compute page count for segment *i*.
   - If `_c_<name>.pdf` exists, do not use plain `<name>.pdf` for boundaries for that row.
   - If both `_raw_<name>.pdf` and plain `<name>.pdf` exist in that `student_dir` but `_c_<name>.pdf` is absent, stop and ask (likely main/raw drift that should be repaired first).
   - If neither exists for any row, stop and ask.
3. Split cleaned PDF by those derived per-file page counts in original txt order.
4. Move each split cleaned segment **i** into **that row’s** template folder (`DAYDREAMEDU_ROOT/template/<subject>/<grade>/<doc_type>/` parsed from the same list line), not a single batch-wide folder:
   - Keep canonical basenames (without `_raw_`).
5. Run `PdfFileManager().scan_for_new_files` on **every distinct directory** that needs registry visibility for this batch:
  - **All** template folders that received a split (union of row template dirs).
   - **All** student-scope folders referenced by list rows (`student_dir` union).
   - After scan, resolve main candidates in this order for both sides:
     1. `<dir>/_c_<name>.pdf`
     2. `<dir>/<name>.pdf`
   - Student-side preference is strict: when `_c_<name>.pdf` exists, treat it as the completion main and ignore plain `<name>.pdf`.
   - Note: scan/compress may materialize `_raw_` + `_c_` pairs from plain split files; do not assume the pre-scan plain path remains the main file.
   - Important: `scan_for_new_files` does not rewrite existing registered paths for files moved externally; do not treat scan as a substitute for move reconciliation.
6. Ensure template/completion status:
   - General files become/are registered with `is_template=true`.
   - Student files remain `is_template=false`.
7. Link completion to template **for each list row** (aligned with segment index *i*):
  - Match by canonical basename between **that row’s** `student_dir` and **that row’s** template directory (never assume a single completion folder or single template folder for the whole batch).
   - Completion main path should use `_c_` naming where present (`_c_<name>.pdf`).
   - Template main path should use `_c_` naming where present (`_c_<name>.pdf`).
   - Call `link_to_template(completed_id=<student_main_id>, template_id=<general_main_id>, inherit_metadata=True)`.

## Verification checklist (required)

- Every intended general main file is present and registered as template (`is_template=true`).
- Every intended student main file is present and registered as completion (`is_template=false`).
- Every student completion in scope resolves a template link to the matching general template file.
- No unexpected duplicate template candidates for the same canonical basename **within the same template folder** (`DAYDREAMEDU_ROOT/template/<subject>/<grade>/<doc_type>/`).
- Verification should be identity-based in the registry (resolved main path + linked template id), not strict string equality against the pre-scan plain split filename.
- No path-drift for moved files: for each file moved in this run, old path is not the active registered path and final destination path resolves via `get_file_by_path`.

## Rerun and failure handling

- If a completion already has a template link, skip and record unless user asks to relink.
- If cleaned split counts do not match expected source counts, stop and ask (no guessed boundaries).
- If destination files already exist, stop and ask before replacing.

## Cleanup

- After successful Phase B, move temporary artifacts to Trash when present:
  - `DAYDREAMEDU_ROOT/<doc label> - merged.pdf`
  - `DAYDREAMEDU_ROOT/<doc label> - cleaned.pdf`

## Observed in live run

- In real WA/Exam student folders, completion files may exist only as `_c_*.pdf` plus `_raw_*.pdf`, without plain `<name>.pdf`.
- Phase B boundary detection should prefer `_c_*.pdf` first, with plain `<name>.pdf` only as fallback when `_c_` is absent.
- Template linking should target main files (`_c_*.pdf`) on both student and general sides when available.
- In template-folder Phase B runs, scan/compress can replace a newly split plain file with `_raw_` and `_c_`; post-scan linking/verification should resolve `_c_` first, then plain.

## MVP constraints

- This MVP optimizes for recurring WA/Exam runs: either one student-scope leaf folder or **one multi-folder batch** with a single merged/cleaned handoff and per-row routing in Phase B.
- It does not yet include advanced registry cleanups used in the two-part "student completion from general" workflow.
- If future runs need book-group or mapping repair semantics, extend this skill with an "advanced mode" section.
