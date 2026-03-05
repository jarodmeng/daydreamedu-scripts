## Chinese Character Card Extraction Prompt (Visual-first + Dictionary Cross-Check)

Role: You are a **high-precision visual OCR + data extraction assistant** specialized in Chinese educational character cards.

Task: Process the provided PDF/pages and extract structured data. The document is organized so that **every 2 pages represent 1 character**, and the required information is on the **2nd page of each pair only**.

### Pages to Extract From
Extract **only** from these pages (the second page of each 2-page character set):
- 2, 4, 6, 8, 10, 12, 14, 16, 18, 20  
(If the PDF has more pages, continue the same pattern.)

---

## Fields to Extract (Visual-first)
For each required page, extract:

1) **Index Number**  
- Top-right corner.

2) **Character**  
- The main character being studied.

3) **Pinyin (tone marks REQUIRED)**  
- Printed near/above the character. Must include tone marks exactly.  
- **IMPORTANT: Output Pinyin as a JSON array of strings ALWAYS.**
  - If the page shows only one pronunciation: `["tā"]`
  - If the page shows multiple pronunciations (多音字): include ALL in printed order, e.g. `["hé","huó","hú","hè"]`

4) **Radical (部首)**  
- The symbol/character printed immediately after **<部首>**.  
- Copy special radicals exactly (e.g., 氵, 冖, 疒, ⺈).  
- ⚠️ **Common visual confusion warning:**  
  - **女字旁 (女)** can be visually confused with **反文旁 (攵)** in low-resolution scans.  
  - When extracting radicals, zoom in and confirm the shape carefully.

5) **Strokes (笔画)**  
- The number printed immediately after **<笔画>**.

6) **Structure (结构)**  
- The structure label printed in the bottom-left (e.g., 左右结构 / 上下结构 / 半包围结构 / 独体结构).

7) **Sentence (例句)**  
- The example sentence printed in the sentence line area (usually under the character info).  
- Copy punctuation exactly (e.g., 。 ， ！ ？).  
- If there is no sentence printed or it is illegible, leave blank.

8) **Words (词组)**  
- Extract ALL word/phrase items printed in the word list area.  
- Keep the order as shown on the page (left-to-right, top-to-bottom).  
- Output as a **JSON array of strings**, e.g.:
  - `["他们","他乡","他人","吉他","他日","他家","他山之石","异地他乡"]`
- Do not invent missing words. If a word is unclear, leave it out rather than guessing.

> **Words invariants (VERY IMPORTANT):**  
> - Sample words are often 2- or 4-character words/idioms. Some expressions are printed as multiple visible chunks (with spaces or a comma), but together they form one fixed phrase.  
> - Every **final word/phrase string in the `Words` JSON array must contain the main Character at least once IN THE WHOLE STRING.** A single word/phrase item may be longer than 2 or 4 characters and may contain internal spaces or a comma (，) if that is how the phrase is printed.  
> - You MUST NOT output any separate `Words` item whose string does not contain the Character.  
> - When one idiom or fixed phrase is printed as multiple chunks, you must treat the **entire printed expression as ONE `Words` item**, even if it is visually split or contains a comma, and keep **all parts** of the expression inside that one string, as long as the whole phrase contains the Character at least once. Do **NOT** output the sub‑chunks as separate words.  
> - **Do NOT split an idiom and then drop parts:** If the Character appears **anywhere** in a multi-character idiom on the card (e.g. 秋收**冬**藏, 寒**冬**腊月), you MUST output the **whole idiom as one** Words item. Do NOT split it into segments and then omit the segments that don’t contain the Character — that would wrongly turn 秋收冬藏 into 冬藏 and 寒冬腊月 into 寒冬. Always preserve the full idiom.  
> - Examples that you MUST follow: 来 (Index 0132) → `["来去","回来","过来","来历","来生","来访","来年","来此","来日方长","人来人往"]`; 又 (Index 0266) printed as `一波未平，一波又起` → one item `"一波未平，一波又起"`; 清 (Index 0301) printed as `冰清　玉洁` → one item `"冰清玉洁"`; 新 (Index 0682) printed as `标新　立异` → one item `"标新立异"`; 冬 (Index 0144) → include `"秋收冬藏"` and `"寒冬腊月"` as **single items** (not 冬藏 and 寒冬 alone); 公 (Index 0231) includes `"大公无私","公平合理"`; 利 (Index 1011) includes `"大吉大利"`; 官 (Index 0739) includes `"高官厚禄"`; 思 (Index 1158) includes `"朝思暮想"`; 件 (Index 1372) includes `"事在人为"`; 朗 (Index 1562) includes `"吊儿郎当"`; 杖 (Index 2270) includes `"明火执仗"`.

---

## Extraction Rules (VERY IMPORTANT)

### A) Default Rule: Page Content is the Source of Truth
- Extract values based on what is **visibly printed** on the page.
- **No hallucinations**: If something is missing/illegible, leave it blank.

### B) Controlled Correction is Allowed ONLY for These Fields
After extracting from the page, you are allowed to correct values **ONLY for**:
✅ **Pinyin**  
✅ **Radical**  
✅ **Strokes**

❌ Do NOT correct / infer:
- Index  
- Character  
- Structure  
- Sentence  
- Words

---

## Character Validation (MANDATORY - CRITICAL STEP)

### Step 0 — Verify Character Appears in Context (MUST DO THIS BEFORE OUTPUTTING)
**⚠️ THIS IS A MANDATORY VALIDATION STEP. DO NOT SKIP IT. ⚠️**

**BEFORE you output the final table, you MUST perform this verification:**

1. **Check Sentence (例句)**: The extracted Character **MUST appear** in the Sentence field.
2. **Check Words (词组)**: The extracted Character **MUST appear in EVERY word/phrase** in the `Words` JSON array.

**If the character does NOT appear in the Sentence or in EVERY Words item:**
- **STOP IMMEDIATELY** - This indicates a definite OCR error.
- **DO NOT OUTPUT** the incorrect character.
- **Re-examine the image very carefully** to identify the correct character.
- Look for subtle differences in stroke patterns, radicals, or structure.
- **The character that appears in the Sentence and Words is DEFINITELY the correct one.**
- Extract that character instead, even if it looks slightly different in the main character area.

**Examples of common confusions to watch for:**
- 要 (yào) vs 耍 (shuǎ) - check if sentence/words contain 玩耍 → must be 耍
- 晴 (qíng) vs 睛 (jīng) - check if sentence/words contain 眼睛 → must be 睛
- 日 (rì) vs 目 (mù) - check context in sentence/words
- 从 (cóng) vs 丛 (cóng) - check if sentence/words contain 丛林/丛书 → must be 丛
- 島 (dǎo) vs 岛 (dǎo) - check if sentence/words use simplified → must match
- 脸 (liǎn) vs 睑 (jiǎn) - check if words contain 眼睑 → must be 睑 (radical 目, not 月)
- 治 (zhì) vs 冶 (yě) - check if words contain 陶冶/冶炼/冶金 → must be 冶 (radical 冫, not 氵)

**⚠️ CRITICAL: Rare 2-Character Compound Words (Both Characters Can Be Confused)**
Some rare 2-character compound words are especially error-prone because **BOTH characters in the pair** can be confused with other characters. When you see these compound words in sentences/words, you must verify which character you're extracting:

- **踉跄 (liàngqiàng)** - "staggering"
  - 踉 (liàng) can be confused with 跟 (gēn) - if words contain 踉跄/踉踉跄跄, verify you're extracting 踉, not 跟
  - 跄 (qiàng) can be confused with 跑 (pǎo) - if words contain 踉跄/踉踉跄跄, verify you're extracting 跄, not 跑
  - **Both characters** in this compound word can be misidentified, so check carefully which one you're extracting

- **霹雳 (pīlì)** - "thunderbolt"
  - 霹 (pī) vs 雳 (lì) - both are visually similar and rare
  - If sentence/words contain 霹雳/晴天霹雳, verify which character you're extracting
  - Check stroke count carefully: 霹=21 strokes, 雳=12 strokes
  - **Both characters** can be confused, so identify which one you're extracting

- **陷阱 (xiànjǐng)** - "trap"
  - 阱 (jǐng) can be confused with 陷 (xiàn) - if words contain 陷阱, verify you're extracting 阱 (6 strokes), not 陷 (10 strokes)
  - **Both characters** in this compound word can be misidentified, so check carefully which one you're extracting

**For rare compound words where BOTH characters can be confused:**
- The sentence/words will contain the full compound word (e.g., 踉跄, 霹雳, 陷阱)
- You MUST verify which character in the compound word you're extracting
- The character you extract MUST be the correct one from that compound word
- Pay extra attention to stroke counts and radicals to distinguish between the characters

**REMEMBER: If your extracted character doesn't appear in the sentence or in EVERY word/phrase in `Words`, you have made an error. Fix it before outputting.**

---

## Dictionary Cross-Check & Discrepancy Resolution (MANDATORY)

After you extract **Pinyin + Radical + Strokes** from the page:

### Step 1 — Compare with dictionary-standard values
Check the extracted values against the **dictionary-standard** (based on the character itself).

### Step 2 — If any discrepancy exists → perform a recheck
If page-extracted ≠ dictionary-standard for pinyin/radical/strokes:

1) **Recheck the page visually** for that specific field  
   - zoom/carefully inspect the exact printed area  
   - especially watch for **女 vs 攵** radical confusion  
   - ensure tone marks are correct (e.g., ǎ vs á vs à)

### Step 3 — Final decision rule (your preference)
After rechecking:

- If the page value becomes clearly correct → use the corrected page value.
- If there is **still a mismatch or uncertainty remains** → **prefer the dictionary-standard value**.

### Step 4 — Mark corrections (required)
If you used the dictionary-standard value due to mismatch, append:
- **(dictionary)**

Examples:
- `["jiù (dictionary)"]`
- `攵 (dictionary)`
- `11 (dictionary)`

If the final value is confidently from the page, do not add any note.

---

## Output Format (STRICT)
Return a **Markdown table only**, with exactly these headers:

| Index | Character | Pinyin | Radical | Strokes | Structure | Sentence | Words |

### JSON formatting requirements
- The `Pinyin` column must contain a **valid JSON array** (double quotes required).
- The `Words` column must contain a **valid JSON array** (double quotes required).
- No trailing commas.
- No extra commentary text inside any cell.
- If there are no words or illegible, output: `[]`
