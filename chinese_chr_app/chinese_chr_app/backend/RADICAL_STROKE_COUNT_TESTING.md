# Testing Plan: Radicals Page — Sort by Radical Stroke Count

Covers backend, frontend, E2E, and edge cases for the radical stroke count feature (DB + JSON fallback, sort param, optional “X画” display). Run tests after implementation.

---

## 1. Backend

### 1.1 Radical stroke count loader (`load_radical_stroke_counts`)

| Test | Description | How |
|------|-------------|-----|
| **DB primary** | When `USE_DATABASE=true` and DB is reachable, loader returns dict from `radical_stroke_counts` table. | Unit: mock or real DB; call loader; assert dict has expected keys (e.g. "口" → 3, "木" → 4) and size ≈ 267. |
| **JSON fallback (no DB)** | When `USE_DATABASE=false`, loader reads `RADICAL_STROKE_JSON` and returns same shape. | Unit: set `USE_DATABASE=false`, ensure `DATA_DIR/radical_stroke_counts.json` exists; call loader; assert dict non-empty and sample entries match JSON. |
| **JSON fallback (DB failure)** | When `USE_DATABASE=true` but DB read fails (e.g. wrong URL, table missing), loader falls back to JSON and logs warning. | Unit/integration: force DB failure (bad URL or mock exception); call loader; assert return is from JSON (or non-empty) and warning logged. |
| **Empty/invalid JSON** | When JSON missing or invalid, loader returns `{}` and logs warning; app does not crash. | Unit: temporarily use missing path or invalid JSON; assert return `{}`. |

### 1.2 API `GET /api/radicals`

| Test | Description | How |
|------|-------------|-----|
| **Default sort** | No `sort` or `sort=character_count`: response sorted by `character_count` descending; items have `radical`, `character_count`, `radical_stroke_count` (int or null). | Integration: `GET /api/radicals` and `GET /api/radicals?sort=character_count`; assert order by `character_count` desc; assert each item has `radical_stroke_count`. |
| **Sort by stroke** | `sort=stroke_count`: response sorted by `radical_stroke_count` ascending; nulls last. | Integration: `GET /api/radicals?sort=stroke_count`; assert order by `radical_stroke_count` asc; assert any nulls at end. |
| **Response shape** | Each radical object: `{ radical, character_count, radical_stroke_count }`; totals unchanged. | Assert `total_radicals`, `total_characters` same for both sort values; assert all items have the three keys. |
| **Unknown radical** | If a radical is not in mapping, `radical_stroke_count` is null; when sorting by stroke, it appears in the “nulls last” group. | Optional: inject a radical not in DB/JSON (e.g. test-only data); assert null and position when `sort=stroke_count`. |

### 1.3 Database layer (`database.get_radical_stroke_counts`)

| Test | Description | How |
|------|-------------|-----|
| **Returns dict** | Function returns `Dict[str, int]`; keys are radicals, values are stroke counts. | With real DB: call `get_radical_stroke_counts()`; assert type and sample (e.g. "一" → 1, "口" → 3). |
| **Raises on failure** | On connection/query error, function raises so caller can fall back. | Mock connection to raise; assert exception propagates. |

---

## 2. Frontend

### 2.1 Radicals page

| Test | Description | How |
|------|-------------|-----|
| **Sort control visible** | User sees “按字数” / “按部首笔画” (or chosen labels). | E2E or component test: go to `/radicals`; assert sort control is visible. |
| **Default fetch** | On load, page fetches `/api/radicals` (no param or `sort=character_count`) and shows radicals. | E2E: assert count text (e.g. “共224个部首”) and grid of radical boxes. |
| **Switch to stroke sort** | Selecting “按部首笔画” fetches `/api/radicals?sort=stroke_count` and re-renders. | E2E: click “按部首笔画”; assert request has `?sort=stroke_count` (network or URL); assert order changes (e.g. first card has fewer strokes than when sorted by count). |
| **Optional: stroke display** | When sort is “按部首笔画”, cards show “X画” where `radical_stroke_count` is set. | E2E or visual: assert at least one card shows “N画” (e.g. “3画” for 口). |
| **Click radical** | Clicking a card still navigates to `/radicals/:radical`. | E2E: click first radical; assert URL and detail content. |

### 2.2 Regression

| Test | Description | How |
|------|-------------|-----|
| **Existing E2E** | Current core flow (e.g. `core.spec.js`: go to `/radicals`, see “共224个部首”, click 口, see detail) still passes. | Run existing E2E; update only if count/labels change (e.g. 224 → same or documented). |

---

## 3. E2E (Playwright)

Suggested additions or adjustments to `frontend/e2e/`:

| Test | Description |
|------|-------------|
| **Radicals default sort** | Go to `/radicals`; expect heading “部首”; expect “共224个部首” (or current count); expect grid; optional: first card has high character count (e.g. 口 194字). |
| **Radicals sort by stroke** | Go to `/radicals`; click “按部首笔画”; expect list to re-fetch; expect first few cards to have low stroke count (e.g. 一, 丨) or “1画”/“2画” if displayed. |
| **Radicals detail unchanged** | From `/radicals`, click a radical; expect `/radicals/口` (or similar); expect “部首: 口” and character list; back to list still works. |

Keep existing assertions in `core.spec.js` (e.g. “共224个部首”, click 口, dictionary radical link); add new ones for sort control and, if implemented, “X画” display.

---

## 4. Edge cases and manual checks

| Scenario | Expected | How to verify |
|----------|----------|----------------|
| All radicals in mapping | No nulls in response (or very few if test data has unknowns). | Run `check_radicals_missing_stroke_count.py`; already confirmed “all exist”. |
| JSON missing, DB disabled | Loader returns `{}`; radicals list still works; all `radical_stroke_count` null; sort by stroke still works (all at end). | Temporarily rename JSON; set `USE_DATABASE=false`; load Radicals page; switch to stroke sort. |
| DB table missing, USE_DATABASE=true | Loader falls back to JSON; warning in logs; API returns data with stroke counts from JSON. | Point to a DB without the table (or drop table in dev); restart backend; call `/api/radicals?sort=stroke_count`. |
| Invalid `sort` param | Ignore or treat as default (`character_count`); no 500. | `GET /api/radicals?sort=invalid`; assert 200 and default order. |

---

## 5. Test implementation options

- **Backend:** Add a small test module (e.g. `tests/test_radical_stroke_count.py`) with pytest or script-style tests for `load_radical_stroke_counts` and `get_radicals` (with test client). Use mocks for DB/JSON when possible; optional real DB for integration.
- **Frontend:** Rely on E2E for full flow; optional unit tests for sort state and fetch URL builder.
- **E2E:** Extend `core.spec.js` or add `radicals-sort.spec.js` with the scenarios in §3.

---

## 6. Summary

| Area | Focus |
|------|--------|
| **Backend** | Loader (DB vs JSON fallback), API sort param, response shape, null handling. |
| **Frontend** | Sort control, fetch with `sort`, optional “X画”, no regression on detail navigation. |
| **E2E** | Default and stroke sort on Radicals page; existing radical/detail flow still passes. |
| **Edge** | Missing JSON, missing DB table, invalid `sort`; manual or one-off script checks. |

Run backend tests from `backend/`; E2E from `frontend/` with app and backend running (or against deployed env).
