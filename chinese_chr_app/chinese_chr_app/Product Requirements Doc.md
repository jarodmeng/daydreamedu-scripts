Chinese Learning App

Project Overview:

The goal of the app is to help primary school students learn Chinese, esepecially simplied Chinese characters. Each user should have their own profile to track their learnings, progresses, mistakes, and more. The system provides multiple modules of functions.

Skills Required
* Backend server development
* Backend database management
* Frontend user interface development
* System logging

Chinese character data

I have data on 3000 common simplifed chinese character cards.
* There are 3000 folders in the `chinese_chr_app/data/png/` folder. All folders are named using a `<dddd>` pattern. The names correspond to the character cards' index numbers.
* Each `<dddd>` folder has 2 PNG files. `page1.png` is the front of the character card. `page2.png` is the back of the character card.
* The front side of a character card is a full size simplified Chinese character. The back side of the character card contains more detailed information of the simplified Chinese character.
    * The character
    * The pinyin
    * The radical
    * The number of strokes
    * A sample sentence (例句)
    * A few sample words (词组)
    * The order of strokes (笔顺)
    * The structure (结构), e.g. 左右结构，上下结构，半包围结构，etc
* The structured information of all character cards is stored in the `/Users/jarodm/github/jarodmeng/daydreamedu-scripts/chinese_chr_app/data` folder.
    * The `characters.json` file contains the information in a JSON format. This is the primary data format used by the application.
        * The fields of information included in the structured data (currently stored in `characters.json`) are the following:
        * **Index** (string): The character card index number in `<dddd>` format (e.g., "0001", "0002", "3000")
        * **Character** (string): The simplified Chinese character itself (e.g., "爸", "妈")
            * **Pinyin** (array of strings): The pinyin pronunciation(s) of the character.
            * Tone marks are required (e.g., "bà" not "ba")
        * **Radical** (string): The radical component of the character (e.g., "父", "女")
        * **Strokes** (string): The number of strokes required to write the character (e.g., "8", "6")
        * **Structure** (string): The structural classification of the character (e.g., "左右结构", "上下结构", "半包围结构")
        * **Sentence** (string): A sample sentence (例句) that uses the character in context. This field is optional and may be empty for some characters.
            * **Words** (array of strings): Sample words/phrases (词组) that contain the character. This field is optional and may be an empty array `[]` for some characters.
    * We also have structured dictionary data for all 3000 characters in a `extracted_characters_hwxnet.json` file. This file contains dictionary reference data extracted from 汉文学网 (HWXNet) and serves as a source of truth for dictionary-corrected information. The fields included in this structured dictionary data are:
        * **character** (string): The simplified Chinese character itself
        * **index** (string): The character card index number in `<dddd>` format, matching the index from `characters.json`
        * **分类** (array of strings): Character category classification (e.g., "通用字", "常用字", "次常用字")
        * **拼音** (array of strings): All pronunciations of the character with tone marks (supports breve variants: ă, ĕ, ŏ, ĭ, ŭ)
        * **部首** (string): The radical component of the character (used as the authoritative source for radical corrections)
        * **总笔画** (integer): The total number of strokes required to write the character
        * **基本字义解释** (array of objects): Detailed meanings and explanations, with each entry containing:
            * **读音** (string): The pronunciation for this meaning entry
            * **释义** (array of objects): List of meanings, each containing:
                * **解释** (string): The meaning explanation
                * **例词** (array of strings): Example words/phrases that use this meaning
        * **英文翻译** (array of strings): English translation words for the character
        * **source_url** (string): The URL from which the data was extracted

Key Features

Milestone 1: A search function to learn about a particular character
* A website for now. We will build it into a mobile app in future milestones.
* No user profile yet. We will build per-user profiles in future milestones.
* When the website loads, it has a search box in the middle of the page.
* The user can input a simplified Chinese character to search.
    * If the character is found in the 3000 character cards, display page 1 and page 2 of the character card side by side below the search bar.
        * Display the other meta data (extracted from the 冯氏早教识字卡 back-side information) in a **read-only** table below the card png files: 拼音，部首，笔画，例句，词组，结构.
        * Also display meta structured dictionary data in a table: 拼音，部首，总笔画，分类，基本解释，英语
    * If the character is not found, display an error message and ask the user to input a new character.

Milestone 2: A radicals page to organize characters by radical
* A new page named "部首 (Radicals)" accessible from the main search page via navigation links.
* The radicals page displays all unique radicals in a grid layout with clickable boxes.
* Each radical box shows:
    * The radical character displayed in KaiTi (楷体) font
    * The number of characters associated with that radical
* Radicals are sorted by the number of associated characters (descending order), with radicals having more characters appearing first.
* When a user clicks on a radical box, they are directed to a detail page dedicated to that radical.
* The radical detail page shows:
    * All characters associated with the selected radical
    * Each character is displayed in a clickable box showing:
        * The character in KaiTi (楷体) font
        * The pinyin pronunciation(s)
        * The number of strokes
    * Characters are sorted first by number of strokes (ascending), then by pinyin (alphabetically)
    * Clicking on a character box navigates to the search page with that character pre-filled
* Navigation links are available on all pages to switch between the search page and radicals page.
* The radicals data is generated dynamically from `characters.json` on-the-fly and cached in memory for efficient performance, ensuring it stays synchronized with any character edits.

Milestone 3: Simplify navigation bar to Search and Segmentation (分类)
Milestone 2 introduces a segmentation page (部首 / Radicals). Rather than having each segmentation occupy one space in the top navigation bar, we consolidate segmentations into one top-level "Segmentation (分类)" button in the navigation bar (and keep it extensible for future segmentations).

The implemented behavior is:
* The top navigation bar now has two primary items:
    * **Search** – links to the main search page (`/`)
    * **Segmentation (分类)** – acts as a dropdown menu trigger, not a standalone page
* When the user hovers over **Segmentation (分类)** on desktop (or taps it on touch devices), a dropdown menu appears with submenu items:
    * **部首 (Radicals)** – links to the radicals page (`/radicals`)
* The dropdown stays open while the cursor is over the Segmentation button or its menu, so users can reliably click submenu items.
* The active tab is clearly indicated with a darker green background and a black border:
    * **Search** is highlighted when the user is on `/`
    * **Segmentation (分类)** is highlighted when the user is on any segmentation page (currently `/radicals`)
* The navigation bar is implemented via a shared `NavBar` component so that future segmentation types can be added by extending the Segmentation submenu without changing the overall layout.

Milestone 4: Display stroke order animation
* On the character search page, when a character is found, display a stroke order animation for that character in place of the original page1.png image.
* The stroke order animation:
    * Uses SVG-based rendering to draw each stroke in sequence.
    * Plays automatically once when the character is loaded.
    * Can be replayed by the user via a “重播” button under the animation.
* The stroke order panel and the 字卡 panel are displayed side by side with consistent sizing so that the animation visually matches the layout of the 冯氏字卡背面.
* The stroke order animation is currently implemented as a frontend-only feature (no server-side changes required to generate frames), so it can be iterated on independently of backend deployments.

Milestone 5: Add a "Num of strokes" (笔画) page in Segmentation (分类)

* Add a new segmentation page: **笔画 (Strokes)**
    * Routes: `/stroke-counts` and `/stroke-counts/:count`
* `/stroke-counts` shows a grid of **stroke counts that exist** (≥1 character), sorted ascending; each tile shows: `N画` + `character_count`.
* `/stroke-counts/:count` shows all characters with that stroke count, sorted by `zibiao_index` (ascending); each card shows: Character + 拼音 + 部首; click navigates to `/?q=<char>`.
* Data source: **HWXNet only** (`extracted_characters_hwxnet.json`) for 总笔画/拼音/部首/`zibiao_index`.
* Backend API:
    * `GET /api/stroke-counts`
    * `GET /api/stroke-counts/<count>`

Milestone 6: Add pinyin search

Allow pinyin in search box. User is supposed to enter pinyin for 1 character. The format of the pinyin can be pinyin without tone (e.g. "ke") or pinyin with numeric tone (e.g. "ke3" to indicate 3rd tone and "ma0" to indicate no tone). If the pinyin input is valud, find all characters that have the pinyin and display them in a page ranked by their stroke count. If the pinyin input isn't found, display a message saying in Chinese that it's not found.

**Decisions (from proposal Q&A):**
* **2.1** Single search box: if input is exactly one CJK character → character search; otherwise → pinyin search (Option A).
* **2.2** Accept `5` for neutral tone in addition to `0`. Accept tone marks (e.g. nǐ, kě) as input. Invalid if both tone marks and numeric tone are provided.
* **2.3** Differentiate errors: invalid format vs pinyin not found (different Chinese messages).
* **2.4** Dedicated route for pinyin results. Each result card shows: character + pinyin + radical (部首) + stroke count.
* **2.5** Data source: HWXNet only. Ranking: ascending by stroke count.
* **3.1** Add a searchable column (see below): maps 拼音 to the format the search accepts; ü normalized to v.
* **3.2** Malformed/unsupported format → Chinese message e.g. "拼音输入格式错误".
* **3.3** Match if any of the character's pinyin readings matches.
* **Confirmed:** Column name is **searchable_pinyin** (normalized from 拼音). Error strings: "拼音输入格式错误" (invalid format), "未找到该拼音的汉字" (no match). Secondary sort: **zibiao_index** ascending when stroke count ties.

---

**Milestone 6: Implementation Plan (no execution)**

**1. Searchable pinyin column (database)**

* **1.1 Script:** Create a one-off (or migration) script that: **(Done)** — `backend/scripts/add_searchable_pinyin_column.py`: adds `searchable_pinyin` column, backfills from `pinyin` (normalize ü→v, base + tone). Supports `--no-backup`, `--skip-filled`.
  * Adds a column to the `hwxnet_characters` table: e.g. `searchable_pinyin jsonb` (or `text[]`). Type choice: JSONB array of strings allows `?|` containment in Postgres for "any of these keys match".
  * For each row, read the existing `pinyin` (JSONB array of strings like `["bà", "wŏ"]`).
  * For each pinyin string in that array:
    * Normalize: strip tone marks → base syllable; map ü → v (and accept u where context is ü); derive tone number (1–4, or 0/5 for neutral).
    * Produce searchable forms: `base` (e.g. "ba", "wo") and `base + str(tone)` for the specific tone (e.g. "ba4", "wo3"). For neutral, produce both "ma0" and "ma5".
  * Store in the column the list of all such strings for that character (e.g. for 我 with 拼音 ["wŏ"] → ["wo", "wo3"]). One character can have multiple readings (e.g. 长 → "chang"/"chang2" and "zhang"/"zhang3"); union all searchable forms, no duplicates.
* **1.2 Index:** Add a GIN index on `searchable_pinyin` for fast containment queries. **(Done)** — `idx_hwxnet_searchable_pinyin` created; script also runs this after backfill.
* **1.3 Backfill:** Script runs once to backfill existing rows; optionally support re-run to refresh from current `pinyin` (e.g. after data fixes). **(Done)** — covered by 1.1 script; use `--skip-filled` to only fill NULL rows.

**2. Pinyin normalization (shared logic)** **(Done)** — `backend/pinyin_search.py`: `parse_pinyin_query`, tone-mark/numeric/no-tone, invalid if both; `compute_searchable_pinyin_for_entry` for in-memory index.

* **2.1 Input parsing (user query):**
  * Input must be a single syllable (no spaces; reject multiple syllables or invalid chars).
  * **Tone marks vs numeric:** If the string contains any Unicode tone mark (e.g. ā á ǎ à, ē é ě è, … ŭ) then it is "tone-mark form". If it contains a trailing digit 0–5, it is "numeric form". If both tone marks and a trailing digit appear → invalid, return "拼音输入格式错误".
  * **Tone-mark form:** Normalize to base (strip diacritics, ü/ǖ/ǘ/ǚ/ǜ → v) and derive tone 1–4 or neutral; produce a single search key: `base + str(tone)` (neutral → "0" or "5", pick one consistently for lookup).
  * **Numeric form:** Parse trailing 0–5 (0 and 5 = neutral); rest of string is base; normalize ü → v; produce key `base + str(tone)` (e.g. "ke3" → "ke3", "ma0" → "ma0").
  * **No tone:** Only base syllable (e.g. "ke", "lv"). Normalize ü → v. For lookup, match any character whose `searchable_pinyin` contains `base` OR any of `base+"1"`, `base+"2"`, `base+"3"`, `base+"4"`, `base+"0"`, `base+"5"` (i.e. any tone variant).
* **2.2 Stored pinyin (HWXNet 拼音):** Same normalization for DB/stored data: from "cháng" → base "chang", tone 2 → store "chang", "chang2". Support breve variants (ă ĕ ŏ ĭ ŭ) as equivalent to ā é ǒ ī ū for tone derivation. ü and ǖ/ǘ/ǚ/ǜ → v in base.

**3. Backend API** **(Done)** — `GET /api/pinyin-search?q=<query>` in `app.py`; uses DB when USE_DATABASE else in-memory; 400/200 responses per plan.

* **3.1 Endpoint:** Add `GET /api/pinyin-search?q=<query>` (or `GET /api/pinyin-search/<query>`). Do not overload `GET /api/characters/search` so that character search and pinyin search remain clearly separated and response shapes stay simple.
* **3.2 Behavior:**
  * Parse `q` with the shared input parser.
  * If invalid (mixed tone mark + digit, or malformed syllable, or empty) → 400 with `{ "error": "拼音输入格式错误" }`.
  * If valid:
    * **When USE_DATABASE=true:** Query `hwxnet_characters` where `searchable_pinyin` contains the resolved key (for no-tone query: WHERE searchable_pinyin ?| array[base, base||'1', base||'2', …]; for tone-specific: WHERE searchable_pinyin ?| array[base||digit]). Select columns needed for list: character, 部首, 拼音, 总笔画, zibiao_index (and index if needed). Sort by 总笔画 ASC, then zibiao_index ASC. Deduplicate by character (one row per character).
  * **When USE_DATABASE=false:** Use in-memory HWXNet data: build the same searchable key set per character in code (or build a one-time in-memory index: map search_key → list of character entries). Look up and return same shape. Sort by 总笔画 ascending, then zibiao_index.
* **3.3 Response:**
  * Success with results: `200` + `{ "found": true, "query": "<query>", "characters": [ { "character", "pinyin", "radical" (部首), "strokes" (总笔画), "zibiao_index", "index" } ] }`.
  * Valid query but no match: `200` + `{ "found": false, "query": "<query>", "error": "未找到该拼音的汉字", "characters": [] }`.
  * Invalid format: `400` + `{ "error": "拼音输入格式错误" }`.

**4. Frontend** **(Done)** — `PinyinResults.jsx` + route `/pinyin/:query`; Search.jsx: single CJK → character search, else redirect to `/pinyin/:query`; placeholder updated.

* **4.1 Search page (existing, `/`):**
  * On submit: read trimmed input. If exactly one CJK character (e.g. `\u4e00`–`\u9fff`) → current character search: `GET /api/characters/search?q=<char>`, show single-character result.
  * Otherwise → treat as pinyin: redirect to dedicated pinyin results route with query in URL (e.g. `/pinyin/ke3` or `/pinyin?q=ke3`).
* **4.2 Dedicated route (Option B):** Add route `/pinyin/:query` or `/pinyin?q=...` (recommend path param so one URL = one pinyin result: `/pinyin/ke3`).
  * Page loads: read query from URL, call `GET /api/pinyin-search?q=<query>`.
  * If 400: show "拼音输入格式错误".
  * If 200 and `found === false`: show "未找到该拼音的汉字".
  * If 200 and `found === true`: show list of cards; each card shows **character + pinyin + radical (部首) + stroke count**; sorted ascending by stroke count (backend already sorts). Each card links to `/?q=<character>` so clicking opens the existing character detail view.
* **4.3 Navigation:** From Search page, user can type pinyin and submit → redirect to pinyin result page. No need for a separate nav item for "pinyin search" unless you want one; the single search box suffices.
* **4.4 Placeholder:** Consider placeholder text like "输入汉字或拼音（如 ke 或 ke3）" on the search input.

**5. Database layer (when USE_DATABASE=true)** **(Done)** — `database.get_characters_by_pinyin_search_keys(search_keys)`; GIN index; sort 总笔画 ASC, zibiao_index ASC; dedupe by character.

* **5.1** Extend `database.py`: add function e.g. `get_characters_by_pinyin_search_key(search_key: str)` (and for no-tone, a variant that accepts multiple keys or a single base) that queries `hwxnet_characters` by `searchable_pinyin` and returns list of dicts with character, 部首, 拼音, 总笔画, zibiao_index, index (same shape as needed by API). Use the new column and GIN index. Sort results by 总笔画 ASC, then zibiao_index ASC.
* **5.2** For "no tone" search (user entered "ke"), either: (a) call DB with multiple keys (base, base+1, base+2, base+3, base+4, base+0, base+5) and merge/deduplicate by character, then sort by 总笔画 ASC, then zibiao_index ASC; or (b) use a single containment check if Postgres supports "any of these keys" (e.g. `?|` with array of keys).

**6. Test plan (Playwright E2E + backend API)** **(Done)** — `frontend/e2e/pinyin-search.spec.js` (search→pinyin redirect, CJK stays, results page, no match, invalid format, placeholder); `backend/tests/test_pinyin_search.py` (tone/no-tone, no match, invalid, empty).

Use the existing Playwright E2E setup (`frontend/e2e/`, `playwright.config.js`, `npm run test:e2e`) and backend API tests (`backend/tests/test_api.py`) where applicable. Do not add or run tests until explicit permission is given; this section only specifies what to implement.

* **6.1 E2E: Search box → pinyin → dedicated pinyin results route**
  * From the Search page (`/`), type a pinyin query (e.g. `ke3` or `ma`) in the search input and submit. Expect redirect to the pinyin results route (e.g. `/pinyin/ke3` or `/pinyin?q=ke3`). Assert URL and that the pinyin results view is shown (not the single-character view).
  * From the Search page, type a single Chinese character and submit. Expect no redirect to pinyin; stay on `/` with `?q=<char>` and show single-character result (existing behavior). Ensures the heuristic (one CJK char = character search) is not broken.

* **6.2 E2E: Pinyin results page — success**
  * Navigate directly to a pinyin results URL for a query that returns at least one character (e.g. `/pinyin/wo3` for 我, or a syllable known to exist in HWXNet). Expect: page shows a list of result cards; each card displays character, pinyin, 部首, and stroke count; results are ordered by stroke count ascending. Optionally assert presence of a known character (e.g. 我 for `wo3`).
  * On the same page, click one result card. Expect navigation to `/?q=<character>` and the single-character detail view (笔顺动画, 字典信息, etc.). Reuse existing stroke fixture routing in E2E if needed so 笔顺 loads.

* **6.3 E2E: Pinyin results page — no match**
  * Navigate to a pinyin results URL for a valid syllable that has no characters in the dataset (or a synthetic query that the backend returns as `found: false`). Expect the page shows the message "未找到该拼音的汉字" and no result cards (or empty list).

* **6.4 E2E: Pinyin results page — invalid format**
  * Navigate to a pinyin results URL that triggers invalid-format (e.g. mixed tone mark and digit, or malformed syllable). Expect the page shows "拼音输入格式错误" (or the backend returns 400 and the frontend displays that message).

* **6.5 E2E: Placeholder and accessibility**
  * On the Search page, assert the search input placeholder text indicates pinyin is supported (e.g. "输入汉字或拼音（如 ke 或 ke3）"). If the pinyin results page or cards use `data-testid` for stability, add minimal assertions using `getByTestId` where it matches existing project style (e.g. `data-testid="pinyin-result-card"` or `data-testid="pinyin-no-results"`).

* **6.6 Backend API tests (optional but recommended)**
  * In `backend/tests/test_api.py` (or a dedicated `test_pinyin_search.py`): call `GET /api/pinyin-search?q=...` for: (a) a valid tone-specific query that returns characters — assert 200, `found: true`, `characters` array, and sort order (总笔画 ASC, then zibiao_index ASC); (b) a valid no-tone query — assert 200 and at least one character when the syllable exists; (c) valid query with no match — assert 200, `found: false`, `error`: "未找到该拼音的汉字"; (d) invalid format (e.g. mixed tone mark and digit) — assert 400, `error`: "拼音输入格式错误". Use the same test backend/data as existing API tests (JSON or test DB per project setup).