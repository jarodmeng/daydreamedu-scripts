---
name: reprocess-student-completion-from-general-part1
description: >-
  Moves mistaken general-scope `_raw_` book PDFs (actually a student's filled work)
  into that student's DaydreamEdu mirror folder, strips the `_raw_` basename prefix,
  removes their registry rows (main + raw), and writes `<book folder name> - merged.pdf`
  at the literal `DAYDREAMEDU_ROOT` for out-of-band cleaning. Use when the user provides
  a text file listing absolute paths to `_raw_*.pdf` files under a general-scope
  `…/<subject>/<grade>/Book/<book>/` tree, or asks to start the
  "student completion from general" reprocess workflow before merging/cleaning.
---

# Reprocess student completion from general (part 1 — before cleaning)

## When this skill applies

- The user supplies a **`.txt` file** (one absolute path per line, `#` comments allowed) listing PDFs that live under **general-scope** DaydreamEdu (`…/<subject>/<grade>/Book/<book>/…`) with **`_raw_` prefixes**, but those files are **actually a student's completions** (wrong scope).
- Goal of part 1: **on-disk relocation** into the student's tree, **registry cleanup**, and a **single merged PDF** at the **top level** of `DAYDREAMEDU_ROOT` for the user to clean in another app.

Part 2 (separate skill) handles split, move back to general, re-scan, template links, and verification.

## Required inputs (ask if missing)

1. **Path to the list file** — same format as bookmark exports: absolute paths, one per line.
2. **Student folder email segment** — the directory name under `<subject>/` that identifies the student (same string as that student’s row in **`students.email`** in the registry). **Do not invent this:** use only the value the user supplies for the run; do not embed real student emails in skills, logs, or commits.
3. **Confirmation on `_c_` mains** — `PdfFileManager.delete_file(main, keep_related=False)` **removes the registered `_c_` main from disk** when that path still exists. If the user wants to **keep** those `_c_` files, do **not** use `delete_file` on the mains; use a registry-only strategy (not covered by default `PdfFileManager` APIs) or clarify with the user.

## Prerequisites

- Read and follow **[`pdf-file-manager`](../pdf-file-manager/SKILL.md)** for registry work (`PdfFileManager`, not raw SQLite).
- Resolve **`DAYDREAMEDU_ROOT`** with **`resolve_daydreamedu_root()`** from [`ai_study_buddy/files/roots.py`](../../../ai_study_buddy/files/roots.py).

## Path layout rules

**General-scope source** (from list):

`DAYDREAMEDU_ROOT/<subject>/<grade>/<rest…>/<file>.pdf`  

where `<grade>` is `P3`–`P6`, `PSLE`, or `Archive` (no `@` in that segment).

**Student destination** (mirror structure, insert email after subject):

`DAYDREAMEDU_ROOT/<subject>/<student_email>/<grade>/<rest…>/<file_without_raw_prefix>.pdf`

- **`rest`** is everything after `<grade>/` in the relative path (typically `Book/<book name>/…`).
- Rename on move: if basename is `_raw_<name>.pdf`, destination basename is **`<name>.pdf`** (strip the literal `_raw_` prefix once).

If any listed path already contains a student email segment between subject and grade, **stop** and ask—the script assumes **general-scope** sources.

## Step-by-step

### 1) Validate the list

- Read the txt; skip empty lines and `#` comments.
- For each path: resolve with `Path(…).expanduser().resolve()`, assert `file.is_file()`, assert basename starts with **`_raw_`**, assert path is under `DAYDREAMEDU_ROOT`.
- Prefer **one book folder** per run (all files share the same `…/Book/<book name>/` parent). If paths span multiple books, stop and ask.

### 2) Move files on disk (`mv`)

- Workspace rule: use **`mv`** (shell), not copy+delete.
- For each source path, compute destination directory with **`mkdir -p`**, then **`mv source dest`**.
- If destination exists, **stop** without overwriting.

### 3) Registry — remove old general-scope rows

For each **original** (pre-move) raw path from the list:

1. `PdfFileManager().get_file_by_path(original_raw_path)`.
2. If **not** found, log and continue (path may never have been registered or was removed earlier).
3. If found and `file_type == 'raw'`, locate the linked **`main`** via **`get_related_files`** / `raw_source` (see [`pdf_file_manager.py`](../../../ai_study_buddy/pdf_file_manager/pdf_file_manager.py)).
4. If a linked **`main`** exists: **`delete_file(main_id, keep_related=False, notes=…)`** so the **main row and raw row** and **`raw_source` relations** are removed together.  
   - This attempts **`os.remove`** on registered paths; after **part 1** disk moves, old raw paths are usually absent on disk, so **`os.remove`** may only log a warning—expected.
5. Else (**raw** only, no linked **main**): **`delete_file(raw_id, keep_related=False, …)`** or stop and clarify with the user if orphan removal is unsafe.

### 4) Merge — output location and naming

- **Book name** = the parent directory of each listed file when that parent sits directly under **`Book/`** (i.e. the directory named `<book name>` in `…/Book/<book name>/<file>.pdf`). If paths do not follow `…/Book/<book name>/…`, **stop**—do not guess the book label.
- Write the merged PDF at the **literal top level** of DaydreamEdu:

  `DAYDREAMEDU_ROOT/<book name> - merged.pdf`

  (User convention from this workflow; do not place under `Book/` unless the user asks.)
- If that merged path **already exists**, **stop** unless the user explicitly authorises replacing it (then move the existing file to Trash first, still no `rm`).

### 5) Merge — page order

- Concatenate PDFs in **exactly the order of lines in the txt file**.
- After moves, source PDFs for merging are the **student-folder** paths (basename **without** `_raw_`).
- Use **`pypdf`** (`PdfWriter` / `PdfReader`) or another project-standard merge; verify total page count equals the sum of parts.

### 6) Handoff

- Tell the user part 1 is complete; they clean the merged file externally and produce:

  `DAYDREAMEDU_ROOT/<book name> - cleaned.pdf`

  at the **same top-level** convention unless they specify otherwise.
- Point them to **[`reprocess-student-completion-from-general-part2`](../reprocess-student-completion-from-general-part2/SKILL.md)** with the **same list txt** and the **cleaned file path**. Part 2 **always** moves top-level **`- merged.pdf`** / **`- cleaned.pdf`** under `DAYDREAMEDU_ROOT` to Trash when those paths exist (see part 2 step 7).

## Optional cleanup (only if asked)

- To remove merged/cleaned artifacts from `DAYDREAMEDU_ROOT`, **move to Trash** with `mv <file> ~/.Trash/` (project rule: no `rm` for user deletes).

## Risks and edge cases

- **Wrong student folder** if the email segment is mistyped—confirm it matches **`students.email`** before moving.
- **Partial runs** (some `mv` succeeded, registry half-cleared): there is no built-in resume protocol; inspect disk + registry and reconcile manually before retrying.
- **Non-`Book` layouts** (e.g. exercises not under `Book/<name>/`): this workflow assumes book-style paths; generalise only with explicit user mapping.

## Related

- Registry and scan behaviour: [`pdf-file-manager`](../pdf-file-manager/SKILL.md), [`SPEC.md`](../../../ai_study_buddy/pdf_file_manager/SPEC.md) (`compress_and_register`, `scan_for_new_files`).
- DaydreamEdu root: [`ARCHITECTURE.md`](../../../ai_study_buddy/pdf_file_manager/ARCHITECTURE.md#local-daydreamedu-root-not-in-git).
