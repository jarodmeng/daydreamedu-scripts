Chinese Learning App

# Project Overview:

The goal of the app is to help Singapore primary school students learn (simplified) Chinese.

The app's functionalities broadly fall into 2 categories.
(1) Utility functions. The use case is reactive and initiated by the user (primary school student) when they have a specific request (e.g. find a character they haven't encountered before; find a character that they know the pinyin but not the tone; understand the meanings of a character; find how to write a character, etc).
(2) Learning functions. The use case is more proactive. The user doesn't use the app as a utility tool like a dictionary, but as a learning facilitator. We envision this part of the functions to be data-driven customized gameified experiences aiming to improving the user's Chinese lanaguage proficiency in the most efficient way.

The app has the following characteristics.
(1) Data-driven. It should have logging of key functions' usage to help analyze their effectiveness. We should also leverage qualitative feedback from users.
(2) Customized. Each logged-in user has their own traking of their activities and learnings. The experiences (especially in the learning functions) should be customized for each logged-in user based on their unique situation (e.g. proficiency, mistake patterns, goals, etc).

# Chinese character data

We started with 3000 冯氏早教识字卡 (Feng) character cards and later added dictionary metadata from 汉文学网 (HWXNet), expanding coverage to the **union** of the 3000 Feng characters and the 3500 level-1 commonly used characters (通用规范汉字一级字表). The app therefore has two data sources that work together.

**1. Feng character cards (3000 characters)**

* There are 3000 folders in `chinese_chr_app/data/png/`. Each folder is named with a `<dddd>` pattern corresponding to the character card index (e.g. "0001", "3000").
* Each folder contains 2 PNG files: `page1.png` (front — full-size character) and `page2.png` (back — detailed info: character, pinyin, radical, strokes, 例句, 词组, 笔顺, 结构).
* Structured card metadata for these 3000 characters is stored in `characters.json` (or, when `USE_DATABASE=true`, in the `feng_characters` table). Location: the app’s `data` folder (e.g. `chinese_chr_app/data`).
* **Fields in Feng / `characters.json` data:**
    * **Index** (string): Card index in `<dddd>` format (e.g. "0001", "3000")
    * **Character** (string): The simplified Chinese character (e.g. "爸", "妈")
    * **Pinyin** (array of strings): Pronunciation(s) with tone marks (e.g. "bà" not "ba")
    * **Radical** (string): Radical component (e.g. "父", "女")
    * **Strokes** (string): Number of strokes (e.g. "8", "6")
    * **Structure** (string): Structural classification (e.g. "左右结构", "上下结构", "半包围结构")
    * **Sentence** (string): Sample sentence (例句); optional, may be empty
    * **Words** (array of strings): Sample words/phrases (词组); optional, may be `[]`

**2. HWXNet dictionary data (union of 3000 Feng + 3500 level-1 → ~3664 unique characters)**

* Dictionary reference data from 汉文学网 is stored in `extracted_characters_hwxnet.json` (or, when `USE_DATABASE=true`, in the `hwxnet_characters` table). Same `data` folder as above.
* HWXNet is the source of truth for dictionary display, radicals list, stroke-counts list, and pinyin search. Characters that are in HWXNet but not in the Feng set have no card images; search still shows dictionary info.
* **Fields in HWXNet data:**
    * **character** (string): The simplified Chinese character
    * **index** (string): Card index in `<dddd>` format when the character is in the Feng set; may be empty for level-1-only characters
    * **分类** (array of strings): Category (e.g. "通用字", "常用字", "次常用字")
    * **拼音** (array of strings): All pronunciations with tone marks (supports breve: ă, ĕ, ŏ, ĭ, ŭ)
    * **部首** (string): Radical (authoritative for dictionary)
    * **总笔画** (integer): Total stroke count
    * **基本字义解释** (array of objects): Meanings and explanations; each entry has **读音**, **释义** (each with **解释**, **例词**)
    * **英文翻译** (array of strings): English translation words
    * **source_url** (string): URL from which the data was extracted

**3. Character stroke data**

The app uses two kinds of stroke-related data: (a) stroke **order** (笔顺) for the HanziWriter animation on the Search page, and (b) **radical stroke counts** for sorting the Radicals page by 按部首笔画.

* **Stroke order (笔顺) for animation**
    * The Search page shows a stroke-order animation (笔顺动画) for the displayed character using [HanziWriter](https://hanziwriter.org/) and data compatible with [Make Me a Hanzi](https://github.com/skishore/makemeahanzi).
    * **Source:** Character stroke-order JSON is fetched from the `hanzi-writer-data` npm package (CDN: jsdelivr or unpkg, version 2.0.1). The app does **not** store this data in Feng or HWXNet; it is loaded on demand.
    * **Backend:** `GET /api/strokes?char=<character>` proxies the JSON from the CDN through the backend. This avoids client-side CORS/CDN issues and allows optional local caching.
    * **Caching:** The backend may cache fetched JSON under `data/temp/hanzi_writer/` (one file per character, keyed by Unicode code point). Cache is best-effort (e.g. ephemeral on Cloud Run).
    * **Optional env:** `HW_STROKES_VERIFY_SSL` — when set to `0`/`false`, the backend skips SSL verification when fetching from the CDN (useful in some dev/CI environments).
    * If the CDN has no data for a character, the animation shows an error (e.g. "无法加载笔顺动画"); the rest of the Search page (card, dictionary) still works.

* **Radical stroke counts (部首笔画数)**
    * Used to sort the Radicals page by radical stroke count (按部首笔画). Each radical is mapped to its stroke count (e.g. 一 → 1, 口 → 3).
    * **Stored:** In the app’s `data` folder as `radical_stroke_counts.json` (format: `{ "一": 1, "口": 3, ... }`). When `USE_DATABASE=true`, the backend uses the `radical_stroke_counts` table as primary source and falls back to this JSON if the DB read fails (e.g. table missing).
    * **Source:** Extracted from 汉文学网 [按部首查字](https://zd.hwxnet.com/bushou.html) via `extract_character_from_wxnet/extract_radical_stroke_counts.py`. The script writes `chinese_chr_app/data/radical_stroke_counts.json`. For DB-backed deployment, create and populate the table once: `python scripts/create_radical_stroke_counts_table.py` (see backend [DATABASE.md](backend/DATABASE.md) and [DEPLOYMENT.md](backend/DEPLOYMENT.md)).

* **Per-character stroke count (笔画数)** — The **number** of strokes for a character (e.g. 8, 6) comes from Feng data (**Strokes**) and HWXNet (**总笔画**), and is used in dictionary display, the 笔画 (stroke-counts) segmentation, and sorting. That is documented in sections 1 and 2 above; no separate stroke-count data store is used.

# Key Features

## Milestone 1: A search function to learn about a particular character
* A website for now. We will build it into a mobile app in future milestones.
* No user profile yet. We will build per-user profiles in future milestones.
* When the website loads, it has a search box in the middle of the page.
* The user can input a simplified Chinese character to search.
    * If the character is found in the 3000 character cards, display page 1 and page 2 of the character card side by side below the search bar.
        * Display the other meta data (extracted from the 冯氏早教识字卡 back-side information) in a **read-only** table below the card png files: 拼音，部首，笔画，例句，词组，结构.
        * Also display meta structured dictionary data in a table: 拼音，部首，总笔画，分类，基本解释，英语
    * If the character is not found, display an error message and ask the user to input a new character.

## Milestone 2: A radicals page to organize characters by radical
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

## Milestone 3: Simplify navigation bar to Search and Segmentation (分类)
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

## Milestone 4: Display stroke order animation
* On the character search page, when a character is found, display a stroke order animation for that character in place of the original page1.png image.
* The stroke order animation:
    * Uses SVG-based rendering to draw each stroke in sequence.
    * Plays automatically once when the character is loaded.
    * Can be replayed by the user via a “重播” button under the animation.
* The stroke order panel and the 字卡 panel are displayed side by side with consistent sizing so that the animation visually matches the layout of the 冯氏字卡背面.
* The stroke order animation is currently implemented as a frontend-only feature (no server-side changes required to generate frames), so it can be iterated on independently of backend deployments.

## Milestone 5: Add a "Num of strokes" (笔画) page in Segmentation (分类)

* Add a new segmentation page: **笔画 (Strokes)**
    * Routes: `/stroke-counts` and `/stroke-counts/:count`
* `/stroke-counts` shows a grid of **stroke counts that exist** (≥1 character), sorted ascending; each tile shows: `N画` + `character_count`.
* `/stroke-counts/:count` shows all characters with that stroke count, sorted by `zibiao_index` (ascending); each card shows: Character + 拼音 + 部首; click navigates to `/?q=<char>`.
* Data source: **HWXNet only** (`extracted_characters_hwxnet.json`) for 总笔画/拼音/部首/`zibiao_index`.
* Backend API:
    * `GET /api/stroke-counts`
    * `GET /api/stroke-counts/<count>`

## Milestone 6: Add pinyin search

* The search box accepts **pinyin** as well as a single Chinese character. One input = one syllable (e.g. "ke", "wo3", "nǐ").
* **Input formats:** Pinyin without tone (e.g. "ke"); pinyin with numeric tone (e.g. "ke3", "ma0" or "ma5" for neutral); or pinyin with tone marks (e.g. nǐ, kě). Invalid if both tone marks and a numeric tone are in the same input.
* **Behavior:** If the user enters exactly one CJK character → character search (existing). Otherwise → pinyin search: show a dedicated results page listing all characters with that reading, **ranked by stroke count** (ascending). Each result shows character, 拼音, 部首, and stroke count; clicking a result opens the character detail view.
* **Errors:** Invalid format → "拼音输入格式错误". Valid pinyin but no matching characters → "未找到该拼音的汉字".
* **Data:** HWXNet only. Match if any of the character’s pinyin readings matches. Route: `/pinyin/:query`. API: `GET /api/pinyin-search?q=<query>`.

---

# Learning Functions: Vision, Goals, and MVP (Milestone 7+)

This section captures the current direction of the product shift toward (2) Learning functions and links to the deeper research + brainstorming paper trail.

## Research + brainstorming paper trail

See: `chinese_chr_app/chinese_chr_app/Learning Functions Research & Brainstorming.md`

## Product vision (learning functions)

Build a **personalized Chinese practice loop** that reliably converts short daily practice into durable gains in:

- Reading (recognition + comprehension)
- Vocabulary (characters → words → sentences)
- Writing (optional but supported via a production pathway)
- Pronunciation/tones (optional module; staged perception → production)

The differentiator is not “more content”, but **better scheduling + feedback + transfer practice** using the content/data we already have.

## Tangible goals (6–12 weeks horizon)

- Establish a daily practice habit with 5–8 minute sessions that kids can complete independently.
- Demonstrate durable retention (not just same-day performance) on a meaningful slice of items.
- Demonstrate transfer in at least one dimension (e.g., radical-based meaning inference in new contexts, or new sentences using previously learned words).

## North-star metric

**Retained items per active learner per week (30-day retention)**.

An item counts as “retained” if the learner answers it correctly on a check that occurs ≥30 days after first introduction (or first “learned” milestone), without hints.

## MVP recommendation (1–2 experiences)

### MVP 1: Daily Micro-Session (5–8 minutes)

A short daily practice session that implements guided retrieval + feedback + spacing. Uses existing Feng/HWXNet data, and can optionally include a micro-write step using stroke-order replay/tracing.

### MVP 2: Graded Micro-Stories (read + optional listen + micro-checks)

Very short leveled stories with tap-to-gloss and lightweight accountability. At least one retrieval prompt per story should feed into the Daily Micro-Session item schedule.