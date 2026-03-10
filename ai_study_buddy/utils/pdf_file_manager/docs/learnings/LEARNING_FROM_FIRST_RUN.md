### Overview

This document captures the main patterns and lessons from the first round of one‑off scripts built on top of `pdf_file_manager` (now housed under `scripts/archive/`). **Proposals 1–4 have been implemented** as of v0.1.1; see [CHANGELOG.md](../../CHANGELOG.md) § v0.1.1 and the [proposals](../proposals) folder.

The learnings here are based on the following scripts present at the time of writing (all paths are under `ai_study_buddy/utils/pdf_file_manager/scripts/archive/`):

- `_bootstrap_exam_scan.py`
- `_bootstrap_p5_chinese_exams.py`
- `_bootstrap_p5_english_eoy_exam.py`
- `_bootstrap_p5_math_exam.py`
- `_daydreamedu_leaf_vs_scan_roots.py`
- `_delete_duplicate_p5_worksheet1.py`
- `_fix_p3_exam_legacy_entries.py`
- `_fix_p6_exam_is_template.py`
- `_link_p5_worksheet1_template.py`
- `_link_p6_wa1_template.py`
- `_scan_chinese_p6_psle_general.py`
- `_scan_chinese_winston_selected_leaves.py`
- `_scan_english_p6_psle_general.py`
- `_scan_english_winston_selected_leaves.py`
- `_scan_math_selected_leaves.py`
- `_scan_p5_chinese_exercise_activity.py`
- `_scan_p5_english_activity.py`
- `_scan_p5_english_exercise.py`
- `_scan_p6_chinese_all.py`
- `_scan_p6_english_all.py`
- `_scan_p6_exam.py`
- `_scan_p6_psle_folders.py`
- `_scan_science_remaining_leaves.py`
- `_summarize_pdf_leaf_dirs_vs_scan_roots.py`

- **Goal of the utility**: maintain a registry of PDF study materials (exams, worksheets, activities, notes) with:
  - Stable IDs and metadata (`subject`, `doc_type`, `is_template`, `metadata`, `student_id`).
  - Raw vs main versions (`_raw_*.pdf` archives and `_c_*.pdf` working copies).
  - Relations between files (raw/main counterparts, templates vs completed work).
  - Higher-level groupings (exam sets, book exercises, ad‑hoc collections).

The one‑off scripts largely exercise three areas:

- Adding/ensuring **students** and **scan roots**.
- Running **scans** (dry‑run + real) on leaf folders.
- Doing **domain‑specific post‑processing** (exam groups, template links, data fixes, coverage diagnostics).

---

### What should become native features?

#### 1. Helpers to ensure students and scan roots

**Observed pattern**

Almost every script repeats the same logic:

- Ensure a student row exists:
  - `mgr.get_student(student_id)` → if missing, `mgr.add_student(student_id, name, email)`.
- Ensure a scan root exists:
  - `existing = mgr.list_scan_roots()`
  - If no `r.path == root_str`, call `mgr.add_scan_root(root_str, student_id=...)`.

**Suggested native helpers**

- `ensure_student(student_id, name, email=None) -> Student`
- `ensure_scan_root(path, student_id=None) -> ScanRoot`
- Optionally: `ensure_scan_roots([(path, student_id), ...])`

These would cut down boilerplate in every scanning script and make the intended workflow obvious.

#### 2. A proper “scan” CLI subcommand

**Observed pattern**

All the `_scan_*.py` and `_bootstrap_*_exam.py` scripts implement some variant of:

- Add/ensure scan roots.
- Dry run:
  - `scan_for_new_files(roots=[root_str], dry_run=True)`
  - Print “would process: <path>”.
- Real scan:
  - `scan_for_new_files(roots=[root_str], dry_run=False, on_file_start=...)`
  - Print per‑file progress and whether compression was used.

**Suggested native CLI**

Extend `_cli_main` with something like:

- `pdf_file_manager scan [--root PATH ...] [--dry-run] [--min-savings-pct N] [--progress]`

Behavior:

- If `--root` is provided, only scan those roots.
- Otherwise, scan all configured scan_roots.
- Support a progress callback when `--progress` is enabled.

This would absorb the bulk of logic in the scripts under `scripts/archive/`, for example:

- `scripts/archive/_scan_math_selected_leaves.py`
- `scripts/archive/_scan_science_remaining_leaves.py`
- The various `scripts/archive/_scan_p5_*.py` / `scripts/archive/_scan_p6_*.py` language/subject scripts
- `scripts/archive/_bootstrap_exam_scan.py` and the P5/P6 bootstrap scripts (for the scanning part).

#### 3. Coverage / diagnostics tools for scan roots

**Observed pattern**

Three scripts are essentially “coverage reports”:

Three scripts under `scripts/archive/` are essentially “coverage reports”:

- `scripts/archive/_daydreamedu_leaf_vs_scan_roots.py`:
  - Walks a DaydreamEdu base path for all **leaf directories** (no subdirectories).
  - Compares them to `scan_roots`.
  - Reports leaf dirs that are not yet scan roots.
- `scripts/archive/_summarize_pdf_leaf_dirs_vs_scan_roots.py`:
  - Derives leaf dirs from `pdf_files.path` parents.
  - Compares to `scan_roots` to find:
    - Leaf dirs with PDFs but not in `scan_roots`.
    - Scan roots currently without any direct PDFs.
- `scripts/archive/_scan_science_remaining_leaves.py`:
  - For Science, identifies leaf dirs under the subject base that are **not** in `scan_roots`, then adds them and scans them.

**Suggested native features**

- A small helper to find leaf dirs:
  - `find_leaf_dirs(base: Path) -> list[Path]` (even if only used internally).
- A CLI subcommand, e.g.:
  - `pdf_file_manager coverage --base PATH`
  - Output:
    - Count of leaf dirs under `base`.
    - Count of scan_roots.
    - Intersection counts.
    - List of leaf dirs not in scan_roots and scan_roots that currently have no PDFs.

This would turn the current one‑off reporting scripts into “standard tools” for monitoring coverage.

#### 4. Template/completion linking helpers

**Observed pattern**

Several scripts encode the same workflow:

- Identify a “blank” or “(empty)” version of a worksheet/exam and its filled counterpart in the same folder.
- Mark the blank version as a template and the filled version as non‑template:
  - `update_metadata(template_id, is_template=True)`
  - `update_metadata(completed_id, is_template=False)`
- Link them:
  - `link_to_template(completed_id, template_id)`

Scripts (all now in `scripts/archive/`):

- `_bootstrap_p5_math_exam.py` (applies for P5 Math exam files with `(empty)` suffixes).
- `_link_p5_worksheet1_template.py`
- `_link_p6_wa1_template.py`

**Suggested native helpers**

Keep filename heuristics domain‑specific, but centralize the linking pattern:

- Add a small helper:
  - `link_template_by_paths(completed_path, template_path)`:
    - Uses `get_file_by_path` to find both.
    - Sets `is_template` flags.
    - Calls `link_to_template`.
- Or a CLI command:
  - `pdf_file_manager link-template --template PATH --completed PATH`

Future one‑off scripts would then only have to:

- Decide on the path pairs (based on the naming scheme).
- Call the helper/CLI, rather than re‑implementing the linking logic each time.

#### 5. Safer, higher‑level migrations instead of raw SQL

**Observed pattern**

Some archived scripts reach directly into the SQLite connection and private methods:

- `scripts/archive/_fix_p3_exam_legacy_entries.py` uses `mgr._get_connection()` and hand‑written SQL for special cases.
- `scripts/archive/_summarize_pdf_leaf_dirs_vs_scan_roots.py` opens a new SQLite connection itself.

This is acceptable for tightly scoped, one‑off migrations but is brittle for general use.

**Suggested practice**

- Prefer existing high‑level methods when possible:
  - `compress_and_register`, `link_files`, `update_metadata`, `delete_file`, `link_to_template`, `get_operation_log`, etc.
- If low‑level SQL is needed:
  - Confine it to explicitly documented migration scripts (and keep them out of the “normal usage” path).
  - Consider adding small read‑only helpers to `PdfFileManager` where repeated patterns emerge (e.g., “list leaf dirs in registry”) so that diagnostics don’t need to open independent SQLite connections.

---

### Common usage patterns (informal HOWTO)

This section summarizes how the one‑off scripts use `PdfFileManager` and what seems to be the intended best practice.

#### Concepts and naming

- A **registry DB** (SQLite) stores:
  - Students (`students` table).
  - Scan roots (`scan_roots` table).
  - Files and metadata (`pdf_files`).
  - Relations (`file_relations`) and groups (`file_groups`, `file_group_members`).
- **Raw vs main files**:
  - Raw archive: `_raw_<name>.pdf` (`file_type='raw'`).
  - Main working file: `_c_<name>.pdf` (`file_type='main'`).
  - Unknown/legacy: no `_c_` / `_raw_` prefix (`file_type='unknown'`), normalized by `compress_and_register`.
- **Metadata inference**:
  - `_infer_from_path` uses the full path to infer:
    - `subject` (`english`, `math`, `science`, `chinese`).
    - `doc_type` (`exam`, `worksheet`, `activity`, `notes`) based on `Exam`/`Exercise`/`Activity`/`Note` segments.
    - `is_template` by checking for grade/scope segments (P3–P6, PSLE, Archive) vs student folders.
    - Extra metadata such as `grade_or_scope` and `chinese_variant`.

#### Typical scanning workflow

**1. Instantiate the manager**

- In almost all scripts:

```python
from pdf_file_manager import PdfFileManager

mgr = PdfFileManager()  # Optionally PdfFileManager(db_path=".../custom.db")
```

**2. Ensure students (for student‑specific folders)**

```python
STUDENT_ID = "winston"
if mgr.get_student(STUDENT_ID) is None:
    mgr.add_student(STUDENT_ID, "Winston Meng", "winston.ry.meng@gmail.com")
```

This is done once per script when scanning under `.../winston.ry.meng@gmail.com/...`.

**3. Ensure scan roots**

Best‑practice pattern used everywhere:

```python
root_str = str(root.resolve())
existing_roots = mgr.list_scan_roots()
if not any(r.path == root_str for r in existing_roots):
    mgr.add_scan_root(root_str, student_id=STUDENT_ID_OR_NONE)
```

Rules observed for `student_id`:

- Subject‑level/general templates (e.g. `.../Singapore Primary Math/P6/Exam`): `student_id=None`.
- Student‑folders (e.g. `.../winston.ry.meng@gmail.com/P5/Exercise`): `student_id="winston"`.

**4. Scan: dry run first, then real scan with progress**

Dry run is used everywhere before doing any write:

```python
dry = mgr.scan_for_new_files(roots=[root_str], dry_run=True)
for r in dry:
    print(f"would process: {r.file.path}")
if not dry:
    print("No new PDFs to register for this folder.")
    return
```

Then a real scan with `on_file_start`:

```python
done = [0]
total = len(dry)

def on_file_start(pdf_path: Path) -> None:
    done[0] += 1
    print(f"[{done[0]}/{total}] {pdf_path.name} ...")

results = mgr.scan_for_new_files(
    roots=[root_str],
    dry_run=False,
    on_file_start=on_file_start,
)
for r in results:
    print(f"-> {r.file.name} (compressed={r.compressed})")
```

Most scripts restrict `scan_for_new_files` to the explicit `roots=[root_str]` to avoid surprises; only a few early scripts call it with no `roots` (meaning “all scan_roots”).

**5. Let `scan_for_new_files` handle classification**

The scripts typically do *not* call `register_file` directly. Instead they:

- Use `scan_for_new_files` (which:
  - Calls `compress_and_register` for unknown PDFs under the leaf root.
  - Creates `_raw_` and `_c_` pairs when compression is beneficial.
  - Records relations and metadata.
  - Uses `_infer_from_path` to set subject, doc_type, is_template, and additional metadata.
- Then rely on `find_files`/`get_file_by_path` afterwards for further work.

The only places that bypass this are:

- Legacy fixes (`scripts/archive/_fix_p3_exam_legacy_entries.py`), by design.
- Some manual `delete_file` calls for known duplicates.

#### Templates and completed work

**Pattern**

Scripts that link templates all follow:

1. Find candidate template and completed files using `get_file_by_path` on known paths (with multiple name variants tried).
2. Skip if `mgr.get_template(completed.id)` is already set.
3. Set `is_template` flags via `update_metadata`.
4. Call `link_to_template(completed.id, template.id)`.

Example pattern:

```python
template_file = mgr.get_file_by_path(template_path)
completed_file = mgr.get_file_by_path(completed_path)
if not template_file or not completed_file:
    # log and skip
    ...
if mgr.get_template(completed_file.id):
    # already linked, skip
    ...
mgr.update_metadata(template_file.id, is_template=True)
mgr.update_metadata(completed_file.id, is_template=False)
mgr.link_to_template(completed_file.id, template_file.id)
```

Best practice is to keep **naming heuristics** outside the manager (in scripts), but always use `update_metadata` and `link_to_template` as the way to encode “blank vs filled” semantics.

#### Exam groups (file groups)

**Pattern**

Exam grouping scripts (`_bootstrap_p5_chinese_exams.py`, `_bootstrap_p5_math_exam.py`, `_bootstrap_p5_english_eoy_exam.py`) do:

1. Filter all `file_type="main"` files under a particular root:

   ```python
   mains = [f for f in mgr.find_files(file_type="main") if f.path.startswith(root_str)]
   ```

2. Bucket them by exam label using a filename heuristic:

   - Strip `_c_` prefix.
   - Remove `.pdf` suffix and domain suffix (`.p5.chinese.*`, etc).
   - Remove final role suffix in parentheses (`(题目)`, `(答案)`, `(作文)`, `(Paper 1)`, `(Paper 2)`, `(empty)`).

3. For each label:

   ```python
   existing = [g for g in mgr.list_file_groups(group_type="exam") if g.label == label]
   grp = existing[0] if existing else mgr.create_file_group(label, group_type="exam")
   for f in files:
       try:
           mgr.add_to_file_group(grp.id, f.id)
       except Exception:
           # already a member
           pass
   mgr.set_file_group_anchor(grp.id, files[0].id)
   ```

Best practice:

- The **meaning** of an exam group is encoded in the filename‑to‑label heuristic.
- `PdfFileManager` provides the **grouping primitives** (`create_file_group`, `add_to_file_group`, `set_file_group_anchor`) which are used uniformly.

#### Deletion and data fixes

**Deletion**

- Scripts use:

  ```python
  f = mgr.get_file_by_path(path)
  mgr.delete_file(f.id, notes="...", keep_related=False)
  ```

- `delete_file` is relied upon to:
  - Remove the file from disk.
  - Cascade delete raw archives when deleting a main (`raw_source` relation).
  - Clear `has_raw` flags when needed.
  - Clean up group memberships and relations.

**Migrations and data fixes (howto)**

- **Prefer high‑level APIs** when fixing or migrating data: `update_metadata`, `delete_file`, `link_to_template`, `link_files`, `get_operation_log`, `find_files`, `get_file`, `get_file_by_path`, `list_scan_roots`, etc. These keep invariants intact and remain valid across refactors.
- **Confine low‑level SQL** to single‑purpose, documented one‑off scripts (e.g. under `scripts/archive/` or a dedicated `migrations/`). In those scripts, document what they do and which DB/schema they assume.
- **Do not rely on `_get_connection()`** in long‑term tooling; it is internal. Scripts that need registry-derived data (e.g. “all paths in pdf_files”, “leaf dirs from registry”) should use a supported read‑only API when available (see proposals) instead of opening a separate connection or using private APIs.
- **One‑off migrations** (e.g. `scripts/archive/_fix_p3_exam_legacy_entries.py` — legacy main/raw/unknown row fixes) are acceptable when the repair cannot be expressed with the public API; treat them as exceptional and documented, not as everyday patterns.

#### Diagnostics / coverage

Common patterns for “what am I missing?”:

- Compare leaf dirs under a filesystem base vs `scan_roots`:
  - Identify leaf dirs that are not yet registered as scan roots.
- Compare leaf dirs from `pdf_files.path` parents vs `scan_roots`:
  - Identify:
    - Leaf dirs that have PDFs but are not scan roots.
    - Scan roots that currently have no PDFs directly under them.

Best practice today:

- Run these separate scripts periodically to check coverage.
- In the future, a built‑in `coverage` CLI would replace these bespoke scripts.

---

### Summary: intended “happy path”

Putting all of the above together, the intended ergonomic flow maps one-to-one to the five “what should become native features?” items:

- **1. [Ensure students and scan roots]** Configure scan roots for each subject/grade/folder you care about (via a future `ensure_scan_root` / `ensure_student` or equivalent), optionally with a `student_id` for per‑student copies.
- **2. [Scan CLI]** Use `scan_for_new_files` in a dry‑run‑then‑real pattern whenever you add new PDFs—ideally via a future `scan` CLI that supports `--root`, `--dry-run`, and `--progress`.
- **3. [Coverage/diagnostics]** Use diagnostics/coverage tools (e.g. a future `coverage` CLI) to ensure all relevant leaf folders are represented in `scan_roots` and the registry does not drift from the filesystem layout.
- **4. [Template linking]** Use template linking (and file groups) as thin layers on top of `find_files` + filename heuristics—with a future `link_template_by_paths` or `link-template` CLI so scripts only supply path pairs.
- **5. [Safer migrations]** For registry-derived data (paths, leaf dirs from `pdf_files`), use the coverage API/CLI (Proposal 3) so reporting never needs raw SQL or a separate connection. For migration practice (prefer high‑level APIs, confine SQL to one‑off scripts), see the “Migrations and data fixes (howto)” section above.

