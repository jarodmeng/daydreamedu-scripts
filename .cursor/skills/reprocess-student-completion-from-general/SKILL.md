---
name: reprocess-student-completion-from-general
description: >-
  Reprocesses mistaken template-branch book PDFs (`_c_` mains with linked
  `_raw_` files, or legacy `_raw_` entries) that are actually a student's
  completions. Phase A moves the existing registered rows to student
  scope while preserving raw/main relations, snapshots and removes template-only
  book ownership, and builds a merged raw PDF for external cleaning. Phase B
  splits the cleaned PDF back into general-scope template units, re-scans,
  restores book-answer mappings, links student completions to templates, and
  verifies registry integrity.
---

# Reprocess student completion from general (unified)

## When this skill applies

- User provides a txt list of template-branch book PDFs under a `.../Book/<book name>/` tree.
- List entries may be `_c_<name>.pdf` registered mains with sibling/linked `_raw_<name>.pdf`, or legacy `_raw_<name>.pdf` entries.
- Those files are actually student completions and must be re-scoped.
- User will clean writings externally on a single merged file between phases.

## Required inputs (ask if missing)

1. Path to txt list file (absolute paths, one per line, `#` comments allowed).
2. Target `student_id` (for example `winston`). Resolve the student with `PdfFileManager.get_student(student_id)` and use its `email` as the folder segment.
3. Confirmation that external cleaning will produce a cleaned merged PDF for Phase B.
4. For Phase B runs: cleaned PDF path plus the same txt list used in Phase A.

## Prerequisites

- Read and follow [`pdf-file-manager`](../pdf-file-manager/SKILL.md).
- Resolve DaydreamEdu root with `resolve_daydreamedu_root()` from [`ai_study_buddy/files/roots.py`](../../../ai_study_buddy/files/roots.py).
- Use `PdfFileManager` for registry lookups and mutations. Do not query or edit the registry SQLite database directly.
- For listed source rows, require registered raw/main rows and move them with `PdfFileManager.move_file(...)` so disk path, registry path, and path-derived scope fields stay aligned. Use shell `mv` only for generated split files, merged/cleaned artifacts, or other unregistered files.
- Move deletions to Trash (`mv <path> ~/.Trash/`), never `rm`.

## Path layout rules

- Source list paths must be template branch:
  - `DAYDREAMEDU_ROOT/template/<subject>/<grade>/Book/<book name>/<file>.pdf`
  - `<grade>` must be one of `P1`-`P6` or `PSLE`.
- Student destination mirror:
  - `DAYDREAMEDU_ROOT/completion/<subject>/<student_email>/<grade>/Book/<book name>/<same basename>.pdf`
- Preserve technical prefixes on moved student files:
  - `_c_<name>.pdf` remains `_c_<name>.pdf`.
  - `_raw_<name>.pdf` remains `_raw_<name>.pdf`.
- Canonical unit key:
  - Use `normalize_pdf_display_name(...)` from `pdf_file_manager.py` for matching rows across listed files, moved completions, regenerated templates, and saved mappings.
- Phase A merge source:
  - If the list row is `_c_<name>.pdf`, merge the sibling linked `_raw_<name>.pdf`, not the `_c_` file.
  - If the list row is `_raw_<name>.pdf`, merge that raw file and resolve its linked or sibling main.

If any input path already includes a student-email segment between subject and grade, stop and ask.

## Fail-fast validation (before any mutation)

1. Parse txt entries in order, skipping blank/comment lines.
2. Validate each path:
   - exists as a file;
   - lives under DaydreamEdu root;
   - basename starts with `_c_` or `_raw_`;
   - fits expected general-scope book layout.
3. Ensure all entries belong to exactly one book folder (`.../Book/<book name>/`).
4. Resolve the target student:
   - `get_student(student_id)` must exist;
   - `student.email` must be non-empty;
   - destination folder must use `student.email`, not the bare `student_id`.
5. For every row, resolve the registry identity and raw/main pair:
   - `_c_` row: must be registered as `file_type='main'`; `get_related_files(main.id)` may return both `raw_source` and `main_version` rows for the same raw, so dedupe by related file id and require exactly one unique `file_type='raw'` counterpart; the raw path must be the expected sibling `_raw_<name>.pdf` unless the user explicitly approves a non-sibling relation.
   - `_raw_` row: must be registered as `file_type='raw'`; dedupe `get_related_files(raw.id)` by related file id and require exactly one unique `file_type='main'` counterpart; prefer a sibling `_c_<name>.pdf` main when present.
   - Main and raw rows must share invariant metadata (`doc_type='book'`, subject, grade, unit, template flag) before mutation; repair drift first if needed.
6. Ensure each canonical unit key appears once only.
7. Pre-check destination collisions for both planned student-scope paths:
   - main destination path;
   - raw destination path.
   Check both on disk and in `PdfFileManager.get_file_by_path(...)`.
8. Snapshot current template-only ownership before moves:
   - raw/main relation ids and old paths;
   - book group membership for each main;
   - `get_book_answer_mapping(main.id)` payload, if present, including answer file id/path, page range, split-page flags, source, and notes;
   - existing template/completion links: `get_template(main.id)` and `get_completions(main.id)`.
9. Existing template/completion links require explicit handling:
   - if listed mains already have `get_template(main.id)`, stop unless the user explicitly wants to relink;
   - if listed mains have `get_completions(main.id)`, stop unless the workflow also migrates those dependent completion links to the regenerated templates.
10. Derive `<book name>` and verify merged/cleaned top-level artifact paths are not conflicting unless user approves replacement.
11. Derive a durable Phase A snapshot path and verify it does not already exist unless the user approves replacement:
   - default: `DAYDREAMEDU_ROOT/<book name> - reprocess-snapshot.json`.

## Workflow

### Phase A - relocate, detach template ownership, merge (mandatory)

1. Resolve the row model in txt order:
   - `unit_key` from `normalize_pdf_display_name(...)`;
   - source main row and source raw row;
   - main destination and raw destination under the student mirror;
   - raw merge source for Phase A.
2. Snapshot book-answer mappings and link state before any move:
   - Persist a local JSON artifact keyed by `unit_key`; do not rely on in-memory state because Phase A stops for external cleanup.
   - Default snapshot path: `DAYDREAMEDU_ROOT/<book name> - reprocess-snapshot.json`.
   - Include old main id, old raw id, old paths, destination paths, page counts, saved mapping payload, group ids, and any template/completion relation ids.
   - Do not proceed if the snapshot count differs from the txt entry count.
3. Move both registered rows into the student mirror:
   - Call `PdfFileManager.move_file(main_id, student_book_dir)`.
   - Call `PdfFileManager.move_file(raw_id, student_book_dir)`.
   - Preserve basenames and technical prefixes.
   - After moving both rows, the raw/main relation should still point between the same two ids; this is the desired behavior because file relations are id-based.
4. Reclassify the moved pair as a student completion:
   - `move_file(...)` reapplies path-derived scope fields; verify the main and raw now have `student_id=<target student_id>` and `is_template=false`.
   - If `student_id` did not infer from the student email segment, stop and repair via `update_metadata(..., student_id=<target student_id>, is_template=False)` on the main so parity sync updates the raw.
5. Detach template-only ownership from the moved main ids:
   - remove moved mains from any `group_type='book'` membership using `remove_from_file_group`;
   - delete saved `book_answer_mapping` rows for moved main ids after the payload is safely snapshotted;
   - do not delete the moved main/raw rows.
6. Build merged PDF from the moved raw files in original txt order:
   - output path: `DAYDREAMEDU_ROOT/<book name> - merged.pdf`.
   - verify merged page total equals sum of source pages.
7. Stop at checkpoint and hand off:
   - user cleans merged PDF externally;
   - expected cleaned output default:
     - `DAYDREAMEDU_ROOT/<book name> - cleaned.pdf`.

### Checkpoint gate (hard stop)

Do not continue to Phase B until the user provides and confirms the cleaned PDF path.

### Phase B - split cleaned, restore general templates, relink

1. Confirm cleaned PDF exists.
2. Load or reconstruct the Phase A snapshot for the same txt list:
   - order and `unit_key` values must match exactly;
   - moved main and raw destination paths must still resolve in the registry;
   - saved mapping payloads must be present for every unit that had a mapping before Phase A.
3. Derive per-file split boundaries in txt order from moved student completion mains:
   - prefer `_c_<name>.pdf`;
   - fallback plain `<name>.pdf` only when no `_c_` main exists;
   - never use `_raw_` for boundaries unless there is no registered main and the user approves repair.
4. Validate page totals:
   - `sum(part_counts) == cleaned_pdf_pages`; stop if mismatch.
5. Split cleaned PDF into unit files using canonical template basenames:
   - Prefer plain `<name>.pdf` split outputs, then let `scan_for_new_files` compress/register them if needed.
   - If writing `_c_<name>.pdf` directly, ensure no `_raw_` template source will be expected from compression.
6. Move split units into the original template book folder (`mv`, no overwrite).
7. Re-scan both folders with `PdfFileManager.scan_for_new_files`:
   - first `dry_run=True`, then `dry_run=False`;
   - roots limited to general and student book folders (not broad root scan).
8. Resolve each regenerated template main:
   - match by `unit_key` within the template book folder;
   - prefer `_c_<name>.pdf`, then plain `<name>.pdf`;
   - there must be exactly one template main per expected unit key.
9. Restore template book group membership:
   - call `ensure_book_group_from_path(template_book_dir)`;
   - verify group members are general-scope template mains only;
   - student moved mains must not be group members.
10. Restore saved book-answer mappings onto regenerated template mains:
   - for each saved mapping, call `set_book_answer_mapping(new_template_main_id, saved_answer_file_id, saved_answer_page_start, saved_answer_page_end, starts_mid_page=saved_starts_mid_page, ends_mid_page=saved_ends_mid_page, source=saved_source, notes=saved_notes)`;
   - answer files should remain registered template book mains; stop if any saved answer file id no longer resolves.
11. Link each moved student completion main to matching regenerated template main:
   - prefer `_c_<name>.pdf` pair on both sides;
   - call `link_to_template(..., inherit_metadata=True)`;
   - if already linked, skip unless user asks to relink.

## Detailed validation plan (required)

Run validation at four checkpoints. Do not continue past a failed checkpoint unless the user explicitly approves a repair plan.

### Validation A - preflight before Phase A

- Txt parsing:
  - non-comment entry count is non-zero;
  - every entry is a direct PDF under one `DAYDREAMEDU_ROOT/template/<subject>/<grade>/Book/<book name>/` folder;
  - all entries have unique canonical unit keys.
- Student resolution:
  - target `student_id` exists;
  - target student has an email;
  - planned destination path is `DAYDREAMEDU_ROOT/completion/<subject>/<student.email>/<grade>/Book/<book name>/...`.
- Registry exact-path checks:
  - every listed path resolves with `get_file_by_path`;
  - each unit has exactly one main and exactly one unique raw counterpart after deduping `get_related_files(...)` by related file id;
  - counterpart relation is visible through `get_related_files` from both sides (`raw_source` and `main_version` rows may both be present);
  - no destination main/raw path exists on disk or in the registry.
- Ownership snapshot:
  - book group memberships, book-answer mappings, and template/completion relations are captured for each main;
  - saved mapping count equals the number of pre-existing mappings;
  - existing `get_completions(main.id)` is empty, or the workflow has an explicit dependent-link migration plan.
- Merge-source check:
  - every Phase A merge source is a raw PDF;
  - page count sum is recorded before merging.
- Snapshot artifact:
  - planned snapshot JSON path is known;
  - existing snapshot path is absent unless replacement was explicitly approved.

### Validation B - after Phase A moves and before external cleanup

- Disk and registry path reconciliation:
  - old template main/raw paths no longer exist and no longer resolve via `get_file_by_path`;
  - new student main/raw paths exist and resolve via `get_file_by_path`;
  - moved rows keep the same ids captured in the snapshot.
- Raw/main parity:
  - moved main has `file_type='main'`, `has_raw=true`, `student_id=<target student_id>`, `is_template=false`;
  - moved raw has `file_type='raw'`, `student_id=<target student_id>`, `is_template=false`;
  - `get_related_files(main.id)` returns the moved raw, and `get_related_files(raw.id)` returns the moved main.
- Template ownership detached:
  - moved mains are not members of any `group_type='book'`;
  - moved main ids have no `book_answer_mapping`;
  - saved mapping payloads still exist in the Phase A snapshot.
- Merge artifact:
  - merged PDF exists;
  - merged page count equals the recorded raw page-count sum.
- Snapshot artifact:
  - snapshot JSON exists on disk;
  - snapshot JSON can be parsed and has one row per txt entry in the same order.

### Validation C - before Phase B linking

- Cleaned PDF:
  - cleaned PDF exists;
  - cleaned page count equals `sum(student_main_page_counts)` from moved completion mains.
- Split outputs:
  - each split segment is routed to the original template book folder;
  - no split output overwrites an existing template file unless the user explicitly approved replacement.
- Post-scan registry:
  - each regenerated template unit resolves as exactly one main file under the template folder;
  - each template main has `doc_type='book'`, expected subject, expected grade metadata, `is_template=true`, and `student_id is None`;
  - student moved mains still resolve under the completion folder and remain `is_template=false`.

### Validation D - final integrity after Phase B

- Template/completion links:
  - every moved student completion main has `get_template(main.id)` equal to the matching regenerated template main;
  - every regenerated template main has the moved completion in `get_completions(template.id)`;
  - no moved completion points to an old/deleted template id.
- Raw/main parity:
  - moved student raw/main pairs remain linked and metadata-aligned;
  - regenerated template mains either have correct raw/main pairs from scan/compression or intentionally have `has_raw=false` if compression was skipped.
- Book group:
  - `ensure_book_group_from_path(template_book_dir)` returns the canonical book group;
  - group members include regenerated template mains for expected unit keys;
  - group members do not include student-scope completion mains.
- Book-answer mappings:
  - every saved mapping is restored on the regenerated template main for the same unit key;
  - restored mappings point to registered answer mains;
  - page ranges, mid-page flags, source, and notes match the saved payload.
- Full hygiene:
  - run `python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity`;
  - investigate any new failures before cleanup.

## Verification checklist (summary)

- Template unit mains are registered as templates (`is_template=true`) with no student id.
- Student unit mains are completions (`is_template=false`) with correct student id.
- Each student completion resolves to the expected template path via `get_template`.
- Raw/main parity looks correct for both sides (raw exists and metadata parity is preserved).
- Template book group membership contains exactly one main per expected unit (no duplicate units).
- Saved book-answer mappings are restored to regenerated template unit ids.
- Moved student mains have no template book group membership and no unit answer mapping.

## Artifact cleanup (required)

After successful Phase B, move top-level artifacts to Trash if present:

- `DAYDREAMEDU_ROOT/<book name> - merged.pdf`
- `DAYDREAMEDU_ROOT/<book name> - cleaned.pdf`
- `DAYDREAMEDU_ROOT/<book name> - reprocess-snapshot.json`

## Rerun/failure handling

- Partial Phase A (some moved, some not): stop and reconcile disk + registry before retry.
- Page mismatch after cleaning: stop; do not guess split boundaries.
- Mixed books in one txt: split into separate runs.
- Existing destination files: stop unless user explicitly instructs replacement.
- Existing dependent completions from the listed template mains: stop unless the user approves migrating those completion links to regenerated template mains.
- Lost Phase A snapshot: reconstruct from operation log and current registry where possible; if mapping payloads cannot be reconstructed confidently, stop.

## Migration note

- This unified skill is now the single source of truth for this workflow.
