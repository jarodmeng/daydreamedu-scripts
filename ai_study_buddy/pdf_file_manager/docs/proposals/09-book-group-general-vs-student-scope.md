# Proposal 9: Book groups — discriminate general templates vs student mirrors

**Happy path item:** [Book file groups] — `ensure_book_group_from_path` should only attach **general-scope template** mains to `group_type='book'`. Student-scope book mains are **linked** to those templates and must not appear as duplicate `file_group` members when both trees share the same `…/Book/<book name>/` basename.

---

## Implementation status

| Area | Status |
| --- | --- |
| Problem identified; manual `remove_from_file_group` workaround documented in workflows | **Observed** (e.g. reprocess-student-completion-from-general Phase B after scanning both roots) |
| Code change in `ensure_book_group_from_path` (B + C + prune; see **Implementation plan** below) | **Implemented** (`v0.3.6`) |

---

## Motivation

DaydreamEdu layout has two common shapes for the same *logical* title:

1. **General (templates):** `DAYDREAMEDU_ROOT/<subject>/<grade>/Book/<book name>/…`
2. **Student mirror:** `DAYDREAMEDU_ROOT/<subject>/<student_email>/<grade>/Book/<book name>/…`

`PdfFileManager._infer_from_path` already distinguishes these for **`is_template`** (grade-scope segment + student folder heuristic). Student-scope book mains are **linked** in the registry to their general-scope template mains (`template_main` ↔ completion). The book **`file_group`** should therefore list **only** those general-scope template files: one canonical set of units per book. Student completions remain discoverable via links, not as duplicate `file_group_members` rows.

---

## Problem

`ensure_book_group_from_path` (see `pdf_file_manager.py`) currently:

1. Resolves the **`book_folder`** (`…/Book/<book name>/`).
2. Finds **one** existing `group_type='book'` group whose **`label`** equals **`book_folder.name`**.
3. Adds every `doc_type='book'`, `file_type='main'` file whose **parent directory** equals **`book_folder`** to that group.

Because **label is only the short book directory name**, the **first** group created for e.g. `Grammar MCQs Explained Primary 1` is reused when `ensure_book_group_from_path` runs for:

- the **general** book folder, and later
- the **student** book folder with the **same** basename.

Scanning **both** folders in one `scan_for_new_files(roots=[general_book_dir, student_book_dir])` then adds **student `_c_` mains** into the **same** `file_group` as **general template `_c_` mains**, producing:

- duplicate **members** for the same unit basename (template + completion), even though completions are already **linked** to templates, and
- incorrect semantics for anything that assumes “this group = one set of template units for the book.”

Operational impact: workflows must **manually** call `remove_from_file_group` for student mains after linking (fragile, easy to forget).

---

## Goals

1. **`group_type='book'` membership:** include **only** general-scope **template** mains for that book folder (the canonical unit list for `book_answer_mappings`, anchors, coverage, and “units in this book”).
2. **Student mirrors:** do **not** add student-scope book mains to the book `file_group`; rely on registry **template ↔ completion** links to relate student work to the grouped templates.
3. **Backward compatibility:** existing DBs with a single group per label should keep working or migrate predictably (e.g. strip student members once, or filter on sync going forward).

---

## Design options

### Option A — Scope-aware group lookup (minimal schema)

- Extend group resolution so **`label` alone is not** the sole key when multiple book folders share a name.
- **Preferred key:** normalized **resolved path** of the **general** book folder (e.g. `str(book_folder.resolve())`), stored in a new column such as **`canonical_book_folder`** on `file_groups` (nullable for legacy rows), **or** encoded into `label` with a stable convention (higher migration risk).
- `ensure_book_group_from_path` when run on the **general** book folder: find/create by `canonical_book_folder`; **only** general template mains become members.
- If this option is chosen mainly to disambiguate **which** physical folder owns the group, student paths still do not contribute members (see Option C).

**Pros:** Clear semantics for “which directory is the book anchor,” queryable. **Cons:** migration + UI/CLI that display `label` must stay stable.

### Option B — Skip book grouping for student paths (no schema)

- In `ensure_book_group_from_path`, if **`book_folder`** is under a **student mirror** (same predicate as “student folder” in `_infer_from_path`: e.g. segment with `@` followed by a grade-scope segment), **do not** add mains to any `group_type='book'` row (and optionally no-op or resolve the **linked general** group for diagnostics only).
- **Pros:** Fast to ship, no DB migration; aligns with “group = templates only.” **Cons:** heuristic must stay in sync with path rules; no student-local book group (not needed if links are the source of truth).

### Option C — Filter members to general templates only (no schema)

- Keep a **single** group per `label` keyed from the **general** tree, but when **adding** mains, **only** include files that are **general-scope templates** (`is_template=True` and/or path not under student mirror). Student `_c_` mains are never inserted into `file_group_members` for `group_type='book'`.
- **Pros:** Small change; matches the product model (student files **linked**, not duplicated in the group). **Cons:** one-time cleanup may be needed for DBs that already have student members in book groups.

---

## Recommendation

**Primary invariant:** book `file_group` members = **general-scope template mains only**; student mirrors are excluded because they are **linked** to those templates.

Implement **both** **Option B** (skip student book folders) and **Option C** (filter adds to templates only): B avoids pointless work and clarifies call semantics; C is the safety net when `ensure_book_group_from_path` is invoked from paths that are not obviously student-scoped, or when `find_files` spans mixed rows. Add an explicit **prune** step when syncing the **general** book folder so existing DBs lose stale members without a manual one-off.

Prune should be computed as **set reconciliation** (`desired_member_ids` derived from current eligibility predicate), not only `is_template=False` removal. This removes stale rows from previous bad syncs, wrong-folder inserts, and mixed-label collisions in one pass.

Consider **Option A** later if label collisions between different **general** paths need a stable canonical path key; it does not change the “members = templates only” rule. If Option A is introduced, update APIs that currently assume a unique group per `label` (for example `import_book_answer_mappings_from_json`, which currently errors when multiple groups share one label).

---

## Implementation plan

Target: `PdfFileManager.ensure_book_group_from_path` in `pdf_file_manager.py` (and tests under `pdf_file_manager/tests/`). Call site: end of `scan_for_new_files` loops `book_folders_to_sync` and calls `ensure_book_group_from_path` per folder—student and general book folders can both enqueue the same scan batch.

### Shared predicate (keep in sync with `_infer_from_path`)

`_infer_from_path` treats a path as a **student mirror** when some segment contains `@` and the **next** segment is a grade/scope token (`P1`–`P6`, `PSLE`) — see `has_student_folder` in `PdfFileManager._infer_from_path`.

- [ ] **Extract** a single helper (e.g. `_path_has_student_mirror_layout(path: Path) -> bool`) that implements **the same** rule as `has_student_folder` in `_infer_from_path`, so Option B and any path-based checks do not drift from inference.
- [ ] **Refactor** `_infer_from_path` to use that helper for `has_student_folder` (single source of truth).
- [ ] **Unit-test** the helper against a small table of paths: general `…/Math/P5/Book/…` → false; `…/user@host.com/P5/Book/…` → true; optional: Google Drive–style `…/user@gmail.com/…/P6/…` → true per existing docstring on `_infer_from_path`.

### Option B — Skip book grouping for student book folders

- [ ] **API choice:** either change **`ensure_book_group_from_path`** return type to **`FileGroup | None`** (clear skip signal), or keep return type stable and return the existing canonical group for compatibility. Pick one explicitly in release notes.
- [ ] After resolving **`book_folder`** (existing logic: `target` dir vs `_infer_book_folder`), if **`_path_has_student_mirror_layout(book_folder)`** is **true**, skip membership mutations for this path: do **not** create a `file_groups` row, do **not** add members, do **not** prune members, do **not** set anchor from this path.
- [ ] **Call site:** `scan_for_new_files` is currently the only caller; verify no behavior change at the call site for either API choice above.

```1211:1213:ai_study_buddy/pdf_file_manager/pdf_file_manager.py
        if not dry_run:
            for book_folder in sorted(book_folders_to_sync):
                self.ensure_book_group_from_path(book_folder)
```

- [ ] **CHANGELOG** entry under `pdf_file_manager` describing behavior change and final API decision above.
- [ ] **Docstring** on `ensure_book_group_from_path`: document student-path skip behavior and returned value semantics.

### Option C — Only add general template mains; prune stale members

**Add path**

- [ ] When building `main_files` for the group, restrict to rows that are **`doc_type='book'`**, **`file_type='main'`**, parent dir equals `book_folder`, **`is_template is True`** (and optionally re-check not student layout if paranoid). This matches Option C even when B is skipped due to a bug.

**Prune path (recommended for existing DBs)**

- [ ] After resolving `group` for a **non-student** `book_folder`, compute `desired_member_ids` using the same eligibility predicate as add: `doc_type='book'`, `file_type='main'`, parent equals `book_folder`, `is_template=True` (and optional mirror-layout recheck).
- [ ] Reconcile group membership against that set: add missing desired ids, then remove every current member not in `desired_member_ids` via `remove_from_file_group(group.id, file.id)`.
  - Order: compute desired member ids → add missing → **prune anything not desired** → then existing anchor logic (anchor should remain a template main).

### Tests

- [ ] **Test B:** `ensure_book_group_from_path` on a path under `…/<segment-with-@>/<grade>/Book/<label>/` returns **`None`** and does **not** create a `group_type='book'` row when no general group exists yet (student-only sync must not invent a book group).
- [ ] **Test C + prune:** Fixture DB or temp registry: one book group with label L containing one eligible template member and one ineligible member (for example non-template or wrong parent folder). After `ensure_book_group_from_path` on **general** folder, only desired members remain.
- [ ] **Integration-style:** Two book folders same basename (general + student), registered mains in each — sync or direct `ensure_book_group_from_path` on general → group contains only template; call on student → no duplicate adds (B + C).
- [ ] **Ordering regression:** student-only scan first should not create a book group; subsequent general scan should create/sync group and set anchor from general template members.

### Updating documentation (small version bump)

- [ ] **Versioning approach:** treat this as a **patch** release for `pdf_file_manager` (behavior fix, no new feature surface). Current docs show `v0.3.5`; target next patch (for example `v0.3.6`).
- [ ] **CHANGELOG:** add a new top entry in `ai_study_buddy/pdf_file_manager/CHANGELOG.md` that includes:
  - book-group membership invariant (`group_type='book'` contains general template mains only),
  - student-path skip behavior in `ensure_book_group_from_path`,
  - prune-via-set-reconciliation behavior on general sync,
  - any API signature/return-value decision for `ensure_book_group_from_path`.
- [ ] **README version line:** update `**Version: ...**` in `ai_study_buddy/pdf_file_manager/README.md` to match the changelog bump in the same change.
- [ ] **README behavior docs:** update “Book file groups” / scan behavior text so manual `remove_from_file_group` cleanup is no longer described as required for normal flows.
- [ ] **SPEC update:** add/adjust normative statements in `ai_study_buddy/pdf_file_manager/SPEC.md`:
  - expected semantics of book-group membership,
  - student mirror exclusion rule,
  - idempotent reconciliation semantics for `ensure_book_group_from_path`.
- [ ] **ARCHITECTURE update:** document where the student-mirror predicate is shared (`_infer_from_path` + group sync path) so future changes do not drift.
- [ ] **DECISIONS entry:** add/update an entry in `ai_study_buddy/pdf_file_manager/DECISIONS.md` capturing:
  - why book groups are canonicalized to **general template mains only**,
  - why student book mains are represented via template links instead of group members,
  - why reconciliation uses desired-set membership (not append-only behavior),
  - compatibility note on label-based grouping and the deferred Option A path-key design.
- [ ] **TESTING update:** add/refresh relevant section in `ai_study_buddy/pdf_file_manager/TESTING.md` to include new regression scenarios (student-only-first scan order; prune of ineligible members).

### Workflow docs

- [ ] Update **Test plan** section below if assertions change after implementation.
- [ ] Grep workflows (`reprocess-student-completion-from-general`, `scan-goodnotes-folder`, etc.) for “remove_from_file_group” workarounds; **trim** or annotate if behavior is now automatic.
- [ ] Add a short audit helper note (doc or script) to list `group_type='book'` members that are not in the desired eligibility set, so legacy registries can be checked quickly.

### Optional follow-ups (out of scope unless needed)

- [ ] **Option A** (`canonical_book_folder` column): only if duplicate **general** paths with same folder name cause collisions.
- [ ] **CLI helper** to audit book groups for non-template members (one-shot for old DBs) if prune-on-sync is deemed too heavy — likely unnecessary if prune is implemented.

### Next step (post-implementation)

- [ ] **Future full cleanup pass:** after shipping B + C + prune-on-sync and validating in production-like usage, run an optional one-off full-registry reconciliation job/script that iterates all `group_type='book'` groups and enforces desired membership globally for fast convergence of legacy data.

---

## Test plan (when implemented)

- **Fixture:** Same `book name` under `…/<subject>/<grade>/Book/<book>/` and `…/<subject>/<student@email>/<grade>/Book/<book>/`, each with one registered `_c_` book main after scan.
- **Assert:** Exactly **one** `file_groups` row per logical general book (per chosen keying); **members** are only mains under the general template folder, not student mirror mains (even when both trees are scanned).
- **Assert:** `book_answer_mapping` flows that target the general book still resolve the same group id as today for general-only trees.
- **Regression:** Student-only scan does not create a book group; adding the matching general scan later creates/syncs it correctly.
- **Regression:** Single-folder layouts (general only, student only) unchanged except where explicitly intended.

---

## References

- `PdfFileManager.ensure_book_group_from_path` — current label-based lookup and member sync.
- `PdfFileManager._infer_from_path` — `is_template` and grade/student-folder heuristics (include **P1**–**P6**, **PSLE** in `grade_scope`).
- Reprocess workflow: `.cursor/skills/reprocess-student-completion-from-general/SKILL.md` (Phase B scans two roots).
