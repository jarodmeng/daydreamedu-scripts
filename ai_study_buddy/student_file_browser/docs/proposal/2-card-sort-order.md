# Proposal: Student File Browser — Card sort order

**Status:** Implemented (`files` v0.3.6, `student_file_browser` v0.1.7) — **`recent` sort updated** for completion dates (2026-05-27)  
**Tracked by:** Shipped (no separate [TODO.md](../../../TODO.md) item)  
**Depends on:** `student_file_browser` **v0.1.4+**, `ai_study_buddy.files` **v0.3.3+**  
**Related:** [L4_STUDENT_FILE_MANAGEMENT.md](../../../docs/L4_STUDENT_FILE_MANAGEMENT.md); [1-root-id-filter.md](./1-root-id-filter.md)

---

## 1. Summary

Today the card grid follows **index build order**: all mains sorted by **full absolute path** (case-insensitive). Filtering preserves that order; the UI does not re-sort.

Add a **Sort** control (filter bar + URL) with **two** modes: **recency** (default) and **name**. Apply sort **server-side** after `filter_main_pdf_cards` so order is shareable, testable, and consistent with other filter semantics.

**Deliverables:** `FilterCriteria.sort` + `sort_main_pdf_cards` in `ai_study_buddy.files`; `registry_added_at` on `OnDiskMainPdfCard`; `student_file_browser` query parsing + UI; tests; package/L4 docs.

**Ship order:** `files` **v0.3.4** first → bump `serve.py` `FILES_VERSION` → `student_file_browser` **v0.1.5**.

---

## 2. Problem

| Symptom | Cause |
|---------|--------|
| Cards feel ordered by folder path, not title | Implicit path sort from index build |
| Hard to find “what we registered lately” | No recency dimension |
| Operators cannot share a sorted view | Order is implicit; no URL knob |

The **Attempt {n} of {m}** chip (v0.1.4) labels series membership but does not control sort order.

---

## 3. Scope

### In scope

| Layer | Change |
|-------|--------|
| `ai_study_buddy.files` | `FilterCriteria.sort`; `sort_main_pdf_cards`; `registry_added_at` on `OnDiskMainPdfCard` |
| `student_file_browser` | `filters.py` + `serve.py` + `static/app.js`; tests in `tests/test_filters.py` |
| Docs | `files` + `student_file_browser` README/SPEC/CHANGELOG/TESTING; L4 URL table; `ARCHITECTURE.md` pipeline line |

### Out of scope (v1)

- Additional sort presets (path, completion series, review, marking).
- Multi-dimensional / user-composable sort keys.
- Section headers or grouped grid.
- Client-only sort.
- `localStorage` for sort preference.
- Changing **index build** order in `build_main_pdf_index_for_roots`.

---

## 4. Sort options

Exactly **two** user-facing modes. Tie-breakers are **fixed per mode** (not user-configurable).

### 4.1 `recent` — Completed (recent) (default)

| | |
|--|--|
| **Primary key** | `completion_date` descending (`YYYY-MM-DD` from `file_completion_dates`) |
| **Tie-breaker** | `absolute_path` casefold, ascending |
| **Undated registered** | No `completion_date` → middle block, path ascending (not sorted by `registry_added_at`) |
| **Unregistered** | No `registry_added_at` → trailing block, path ascending |
| **Use when** | Default browse; “what did the student finish most recently?” |

**Enrichment:** `card.completion_date` / `completion_date_source` from `PdfFileManager.get_completion_date` when registered; `card.registry_added_at = pdf_file.added_at` still set for **Registered** display only.

**Normative spec:** [proposal 17 §5.4](../../../pdf_file_manager/docs/proposals/17-completion-date.md#54-consumers-when-no-row-exists). Shipped in `files` **v0.3.6** (replaces v0.3.4 `added_at` proxy for `recent` sort).

---

### 4.2 `name` — Display name

| | |
|--|--|
| **Primary key** | `(normal_name or basename)` casefold, ascending (A–Z) |
| **Tie-breaker** | `absolute_path` casefold, ascending |
| **Use when** | Browsing worksheets by title |

Multiple attempts sharing the same `normal_name` order by path only (acceptable for v1).

---

## 5. Decisions (resolved)

| # | Decision |
|---|----------|
| 1 | Default `sort` = **`recent`**; omit from URL when default |
| 2 | Invalid / unknown `sort` → coerce to **`recent`** (no HTTP 400) |
| 3 | Unregistered under `recent` → **after** all registered; path tie-breaker in tail |
| 4 | `registry_added_at` = raw **`PdfFile.added_at`** string on card JSON |
| 5 | Sort always applied at API boundary (default changes grid vs today’s implicit path order) |
| 6 | `/api/config` unchanged (no contextual sort meta in v1) |
| 7 | `meta.sort` on `/api/inventory` — **skipped** in v1 (not echoed) |

---

## 6. Server design

### 6.1 Pipeline

```text
index_rows → build_enriched_inventory → filter_main_pdf_cards → sort_main_pdf_cards → JSON items
```

Sort runs on the **filtered** list only (`total_after_filter` unchanged).

### 6.2 `sort_main_pdf_cards` (normative)

Add to [`files/on_disk_inventory.py`](../../../files/on_disk_inventory.py):

```python
_VALID_SORT_KEYS = frozenset({"name", "recent"})

def _display_name_key(card: OnDiskMainPdfCard) -> str:
    return (card.normal_name or card.basename).casefold()

def _path_key(card: OnDiskMainPdfCard) -> str:
    return card.absolute_path.casefold()

def sort_main_pdf_cards(
    cards: list[OnDiskMainPdfCard],
    sort: str = "recent",
) -> list[OnDiskMainPdfCard]:
    key = sort if sort in _VALID_SORT_KEYS else "recent"
    if key == "name":
        return sorted(cards, key=lambda c: (_display_name_key(c), _path_key(c)))
    # recent: registered block (newest first), then unregistered tail
    registered = [c for c in cards if c.registry_added_at]
    unregistered = [c for c in cards if not c.registry_added_at]
    registered.sort(key=_path_key)  # tie-breaker (stable)
    registered.sort(key=lambda c: c.registry_added_at, reverse=True)  # primary: newest first
    unregistered.sort(key=_path_key)
    return registered + unregistered
```

Single-pass tuple keys are fine if unit tests assert the same ordering.

### 6.3 `FilterCriteria` + exports

```python
@dataclass(frozen=True)
class FilterCriteria:
    # ... existing fields ...
    sort: str = "recent"
```

Export `sort_main_pdf_cards` from [`files/__init__.py`](../../../files/__init__.py) and `__all__`.

### 6.4 `OnDiskMainPdfCard`

```python
registry_added_at: str | None = None  # PdfFile.added_at when registered
```

Included in `to_dict()` automatically via `fields(self)`.

### 6.5 `student_file_browser/filters.py`

Mirror `root_id` validation:

```python
_VALID_SORT_KEYS = frozenset({"name", "recent"})

def filter_criteria_from_query(params):
    sort_raw = (_one("sort", "recent") or "recent").strip().lower()
    sort = sort_raw if sort_raw in _VALID_SORT_KEYS else "recent"
    return FilterCriteria(..., sort=sort)
```

### 6.6 `serve.py`

```python
from ai_study_buddy.files import ..., sort_main_pdf_cards

filtered = filter_main_pdf_cards(cards, criteria, pfm=pfm)
filtered = sort_main_pdf_cards(filtered, criteria.sort)
```

Bump `FILES_VERSION` to **`0.3.4`** when `files` ships.

---

## 7. Frontend UI integration

### 7.1 Control placement

**Sort** `<select>` in the filter **actions** row, after **Filter** and **Reset** (`.filter-actions`).

| `sort` value | UI label | Order in dropdown |
|--------------|----------|-------------------|
| `recent` | Recent first | 1 (default selected) |
| `name` | Name (A–Z) | 2 |

Static options (not from `/api/config` meta).

### 7.2 `static/app.js` touchpoints

| Function | Change |
|----------|--------|
| `defaultFilterState()` | `sort: "recent"` |
| `stateFromUrl()` | `sort: p.get("sort") \|\| "recent"` |
| `qsFromState(state)` | if `state.sort !== "recent"` → `p.set("sort", state.sort)` |
| `buildFilters(state)` | `addSelect("sort", …, actions)` after **Reset** in `.filter-actions` |
| `addSelect` | `id === "sort"` → `change` → `onApplyFilters` |
| `readStateFromDom()` | read `document.getElementById("sort")?.value \|\| "recent"` |
| `resetFilters()` | uses `defaultFilterState()` → `sort: "recent"` |

**Sort** reapplies inventory on `change` (no separate **Filter** click). Other filters still require **Filter**. **Reset** restores `sort=recent`.

### 7.3 URL

| Param | Values | Default |
|-------|--------|---------|
| `sort` | `name` \| `recent` | `recent` (omit when default) |

```text
http://localhost:8771/?student=emma&subject=chinese&doc_type=exercise&sort=name
```

---

## 8. Versioning

| Package | Version | Notes |
|---------|---------|--------|
| `ai_study_buddy.files` | **v0.3.4** | `sort_main_pdf_cards`, `FilterCriteria.sort`, `registry_added_at` |
| `student_file_browser` | **v0.1.5** | Sort control + URL; requires `files` v0.3.4 |

---

## 9. Tests

### 9.1 `files/tests/test_on_disk_inventory.py`

- [x] `test_sort_main_pdf_cards_name` — two cards, titles `B` / `A` → A first
- [x] `test_sort_main_pdf_cards_name_tie_path` — same `normal_name`, paths differ → path ascending
- [x] `test_sort_main_pdf_cards_recent` — two registered, `added_at` `2026-01-01` vs `2026-06-01` → newer first
- [x] `test_sort_main_pdf_cards_recent_unregistered_tail` — one registered + one unregistered → registered first
- [x] `test_sort_main_pdf_cards_invalid_coerces_recent` — `sort="bogus"` behaves as `recent`
- [x] `registry_added_at` on enrich — asserted in `test_enrich_on_disk_main_pdf_populates_completion_series_fields`

Use lightweight `OnDiskMainPdfCard(...)` fixtures (no disk), same style as existing inventory tests.

### 9.2 `student_file_browser/tests/test_filters.py`

- [x] `test_filter_criteria_from_query_sort_default` — `{}` → `sort == "recent"` (via `test_filter_criteria_from_query_defaults`)
- [x] `test_filter_criteria_from_query_sort_name`
- [x] `test_filter_criteria_from_query_invalid_sort` → `recent`

---

## 10. Documentation checklist

- [x] `files/CHANGELOG.md` — v0.3.4 entry
- [x] `files/SPEC.md` / `README.md` — `sort_main_pdf_cards`, `registry_added_at`, `FilterCriteria.sort`; package version **v0.3.4**
- [x] `files/TESTING.md` — sort tests + `student_file_browser/TESTING.md` sort smoke
- [x] `student_file_browser/CHANGELOG.md` — v0.1.5 entry (+ sort-on-change, card date line)
- [x] `student_file_browser/SPEC.md` — `sort` query param + UI bullet
- [x] `student_file_browser/README.md` — short operator note
- [x] `student_file_browser/ARCHITECTURE.md` — pipeline includes sort step
- [x] `docs/L4_STUDENT_FILE_MANAGEMENT.md` — URL table row for `sort`

---

## 11. Implementation checklist

### Phase 1 — `files` (land first)

- [x] `OnDiskMainPdfCard.registry_added_at`
- [x] `enrich_on_disk_main_pdf` — set `registry_added_at` from `pdf_file.added_at` immediately after `reg_row` resolves to `PdfFile`
- [x] `FilterCriteria.sort: str = "recent"`
- [x] `sort_main_pdf_cards` + `_VALID_SORT_KEYS`
- [x] Export from `files/__init__.py`
- [x] Tests §9.1
- [x] Bump **v0.3.4** in `files/CHANGELOG.md`

### Phase 2 — `student_file_browser`

- [x] `filters.py` — parse / validate `sort`
- [x] `serve.py` — import `sort_main_pdf_cards`; call after filter; `FILES_VERSION = "0.3.4"`
- [x] `static/app.js` — §7.2 touchpoints
- [x] Tests §9.2
- [x] Bump **v0.1.5** in `student_file_browser/CHANGELOG.md`

### Phase 3 — Docs & smoke

- [x] §10 documentation (SPEC, ARCHITECTURE, CHANGELOG, L4 URL table, files README/SPEC)
- [x] Manual smoke: sort **Recent first** / **Name (A–Z)** reorder grid (operator-verified 2026-05-20)

### Post-ship UX (same release)

- [x] **Sort** control moved after **Reset** in `.filter-actions`
- [x] **Sort** `change` handler — reapplies inventory without **Filter** click
- [x] Registered cards show `registry_added_at` under title (`.card-registry-date`)

---

## 12. Acceptance criteria

1. [x] `sort` query param changes `/api/inventory` item order without changing filter counts.
2. [x] Omitted or default `sort` → **recent**: registered by `registry_added_at` descending; unregistered last (path ascending in tail).
3. [x] `sort=name` → display name A–Z, then path.
4. [x] Invalid `sort` coerces to `recent` (files + `filters.py`).
5. [x] **Sort** dropdown reapplies on change; **Filter** / **Reset** / URL sync work; `sort=name` in URL round-trips.
6. [x] View PDF / Review Workspace / Copy path unchanged.
7. [x] `files` v0.3.4 + `student_file_browser` v0.1.5 documented; `/api/health` `files_version` is `0.3.4`.

---

## 13. References

- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [files/on_disk_inventory.py](../../../files/on_disk_inventory.py) — `enrich_on_disk_main_pdf`, `filter_main_pdf_cards`
- [files/main_pdfs.py](../../../files/main_pdfs.py) — index path sort (pre-API only)
- [student_file_browser/filters.py](../../filters.py)
- [student_file_browser/serve.py](../../serve.py) — `FILES_VERSION`
- [static/app.js](../../static/app.js) — `buildFilters`, `defaultFilterState`
- [1-root-id-filter.md](./1-root-id-filter.md) — precedent for filter + URL pattern
