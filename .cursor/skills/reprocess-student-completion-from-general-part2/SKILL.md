---
name: reprocess-student-completion-from-general-part2
description: >-
  After external cleaning of a merged book PDF, splits the cleaned file back into
  unit PDFs (names from the original list without `_raw_`), moves them into the
  general-scope book folder, re-scans general + student book folders with
  pdf_file_manager, links each student `_c_` main to its general template main,
  verifies metadata and general book `file_groups` membership (no duplicate units),
  then removes top-level `DAYDREAMEDU_ROOT` merged/cleaned artifacts to Trash.
  Use when the user supplies the cleaned PDF path plus the same txt file used in
  part 1 listing the original general-scope `_raw_` paths.
---

# Reprocess student completion from general (part 2 — after cleaning)

> Preferred workflow: use the unified skill [`reprocess-student-completion-from-general`](../reprocess-student-completion-from-general/SKILL.md). Keep this part-2 skill for backward compatibility and narrow/legacy runs.

## When this skill applies

- **Part 1** is already done: mistaken `_raw_` files were moved into the student's DaydreamEdu tree (basename **without** `_raw_`), registry rows for the old general paths were cleared (**including** general-scope **`group_type='book'`** membership and any **`book_answer_mappings`** for those unit mains—see part 1 step 3), and a **merged** PDF was produced for cleaning.
- The user supplies:
  1. **Path to the cleaned PDF** (typically `DAYDREAMEDU_ROOT/<book name> - cleaned.pdf` at the **literal top level** of DaydreamEdu—confirm if different).
  2. **The same `.txt` list** used in part 1 (absolute paths to the **original** general-scope `_raw_` files, in the desired **split/merge order**).

## Required inputs (ask if missing)

1. **Cleaned PDF path** — must exist on disk.
2. **Original list txt** — same line order as part 1; paths may be stale (files moved) but must still encode **subject / grade / book / original basenames**.

## Prerequisites

- Read **[`pdf-file-manager`](../pdf-file-manager/SKILL.md)**.
- **`resolve_daydreamedu_root()`** from [`ai_study_buddy/files/roots.py`](../../../ai_study_buddy/files/roots.py).
- **Student book directory** — prefer the user to confirm **`DAYDREAMEDU_ROOT/<subject>/<student_email>/<grade>/Book/<book name>/`** (same **`<student_email>`** as part 1). If the list txt is intact, derive **`student_email`** by scanning the resolved first path’s segments for a folder name equal to a known **`students.email`** row, or by asking the user—**do not guess** a mailbox string.
- Paths must be under the **DaydreamEdu** tree used for templates (not a **`GoodNotes/`** root), or **`compress_and_register`** / scan semantics differ (`preserve_input`).

## Derive paths from the list

From the **first** non-empty path in the txt:

1. Resolve against `DAYDREAMEDU_ROOT` → relative path parts: `<subject>/<grade>/Book/<book name>/file.pdf`.
2. **General book directory** = `DAYDREAMEDU_ROOT/<subject>/<grade>/Book/<book name>/`.
3. **Student book directory** = `DAYDREAMEDU_ROOT/<subject>/<student_email>/<grade>/Book/<book name>/`.

For **each** line, destination basename after cleaning = original basename with **`_raw_` stripped once** (e.g. `_raw_Foo.pdf` → `Foo.pdf`). That basename is used for both the **split output** name and the **general-scope** file after the move.

## Step-by-step

### 1) Page boundaries — use student-folder copies

- For each line in txt order, map to the file under the **student book directory** with the **stripped basename** (these are the moved originals; page counts must match the cleaned merge **unless** the user changed page counts while cleaning—if totals differ, **stop** and reconcile with the user).
- **Before counting:** assert **every** `student_book_dir / <stripped_basename>` exists and is a file; if any is missing, **stop** (wrong email folder, wrong book, or part 1 incomplete).
- Compute `counts[]` with **`pypdf.PdfReader`** (`len(pages)` per file).
- Assert **`sum(counts) == len(PdfReader(cleaned).pages)`** before splitting.

### 2) Split the cleaned PDF

- Write **N** parts (one per list line, in list order) temporarily to **`DAYDREAMEDU_ROOT`** with the **stripped basenames** (no `_raw_` yet—`compress_and_register` in scan will recreate `_raw_` + `_c_`).
- **Collision check:** for each output basename, assert **`not (DAYDREAMEDU_ROOT / basename).exists()`** before writing—unrelated PDFs sitting at the DaydreamEdu root with the same name would otherwise be overwritten or cause a hard failure. If a collision exists, stop or use a disposable subfolder under root (e.g. move outputs there, then `mv` into general) after clearing it.

### 3) Move splits into general-scope book folder

- Use **`mv`** per file from `DAYDREAMEDU_ROOT/<basename>` → **general book directory** (workspace move rule).

### 4) Re-scan both book folders

```text
PdfFileManager().scan_for_new_files(roots=[general_book_dir, student_book_dir], dry_run=True)
PdfFileManager().scan_for_new_files(roots=[general_book_dir, student_book_dir], dry_run=False)
```

- **Do not** scan all of `DAYDREAMEDU_ROOT` while merged/cleaned PDFs still sit there—restrict `roots` to the two **book** directories only (artifact removal happens in step 7).
- **Scope:** each root’s **direct** **`*.pdf`** children are considered (see [`SPEC.md`](../../../ai_study_buddy/pdf_file_manager/SPEC.md) — no recursion). Any other unregistered PDF in those folders is processed too; warn the user if that is unexpected.

### 5) Template links (DaydreamEdu student → DaydreamEdu general)

- `scan_for_new_files` does **not** auto-link student **`_c_`** mains to general template **`_c_`** mains.
- For each list row, pair **`_c_`** files whose **full basename is identical** between **student** and **general** book directories (same `_c_<stem>.pdf`); do not pair on a partial substring match.
- Call **`link_to_template(completed_id=<student_main_id>, template_id=<general_main_id>, inherit_metadata=True)`**  
  (see [`pdf_file_manager.py`](../../../ai_study_buddy/pdf_file_manager/pdf_file_manager.py) — template must have **`is_template=True`**, completed must have **`is_template=False`**).
- **Idempotency:** if **`link_to_template`** raises because a completion is **already linked**, either **`unlink_template`** first with user consent or **skip** that pair and record it—do not assume a clean slate on re-runs.

### 6) Verification

**General-scope (templates)** — for each restored unit:

- Raw + main: **`is_template=True`**, **`student_id`** null (unless overridden).
- **`metadata.unit`** sensible for book inference.
- **`get_file_group_membership(main_id)`** includes a **`group_type='book'`** group labelled with the book name.

**General book group — no duplicate units**

- Resolve the same general book group as part 1: **`list_file_groups(group_type='book')`** where **`label`** equals **`<book name>`** from the list (one match expected).
- After scan, **`get_file_group(group_id).members`** should contain **exactly one `main`** per list line (same **N** as the txt), each path under **`general_book_dir`**. If the member count is **> N** or any basename appears twice, part 1 registry/group cleanup was incomplete or an extra PDF sits in the general folder—**stop** and reconcile before relying on links or mappings.

**`book_answer_mappings` (optional follow-up)**

- Part 1 **`delete_book_answer_mapping`** removed per-unit answer coverage for those mains. New mains get **new** `pdf_files` ids after re-scan, so **old mapping rows cannot “come back”** automatically.
- If this book relied on registry answer mappings, re-apply them with the usual tools (e.g. **`import_book_answer_mappings_from_json`** / **`set_book_answer_mapping`** per **[`pdf-file-manager`](../pdf-file-manager/SKILL.md)** and **`SPEC.md`**) using the **new** unit file ids or paths—outside the default part 2 loop unless the user asks.

**Student folder** — for each unit:

- Raw + main: **`is_template=False`**, **`student_id`** set to the registry’s short id for that student (non-null).
- **`metadata.unit`** matches the general template.
- **`get_template(student_main_id)`** resolves to the **general** `_c_` main path.

**Book groups and raws:** `file_group` membership is attached to **`main`** rows for books; **raw** rows may show **no** group—expected per current book-group rules; do not treat as failure if unit/template/student flags are otherwise correct.

### 7) Artifact cleanup (required)

- **Always** finish the run by removing top-level workflow PDFs from `DAYDREAMEDU_ROOT` so they are not left cluttering the tree or picked up by a broad scan later.
- For **`<book name>`** derived from the list (same as part 1), if either file exists, move it to Trash with **`mv`** (project rule: no `rm`):
  - `DAYDREAMEDU_ROOT/<book name> - merged.pdf`
  - `DAYDREAMEDU_ROOT/<book name> - cleaned.pdf`
- If the user supplied the cleaned file at a **different** path, still remove the top-level **`- cleaned.pdf`** when present; only move paths that **`Path.is_file()`** confirms exist.

## Failure modes

- **Book group has duplicate or extra mains** after step 4 → see step 6 “no duplicate units”; fix registry + folder contents before proceeding.
- **Page total mismatch** after cleaning → user may have added/removed pages; do not guess split boundaries.
- **Multiple books in one txt** → unsupported without splitting the workflow per book.
- **Destination PDF already exists** in general folder → stop; user must resolve collisions.
- **Stale or edited list txt** (first line no longer parses to the right `<subject>/<grade>/Book/<book name>`) → wrong general/student dirs; validate derived paths against disk before splitting.
- **List paths need not exist on disk** in part 2 (part 1 already moved them); the txt is still required for **order**, **basenames**, and **directory layout** inference.

## Related

- Part 1: **[`reprocess-student-completion-from-general-part1`](../reprocess-student-completion-from-general-part1/SKILL.md)**
- **[`pdf-file-manager`](../pdf-file-manager/SKILL.md)**
