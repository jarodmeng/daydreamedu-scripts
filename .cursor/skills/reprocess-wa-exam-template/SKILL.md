---
name: reprocess-wa-exam-template
description: >-
  Reprocesses student scanned weighted assessment/exam PDFs into cleaned
  general-scope templates and links student completion files to those templates.
  Use when school-returned papers are scanned with writing, usually as `_raw_`
  files, and the user wants a merged file for external cleanup followed by
  template/completion registry linking.
---

# Reprocess WA/Exam Template (MVP)

## When this skill applies

- Student scanned school papers (weighted assessments or exams) include handwriting and must be cleaned.
- Files are currently student completion files and should end with template-linked completion records.
- User wants to clean one merged file externally, not multiple files.

## Required inputs (ask if missing)

1. Path to the list txt file (absolute paths, one PDF per line; `#` comments allowed).
2. Confirmation of external-cleaning handoff path (default output convention is used unless user overrides).

## Input conventions and derivation rules

- Do not ask for student email as a required input in MVP.
- Derive student scope and destination paths directly from each listed path.
- The target doc type is inferred from the same folder structure as the source student-scope files (for example `Exam` or `Weighted Assessment`) and reused for general-scope outputs.
- All listed files in one run should share one subject + one grade + one doc type. If mixed, stop and ask.
- Canonical source layout for each listed path is:
  - `DAYDREAMEDU_ROOT/<subject>/<student_email>/<grade>/<doc_type>/<filename>.pdf`
  - with `<grade>` in `P1`-`P6`, `PSLE`, or `Archive`.
- Canonical general template destination layout is:
  - `DAYDREAMEDU_ROOT/<subject>/<grade>/<doc_type>/<filename_without_raw_prefix>.pdf`
- If any listed path does not match the canonical source layout exactly, stop and ask; do not infer by guesswork.
- Derive `<doc label>` for merged/cleaned artifacts from stable shared scope:
  - default: `<subject> <grade> <doc_type>`
  - if user provides a custom label/path, use that instead.
- If list lines name `_c_<name>.pdf` (completion mains), **do not merge those files for Phase A**. Resolve the sibling `_raw_<name>.pdf` in the same directory, require that it exists, and merge `_raw_` PDFs in list order. Basename and collision checks use the resolved `_raw_` paths (working basename = strip one leading `_raw_`).

## Fail-fast validation (run before Phase A actions)

1. Parse and normalize all list entries (`expanduser().resolve()`), preserving txt order.
2. Reject immediately if any item:
   - is not under `DAYDREAMEDU_ROOT`;
   - is not a `.pdf`;
   - does not exist as a file;
   - does not match the canonical source layout above.
3. Compute shared tuple `(subject, student_email, grade, doc_type)` from all rows:
   - if more than one unique tuple is present, stop and ask to split into separate runs.
4. Check canonical basename mapping (after resolving merge targets: `_c_` list → `_raw_` sibling when applicable):
   - working basename = strip exactly one leading `_raw_` when present;
   - if two different source rows map to the same working basename, stop and ask.
5. Compute destination collision checks before moving:
   - any existing destination completion/template file path => stop and ask;
   - any existing merged/cleaned artifact at intended path => stop and ask (or require explicit replacement instruction).
6. Only proceed to Phase A after all checks pass.

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
2. Derive normalized target metadata from paths:
   - Subject, student segment, grade, doc type, and basename.
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
2. Derive per-file split boundaries from student completion files in original txt order:
   - For each canonical basename `<name>.pdf`, check student folder in this order:
     1. `<student_dir>/_c_<name>.pdf`
     2. `<student_dir>/<name>.pdf`
   - Use the first existing main candidate to compute page count.
   - If `_c_<name>.pdf` exists, do not use plain `<name>.pdf` for boundaries.
   - If both `_raw_<name>.pdf` and plain `<name>.pdf` exist but `_c_<name>.pdf` is absent, stop and ask (likely main/raw drift that should be repaired first).
   - If neither exists for any entry, stop and ask.
3. Split cleaned PDF by those derived per-file page counts in original txt order.
4. Move split cleaned files into matching general-scope folder for inferred subject + grade + doc type:
   - Keep canonical basenames (without `_raw_`).
5. Run `PdfFileManager().scan_for_new_files` on:
   - The affected general-scope folder.
   - The matching student-scope folder.
   - After scan, resolve main candidates in this order for both sides:
     1. `<dir>/_c_<name>.pdf`
     2. `<dir>/<name>.pdf`
   - Student-side preference is strict: when `_c_<name>.pdf` exists, treat it as the completion main and ignore plain `<name>.pdf`.
   - Note: scan/compress may materialize `_raw_` + `_c_` pairs from plain split files; do not assume the pre-scan plain path remains the main file.
   - Important: `scan_for_new_files` does not rewrite existing registered paths for files moved externally; do not treat scan as a substitute for move reconciliation.
6. Ensure template/completion status:
   - General files become/are registered with `is_template=true`.
   - Student files remain `is_template=false`.
7. Link completion to template:
   - Match by canonical basename in corresponding student/general folders.
   - Completion main path should use `_c_` naming where present (`_c_<name>.pdf`).
   - Template main path should use `_c_` naming where present (`_c_<name>.pdf`).
   - Call `link_to_template(completed_id=<student_main_id>, template_id=<general_main_id>, inherit_metadata=True)`.

## Verification checklist (required)

- Every intended general main file is present and registered as template (`is_template=true`).
- Every intended student main file is present and registered as completion (`is_template=false`).
- Every student completion in scope resolves a template link to the matching general template file.
- No unexpected duplicate template candidates for the same canonical basename.
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
- In general-scope Phase B runs, scan/compress can replace a newly split plain file with `_raw_` and `_c_`; post-scan linking/verification should resolve `_c_` first, then plain.

## MVP constraints

- This MVP optimizes for recurring WA/Exam runs with one coherent batch.
- It does not yet include advanced registry cleanups used in the two-part "student completion from general" workflow.
- If future runs need book-group or mapping repair semantics, extend this skill with an "advanced mode" section.
