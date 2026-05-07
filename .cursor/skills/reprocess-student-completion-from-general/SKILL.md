---
name: reprocess-student-completion-from-general
description: >-
  Reprocesses mistaken template-branch `_raw_` book PDFs that are actually a
  student's completions using a two-phase workflow with an explicit external
  cleaning checkpoint: Phase A moves files to student scope, cleans registry and
  book group state, and builds a merged PDF; Phase B splits a cleaned PDF back
  into template units, rescans, links student completions to templates, and
  verifies final registry integrity. Use when a list of template-branch `_raw_`
  files needs correction without losing template/completion relationships.
---

# Reprocess student completion from general (unified)

## When this skill applies

- User provides a txt list of template-branch `_raw_` PDFs under a `.../Book/<book name>/` tree.
- Those files are actually student completions and must be re-scoped.
- User will clean writings externally on a single merged file between phases.

## Required inputs (ask if missing)

1. Path to txt list file (absolute paths, one per line, `#` comments allowed).
2. Student folder email segment to insert under `<subject>/`.
3. Confirmation that external cleaning will produce a cleaned merged PDF for Phase B.
4. For Phase B runs: cleaned PDF path plus the same txt list used in Phase A.

## Prerequisites

- Read and follow [`pdf-file-manager`](../pdf-file-manager/SKILL.md).
- Resolve DaydreamEdu root with `resolve_daydreamedu_root()` from [`ai_study_buddy/files/roots.py`](../../../ai_study_buddy/files/roots.py).
- Use shell `mv` for moves; do not emulate moves via copy+delete.
- Move deletions to Trash (`mv <path> ~/.Trash/`), never `rm`.

## Path layout rules

- Source list paths must be template branch:
  - `DAYDREAMEDU_ROOT/template/<subject>/<grade>/Book/<book name>/<file>.pdf`
  - `<grade>` must be one of `P1`-`P6` or `PSLE`.
- Student destination mirror:
  - `DAYDREAMEDU_ROOT/completion/<subject>/<student_email>/<grade>/Book/<book name>/<file_without_raw_prefix>.pdf`
- Basename normalization:
  - `_raw_<name>.pdf` -> `<name>.pdf` (strip one leading `_raw_`).

If any input path already includes a student-email segment between subject and grade, stop and ask.

## Fail-fast validation (before any mutation)

1. Parse txt entries in order, skipping blank/comment lines.
2. Validate each path:
   - exists as a file;
   - lives under DaydreamEdu root;
   - basename starts with `_raw_`;
   - fits expected general-scope book layout.
3. Ensure all entries belong to exactly one book folder (`.../Book/<book name>/`).
4. Ensure no duplicate normalized basenames after `_raw_` stripping.
5. Pre-check destination collisions for student-scope move targets.
6. Derive `<book name>` and verify merged/cleaned top-level artifact paths are not conflicting unless user approves replacement.

## Workflow

### Phase A - relocate, clean registry, merge (mandatory)

1. Move each listed file into student mirror path with `_raw_` removed from basename (`mv`, no overwrite).
2. Registry cleanup for original template-branch records (per listed original path):
   - locate registered raw/main rows with `PdfFileManager`;
   - remove main from template book group membership;
   - delete unit `book_answer_mapping` if present;
   - delete main with `keep_related=False` to cascade raw relation cleanup.
3. Build merged PDF from moved student files in original txt order:
   - output path: `DAYDREAMEDU_ROOT/<book name> - merged.pdf`.
   - verify merged page total equals sum of source pages.
4. Stop at checkpoint and hand off:
   - user cleans merged PDF externally;
   - expected cleaned output default:
     - `DAYDREAMEDU_ROOT/<book name> - cleaned.pdf`.

### Checkpoint gate (hard stop)

Do not continue to Phase B until the user provides and confirms the cleaned PDF path.

### Phase B - split cleaned, restore general templates, relink

1. Confirm cleaned PDF exists.
2. Derive per-file split boundaries in txt order from student folder files:
   - canonical `<name>.pdf` first;
   - fallback `_c_<name>.pdf` when plain file is absent.
3. Validate page totals:
   - `sum(part_counts) == cleaned_pdf_pages`; stop if mismatch.
4. Split cleaned PDF into unit files using normalized basenames.
5. Move split units into template book folder (`mv`, no overwrite).
6. Re-scan both folders with `PdfFileManager.scan_for_new_files`:
   - first `dry_run=True`, then `dry_run=False`;
   - roots limited to general and student book folders (not broad root scan).
7. Link each student completion main to matching general template main:
   - prefer `_c_<name>.pdf` pair on both sides;
   - call `link_to_template(..., inherit_metadata=True)`;
   - if already linked, skip unless user asks to relink.

## Verification checklist (required)

- Template unit mains are registered as templates (`is_template=true`) with no student id.
- Student unit mains are completions (`is_template=false`) with correct student id.
- Each student completion resolves to the expected template path via `get_template`.
- Raw/main parity looks correct for both sides (raw exists and metadata parity is preserved).
- Template book group membership contains exactly one main per expected unit (no duplicate units).

## Artifact cleanup (required)

After successful Phase B, move top-level artifacts to Trash if present:

- `DAYDREAMEDU_ROOT/<book name> - merged.pdf`
- `DAYDREAMEDU_ROOT/<book name> - cleaned.pdf`

## Rerun/failure handling

- Partial Phase A (some moved, some not): stop and reconcile disk + registry before retry.
- Page mismatch after cleaning: stop; do not guess split boundaries.
- Mixed books in one txt: split into separate runs.
- Existing destination files: stop unless user explicitly instructs replacement.

## Migration note

- This unified skill is now the single source of truth for this workflow.
