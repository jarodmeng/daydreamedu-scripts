# Proposal: Registry-derived completion series (Proposal A)

**Status:** **Implemented** (2026-05-20) — Phases 1–5 complete  
**Audience:** Maintainers of `pdf_file_manager`, `files`, `marking`, Student File Browser, and L4 completion/marking docs  
**Related:** [L4_COMPLETION_MARKING_FRAMEWORK.md](../../../docs/L4_COMPLETION_MARKING_FRAMEWORK.md), [marking proposal: multiple attempts per template](../../../marking/docs/proposal/3-multiple_attempts_per_template_v1_1.md), [Student File Browser root filter](../../../student_file_browser/docs/proposal/1-root-id-filter.md)

### Implementation status (2026-05-20)

| Phase | Package / area | Shipped | Version |
|-------|----------------|---------|---------|
| **1** | `pdf_file_manager` | `completion_series.py`, `PdfFileManager` series API, `tests/test_completion_series.py` (8 tests) | **v0.3.19** |
| **2** | `marking` | Registry-sourced `attempt_sequence` in `artifact_writer.py`; `backfill_attempt_sequence_from_registry.py`; `marking/SPEC.md` writer contract | **v0.3.10** |
| **3** | `files` | `OnDiskMainPdfCard` series fields; `enrich_on_disk_main_pdf`; inventory test; `files/SPEC.md` | **v0.3.3** |
| **4** | `student_file_browser` | Attempt chip beside title | **v0.1.4** |
| **5** | L4 + package README/SPEC | L4 completion + file cross-links; `files/SPEC.md`; `pdf_file_manager` README/SPEC; marking proposal link | ✅ |

**Operator backfill (2026-05-20):** Applied registry backfill (14 JSON) + `learning_db.ingest.import_context_json --artifact-family marking_result` (178 DB rows refreshed).

---

## Why This Proposal Exists

[L4_COMPLETION_MARKING_FRAMEWORK.md](../../../docs/L4_COMPLETION_MARKING_FRAMEWORK.md) defines the mental model for completion PDFs, marking runs, and attempt ordering, but there is still **no canonical registry-layer representation** of “serial completion files from the same template for one student.”

Today:

| Layer | What exists | Gap (pre–Phase 1–3) | After Phase 1–3 |
|-------|-------------|---------------------|-----------------|
| **Registry** | `completed_from` / `template_for`; `get_completions` | No per-student series API | **`get_completion_series*`** — order by `pdf_files.added_at` |
| **Marking JSON** | `template_attempt_group_id`, `attempt_sequence` | Writer counted **artifacts**, not distinct `file_id`s | Writer uses **registry**; re-mark idempotent |
| **File browser** | `file_id`, `root_id`, workflow flags | No attempt ordinal | **Inventory JSON** + **`Attempt N of M`** chip when `attempt_count > 1` |

Operators see two cards with the same basename (e.g. DD scan + GoodNotes redo) and must infer order from paths, chips, or marking JSON.

**Proposal A** adds a **derived, deterministic completion series** computed from existing registry relations—**no new SQLite tables**—and makes it the **single source of truth** for sequence/group identity across marking, inventory enrichment, and (optionally) browser UX.

Deferred: **Proposal B** (mutable `completion_series` tables with editable labels/reorder) only if operators need labels or manual reorder without changing `created_at`.

---

## Scope

### In scope

| Layer | Change |
|-------|--------|
| **`pdf_file_manager`** | New module + `PdfFileManager` helpers to list/order completions in a `(student, template)` series |
| **`marking`** | `_next_attempt_sequence` / `write_marking_artifact` read sequence from registry series (distinct `file_id`s), not JSON artifact count |
| **`files`** | Enrich `OnDiskMainPdfCard` with series fields for registered completions with a template link |
| **`student_file_browser` (Phase 4, v1)** | Surface `attempt_sequence` / `attempt_count` on cards when `attempt_count > 1` (defer UI only if blocked; see §6 #4) |
| **Docs** | L4 completion framework, package README/SPEC/CHANGELOG; backfill note for existing JSON |
| **Tests** | Unit tests in `pdf_file_manager` and `marking`; inventory enrichment tests in `files` |

### Out of scope

- New registry tables or `file_relations` types (Proposal B / C)
- Editable `attempt_label` at registry layer (marking JSON `attempt_label` remains caller-provided; series does not invent labels)
- Cross-root deduplication into one browser card ([root_id filter](../../../student_file_browser/docs/proposal/1-root-id-filter.md) stays separate)
- `progress_vs_previous` or cross-attempt analytics
- Activity / note completions (no template link → series fields stay `null`)
- **Write-time duplicate marking guard** (one active `marking_result` per completion `file_id`; amendments/review on superseded runs) — [TODO.md](../../../TODO.md) **P0-1**

---

## Design

### Terminology

| Term | Definition |
|------|------------|
| **Completion series** | All registered **completion mains** (`is_template=false`, `student_id` set) linked via `completed_from` to the **same** template `file_id` for the **same** `student_id` |
| **Series id** | Stable string, **same formula as marking**: `"<student_slug>::<template_file_id>"` → stored in JSON as `template_attempt_group_id` |
| **Series sequence** | 1-based index of one completion `file_id` within its series, by deterministic sort order |
| **Re-mark** | Second marking JSON for the **same** `attempt_file_id` — does **not** change series membership or sequence |

### Series identity (normative)

```
series_id(student_id, template_file_id) =
  f"{slugify_student(student_id, student_name)}::{template_file_id}"
```

- `student_slug` uses the same rules as `marking.core.artifact_paths.slugify_student` (duplicate in `pdf_file_manager.completion_series` to avoid circular imports). Build from **`students.id` + `students.name`** via `get_student(completion.student_id)` so ids match marking JSON (e.g. `winston::…`, not raw UUIDs in the slug).
- If `template_file_id` is unknown (no `completed_from` link): **no series** — all series fields `null`. Do **not** invent `series_id` from completion `file_id` alone.

### Member discovery and ordering

**Members** of series `(student_id, template_file_id)`:

1. `template = get_file(template_file_id)`; must exist and `is_template=true`.
2. `candidates = get_completions(template_file_id)` — existing API returns completions linked via `template_for`.
3. Filter: `c.student_id == student_id` and `c.is_template is False` and `c.file_type == 'main'`.
4. Sort ascending by:
   - primary: **`pdf_files.added_at`** (registry column on `PdfFile`; ISO 8601 — first registration time, not link time)
   - tie-breaker: resolved `path` ascending (POSIX string)

**Sequence** for member at index `i` (0-based): `attempt_sequence = i + 1`.

**`attempt_count`**: `len(members)` for that series.

This ordering matches the **intended** semantics in [L4_COMPLETION_MARKING_FRAMEWORK.md](../../../docs/L4_COMPLETION_MARKING_FRAMEWORK.md). Legacy JSON backfill used artifact `created_at`; registry backfill uses **`pdf_files.added_at`** (see `backfill_attempt_sequence_from_registry.py`).

### Public API (`pdf_file_manager`)

New module: `ai_study_buddy/pdf_file_manager/completion_series.py`

```python
@dataclass(frozen=True)
class CompletionSeriesMember:
    file_id: str
    path: str
    added_at: str  # pdf_files.added_at at registration
    attempt_sequence: int  # 1-based within series

@dataclass(frozen=True)
class CompletionSeries:
    series_id: str
    student_id: str
    template_file_id: str
    members: tuple[CompletionSeriesMember, ...]  # sorted

    @property
    def attempt_count(self) -> int:
        return len(self.members)
```

**`PdfFileManager` methods** (thin delegates):

| Method | Returns |
|--------|---------|
| `get_completion_series(student_id, template_file_id) -> CompletionSeries \| None` | Full series or `None` if template missing, not a template, or **zero** members for this student; one member → `attempt_count = 1` |
| `get_completion_series_for_file(file_id) -> CompletionSeries \| None` | Resolve template via `get_template(file_id)`; then series for that student |
| `get_completion_series_member(file_id) -> tuple[CompletionSeries, CompletionSeriesMember] \| None` | Series + this file’s member row |
| `completion_series_id(student_id, template_file_id) -> str \| None` | Series id only (no member scan) when template known |
| `next_attempt_sequence_for_completion(file_id) -> int \| None` | Sequence slot for **this** file if already in series; else `attempt_count + 1` for a **new** completion about to be linked (marking writer use) |

**`next_attempt_sequence_for_completion` contract (marking writer):**

- Load series for completion’s `file_id` (must already be linked to template when marking runs).
- If `file_id` is already a member: return that member’s `attempt_sequence` (idempotent re-mark / re-write).
- If not yet in series but template link exists: return `len(members) + 1` only when adding a **new** file_id (normal case: file registered and linked before mark).
- If no template link: return `None`.

This fixes the bug where `_next_attempt_sequence` scans all JSONs and increments on re-mark.

### Marking artifact alignment

On `write_marking_artifact`, when `context.template_file_id` is set:

1. `template_attempt_group_id = completion_series_id(...)` (same string as `series_id`).
2. `attempt_sequence = next_attempt_sequence_for_completion(attempt_file_id)` **unless** caller explicitly set `attempt_sequence` (preserve override for tests).
3. Do **not** scan `marking_results/**/*.json` for sequence.

**Backfill:** Extend or add workflow `marking/workflows/backfill_attempt_sequence_from_registry.py` (dry-run + apply) that, for each JSON with `template_file_id` + `attempt_file_id`, sets `attempt_sequence` and `template_attempt_group_id` from registry series. Does not change marks/diagnoses. Run after deploy; optional one-time operator step.

### Inventory enrichment (`files`)

Extend `OnDiskMainPdfCard` (optional fields, default `None`):

| Field | Type | Meaning |
|-------|------|---------|
| `template_file_id` | `str \| None` | From registry `get_template` when registered completion |
| `completion_series_id` | `str \| None` | Same as `template_attempt_group_id` |
| `attempt_sequence` | `int \| None` | This card’s sequence in series |
| `attempt_count` | `int \| None` | Total completions in series for this student+template |

Populate in `enrich_on_disk_main_pdf` / `enrich_registered_completion` when `pfm` is available and `has_template` is true. Unregistered or unlinked completions: leave `null`.

Expose on `/api/inventory` card JSON for Student File Browser.

### Student File Browser (optional UX)

When `attempt_count > 1` and `attempt_sequence` is set, show chip or subtitle: **`Attempt {sequence} of {count}`** (do not hide duplicate basenames; `file_id` remains authoritative).

### Edge cases (normative)

| Case | Behavior |
|------|----------|
| No `completed_from` link | `completion_series_id = null`; all series fields null |
| Template re-created (new `template_file_id`) | New series id; old completions stay on old template’s series |
| Same student, same template, two files, same `added_at` | Path tie-breaker stabilizes order |
| `get_completions` includes other students | Filtered out by `student_id` |
| Completion registered, not yet linked at mark time | Writer sets `attempt_sequence = null` until `completed_from` exists |
| Completion not in registry (tests / dev) | Writer **degraded mode**: `attempt_sequence = 1` when `template_file_id` set but `attempt_file_id` not in DB (no JSON scan) |
| Twin DD/GN completions, both linked | Both appear in series; two sequences (expected) |

---

## Migration Plan

No registry schema migration.

1. ~~**Deploy** `completion_series` helpers (read-only).~~ **Done** (v0.3.19).
2. ~~**Deploy** marking writer change (new artifacts get correct sequence; re-mark idempotent).~~ **Done**.
3. ~~**Run** optional backfill on `context/marking_results/**`~~ **Done** (2026-05-20: 14 JSON + DB import).
4. ~~**Deploy** files enrichment~~ **Done** (v0.3.3). ~~Browser chip (Phase 4)~~ **Done** (`student_file_browser` v0.1.4).

**Rollback:** Revert marking writer to prior `_next_attempt_sequence`; series helpers remain harmless. Backfilled JSON can stay (values should match registry) or be re-run after rollback.

**Compatibility:** Existing `marking_result` readers unchanged. `template_attempt_group_id` formula unchanged—only **how** sequence is computed changes.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| `created_at` does not reflect “real world” attempt order (backdated scan) | Document that series order is **registry discovery order**; Proposal B if manual reorder needed |
| Circular import `marking` ↔ `pdf_file_manager` | Keep slugify in `pdf_file_manager` as copy or shared `ai_study_buddy.common` one-liner; marking calls **into** pfm only from writer |
| `get_completions` performance on large templates | Cache per `(student_id, template_id)` within a request; series size is small in practice |
| Backfill changes `attempt_sequence` on old JSON | Dry-run diff report; operator review; learning DB re-ingest if dual-write enabled |

---

## Open questions (resolved)

| # | Question | Decision |
|---|----------|----------|
| 1 | Sort key: `added_at` vs file `mtime` vs `file_relations.created_at`? | **`pdf_files.added_at`** (first registration); tie-breaker resolved `path` ascending. Link time (`file_relations.created_at`) is **not** used. |
| 2 | Should unmarked completions show sequence before first mark? | **Yes.** Registry series is the pre-marking source of truth; inventory enrichment populates `attempt_sequence` / `attempt_count` before any marking run exists. |
| 3 | Re-export `CompletionSeries` from `ai_study_buddy.files`? | **No.** `files` exposes flattened card fields only; series queries go through `PdfFileManager`. |
| 4 | Phase 4 browser UX in v1? | **Yes, ship in v1** when Phase 4 implementation is cheap (chip/subtitle only). If blocked, defer UI only—registry + marking + inventory fields still ship without a browser bump. |

---

## Detailed TODO Checklist (Implementation Monitoring)

### Phase 1 — Registry scaffolding (`pdf_file_manager`) ✅

**Goal:** Deterministic series computation with no marking/files changes.

**Implementation todos**

- [x] Add `pdf_file_manager/completion_series.py` with `CompletionSeries`, `CompletionSeriesMember`, pure functions `build_completion_series(...)`, `series_id_for(...)`.
- [x] Add `PdfFileManager.get_completion_series`, `get_completion_series_for_file`, `get_completion_series_member`, `completion_series_id`, `next_attempt_sequence_for_completion`.
- [x] Share `slugify_student` without importing `marking` (duplicate in `completion_series.py`; parity test vs `marking.core.artifact_paths.slugify_student`).
- [ ] Export new types from `pdf_file_manager` public surface if applicable — deferred (import from `completion_series` or `PdfFileManager`).

**Test todos**

- [x] `pdf_file_manager/tests/test_completion_series.py`: single member → sequence 1; two students same template → isolated series; sort by `added_at` then path; missing template → `None`; filter non-matching `student_id`.

**Success / handoff**

- [x] `python3 -m pytest ai_study_buddy/pdf_file_manager/tests/test_completion_series.py -q` passes (8 tests).
- [x] Manual (2026-05-20): Emma GN redo `c_四年级 补充练习 1.pdf` (`5e7e0e7a-…`) → `attempt_count=2`, `attempt_sequence=2`; pass 1 = DD `_c_` scan (`d427937a-…`, `added_at` 2026-04-27); pass 2 = GN `c_` (target, `added_at` 2026-04-29); `series_id=emma::d651a2c9-…`.

---

### Phase 2 — Marking writer + backfill (`marking`) ✅

**Goal:** Sequence from registry; fix re-mark sequence inflation.

**Implementation todos**

- [x] Replace `_next_attempt_sequence` JSON scan with `PdfFileManager().next_attempt_sequence_for_completion(attempt_file_id)`; **degraded mode** `attempt_sequence = 1` when completion not in registry but `template_file_id` set (no JSON scan).
- [x] Ensure `write_marking_artifact` sets `template_attempt_group_id` from `completion_series_id` (via `_resolve_template_attempt_group_id`).
- [x] Add `marking/workflows/backfill_attempt_sequence_from_registry.py` with `--dry-run` / apply; summary counts (updated/skipped/errors).
- [x] Update `marking/SPEC.md` writer contract: sequence from distinct completion `file_id`s in registry series.

**Test todos**

- [x] Writer test: two JSONs same `attempt_file_id` → same `attempt_sequence` on second write (`test_write_marking_artifact_idempotent_sequence_for_same_attempt_file_remark`).
- [x] Writer test: two different `attempt_file_id`s same template → sequences 1 and 2 (`test_write_marking_artifact_attempt_sequence_from_registry`).
- [x] Production dry-run (2026-05-20): 178 scanned, 14 would update, 0 validation errors.

**Success / handoff**

- [x] `python3 -m pytest ai_study_buddy/marking/tests -q` passes (186 tests).
- [x] Operator apply (2026-05-20): 14 JSON updated; `import_context_json --artifact-family marking_result` → 178 updated, 0 quarantined; JSON/DB spot-check aligned.

**Rollback**

- [x] Documented: revert `artifact_writer.py` only; keep `completion_series` module.

---

### Phase 3 — Inventory enrichment (`files`) ✅

**Goal:** Cards expose series fields before/without marking.

**Implementation todos**

- [x] Extend `OnDiskMainPdfCard` with `template_file_id`, `completion_series_id`, `attempt_sequence`, `attempt_count`.
- [x] Enrich in `enrich_on_disk_main_pdf` via `PdfFileManager.get_completion_series_member` (when `has_template`).
- [x] Bump `files` package version; update `CHANGELOG.md`, `README.md` (**v0.3.3**).

**Test todos**

- [x] `files/tests/test_on_disk_inventory.py`: `test_enrich_on_disk_main_pdf_populates_completion_series_fields`.

**Success / handoff**

- [x] Enriched inventory JSON includes new keys; old clients ignore unknown fields.

---

### Phase 4 — Student File Browser UX (v1)

**Goal:** L4 follow-up #3 — surface attempt ordinal on cards (`Attempt N of M` when `attempt_count > 1`).

**Implementation todos**

- [x] `static/app.js`: render `Attempt {attempt_sequence} of {attempt_count}` when `attempt_count > 1`.
- [x] Bump `student_file_browser` patch version; CHANGELOG (v0.1.4).

**Test todos**

- [x] Manual smoke on completion with 2+ series members.

**Success / handoff**

- [x] Operator confirms chip readable alongside `root_id` chip.

---

### Phase 5 — Documentation, L4, and TODO hygiene

**Goal:** Normative docs match implementation; close framework follow-ups tied to this proposal.

**Documentation todos**

- [x] Update [L4_COMPLETION_MARKING_FRAMEWORK.md](../../../docs/L4_COMPLETION_MARKING_FRAMEWORK.md): add **Completion series (registry-derived)** section; point to this proposal; mark follow-ups **#1** and **#3** resolved when shipped (follow-up **#2** remains [TODO.md](../../../TODO.md) **P0-1**).
- [x] Update [L4_FILE_FRAMEWORK.md](../../../docs/L4_FILE_FRAMEWORK.md) cross-link under completion identity.
- [x] Update `files/SPEC.md` with new `OnDiskMainPdfCard` series fields (`template_file_id`, `completion_series_id`, `attempt_sequence`, `attempt_count`).
- [x] Update `pdf_file_manager` README/API notes for new methods.
- [x] Link this proposal from [marking/docs/proposal/3-multiple_attempts_per_template_v1_1.md](../../../marking/docs/proposal/3-multiple_attempts_per_template_v1_1.md) as registry source of truth for sequence.

**Final sweep** (before marking proposal **Implemented**)

- [x] **Completeness:** Every public method in Phase 1 appears in SPEC/README.
- [x] **Accuracy:** `series_id` formula matches `template_attempt_group_id` in marking schema examples.
- [x] **Consistency:** L4, marking SPEC, and this proposal use the same sort keys and re-mark rules.
- [x] **Implementability:** An agent can execute phases 1→5 without reading source internals beyond linked modules.
- [x] Confirm §6 decisions still match shipped behavior (no drift from resolved open questions).

**TODO.md** (no dedicated open bullet today; on implementation merge, optionally add completed entry under **P1** or **P2** referencing this proposal)

- [x] If a new backlog item is created for implementation tracking, check it off when Phases 1–5 complete.

---

## Acceptance criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `get_completion_series(student_id, template_id)` returns deterministically ordered members with 1-based `attempt_sequence` | ✅ Phase 1 |
| 2 | `next_attempt_sequence_for_completion(file_id)` stable for existing member (re-mark does not increment) | ✅ Phase 1–2 |
| 3 | New marking artifacts get `attempt_sequence` from registry, not JSON file count | ✅ Phase 2 |
| 4 | Optional backfill can repair historical `attempt_sequence` without changing grades | ✅ Applied 2026-05-20 (14 JSON + DB import) |
| 5 | Student File Browser cards show attempt ordinal when `attempt_count > 1` | ✅ Phase 4 (v0.1.4) |
| 6 | L4 completion framework documents registry-derived series | ✅ Phase 5 |

---

## Versioning

| Package | Bump | Notes | Status |
|---------|------|-------|--------|
| `pdf_file_manager` | **v0.3.19** | New module + API | ✅ |
| `marking` | **v0.3.10** | Writer + backfill workflow | ✅ |
| `files` | **v0.3.3** | New optional card fields | ✅ |
| `student_file_browser` | **v0.1.4** | UI chip (Phase 4 only) | ✅ |

---

## Decision

**Adopt Proposal A:** treat completion series as a **derived projection** of `(student_id, template_file_id, completed_from)` with id `"<student_slug>::<template_file_id>"`, and wire marking + inventory to that projection. **Defer Proposal B** (persistent series tables / editable labels) until operators need manual reorder or labels independent of marking JSON.

**Review signals:** All phases complete (acceptance 1–6). Remaining backlog: writer guard [TODO.md](../../../TODO.md) **P0-1** (follow-up #2); optional `CompletionSeries` package export deferred.

---

## References

- [L4_COMPLETION_MARKING_FRAMEWORK.md](../../../docs/L4_COMPLETION_MARKING_FRAMEWORK.md) — identity layers; follow-ups #1 and #3 (series); #2 → [TODO.md](../../../TODO.md) **P0-1**
- [PROPOSAL_WRITING_INSTRUCTIONS.md](../../../docs/PROPOSAL_WRITING_INSTRUCTIONS.md) — required sections and checklist rules
- [marking/core/artifact_writer.py](../../../marking/core/artifact_writer.py) — `_resolve_attempt_sequence` (registry-sourced; replaces JSON scan)
- [marking/workflows/backfill_attempt_sequence_from_registry.py](../../../marking/workflows/backfill_attempt_sequence_from_registry.py) — registry backfill CLI
- [pdf_file_manager/completion_series.py](../../completion_series.py) — series types and `build_completion_series`
- [pdf_file_manager/pdf_file_manager.py](../../pdf_file_manager.py) — `get_template`, `get_completions`, `link_to_template`
- [files/on_disk_inventory.py](../../../files/on_disk_inventory.py) — `OnDiskMainPdfCard`, enrichment path
- [marking/docs/proposal/3-multiple_attempts_per_template_v1_1.md](../../../marking/docs/proposal/3-multiple_attempts_per_template_v1_1.md) — artifact fields (implemented)
