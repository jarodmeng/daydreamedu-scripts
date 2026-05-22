# Completion files registry audit (research note)

**Date:** 2026-04-19  
**Last tally refresh:** **2026-04-22**. Current snapshot: **140** JSON files on disk under `marking_results/**` and **139** completions with **`has_marking`** in the audit set (see **§ Tallies**). Rules include **GoodNotes Science Revision Guide** book-folder exclusions (rule **7**). The audit population is **213** completions (excluding `(reviewed)` and excluded revision-guide paths).
**Scope:** Count and classify **student completion** PDFs using the local `pdf_file_manager` registry (`PdfFileManager`, default `ai_study_buddy/db/pdf_registry.db`), plus on-disk **marking** artifacts under `ai_study_buddy/context/`.

This note records definitions, tallies, registry corrections (metadata and template links), follow-up flags (`has_marking`, `has_template`), and **completion file categories** (see below). It is not a product spec; reproduce numbers with the same code paths and roots on disk.

---

## What counts as a “completion file” (this audit)

All of the following must hold:

1. **Location:** Resolved path is under **`DAYDREAMEDU_ROOT`** or **`GOODNOTES_ROOT`** (`resolve_daydreamedu_root()` / `resolve_goodnotes_root()` in `ai_study_buddy/files/roots.py`).
2. **Student scope:** `PdfFileManager._path_has_student_mirror_layout(path)` is true (email segment immediately followed by `P1`–`P6` or `PSLE`).
3. **Leaf folder:** The PDF’s **parent directory** contains at least one `*.pdf` directly, and passes the **leaf exclusions** for that root (same idea as the Cursor leaf-registry reports):
   - **DaydreamEdu:** `.cursor/commands/daydreamedu-leaf-registry-report.md` — exclude the root leaf `.` only when the sync root qualifies as a leaf (direct PDFs under `DAYDREAMEDU_ROOT`).
  - **GoodNotes:** `.cursor/commands/goodnotes-leaf-registry-report.md` — exclude any path under a `Not completed` segment (case-insensitive); exclude any path under a segment matching regex `^x[A-Z].*$` (lowercase `x`, second character uppercase); and exclude the root leaf `.` when applicable.
4. **Exam or Book:** Path segments include **`Exam`** (classified as exam *tree* for this note) or **`Book`** (book *tree*). If both appear, **Exam** wins (rare).
5. **Registry row shape:** `file_type != 'raw'` (skip `_raw_` archives) and **`is_template == False`** (student-side mains, not blank templates).
6. **Exclude “(reviewed)” second-order completions:** See the section below. For this audit, exclude any file whose **basename** matches `(reviewed)` (case-insensitive), e.g. `… (reviewed).pdf`.
7. **Exclude GoodNotes *Science Revision Guide* book trees (no gradable questions):** If the resolved path is under **`GOODNOTES_ROOT`** and any path segment equals a configured book-folder name, drop the row from the audit population. Canonical folder names live in `GOODNOTES_SCIENCE_REVISION_GUIDE_BOOK_FOLDERS_EXCLUDED` and `is_goodnotes_science_revision_guide_book_excluded()` in `ai_study_buddy/marking/core/completion_registry_audit.py` (currently **Science Revision Guide Primary 4** and **Science PSLE Revision Guide** — exact segment match).

With these rules, the tally is **213** registered files (after the correction below, the `(reviewed)` exclusion, and rule **7**).

The broader definition without rule **6** (still applying rule **7**) matched **221** files (see **§ “(reviewed)” second-order completions**).

---

## “(reviewed)” second-order completions (open question — revisit)

Some GoodNotes PDFs are named with a **`(reviewed)`** suffix (e.g. `_c_… (reviewed).pdf`). They appear to be a **second pass** after work already captured elsewhere: in the registry they often have a **`template_for` / `completed_from` link** to a **DaydreamEdu** PDF in the parallel student folder (same subject / grade / unit naming **without** `(reviewed)`). The DaydreamEdu side is still **student-scoped** (`is_template=False` on both sides in observed rows), not a general-scope blank template.

**Policy is unset:** we have not decided whether these should be first-class completions, duplicates for audit/marking, or a separate workflow state.

**For this audit:** those rows are **excluded** so numbers reflect “primary” completion files only. **8** registry rows matched the `(reviewed)` basename pattern at the time of the note (all under **GoodNotes**; **6** in `P6/Exam`, **2** in `PSLE/Book/English Practice 1000`). Revisit this section when naming, linking, and marking rules for reviewed copies are defined.

---

## Registry correction (2026-04-19)

Two rows under Winston’s student tree had **`is_template=True`** despite living under `…/winston.…/PSLE/Book/English Practice 1000/` — inconsistent with path inference (student mirror ⇒ completion ⇒ `is_template=False`).

Files:

- `_c_EPO_Grammar_Cloze_01.pdf`
- `_c_EPO_Grammar_Cloze_02.pdf`

**Fix:** `PdfFileManager.update_metadata(<file_id>, is_template=False)` for both. Before the fix, strict tallies excluding `is_template=True` under-counted by **2** (240 vs 242 **before** the `(reviewed)` exclusion).

---

## GoodNotes: `scan_for_new_files()` and template links (historical + v0.3.20)

**Learning (2026-04-19):** `PdfFileManager.scan_for_new_files()` registers (and may compress) PDFs under the given scan roots and, for book trees, calls `ensure_book_group_from_path` — but it **never** called `link_goodnotes_template_for_file()` or `link_goodnotes_templates_for_root()`. So a GoodNotes main could sit in the registry with **no** `template_for` / `completed_from` row even when the mirrored **`_c_…` file already exists and is registered** under `DAYDREAMEDU_ROOT`. **Update (pdf_file_manager v0.3.20):** scan now auto-links by default (`auto_link_goodnotes=True`); see `ScanResult.template_link`. A separate root-level linker pass is only needed for already-registered files or when auto-link is disabled.

**Evidence — eight files in the audit set (not one):** Among **234** completions (with `(reviewed)` excluded, and **before** rule **7** excluded Science Revision Guide book trees), **eight** GoodNotes mains had **`get_template()` = `None`** while **`resolve_goodnotes_template_path()`** pointed at an existing, registered DaydreamEdu template. For **all eight**, `operation_log` showed **`register`** and **`update_metadata`** only; the **seven book** paths also had **`group_add` / `group_remove`** from book-group sync — and **none** had **`link_template`**. Subjects/paths: one Emma **P4/Exam** science WA PDF; three Winston **PSLE/Book** Power Pack Math; three Emma **PSLE/Book** Science PSLE Revision Guide; one Abigail **P1/Book** Visible Thinking. Same root cause as a single-file example: scan/book workflow ran; the **post-scan GoodNotes linker never did**. (Three of those eight were under **Science PSLE Revision Guide**; they no longer appear in the **213**-row audit population.)

**Registry fix (2026-04-19):** Ran `link_goodnotes_template_for_file(<path>, auto_fix_template=True, inherit_metadata=True)` for each of the eight. All returned `linked=True` (mirrored templates already had `is_template=True`; no auto-fix needed).

**Implication:** Missing general-scope template links on GoodNotes completions were often an **omitted post-scan step**, not a failed resolution (pre-v0.3.20). **Since v0.3.20**, default scan auto-links new mains; review `ScanResult.template_link` and use `link_goodnotes_templates_for_root` or per-file linking only for backfill, `auto_link_goodnotes=False`, or unresolved stems (see `.cursor/skills/scan-goodnotes-folder/SKILL.md`).

---

## Flags on each completion

| Flag | Meaning |
|------|--------|
| **`has_marking`** | At least one JSON under `ai_study_buddy/context/marking_results/**` matches the completion using the same rules as `find_marking_artifacts_for_attempt()` in `ai_study_buddy/marking/core/artifact_lookup.py`: match `context.attempt_file_id` to the completion’s registry id, or (when id is absent) match resolved `context.attempt_file_path` to the completion path (including `<student_email>` substitution from the student record). |
| **`has_template`** | `PdfFileManager.get_template(completion_id)` returns a template whose path is **general-scope**: `not _path_has_student_mirror_layout(template_path)` — i.e. the linked template is **not** under the student-email mirror layout. |

**Marking artifact schema / workflow context:** see [`../L4_MARKING_RESULT_ARTIFACT.md`](../L4_MARKING_RESULT_ARTIFACT.md).

---

## Tallies (**213** completions — `(reviewed)` excluded, Science Revision Guide GoodNotes book trees excluded)

Counts below reflect the registry **after** the **2026-04-19** GoodNotes template-link fix for the eight files in **§ GoodNotes: `scan_for_new_files()`…** (so GoodNotes rows with no general-scope template link are **DaydreamEdu-only** gaps, not those eight), and use the **2026-04-22** audit population (rule **7** drops **5** GoodNotes book completions under the two revision-guide folder names).

**`has_marking` depends on disk:** the tally refresh walks marking-result JSON under `marking_results/**` and matches them to completions via `artifact_lookup` rules (see **§ Flags**). At the latest **2026-04-22** rerun there are **140** JSON files on disk and **139** audit completions with **`has_marking`** (counts can differ slightly when JSON exists that does not match any audit completion).

### By root and Exam vs Book

| Root | Exam | Book |
|------|-----:|-----:|
| DaydreamEdu | 71 | 34 |
| GoodNotes | 18 | 90 |

### By `(root, exam\|book, has_marking, has_template)`

| Root | Type | has_marking | has_template | Count |
|------|------|-------------|--------------|------:|
| daydreamedu | book | yes | yes | 34 |
| daydreamedu | exam | no | no | 58 |
| daydreamedu | exam | no | yes | 3 |
| daydreamedu | exam | yes | yes | 10 |
| goodnotes | book | no | no | 4 |
| goodnotes | book | no | yes | 9 |
| goodnotes | book | yes | yes | 77 |
| goodnotes | exam | yes | yes | 18 |

**Totals for flags (same 213 files):**

- **`has_marking`:** 139  
- **`has_template` (general-scope link):** 151  

At the time of the audit, all **213** completions had a non-null `student_id`, so path-based marking JSON resolution behaved consistently.

*(Excluding the 8 `(reviewed)` files from the completion definition does not affect these flag totals, which apply only to the **213** audit rows.)*

---

## Completion file categories

Cross-cutting labels for subsets of the **213** audit completions (same inclusion rules as **§ What counts as a “completion file”**). Categories can overlap; this section only lists ones we have named so far.

### Student exam scans without empty templates

**Meaning:** Student-scoped exam completions under **`DAYDREAMEDU_ROOT`** (path includes an **`Exam`** segment) that have **no** `template_for` / `completed_from` link in the registry — i.e. **`PdfFileManager.get_template(completion_id)` returns `None`**. There is no associated **general-scope** blank (empty) paper on file in the `pdf_file_manager` sense for that row, because nothing was ever linked.

**Count:** **58** files at the latest tally refresh. They are **exactly** the **`daydreamedu` + `exam` + `has_marking=no` + `has_template=no`** bucket in the tally table above.

**Typical story:** School-returned or scanned papers registered as `_c_…` mains under the student mirror without a follow-up **`link_to_template`** to the matching general-scope `…/P<n>/Exam/_c_…` template (or the template was never registered). Distinct from **GoodNotes** gaps where the mirror path is resolved by `resolve_goodnotes_template_path()` but the linker was not run — that set was addressed in **§ GoodNotes: `scan_for_new_files()`…**.

### Completion files with templates but no markings

**Meaning:** Completion rows in this audit set where **`has_template`** is true (linked to a **general-scope** template) and **`has_marking`** is false (no matching marking JSON yet), regardless of root or whether the path sits in `Exam` or `Book`.

**Count:** **12** files at the latest **2026-04-22** refresh (`3 + 9` across the root/type breakdown below). GoodNotes *Science Revision Guide* unit PDFs are **out of scope** for this tally (rule **7**); they are not listed here.

| Root | Type | Count (`has_template=yes`, `has_marking=no`) |
|------|------|------:|
| daydreamedu | exam | 3 |
| goodnotes | book | 9 |

Compared with earlier refreshes, counts shrank after marking runs under `context/marking_results/**` and after revision-guide paths were removed from the audit population.

**Current operational interpretation by subgroup (user-confirmed):**

1. `daydreamedu/exam` files are **school exam scans that have been cleaned**, but **learning reports are not created yet**.
2. `goodnotes/book` + `winston/english` (PSLE situational writing) are **practices that require special marking**.
3. `goodnotes/book` + `winston/math` (and similar) outside the revision-guide exclusion are **partial completions** when they appear in this queue.

**Current 12 files (basenames only), grouped by `root` / `student` / `subject` / `grade` / `type`:**

#### `daydreamedu` / `winston` / `math` / `P5` / `exam`

- `_c_EoY (Paper 1).p5.math.045.pdf`
- `_c_EoY (Paper 2).p5.math.046.pdf`
- `_c_Mathematics Practice Paper Set 1 (Paper 1).p5.math.022.pdf`

#### `goodnotes` / `winston` / `math` / `P5` / `book`

- `c_Conquer Exam Standard Mathematics Problem Sums with Terry Chew Primary 5 - 03 Lesson 2 Whole Numbers - Remainder.pdf`
- `c_Conquer Exam Standard Mathematics Problem Sums with Terry Chew Primary 5 - 33 Lesson 17 Area and Perimeter (1).pdf`
- `c_Conquer Exam Standard Mathematics Problem Sums with Terry Chew Primary 5 - 37 Lesson 19 Angles (1).pdf`
- `c_Conquer Exam Standard Mathematics Problem Sums with Terry Chew Primary 5 - 41 Lesson 21 Percentage Discount - Tax.pdf`
- `c_Conquer Exam Standard Mathematics Problem Sums with Terry Chew Primary 5 - 45 Lesson 23 Volume (1).pdf`
- `c_Conquer Exam Standard Mathematics Problem Sums with Terry Chew Primary 5 - 47 Lesson 24 Volume (2).pdf`

#### `goodnotes` / `winston` / `english` / `PSLE` / `book`

- `c_PP English Situational Writing Practice 1.pdf`
- `c_PP English Situational Writing Practice 2.pdf`

#### `goodnotes` / `winston` / `math` / `PSLE` / `book`

- `c_PP Math PSLE Part B P1 to P5 Commonly Tested MCQs - Geometry.pdf`

---

## Implementation notes

- Use **`PdfFileManager`** only for registry reads/updates; do not query SQLite ad hoc for normal workflows (see `.cursor/skills/pdf-file-manager/SKILL.md`).
- **Leaf** checks used the filesystem (`parent.glob('*.pdf')`) so “leaf” matches the command definitions (at least one direct PDF in the folder).
- **`(reviewed)` exclusion:** apply a case-insensitive match on the basename, e.g. regex `\(\s*reviewed\s*\)` or substring `(reviewed)` — the audit used `(reviewed)` in the filename.
- **Science Revision Guide exclusion:** when reproducing these numbers, skip GoodNotes rows where `is_goodnotes_science_revision_guide_book_excluded(path)` is true (`completion_registry_audit.py`).
- Roots and registry DB path depend on the machine (`DAYDREAMEDU_ROOT`, `GOODNOTES_ROOT`, `PDF_REGISTRY_PATH`).
- **`has_marking`:** Recompute tallies whenever new canonical JSON appears under `context/marking_results/` (or paths/IDs in JSON change).

---

## Related

- GoodNotes scan then link workflow: `.cursor/skills/scan-goodnotes-folder/SKILL.md`
- Book groups, general vs student scope: `pdf_file_manager/docs/proposals/09-book-group-general-vs-student-scope.md`
- Template ↔ completion relations: `file_relations` with `template_for` / `completed_from` in `pdf_file_manager/schema.sql` and `PdfFileManager.link_to_template()`.
