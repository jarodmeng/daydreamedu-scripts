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
        * **custom_id** (string): The character card index number in `<dddd>` format (e.g., "0001", "0002", "3000")
        * **Index** (string): The character card index number, same as custom_id
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
        * Display the other meta data (extracted from the 冯氏早教识字卡 back-side information) in a table below the card png files: 拼音，部首，笔画，例句，词组，结构.
            * Make the table cells editable. The user can double click the cell to edit it and press enter to complete the edit. If the edited value is different from the stored data, prompt a dialog to ask the user if they indeed want the information changed. If they click yes, edit the stored data. We should also log every change in a logging file.
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
