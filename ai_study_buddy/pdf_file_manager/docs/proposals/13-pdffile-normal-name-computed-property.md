# Proposal 13: Add computed `PdfFile.normal_name`

**Happy path item:** [Naming ergonomics] — Expose a canonical, display/search-friendly name that strips technical prefixes (`_c_`, `_raw_`, `c_`, `raw_`) and the `.pdf` extension, without changing persisted schema.

---

## Implementation status

**Overall status: Implemented**

| Area | Status |
| --- | --- |
| Problem and scope definition | **Implemented** |
| Dataclass API addition (`PdfFile.normal_name`) | **Implemented** |
| Storage model change (DB column) | **Rejected (out of scope)** |
| Tests and docs updates | **Implemented** |

---

## Motivation

`PdfFile.name` intentionally reflects the on-disk basename exactly (for example `_c_P5 Science WA2 (Booklet A).pdf`).

For agent workflows and human-facing documentation, we often need a normalized logical title:

- without `_c_` / `_raw_` / `c_` / `raw_` transport prefixes,
- without `.pdf`,
- stable across raw/main variants.

Today this normalization logic exists in helper methods, but callers must re-implement or know internal helpers. A first-class property reduces repeated ad hoc string handling.

---

## Problem statement

The current model has one field (`name`) serving two different concerns:

- **physical filename identity** (must preserve exact basename), and
- **logical content name** (prefix/extension stripped).

Mixing these concerns creates avoidable confusion and inconsistent caller behavior.

---

## Goals

1. Add a simple, discoverable API for logical file naming: `PdfFile.normal_name`.
2. Keep existing registry schema and persistence behavior unchanged.
3. Ensure normalization behavior is deterministic and shared with existing prefix-stripping rules.

Non-goals:

- adding a `normal_name` column to `pdf_files`,
- changing `PdfFile.name` semantics,
- renaming files on disk.

---

## Proposed design

### API shape

Add a computed property on `PdfFile` dataclass:

- `normal_name: str`

Semantics:

1. Start from `PdfFile.name`.
2. Strip technical prefix in this order:
   - `_raw_`
   - `_c_`
   - `raw_`
   - `c_`
3. Remove `.pdf` extension via `Path(...).stem`.
4. Return the resulting string.

Examples:

- `_c_P5 Science WA2 (Booklet A).pdf` -> `P5 Science WA2 (Booklet A)`
- `_raw_Weighted Review 3.pdf` -> `Weighted Review 3`
- `c_Math Topical Practice.pdf` -> `Math Topical Practice`
- `raw_Math Topical Practice.pdf` -> `Math Topical Practice`
- `Worksheet.pdf` -> `Worksheet`

### Implementation detail

Introduce a canonical shared helper in `pdf_file_manager` (module-owned source of truth), and have `PdfFile.normal_name` delegate to it.

Reuse existing prefix logic (`_strip_technical_pdf_prefix`) inside that canonical helper so behavior stays consistent across inference helpers, dataclass property output, and downstream callers.

No database migration. No write-path changes.

---

## Downstream findings (standardization opportunity)

A quick scan across `ai_study_buddy/` found multiple downstream implementations that already normalize file names by stripping prefixes and extension:

- `marking/core/artifact_paths.py` (`normalize_attempt_stem`) strips `_raw_`, `_c_`, `raw_`, `c_`.
- `split_book_answer_by_unit_using_ai/scripts/book_context.py` strips `_c_` / `c_` inline in parsing logic.
- `marking/review/attempt_service.py`, `marking/review/detail_service.py`, and `marking/review/models.py` use `Path(...).stem` title fallbacks, which can still expose `_c_` prefixes.

This supports adding `PdfFile.normal_name` upstream with parity for `raw_` and migrating callers gradually.

---

## Why computed (not persisted)

Computed property is preferable because:

- zero schema migration risk,
- no backfill cost for existing rows,
- no drift risk between persisted `name` and derived `normal_name`,
- minimal blast radius for existing call sites.

Persisted column should only be reconsidered if we later need SQL-side filtering/indexing directly on `normal_name`.

---

## Compatibility and rollout

- Fully backward compatible: existing consumers of `name` continue unchanged.
- New consumers can opt into `normal_name` immediately.
- No registry migration needed.

---

## Detailed implementation plan (TODO checklists)

### Phase A — core model change (`pdf_file_manager.py`)

- [x] Add canonical shared helper in `pdf_file_manager` for filename normalization (prefix stripping + extension removal).
- [x] Add computed property `normal_name` to `PdfFile`.
- [x] Implement normalization with iterative prefix removal parity for:
  - [x] `_raw_`
  - [x] `_c_`
  - [x] `raw_`
  - [x] `c_`
- [x] Strip `.pdf` via `Path(...).stem`.
- [x] Ensure `PdfFile.normal_name` delegates to the canonical shared helper.
- [x] Reuse/centralize existing technical-prefix helper logic in that helper to avoid divergence.
- [x] Ensure no persistence-layer change (`schema.sql`, INSERT/SELECT shape) is required.

### Phase B — migrate all downstream usage to canonical normalization (now)

- [x] Replace all downstream ad hoc prefix stripping with canonical upstream normalization in this cycle.
- [x] Marking review titles:
  - [x] `marking/review/attempt_service.py` fallback title path
  - [x] `marking/review/detail_service.py` attempt title fallback
  - [x] `marking/review/models.py` `attempt_title(...)` fallback behavior
- [x] Split-book helper:
  - [x] replace inline `_c_`/`c_` stripping in `split_book_answer_by_unit_using_ai/scripts/book_context.py` with canonical normalization.
- [x] Marking artifact path utilities:
  - [x] make `marking/core/artifact_paths.normalize_attempt_stem` delegate to the upstream canonical normalizer.
  - [x] migrate all direct callers to canonical normalization inputs/outputs.
- [x] Repo-wide cleanup:
  - [x] scan all `ai_study_buddy/` Python modules for manual prefix stripping and replace with canonical usage.
  - [x] remove redundant local normalization helpers once all callers are migrated.
  - [x] if temporary wrappers are needed during edits, remove them before merge when safe.

### Phase C — docs and changelog

- [x] Update `DATA_MODEL.md` `PdfFile` surface with `normal_name` as computed/non-persisted.
- [x] Update `README.md` with short usage guidance: `name` (exact basename) vs `normal_name` (logical display name).
- [x] Add `CHANGELOG.md` entry documenting the new computed property and no-schema-change nature.
- [x] Optionally update skill/docs that currently re-describe manual stripping behavior.

---

## Test checklist

### Unit tests (required)

- [x] `PdfFile.normal_name` strips one prefix + extension:
  - [x] `_c_Foo.pdf` -> `Foo`
  - [x] `_raw_Foo.pdf` -> `Foo`
  - [x] `c_Foo.pdf` -> `Foo`
  - [x] `raw_Foo.pdf` -> `Foo`
- [x] `PdfFile.normal_name` handles repeated prefixes consistently:
  - [x] `_c_raw_Foo.pdf` -> `Foo`
  - [x] `_raw__c_Foo.pdf` -> `Foo`
- [x] Plain names remain stable:
  - [x] `Foo.pdf` -> `Foo`
  - [x] `Foo` -> `Foo`

### Integration/regression checks

- [x] Existing `pdf_file_manager` tests pass (no schema/runtime breakage).
- [x] Marking/review tests touching titles continue passing after fallback updates.
- [x] Split-book scripts still parse expected unit ordering after replacing inline normalization.
- [x] No SQL migration or registry rewrite is required to adopt the feature.
- [x] No remaining downstream manual prefix-stripping logic exists in `ai_study_buddy/` production modules.
- [x] Any temporary compatibility wrapper behavior matches upstream normalizer exactly for all covered prefix patterns and is removed before merge when no callers remain.

### Manual verification checklist

- [x] In a REPL, inspect `manager.get_file(...).name` vs `.normal_name` on both `_c_` and `_raw_` files.
- [x] Confirm review-workspace attempt titles no longer show `_c_`/`_raw_` prefixes when fallback path is used.
- [x] Confirm no behavior regression in GoodNotes paths that use `c_` naming.

---

## Success criteria

- [x] `PdfFile` exposes `normal_name` as computed property and it is available from existing read APIs (`get_file`, `find_files`, relations/group member `file` objects).
- [x] Prefix behavior matches established downstream expectations, including `raw_` parity.
- [x] No schema changes, migration scripts, or registry backfills are introduced.
- [x] Canonical helper ownership is in `pdf_file_manager`; `PdfFile.normal_name` and downstream consumers use that same helper.
- [x] `normalize_attempt_stem` is no longer an independent normalization authority (delegates during migration and is removed when safe).
- [x] All downstream production modules in `ai_study_buddy/` stop doing ad hoc prefix stripping and use upstream-normalized naming.
- [x] Documentation clearly explains when to use `name` vs `normal_name`.

---

## Test plan (summary)

1. **Unit tests for property normalization**
   - `_c_*.pdf` strips prefix + extension.
   - `_raw_*.pdf` strips prefix + extension.
   - `raw_*.pdf` strips prefix + extension.
   - `c_*.pdf` strips prefix + extension.
   - no-prefix names still strip extension.
2. **Behavior consistency**
   - property output matches existing technical-prefix stripping behavior.
3. **Regression**
   - existing tests around `register_file`, `find_files`, and serialization remain green.

---

## Documentation updates

- `DATA_MODEL.md`: add `normal_name` to `PdfFile` returned surface (marked as computed/non-persisted).
- `README.md`: short note under API usage showing when to use `name` vs `normal_name`.
- Optional: skill/docs references that currently describe stripped name logic.

---

## Risks and open questions

- If callers expect non-PDF files in future, extension stripping behavior should remain explicit (currently registry is PDF-focused).
- Confirm whether any downstream JSON serialization should include `normal_name` by default or remain implicit property-only.

---

## Decisions needed (with recommended defaults)

1. **Prefix stripping mode**
   - Decision: strip one prefix only vs iterative stripping until no known prefix remains.
   - **Recommended default:** iterative stripping for parity with existing `normalize_attempt_stem` behavior in `marking/core/artifact_paths.py`.

2. **`raw_` handling scope**
   - Decision: strip `raw_` only at the start of the basename vs anywhere in the string.
   - **Recommended default:** start-only stripping (avoid mutating legitimate mid-name text).

3. **Serialization surface**
   - Decision: include `normal_name` in API/JSON payloads immediately vs property-only initially.
   - **Recommended default:** property-only first; add to serialized payloads only where UX clearly benefits (for example review title fallback APIs).

4. **Phase-1 migration scope**
   - Decision: migrate high-impact modules first vs migrate all downstream usages now.
   - **Recommended default:** migrate all downstream usages now so canonical normalization benefits are realized immediately and duplicate logic is removed.

5. **Shared helper ownership**
   - Decision: make `marking/core/artifact_paths.normalize_attempt_stem` delegate to upstream helper vs keep separate implementation.
   - **Decision taken:** canonical helper is owned by `pdf_file_manager`; downstream helpers delegate.
   - **Outcome:** wrapper removed after call-site migration; no parallel normalization authority remains.

6. **Wrapper lifetime**
   - Decision: keep temporary wrapper names for one commit vs remove immediately where safe.
   - **Decision taken:** migrate all call sites in this cycle; keep wrappers only as short-lived migration scaffolding and remove before merge when no callers remain.

---

## Acceptance criteria

- `PdfFile` exposes `normal_name` as computed property.
- No schema changes or migration scripts are introduced.
- Tests validate normalization across `_c_`, `_raw_`, `raw_`, `c_`, and plain names.
- Docs clarify `name` (physical) vs `normal_name` (logical).
