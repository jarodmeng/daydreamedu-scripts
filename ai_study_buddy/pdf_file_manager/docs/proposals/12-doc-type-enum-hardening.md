# Proposal 12: Harden `doc_type` enums to align with path type folders

**Happy path item:** [Type consistency] — Registry `doc_type` values should match the canonical content-folder segment in file paths so inference, filtering, and workflows are deterministic and strict.

---

## Implementation status

**Overall status: Implemented**

| Area | Status |
| --- | --- |
| Live data check for `main` files in legacy/unused enums | **Observed** |
| Remove unused enums (`book_exercise`, `practice`, `unknown`) from accepted list | **Implemented** |
| Rename enums (`worksheet` -> `exercise`, `notes` -> `note`) | **Implemented** |
| Harden all type-resolution logic to fail fast on unresolved enum | **Implemented** |
| Backfill/migration for existing rows and code paths | **Implemented** |
| Regression tests and docs update | **Implemented** |

---

## Motivation

Current `doc_type` values and on-disk path type folders are close but not fully aligned:

- Path folder uses `Exercise` and `Note`.
- Registry uses `worksheet` and `notes`.
- Enum list still carries values that are unused or not desired for normal operation (`book_exercise`, `practice`, `unknown`).

This mismatch increases cognitive load and can hide errors in type inference or filtering logic.

---

## Verified current-state snapshot (live registry)

Scope: `file_type='main'`, filtered to these `doc_type` values: `[worksheet, book_exercise, practice, notes, unknown]`.

- `worksheet`: **337**
- `notes`: **44**
- `book_exercise`: **0**
- `practice`: **0**
- `unknown`: **0**

Path type segment for these files:

- all `worksheet` rows are under `.../Exercise/...`
- all `notes` rows are under `.../Note/...`

This supports migrating to `exercise` and `note` naming.

---

## Problem statement

`doc_type` currently blends legacy names, modern usage, and fallback values. As a result:

- the same concept has two names (`worksheet` vs `Exercise`, `notes` vs `Note`),
- some enum values are effectively dead branches,
- unresolved type cases can continue as tolerated values (`unknown`) instead of stopping processing.

---

## Goals

1. Make `doc_type` vocabulary match canonical path type folders.
2. Remove dead/unused enum branches from the accepted model surface.
3. Enforce strict processing: unresolved type must raise an exception immediately.
4. Keep migration deterministic and auditable.

Non-goals:

- changing `file_type` semantics (`main` / `raw` / `unknown`),
- redesigning file-group or relation schemas.

---

## Proposed enum contract

Canonical `doc_type` values after this change:

- `exam`
- `exercise`
- `book`
- `activity`
- `note`

Removed from accepted `doc_type` list:

- `worksheet`
- `notes`
- `book_exercise`
- `practice`
- `unknown`

---

## Design and implementation plan

### 1) Centralize and harden enum resolution

Add a single canonical resolver used by all registration/inference/update paths, for example:

- `_normalize_doc_type(value: str) -> str`

Behavior:

- no legacy-alias acceptance (single-shot migration; see Compatibility strategy),
- rejects disallowed values with explicit exception (for example `InvalidDocTypeError`),
- never silently falls back to `unknown`.

### 2) Update path-inference logic

Path-folder to `doc_type` mapping should be explicit and strict:

- `Exam` -> `exam`
- `Exercise` -> `exercise`
- `Book` -> `book`
- `Activity` -> `activity`
- `Note` -> `note`

If a file is in scope for type inference but no valid mapping is resolvable, raise exception and stop that processing unit.

### 3) Update all module logic that branches on `doc_type`

Audit all logic that currently checks or emits old enums, including:

- `register_file`
- `scan_for_new_files`
- `compress_and_register`
- `update_metadata` validation
- `find_files` filters/validation
- helper scripts and validation utilities

Replace old strings and remove dead branches that reference removed enums.

### 4) Data migration/backfill

One-time migration over `pdf_files.doc_type`:

1. `worksheet` -> `exercise`
2. `notes` -> `note`
3. assert count for `book_exercise`, `practice`, `unknown` is zero before enforcing strict validation
4. fail migration if unexpected disallowed values are present

Migration should produce a summary report with before/after counts.

### 5) Processing failure behavior (required)

Any fail-to-resolve `doc_type` in processing must raise a hard exception (no soft fallback):

- registration path: reject file with clear path + reason
- scan batch: either fail whole run (strict mode default) or mark explicit error record and return non-success status
- metadata update: reject invalid `doc_type` values

Recommended exception class:

- `InvalidDocTypeError(ValueError)`

Error message should include:

- offending value,
- file path (if available),
- accepted enum set.

---

## Detailed implementation plan (single-shot)

This plan assumes we do the migration in one shot: first rewrite stored legacy values, then hard-enforce strict canonical enums across all code paths.

### A) Code changes — canonical enums + strict resolution

- [x] **Define canonical enum set** in one place (module constant), e.g.:
  - `DOC_TYPES_CANONICAL = {"exam","exercise","book","activity","note"}`
- [x] **Add `InvalidDocTypeError`** (subclass `ValueError`) if one does not already exist.
- [x] **Implement `_normalize_doc_type(value: str) -> str`**:
  - [x] strip and lowercase input
  - [x] if `value` not in `DOC_TYPES_CANONICAL`, raise `InvalidDocTypeError`
  - [x] return canonical value
- [x] **Replace any direct string validation** of `doc_type` with `_normalize_doc_type(...)`:
  - [x] `register_file(...)` (direct calls and any inference outputs)
  - [x] `update_metadata(..., doc_type=...)`
  - [x] `find_files(doc_type=...)` filter validation (if present)
  - [x] any helper methods that accept/emit `doc_type`
- [x] **Update path inference** so the content-folder segment maps to canonical `doc_type`:
  - [x] `Exam` -> `exam`
  - [x] `Exercise` -> `exercise`
  - [x] `Book` -> `book`
  - [x] `Activity` -> `activity`
  - [x] `Note` -> `note`
  - [x] if a file is “in scope” (i.e., a recognized DaydreamEdu/GoodNotes-style path) but content folder cannot be resolved, raise `InvalidDocTypeError` (include file path).
- [x] **Delete dead branches** that mention removed enums:
  - [x] `worksheet`, `notes`, `book_exercise`, `practice`, `unknown` (doc_type only)

### B) One-shot data migration (registry)

- [x] **Create a migration script** under `ai_study_buddy/pdf_file_manager/scripts/` (name TBD) that uses `PdfFileManager` (not raw sqlite) to:
  - [x] scan for rows where `doc_type in {"worksheet","notes"}` and rewrite:
    - [x] `worksheet` -> `exercise`
    - [x] `notes` -> `note`
  - [x] assert zero rows exist with `doc_type in {"book_exercise","practice","unknown","worksheet","notes"}` after rewrite
  - [x] print a before/after count table
  - [x] exit non-zero on any unexpected values (or unresolved rows)
- [x] **Dry-run option**:
  - [x] add `--dry-run` (default false) to print planned rewrites without persisting
- [x] **Safety checks**:
  - [x] confirm you are operating on the expected registry path (print it)
  - [x] optionally run the existing integrity validator after migration

### C) Documentation updates

- [x] Update `DATA_MODEL.md` `PdfFile.doc_type` list to the canonical set.
- [x] Update `SPEC.md` and `README.md` wherever doc_type values are enumerated.
- [x] Update `.cursor/skills/pdf-file-manager/SKILL.md` where doc_type values are enumerated or implied.
- [x] Add a **patch version bump** entry in `CHANGELOG.md` documenting:
  - [x] the new canonical `doc_type` enum set,
  - [x] removal of legacy/unused values,
  - [x] strict failure behavior on invalid `doc_type`.

### D) Cleanup / follow-ups

- [x] Grep the repo for removed `doc_type` strings and remove/update any references:
  - [x] `"worksheet"`, `"notes"`, `"book_exercise"`, `"practice"`, `"unknown"` (doc_type context)
- [x] Ensure any “unknown” mentioned in docs refers only to `file_type='unknown'`, not `doc_type`.

---

## Test checklist

### Unit tests (library)

- [x] `_normalize_doc_type`:
  - [x] accepts each canonical value
  - [x] rejects legacy values (`worksheet`, `notes`)
  - [x] rejects removed values (`book_exercise`, `practice`, `unknown`)
  - [x] rejects `None` / empty string / whitespace / typos
- [x] `update_metadata(..., doc_type=...)`:
  - [x] persists canonical values
  - [x] raises `InvalidDocTypeError` on non-canonical input
- [x] Path inference:
  - [x] `.../Exercise/...` -> `exercise`
  - [x] `.../Note/...` -> `note`
  - [x] unknown content folder in otherwise in-scope path raises `InvalidDocTypeError`

### Integration tests (scan/register)

- [x] scanning a folder with a valid path layout produces only canonical `doc_type`
- [x] scanning a folder with an invalid/unknown content folder fails fast with a clear exception (includes path)
- [x] no code path inserts `doc_type='unknown'`

### Migration test (script)

- [x] `--dry-run` reports correct rewrite counts without persisting
- [x] real run rewrites all `worksheet`/`notes`
- [x] post-check asserts zero rows remain in removed/legacy values
- [x] script fails with non-zero exit when encountering an unexpected value

### Regression checks (existing suite)

- [x] run the full `pdf_file_manager` test suite
- [x] run `scripts/validate_pdf_registry_integrity.py` (or equivalent) after migration to confirm no new integrity issues were introduced

---

## Compatibility strategy

Single-shot migration (recommended):

- Run the one-time backfill to rewrite stored rows:
  - `worksheet` -> `exercise`
  - `notes` -> `note`
- Verify there are zero rows remaining in removed values:
  - `book_exercise`, `practice`, `unknown`, plus the renamed legacy values
- Then immediately enforce strict canonical enums everywhere:
  - `_normalize_doc_type` rejects any legacy/removed value (no mapping)
  - any fail-to-resolve enum raises `InvalidDocTypeError`

---

## Test plan

1. **Unit tests — enum validation**
   - valid canonical values accepted.
   - removed values rejected in strict mode.
2. **Unit tests — path inference**
   - `Exercise` maps to `exercise`, `Note` maps to `note`.
   - unrecognized content folder raises `InvalidDocTypeError`.
3. **Unit tests — migration**
   - backfill rewrites `worksheet`/`notes`.
   - migration fails when disallowed values remain.
4. **Integration tests — scan/register flow**
   - batch fails fast when type cannot resolve.
   - no `unknown` `doc_type` rows produced.

---

## Risks and open questions

- Existing downstream code may still query `worksheet`/`notes`; all call sites must be migrated.
- Historical analytics or exports keyed by old values need mapping.
- Decide whether scan should hard-fail whole batch or return partial successes with explicit error objects; strict failure is preferred for data integrity.

---

## Acceptance criteria

- No `pdf_files.doc_type` rows remain in `{worksheet, notes, book_exercise, practice, unknown}`.
- Canonical enum set enforced at runtime.
- Any unresolved type in processing raises explicit exception.
- Docs (`README.md`, `SPEC.md`, `DATA_MODEL.md`, skill docs) reflect the new enum contract.
