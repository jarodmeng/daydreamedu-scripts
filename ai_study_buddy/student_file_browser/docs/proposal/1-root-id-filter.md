# Proposal: Student File Browser — Root filter

**Status:** Implemented (`files` v0.3.2, `student_file_browser` v0.1.3)  
**Tracked by:** [TODO.md](../../../TODO.md) **P0-1**  
**Depends on:** `student_file_browser` **v0.1.2+**, `ai_study_buddy.files` **v0.3.1+** (this work → files **v0.3.2**, browser **v0.1.3**)  
**Related:** [L4_STUDENT_FILE_MANAGEMENT.md](../../../docs/L4_STUDENT_FILE_MANAGEMENT.md); [L4_COMPLETION_MARKING_FRAMEWORK.md](../../../docs/L4_COMPLETION_MARKING_FRAMEWORK.md) (completion/marking identity — not in scope here)

---

## 1. Summary

Add a **Root** filter to Student File Browser so operators can limit the grid to **DaydreamEdu**, **GoodNotes**, or **both**.

Inventory rows already have `root_id` (`daydreamedu` | `goodnotes`) and cards show it as a chip. `FilterCriteria` and `filter_main_pdf_cards` do not filter on it; the filter bar and URL have no `root_id` param ([L4 URL table](../../../docs/L4_STUDENT_FILE_MANAGEMENT.md)).

**Deliverables:** `root_id` on `FilterCriteria` + filter/meta in `ai_study_buddy.files`; query parsing + filter bar + URL sync in `student_file_browser`; tests and package/L4 docs.

---

## 2. Problem

When both `DAYDREAMEDU_ROOT` and `GOODNOTES_ROOT` are indexed, the default view can show **two cards** for the same logical paper (one per tree) with **different workflow badges**. Operators cannot hide one tree without mentally ignoring chips.

Typical uses:

- **DaydreamEdu** — marking/review triage (current artifact paths favor DD).
- **GoodNotes** — GN-only completions and exports.
- **All roots** — cross-root audit (~3 twin groups on operator data as of 2026-05-19).

---

## 3. Scope

### In scope

| Layer | Change |
|-------|--------|
| `ai_study_buddy.files` | `FilterCriteria.root_id`; filter branch in `filter_main_pdf_cards`; `root_ids` / `root_counts` in dropdown meta |
| `student_file_browser` | Parse `root_id` query param; **Root** control in filter bar; URL sync |
| Tests | `files/tests/test_on_disk_inventory.py`, `student_file_browser/tests/test_filters.py` |
| Docs | Package README/SPEC/CHANGELOG/TESTING; L4 URL row; close L4 Open Questions §2 |

### Out of scope

- Deduplicating cross-root twins into one card.
- Changing index construction (still index both roots; filter at query time).
- Registry schema, marking writer, or `attempt_sequence` behavior — see [L4_COMPLETION_MARKING_FRAMEWORK.md](../../../docs/L4_COMPLETION_MARKING_FRAMEWORK.md).

---

## 4. Design

### 4.1 URL parameter

| Param | Values | Default (recommended) |
|-------|--------|------------------------|
| `root_id` | `all` \| `daydreamedu` \| `goodnotes` | `all` (omitted from URL when default) |

Omit from URL when equal to default (same as `scope=completion`).

```text
http://localhost:8771/?scope=completion&student=winston&root_id=daydreamedu
```

### 4.2 `FilterCriteria` (`ai_study_buddy.files.on_disk_inventory`)

```python
@dataclass(frozen=True)
class FilterCriteria:
    scope: str = "completion"
    root_id: str = "all"  # all | daydreamedu | goodnotes
    student: str = ""
    # ... existing fields unchanged ...
```

### 4.3 `filter_main_pdf_cards`

When `criteria.root_id not in ("", "all")`, skip cards where `card.root_id != criteria.root_id`.

### 4.4 Dropdown meta

Add `root_ids` and `root_counts` to `FilterDropdownOptions` (slice excludes `root_id` criterion, same pattern as `subject`). Expose via `/api/config` and `/api/inventory` `meta`.

| Value | UI label |
|-------|----------|
| `all` | All roots |
| `daydreamedu` | DaydreamEdu |
| `goodnotes` | GoodNotes |

### 4.5 Frontend

- **Root** control near **Scope**; options from `meta.root_ids` / counts; hide or disable values with zero count when only one root is configured.
- Validate query values against `serve.py` `ROOT_IDS`.
- **Filter** / **Reset** unchanged; Reset restores default `root_id`.
- **View PDF** / **Review Workspace** links unchanged (per-card `root_id` on card JSON).

---

## 5. Versioning

| Package | Bump |
|---------|------|
| `ai_study_buddy.files` | **v0.3.2** |
| `student_file_browser` | **v0.1.3** |

Update `serve.py` `FILES_VERSION` and `/api/health` `files_version` when files ships.

---

## 6. Open questions (resolved)

| # | Question | Decision |
|---|----------|----------|
| 1 | Default `root_id`? | **`all`** (All roots) |
| 2 | Invalid `root_id` in URL? | Coerce to `all`; do not 400 |
| 3 | Show filter in **template** scope? | Yes (harmless if GN empty) |

---

## 7. Implementation checklist

### Phase 1 — `files`

- [x] `FilterCriteria.root_id` + `filter_main_pdf_cards` branch
- [x] `FilterDropdownOptions.root_ids` / `root_counts`
- [x] Tests; bump files to **v0.3.2**

### Phase 2 — `student_file_browser`

- [x] `filters.py` — parse / validate `root_id`
- [x] `static/app.js` — filter bar, `defaultFilterState`, URL sync
- [x] Tests; bump browser to **v0.1.3**

### Phase 3 — Docs & close P0-1

- [x] README, SPEC, CHANGELOG; [L4_STUDENT_FILE_MANAGEMENT.md](../../../docs/L4_STUDENT_FILE_MANAGEMENT.md) URL table
- [x] Manual smoke: `all` → `daydreamedu` → `goodnotes` (operator-verified)
- [x] [TODO.md](../../../TODO.md) **Completed P0-3**

---

## 8. Acceptance criteria

1. `root_id` query param filters the grid to one sync root or `all`.
2. Filter meta exposes `root_ids` and counts for the current slice.
3. Default documented and applied on Reset.
4. View PDF and Review Workspace deep links unchanged.
5. `files` v0.3.2 + `student_file_browser` v0.1.3 documented.

---

## 9. References

- [L4_STUDENT_FILE_MANAGEMENT.md](../../../docs/L4_STUDENT_FILE_MANAGEMENT.md)
- [L4_FILE_FRAMEWORK.md](../../../docs/L4_FILE_FRAMEWORK.md) — `root_id` on inventory rows
- [files/on_disk_inventory.py](../../../files/on_disk_inventory.py) — `FilterCriteria`, `filter_main_pdf_cards`
- [filters.py](../../filters.py), [static/app.js](../../static/app.js), [serve.py](../../serve.py) (`ROOT_IDS`, `FILES_VERSION`)
