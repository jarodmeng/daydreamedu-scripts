# Proposal: Radicals Page — Sort by Radical Stroke Count

Use the **database table** `radical_stroke_counts` as the primary source for radical→stroke_count, with **JSON file** `radical_stroke_counts.json` as backup when DB is disabled or unavailable. No execution until you approve.

---

## 1. Data source strategy

| Condition | Source |
|-----------|--------|
| `USE_DATABASE=true` and DB connection succeeds | Read from Supabase table `radical_stroke_counts` |
| `USE_DATABASE=false` | Read from `DATA_DIR / "radical_stroke_counts.json"` |
| `USE_DATABASE=true` but DB read fails (e.g. table missing, connection error) | Fall back to JSON file; log warning |

Result: a single **in-memory mapping** `Dict[str, int]` (radical → stroke_count) used when building the radicals API response. Loaded once at startup (or on first `/api/radicals` request) and cached, consistent with `load_radicals()` / `load_hwxnet()`.

---

## 2. Backend changes

### 2.1 `database.py`

- **New function:** `get_radical_stroke_counts() -> Dict[str, int]`
  - Query: `SELECT radical, stroke_count FROM radical_stroke_counts`
  - Return dict: `{ "一": 1, "口": 3, "木": 4, ... }`
  - On exception (e.g. table does not exist, connection error): re-raise so caller can fall back to JSON

### 2.2 `app.py`

- **Path:** Reuse existing `DATA_DIR`; add constant  
  `RADICAL_STROKE_JSON = DATA_DIR / "radical_stroke_counts.json"`  
  (same `DATA_DIR` as `characters.json`; in container this is `/app/data` if set via env).

- **Loader:** `load_radical_stroke_counts() -> Dict[str, int]`
  - If `USE_DATABASE`:
    - Try `database.get_radical_stroke_counts()`; on success return result.
    - On failure: log warning, fall back to JSON.
  - If not `USE_DATABASE`: load from `RADICAL_STROKE_JSON` (read once, return dict).
  - If JSON missing or invalid: return `{}` and log warning (radicals will have no stroke count; sort-by-stroke still works, unknowns sort last).

- **When to call:** On startup, after `load_radicals()` (or in same startup block). Store in a module-level variable, e.g. `radical_stroke_counts_map = None`; set on first load so `/api/radicals` can use it without opening DB on every request if you prefer lazy load, or populate at startup for consistency with other data.

- **`GET /api/radicals`**  
  - **Query param:** `sort` — `character_count` (default) | `stroke_count`  
  - **Response shape (each item):**  
    `{ "radical": "口", "character_count": 194, "radical_stroke_count": 3 }`  
    - `radical_stroke_count` may be `null` if not in mapping (e.g. unknown radical).  
  - **Sorting:**  
    - `sort=character_count`: current behavior — by `character_count` descending.  
    - `sort=stroke_count`: by `radical_stroke_count` ascending; radicals with `null` sorted last (then optionally by `character_count` or `radical` for stable order).  
  - Implementation: after building `radicals_with_count`, look up each `entry['radical']` in `load_radical_stroke_counts()` result (or cached map), set `radical_stroke_count`; then sort by the chosen key.

No new API routes; only `/api/radicals` extended.

---

## 3. Frontend changes

- **`Radicals.jsx`**
  - **State:** Add `sortBy: 'character_count' | 'stroke_count'` (default `'character_count'`).
  - **Fetch:** Call `/api/radicals?sort=character_count` or `/api/radicals?sort=stroke_count` according to `sortBy` (e.g. in `useEffect` when `sortBy` changes).
  - **UI:** Add a sort control near the subtitle (e.g. toggle or dropdown): “按字数” / “按部首笔画”. On change, set `sortBy` and re-fetch.
  - **Display (optional):** When `sortBy === 'stroke_count'`, show “X画” under the radical (from `radical_stroke_count`). If `radical_stroke_count == null`, show “—” or omit.

- **`Radicals.css`**  
  - Styles for the sort control and, if you show it, the stroke-count line (e.g. “3画”) on each card.

---

## 4. JSON file as backup

- **Location:** `DATA_DIR / "radical_stroke_counts.json"` — i.e. `chinese_chr_app/data/radical_stroke_counts.json` in repo; in container, same as other data (e.g. `/app/data` if `DATA_DIR` points there).
- **Format:** Existing format: `{ "一": 1, "口": 3, ... }`.
- **When used:**  
  - Always when `USE_DATABASE` is false.  
  - When `USE_DATABASE` is true but `get_radical_stroke_counts()` fails (table missing, connection error, etc.).
- **Deployment:** Keep the JSON file in the repo and in the image (e.g. COPY in Dockerfile like other data files) so the backup is always available. No need to remove it when using DB.

---

## 5. Edge cases

| Case | Behavior |
|------|----------|
| Radical not in mapping (DB or JSON) | `radical_stroke_count: null` in response; when sorting by stroke, put these last. |
| Empty mapping (JSON missing + DB disabled or failed) | All radicals have `radical_stroke_count: null`; sort-by-stroke still works (all tied at end). |
| Table not yet created in Supabase | DB read fails → fall back to JSON; log warning. |
| Invalid JSON / corrupt file | Treat as empty dict; log warning. |

---

## 6. Summary

- **Primary:** Supabase table `radical_stroke_counts` when `USE_DATABASE=true` and DB read succeeds.
- **Backup:** `radical_stroke_counts.json` when DB is off or DB read fails.
- **API:** `GET /api/radicals?sort=character_count|stroke_count`; each item includes `radical_stroke_count` (int or null).
- **Frontend:** Sort control (“按字数” / “按部首笔画”); optional “X画” on cards when sorting by stroke.

No execution until you give permission.
