# AI Study Buddy — Ingestion Pipeline: Implementation Proposal

> Status: **Proposal** — detailed plan for the first component to build.
>
> Parent docs: [ARCHITECTURE](./L1_ARCHITECTURE.md) (Ingestion Pipeline component), [DATA_STRATEGY](./L3_DATA_STRATEGY.md) (question objects, storage tiers, OCR strategy).

---

## Why This Is First

The entire system depends on structured data from worksheets. The Skill Graph, Student Model, Diagnostic Engine, and Planner all consume question objects. Without the ingestion pipeline, there is nothing to analyze, no mastery to compute, and no plan to generate.

The goal for Phase 1 is not full automation. It's: **get Winston's backlog of scored worksheets into the system as structured, skill-tagged question objects, fast enough to be useful before PSLE.**

---

## What We Have

- **~4,000 pages** of scanned worksheets across 5 subjects (Math, English, Science, Chinese, Higher Chinese), with handwritten workings and teacher markings/scores. Growing ~500 pages/month.
- PDFs live in **Google Drive** (canonical store).
- Most PDFs are **scanned** (image-only, zero extractable text). Some may be digital.
- Mix of scored papers (with teacher marks) and blank/practice papers.
- No consistent naming convention or folder structure assumed.

---

## What the Worksheets Actually Look Like

Based on real samples across all four subjects — from Winston's P5 and P6 exams and weighted assessments at St. Gabriel's Primary School.

### Math paper (8 pages, 40 marks)

**Structure:** Section A (Q1–Q10, 2 marks each, 20 marks) + Section B (Q11–Q15, multi-part, variable marks per sub-part in parentheses, 20 marks). All free-response with working space and "Ans:" lines.

**Four visual layers on every page:**

| Layer | Color | What it contains |
|-------|-------|-----------------|
| Printed text | Black | Question text, section headers, "Ans:" lines, mark allocations, horizontal separators |
| Child's workings | Pencil / black pen | Equations, model drawings, bar diagrams, long division — often sprawling across the page |
| Teacher's marks | Red ink | Ticks (✓), crosses (✗), crossed-out wrong answers, corrected answers, score boxes, method marks ("✓m") |
| Correction workings | Green ink | Reworked solutions (done during review session with Jarod) — only on questions Winston got wrong |

**Key structural signals:** Question numbers ("1.", "2."), sub-part labels ("a)", "(b)"), "Ans:" lines for every answer, horizontal ruled lines between questions, per-page score boxes at bottom-right (earned/available, e.g. "4/6"), mark allocation in parentheses for Section B ("(1)", "(2)", "(3)"), total score circled in red on page 1, school name header on every page.

**Visual complexity:** Heavy handwriting — every question has working out. Model drawings (bar models, unit diagrams) on nearly every Section B word problem. Teacher corrections overwrite student answers in red. Method marks ("✓m") for partial credit in Section B. Handwritten workings overlap with printed text.

### Science paper (16 pages, 40 marks)

**Structure:** Booklet A / MCQ (Q1–Q12, 2 marks each, 24 marks) + Booklet B / Open-ended (Q13–Q16, variable marks per sub-part in square brackets, 16 marks). MCQ answers shaded on a separate **Optical Answer Sheet (OAS)** — the last page.

**Cover page metadata is richer:** Shows section-level breakdown ("BA: 24/24 ★", "BB: 13/16"), percentage ("93%"), and Achievement Level ("AL1") in addition to total marks (37/40).

**MCQ section (Booklet A) is fundamentally different from Math:**

- Each MCQ takes nearly a full page because of large **printed diagrams** — experiment setups (beakers, plants, circuits), line graphs, bar charts, flow charts, data tables. These are integral to the question, not student-drawn.
- Answers are a single number (1–4), shaded on the OAS and also written in parentheses on the question page.
- **Minimal handwriting.** Winston's annotations are conceptual notes, not calculations: "changed var", "measured var", "rate of photosynthesis", "highest point", "displacement method". These are analytical thinking traces.
- **No per-page score boxes** on MCQ pages. Scoring is via the OAS (red ticks next to correct answers) and the aggregate "BA: 24/24" on the cover.

**OAS page (Optical Answer Sheet):**

- Grid of numbered ovals (1–60, only 1–12 used). Winston shaded his chosen oval in pencil.
- Red ticks next to correct answers mark which ones are right.
- This is an **OMR (Optical Mark Recognition)** task — highly structured, should be easy for a vision LLM to read all 12 answers in a single call.

**Open-ended section (Booklet B) is more similar to Math:**

- Multi-part questions with sub-parts (a), (b), (c). Mark allocation in square brackets: [1], [2].
- Answers are **full sentences**, not numbers: *"the number of bubbles produced stayed the same at 50. Because, when there is roughly 15g of baking soda, there is alot of carbon dioxide and the rate of photosynthesis is already at its fastest."*
- Teacher marks as small red numbers (marks awarded) next to each sub-part's bracket — different from Math's ticks/crosses.
- Teacher annotations in green/red on specific phrases in the written answer (underlining, inserting corrections).
- **Per-page score boxes** at bottom-right, same format as Math (e.g. "4/4", "3/4").

### English papers (40 pages across 2 papers, 140 marks total)

English is split across two separate exam papers — the pipeline must link them as one exam.

**Paper 1 (Writing, 14 pages, 50 marks):** Only 2 "questions" in the entire paper:

- **Situational Writing** (14 marks) — comic strip prompt with 5 numbered panels + task instructions (write an email). Answer is a one-page handwritten email on a dedicated answer sheet. Scoring is **rubric-based**: Task Fulfillment (6) + Language & Organisation (8) = 14. Teacher circles content points ①–⑥ in the essay body to show which bullet points were addressed.
- **Continuous Writing** (36 marks) — topic + picture prompts → multi-page handwritten composition (150+ words). **Holistic scoring** out of 36 (likely sub-dimensions like Content, Language, Organisation, but only a single total shown). Teacher corrections throughout: spelling, grammar, word choice in colored ink. Answer spans 4–6 handwritten pages on lined paper.

Many blank pages and transition pages. Composition answer pages are on lined paper (different physical format from the printed exam).

**Paper 2 (Language Use & Comprehension, 26 pages, 90 marks):** Two physical booklets in one PDF:

**Booklet A (MCQ, OAS, 25 marks):** Sections A–D. Answers shaded on OAS. Winston also wrote chosen numbers in parentheses on booklet pages. **OAS page may not be in the scanned PDF** — the pipeline must handle this.

| Section | Format | Example |
|---------|--------|---------|
| A: Grammar | MCQ (4 options), fill-in-blank sentence | "The notebook on the table \_\_\_ to Benjamin." → (2) belongs |
| B: Vocabulary | MCQ (4 options), choose word closest in meaning | Contextual vocabulary |
| C: Vocabulary Cloze | Passage with blanks, choose from word bank | Similar to Grammar Cloze but vocabulary-focused |
| D: Comprehension (Visual Text) | MCQ based on a visual text (poster, flyer, etc.) | Read visual text, answer 5 MCQ |

**Booklet B (Written answers, 65 marks):** Sections E–I — five distinct question formats:

| Section | Format | Example |
|---------|--------|---------|
| E: Grammar Cloze | Passage with numbered blanks, choose from word bank | Write letter "(A)", "(P)" in blank |
| F: Editing | Passage with underlined errors, write correction in numbered box | "rekoniced" → "recognised" |
| G: Comprehension Cloze | Passage with blanks, write one free word per blank | Context-dependent vocabulary |
| H: Synthesis/Transformation | Rewrite sentence preserving meaning, given a starting word | Grammar transformation |
| I: Comprehension OE | Read passage, answer numbered questions with written explanations | [1m], [2m] mark allocations |

**Cover page is a pre-built diagnostic:** Lists every section with skill type and Winston's score — the richest cover page metadata of any subject.

**Teacher qualitative feedback** is unique to English. On comprehension answers, the teacher wrote: "too general", "be more specific", "use evidence from the text". This is direct pedagogical feedback that tells us exactly what skill dimension needs improvement — far more useful than a raw score.

**Comprehension passage** (Section I) is a shared reference for questions 66–75. Winston annotated the passage with reading strategies: underlining key phrases, noting "female caregiver/motherly", "rehab: recover". These annotations are valuable evidence of close reading skill.

### Chinese papers (35 pages across 3 PDFs, 130 marks total)

Chinese is split across **three separate exam PDFs** — the most documents of any subject.

**Paper 1 (试卷一, Writing, 8 pages, 40 marks):** One composition task.

- Written on **grid paper (方格纸)** — one Chinese character per cell, with character-count markers every 60 characters (at 60, 120, 180, 240, 300). This is fundamentally different from English lined paper; character count is precisely tracked.
- Scored with a 2-dimension rubric: 内容 (Content) /20 + 表达 (Expression) /20 = 40.
- Teacher markings: green wavy underlines (positive phrasing), red wavy underlines (issues), red circled individual characters (wrong character), brief marginal notes (e.g. "→ 不太作用"). Character-level corrections are unique to CJK composition.
- Winston wrote ~3 pages (~450 characters). Remaining pages blank.

**Paper 2 (试卷二, Language Use & Comprehension, 90 marks):** Split across two PDFs — Questions booklet (17 pages) and Answer booklet (10 pages, includes OAS as page 9).

Cover page (on Answers booklet): Score breakdown table — Q1–Q25: 42/50, Q26–Q40: 33/40, 总分 75/90.

Paper 2 has 5 sections:

| Section | Questions | Marks | Format | Answer location |
|---------|-----------|-------|--------|-----------------|
| 一 语文应用 (Language Application) | Q1–Q15 | 30 | MCQ (pinyin, vocabulary, conjunctions, word usage) | OAS |
| 二 短文填空 (Cloze Passage) | Q16–Q20 | 10 | **Inline MCQ** — options embedded in running text | OAS |
| 三 阅读理解一 (Reading Comprehension 1) | Q21–Q25 | 10 | MCQ based on a passage | OAS |
| 四 完成对话 (Complete the Dialogue) | Q26–Q29 | 8 | Choose phrase from numbered list, write number | Answer Booklet |
| 五 阅读理解二 (Reading Comprehension 2) | Q30–Q40 | 32 | Mixed: Group A (visual text, 10m) + Group B (passage, 22m) | Answer Booklet |

Section 五 details:

- **Group A (Q30–Q33, 10 marks):** Based on a visual text (校园书法比赛 notice/poster with printed illustration). Q30–Q32 are MCQ-style (2 marks each, number in box). **Q33 is a short writing task** (4 marks) — write a short message in a phone/tablet graphic, scored with mini-rubric: 内容 2/2 + 表达 2/2.
- **Group B (Q34–Q40, 22 marks):** Based on a longer narrative passage. Q34–Q35 find specific words in the passage (2 marks each). Q36–Q40 are open-ended comprehension (3–4 marks each) — full handwritten paragraph answers. Teacher marks individual scoring points with 0.5/1 marks in red.

**Inline MCQ (Section 二) is a distinct format.** Unlike standard MCQ where options are listed below the question, 短文填空 embeds choices within the running passage as "(1 word 2 word 3 word 4 word)" inline. The child circles their choice. The pipeline must recognize this format.

**MCQ annotations on question booklet:** Winston wrote his chosen number in parentheses and marked X/✓ next to options — a useful fallback signal when the OAS is unclear.

**OAS page** is page 9 of the Answers PDF (not separate). Standard bubble sheet for Q1–25. Red ticks next to correct answers. "Score: 42/50" written on margin.

**Scoring on open-ended answers:** Per-question 得分 (score) boxes — circled in red. Teacher marks 0.5/1 points at specific locations in the handwritten answer. Q39 notably scored 0/4, indicating a complete miss — valuable diagnostic signal.

### Higher Chinese papers (26 pages across 3 PDFs, 100 marks total)

Winston is in the Higher Chinese (高华) band, so he takes a **separate, harder exam** in addition to the regular (foundational) Chinese exam. The Higher Chinese exam differs structurally from regular Chinese in fundamental ways.

**Paper 1 (试卷一, Composition, 8 pages, 40 marks):** Identical format to regular Chinese Paper 1.

- Grid paper (方格纸), same character-count markers every 60 characters.
- Same 2-dimension rubric: 内容 (Content) /20 + 表达 (Expression) /20 = 40.
- Same teacher marking style: green wavy underlines (positive), red wavy underlines (issues), circled wrong characters.
- Winston wrote ~3 pages. Cover page shows rubric breakdown: 内容 16/20 + 表达 14/20 = 30/40.

**Paper 2 (试卷二, Language Use & Comprehension, 60 marks):** This is where Higher Chinese diverges dramatically. Split across two PDFs — Questions booklet (10 pages) and Answer booklet (8 pages). **No MCQ. No OAS.** All 23 questions are written answers.

Cover page (Answer Booklet): Total score only — "Your Score out of 60: 36.5." No section-level breakdown like regular Chinese.

| Section | Questions | Marks | Format | Notes |
|---------|-----------|-------|--------|-------|
| 一 语文应用 (Language Application) | Q1–Q10 | 20 | Group A (Q1–5, 10m): Cloze passage with **numbered word bank** — write the number. Group B (Q6–10, 10m): **Error correction** — find wrong character in underlined word, write correct word. | All answers in boxes on Answer Booklet |
| 二 阅读理解 (一) (Reading Comprehension 1) | Q11–Q16 | 16 | Q11–12: **Synonym matching** — find word in passage with same/similar meaning. Q13–14: **Table comparison** — fill 2×2 table (before/after, behaviour/reason). Q15: Open-ended. Q16: Choose best title from 2 options + explain reasoning. | Heavy handwriting; table format is unique |
| 三 阅读理解 (二) (Reading Comprehension 2) | Q17–Q23 | 24 | Q17–18: **Phrase explanation** — explain meaning of a phrase in context. Q19–23: Open-ended comprehension + opinion (4m each). Q21: **Paragraph summary in ≤15 characters** (in grid boxes). | Longest answers; teacher marks individual scoring points at 0.5 granularity |

**How Higher Chinese differs from regular Chinese (key extraction implications):**

- **No MCQ / No OAS** — eliminates OAS extraction entirely. All answers are handwritten — the pipeline must read much more handwriting per question.
- **Fewer total marks** (100 vs 130) and fewer pages (26 vs 35) despite being harder content.
- **Answer format is entirely written** — from single characters in boxes (Q1–Q12) to multi-sentence paragraphs (Q13–Q23). Handwriting density is the highest of any exam.
- **More diverse comprehension question types** — synonym matching, table comparison, phrase explanation, paragraph summary with character limit. These are all written, unlike regular Chinese which has 25 MCQ.
- **Richer teacher feedback on comprehension** — red parenthetical model answers, green corrections with pedagogical notes (e.g. "表情" indicating expected answer type), point-marking at 0.5 granularity. More feedback than regular Chinese (which only has detailed feedback on Q34–Q40).
- **Cover page is simpler** — Paper 2 shows total only (out of 60), not a section breakdown. Less pre-computed diagnostic information than regular Chinese.
- **Scoring**: Group A/B per-section scores circled in red margin (8/10, 10/10). Comprehension questions scored 0–4 with 0.5 granularity. Q23 scored 0/4 — diagnostic signal for opinion-writing weakness.

### Cross-subject observations

| Dimension | Math | Science | English | Chinese | Higher Chinese |
|-----------|------|---------|---------|---------|----------------|
| Pages per exam | 8 | 16 | 40 (14 + 26, two PDFs) | 35 (8 + 17 + 10, **three PDFs**) | 26 (8 + 10 + 8, **three PDFs**) |
| Total marks | 40 | 40 | 140 (50 + 90) | 130 (40 + 90) | 100 (40 + 60) |
| Question types | Short-answer, word problems | MCQ, open-ended | MCQ, cloze, editing, transformation, comprehension, **composition** | MCQ, **inline cloze**, dialogue completion, visual text, open-ended, **grid-paper composition** | **No MCQ.** Word-bank cloze, error correction, synonym matching, table comparison, phrase explanation, paragraph summary, open-ended, **grid-paper composition** |
| Handwriting density | Very heavy | Light (MCQ) to moderate (OE) | Light (MCQ/cloze) to very heavy (composition) | Light (MCQ) to heavy (open-ended + grid-paper composition) | **Very heavy** — every answer is handwritten |
| Answer format | Numbers in "Ans:" boxes | OAS bubbles + written sentences | OAS + word-in-box + sentence rewriting + multi-page essays | OAS + numbers-in-boxes + paragraph answers + **grid-paper composition** | **No OAS.** Numbers/characters in boxes + paragraph answers + **grid-paper composition** |
| Diagrams | Student-drawn (bar models) | Printed (experiments, graphs) | Printed (comic strips, visual texts) | Printed (visual text: notice/poster) — minimal | None — pure text passages |
| Scoring | Ticks/crosses + page score boxes | OAS ticks + mark numbers + page score boxes | **Rubric-based** (composition) + per-item (language sections) + per-section score boxes | **Rubric-based** (composition 内容+表达) + point-marking (0.5/1) on open-ended + per-section 得分 boxes | **Rubric-based** (composition) + per-section circled scores + **0.5 granularity** point-marking on comprehension |
| Teacher feedback | Correct answer in red | Mark numbers in red | **Qualitative comments** ("too general", "use evidence") + grammar corrections in colored ink | **Character-level corrections** (circled wrong characters) + point-marking (0.5/1) + brief margin notes | **Extensive**: red model answers in parentheses + green corrections + point annotations (表情 etc.) + character-level corrections on composition |
| Diagnostic value of cover page | Total marks only | Section breakdown (BA/BB) | **Full 9-section skill-level breakdown** | MCQ/written split (Q1–25 vs Q26–40) + Paper 1 rubric (内容+表达) | Paper 2: total only (out of 60). Paper 1: rubric (内容+表达) |

### Implications for extraction

1. **Vision-LLM-first, not OCR-first.** OCR alone cannot distinguish between visual layers or read OAS bubbles. A vision model (Gemini) handles both formats.
2. **The pipeline must handle two fundamentally different question types:** MCQ (answer is a number, binary outcome, may have a separate OAS page) and free-response/open-ended (answer is text or a number, may have partial marks and method marks).
3. **OAS extraction is a new pipeline step.** When the paper includes an OAS page, extract all MCQ answers in a single vision LLM call. This is the most efficient extraction in the pipeline — one call gives 12+ answers.
4. **Page-level score boxes are the quickest win** but are only present on some pages (Math: all pages; Science: open-ended pages only). The cover page is the fallback for aggregate scores.
5. **Cover page metadata extraction is valuable.** The cover page contains child name, date, school, paper type, total marks, section breakdowns, percentage, and achievement level — all in a single LLM call.
6. **Printed diagrams are semantic content.** Science diagrams must be preserved as image crops with the question object — the diagram IS the question. Math model drawings are student workings (preserved but not the question itself).
7. **The printed structure is highly regular within each subject.** Despite the visual differences between Math and Science, both follow consistent templates — question numbers, section headers, mark allocations, score boxes. Vision-LLM extraction should perform well with subject-aware prompts.
8. **Multi-document exam linking scales differently per subject.** Math/Science: 1 PDF per exam. English: 2 PDFs. Chinese: 3 PDFs. Higher Chinese: 3 PDFs. The `exam_id` field must handle variable document counts per exam.
9. **Higher Chinese is a separate exam with fundamentally different extraction.** No MCQ, no OAS — all written answers. The pipeline skips OAS extraction entirely for HC and instead must read much more handwriting. The `subject` field must distinguish `'chinese'` from `'higher_chinese'`.

---

## What We Need to Produce

A **question object** per question (or sub-part), stored in Postgres:

```sql
CREATE TABLE documents (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  drive_file_id TEXT,
  filename      TEXT NOT NULL,
  child         TEXT NOT NULL,          -- 'winston', 'emma', 'abigail'
  subject       TEXT NOT NULL,          -- 'math', 'english', 'science', 'chinese', 'higher_chinese'
  paper_type    TEXT,                   -- 'wa', 'exam', 'worksheet', 'past_year', 'practice'
  school        TEXT,                   -- 'st_gabriels', 'si_ling', etc. (for template learning)
  grade         TEXT,                   -- 'p6'
  date          DATE,
  total_marks   SMALLINT,
  earned_marks  SMALLINT,
  percentage    NUMERIC(5,2),           -- e.g. 93.00 (from cover page)
  achievement_level TEXT,               -- e.g. 'AL1' (from cover page, Science/PSLE grading)
  page_count    SMALLINT,
  section_info  JSONB,                  -- e.g. {"A": {"marks": 20, "earned": 14}, "B": {"marks": 20, "earned": 6}}
  has_oas       BOOLEAN DEFAULT FALSE,  -- paper includes an Optical Answer Sheet page
  exam_id       UUID,                   -- links multiple documents to the same exam (e.g. English Paper 1 + Paper 2)
  ingested_at   TIMESTAMPTZ DEFAULT now(),
  status        TEXT DEFAULT 'pending'  -- 'pending', 'processing', 'review', 'done'
);

CREATE TABLE pages (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id     UUID REFERENCES documents(id),
  page_number     SMALLINT NOT NULL,
  page_type       TEXT DEFAULT 'question', -- 'cover', 'question', 'oas' (Optical Answer Sheet)
  image_path      TEXT,                 -- path in object storage (full page image)
  ocr_text        TEXT,                 -- raw OCR output (supplementary)
  earned_marks    SMALLINT,             -- from page score box (NULL if no score box, e.g. MCQ pages)
  available_marks SMALLINT,             -- from page score box
  is_scanned      BOOLEAN
);

CREATE TABLE question_objects (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id       UUID REFERENCES documents(id),
  page_id           UUID REFERENCES pages(id),
  section           TEXT,                -- 'A', 'B', 'BookletA', 'BookletB'
  question_type     TEXT NOT NULL,       -- 'mcq', 'short_answer', 'open_ended', 'cloze', 'editing', 'synthesis', 'dialogue_completion', 'composition_sw', 'composition_cw'
  question_number   TEXT NOT NULL,       -- '1', '6', '14'
  sub_part          TEXT,                -- 'a', 'b', NULL for single-part questions
  display_label     TEXT,                -- '1a', '14(b)', 'Q6' — human-readable
  question_text     TEXT,                -- printed question text (OCR or LLM-extracted)
  max_marks         SMALLINT,
  earned_marks      SMALLINT,
  has_method_marks  BOOLEAN DEFAULT FALSE,
  outcome           TEXT,                -- 'correct', 'wrong', 'partial'
  child_answer      TEXT,                -- number for MCQ ('4'), text for open-ended, value for short-answer
  teacher_answer    TEXT,                -- teacher's correction (if wrong)
  mcq_options       SMALLINT,            -- number of options (e.g. 4) — MCQ only
  mcq_chosen        SMALLINT,            -- which option chosen (e.g. 3) — MCQ only
  mcq_correct       SMALLINT,            -- correct option (e.g. 4) — MCQ only, if extractable
  rubric_scores     JSONB,               -- composition only: {"task_fulfillment": 6, "language_organisation": 8}
  teacher_feedback  TEXT,                -- qualitative teacher comments (e.g. "too general", "use evidence from the text")
  passage_ref       UUID,                -- links comprehension questions to their shared passage (references another question_object or a passage table)
  skill_tags        TEXT[],
  error_tags        TEXT[],
  question_crop     TEXT,                -- image path: printed question region (includes diagrams)
  working_crop      TEXT,                -- image path: child's workings
  feedback_crop     TEXT,                -- image path: teacher marks + corrections
  correction_crop   TEXT,                -- image path: correction workings (green, if present)
  bbox              JSONB,               -- bounding box on source page
  extraction_method TEXT,                -- 'manual', 'vision_llm', 'oas_read', 'template'
  review_status     TEXT DEFAULT 'unreviewed',
  created_at        TIMESTAMPTZ DEFAULT now()
);
```

---

## Pipeline Steps

```
Upload PDF
  → 1. Register document (metadata: child, subject, date, paper type)
  → 2. Render pages to images + classify page types (cover, question, OAS)
  → 3. Extract cover page metadata (total marks, sections, percentage, AL)
  → 4. Extract page-level scores (vision LLM reads score boxes where present)
  → 5. If OAS page exists: extract all MCQ answers in one call (OAS read)
  → 6. Extract question structure (vision LLM identifies questions, sub-parts, marks, boundaries)
  → 7. Extract per-question results (ticks/crosses, answers, teacher corrections)
  → 8. Crop question regions (question + diagrams, workings, feedback, corrections)
  → 9. Tag skills (LLM suggests from skill graph, Jarod confirms)
  → 10. Tag errors for wrong/partial answers (LLM suggests, Jarod confirms)
  → 11. Jarod reviews in dashboard → corrections saved
  → 12. Compute/update mastery from confirmed data
```

### Step 1: Register Document

Jarod uploads a PDF through the dashboard and provides metadata:

- **Required:** child, subject
- **Optional (inferred or edited later):** date, paper type, grade, school, total marks

The system saves the PDF to object storage and creates a `documents` row with `status = 'processing'`.

### Step 2: Render Pages + Classify Page Types

Render every page to PNG at 300 DPI using PyMuPDF. Store page images in object storage. Create `pages` rows.

Also run OCR (Cloud Vision) to get supplementary text per page.

**Page type classification:** The first and last pages need special handling. The vision LLM (or simple heuristics on OCR text) classifies each page:

- **Cover page** — contains paper title, child name, date, total marks, section breakdown. Usually page 1.
- **OAS page** — Optical Answer Sheet with shaded bubbles. Usually the last page. Present in Science papers (and possibly others with MCQ sections). Identifiable by the grid of numbered ovals.
- **Question page** — everything else.

### Step 3: Extract Cover Page Metadata

Send the cover page image to Gemini Vision:

> *"This is the cover page of a Singapore primary school exam. Extract: school_name, paper_title, subject, child_name, date, class, total_marks, earned_marks, percentage, achievement_level, section_breakdown (e.g. Booklet A: 24/24, Booklet B: 13/16). Return as JSON."*

This pre-fills the `documents` row with rich metadata — school, date, total/earned marks, section-level scores, percentage, and AL. Jarod confirms or corrects. One LLM call replaces most manual metadata entry.

### Step 4: Extract Page-Level Scores

Send each question page image to Gemini Vision with a focused prompt:

> *"Look at the bottom-right corner of this page. There is a bordered score box showing marks earned and marks available (e.g. '4/6' or '3/7'). Extract: earned_marks, available_marks. If no score box is visible, return null."*

This gives us `pages.earned_marks` and `pages.available_marks`. Summing across pages cross-checks against the document total.

**Note:** Not all pages have score boxes. Math papers have them on every page. Science MCQ pages do not (scoring is via OAS). The LLM returns null for pages without score boxes.

### Step 5: Extract MCQ Answers from OAS (if present)

If the paper has an OAS page, this is the most efficient extraction step in the entire pipeline. Send the OAS page image to Gemini Vision:

> *"This is an Optical Answer Sheet (OAS) from a school exam. It has a grid of numbered rows (1, 2, 3...) with ovals labeled (1), (2), (3), (4). For each row that has a shaded oval, extract: question_number, chosen_option (the shaded number), is_correct (true if there is a red tick next to it). Return as JSON array."*

One LLM call extracts all MCQ answers and their correctness. For a 12-question MCQ section, this creates 12 question objects with `question_type = 'mcq'`, `mcq_chosen`, and `outcome` in a single call.

**Fallback:** If the OAS is missing or unreadable, MCQ answers can be extracted from the booklet pages (Winston writes his choice in parentheses on each question page).

### Step 6: Extract Question Structure

Send each question page image to Gemini Vision with a structured extraction prompt:

> *"This is a page from a Singapore primary school [subject] exam. Identify every question and sub-part visible on this page. For each, extract:*
> - *question_number, sub_part (e.g. 'a', 'b', or null)*
> - *question_type: 'mcq' (multiple choice), 'short_answer' (number/word in answer box), or 'open_ended' (written explanation)*
> - *printed question text (brief summary if long)*
> - *max_marks (from mark allocation like '(3)' or '[2]' or section header)*
> - *approximate bounding box (coordinates as fraction of page dimensions)*
> - *has_diagram (boolean — does this question include a printed diagram, graph, or table?)*
>
> *Return as JSON array."*

**Subject-specific prompts matter.** Math papers have "Ans:" lines and parenthesized marks. Science papers have bracketed marks [1], [2] and experiment diagrams. The prompt should be adapted per subject for best results.

### Step 7: Extract Per-Question Results

Different extraction strategy depending on `question_type`:

**For MCQ questions:** If already extracted from OAS (step 5), skip. Otherwise, extract from the booklet page — look for the answer written in parentheses and any ticks/crosses.

**For short-answer / open-ended questions:** Send the question region (cropped from the page image) to Gemini Vision:

> *"This is a cropped region of a student's exam paper. The student's workings are in pencil/black pen. The teacher's marks are in red ink. Look for:*
> - *Is there a tick (✓) or cross (✗) near the answer?*
> - *What did the student write as their final answer?*
> - *If wrong: did the teacher write a correction in red? What is it?*
> - *Are there method marks ('✓m') indicating partial credit?*
> - *How many marks were awarded? (look for red numbers next to the mark bracket)*
> - *Is there green ink (correction workings done later)?*
>
> *Return: outcome (correct/wrong/partial), earned_marks, child_answer, teacher_answer (if any), has_method_marks (boolean)."*

### Step 6: Crop Question Regions

Using the bounding boxes from step 4, crop each question into separate images:

- **question_crop** — the printed question text region only
- **working_crop** — the area where the child wrote workings
- **feedback_crop** — teacher's marks and corrections (if identifiable as a separate region; otherwise the full question block including all layers)
- **correction_crop** — green ink correction workings (if present)

In practice, for the MVP, a single crop of the entire question block (question + workings + feedback) is sufficient. Separating the layers can be a later refinement.

### Step 7: Skill Tagging

Send the question text + question crop to the LLM along with the subject's skill list:

> *"Given this P6 Math question and the following skill taxonomy, which skills does this question test? Return skill IDs."*

Jarod confirms or corrects. Confirmed tags become training data.

This step depends on the skill graph existing (even as a flat skill list per subject).

### Step 8: Error Tagging

For wrong or partial answers, classify *why* the child got it wrong:

> *"This question was marked [wrong/partial]. Based on the child's workings and the teacher's corrections, what type of error was made? Choose from: careless, concept_gap, misread_question, incomplete_method, wrong_method, missing_units, vocabulary, other. Briefly explain."*

Send the full question block (including workings and teacher feedback) as an image. Jarod reviews.

**MVP simplification:** error tagging can start as a manual field. LLM suggestions are an optimization.

### Step 9: Human Review

The dashboard shows each ingested document with:

- Page images with detected question boundaries overlaid
- Extracted scores per question (pre-filled by the LLM)
- Suggested skill tags and error tags
- Quick-fix controls: adjust boundaries, edit marks, reassign tags, correct answers

**Status flow:** `processing` → `review` (pipeline done, awaiting Jarod) → `done` (Jarod confirmed).

Corrections are saved. Over time, they inform template learning — when the system sees another St. Gabriel's WA paper, it already knows the layout.

### Step 10: Compute Mastery

Once questions are confirmed, the Student Model updates automatically:

- Record an `attempt` for each skill tag on each confirmed question
- Weight by hint/scaffolding level (unassisted > heavily-hinted)
- Recompute mastery score for affected skills
- Update misconception records if error tags are present

---

## Per-Subject Extraction Notes

### Math

**Paper structure:** Section A (Q1–Q10, fixed 2 marks each, all short-answer) + Section B (Q11–Q15, multi-part word problems, variable marks per sub-part in parentheses). No MCQ, no OAS.

**Extraction approach:** Vision-LLM on every page. "Ans:" lines and ticks/crosses are the primary scoring signals. Page score boxes on every page.

**Key challenges:** Heaviest handwriting of all subjects. Model drawings and bar diagrams are student-generated visual problem-solving strategies — must be preserved as image crops. Math notation (fractions, long division) doesn't OCR well. Workings frequently overflow into margins and overlap with printed text.

### Science

**Paper structure:** Booklet A / MCQ (Q1–Q12, 2 marks each, answers on OAS) + Booklet B / Open-ended (Q13–Q16, multi-part, variable marks in square brackets [1], [2]). 16 pages — nearly double Math because large printed diagrams take a full page per MCQ.

**Extraction approach:** OAS page gives all MCQ results in one call (most efficient step). Open-ended pages use the same vision-LLM approach as Math. Cover page provides section-level breakdown (BA/BB scores, percentage, AL).

**Key challenges:** Printed diagrams (experiment setups, graphs, charts, tables) are integral to the question — must be cropped with the question object. Open-ended answers are written sentences, not numbers — harder for the LLM to extract the child's answer vs. the teacher's correction. Student annotations are conceptual ("changed var", "measured var") rather than computational — potentially valuable for tracking analytical thinking but hard to systematically extract.

### English

**Paper structure (confirmed from real papers):** Paper 1 (50 marks: Situational Writing 14 + Continuous Writing 36) + Paper 2 (90 marks: 9 sections across two booklets — Grammar, Vocabulary, Vocabulary Cloze, Comprehension Visual Text [all MCQ/OAS], Grammar Cloze, Editing, Comprehension Cloze, Synthesis/Transformation, Comprehension OE). Two separate PDFs per exam.

**Extraction approach:** This is the most complex subject. Paper 1 produces just 2 question objects (compositions). Paper 2 produces 50–75 question objects across 7+ distinct formats. Cover page of Paper 2 provides a complete per-section diagnostic breakdown — extract this first.

For MCQ sections (A–D): OAS if available, booklet fallback otherwise. For fill-in-blank sections (E, G): each numbered blank is a question object with the passage as shared context. For editing (F): each numbered error box is a question object. For comprehension OE (I): each numbered question with its mark allocation. For compositions: one question object per writing task with `rubric_scores` JSON.

**Key challenges:**
- **Most diverse question types** of any subject — 8 distinct formats in one exam. The `question_type` field must differentiate them.
- **Composition scoring is rubric-based**, not binary. The scoring dimensions (Task Fulfillment, Language & Organisation) must be captured in `rubric_scores` JSONB.
- **Teacher qualitative feedback** ("too general", "use evidence from the text") is the highest-value diagnostic data in the entire system. Must be extracted and stored in `teacher_feedback`.
- **Multi-page handwritten compositions** are dense handwriting on lined paper — hard for vision LLM to transcribe accurately. For MVP, preserve as image crops and extract only the score and rubric dimensions.
- **Two PDFs per exam** — pipeline must support linking Paper 1 and Paper 2 via `exam_id`.
- **OAS may not be in the scanned PDF** — Booklet A's OAS was not present in the sample. The pipeline must fall back to reading MCQ answers from booklet pages.
- **Many blank pages** ("BLANK PAGE" printed) and transition pages — pipeline should detect and skip these.

### Chinese

**Paper structure (confirmed from real papers):** Paper 1 (40 marks: Composition 内容 20 + 表达 20) + Paper 2 (90 marks: 5 sections — 语文应用 30, 短文填空 10, 阅读理解一 10, 完成对话 8, 阅读理解二 32). **Three separate PDFs per exam** — Paper 1 answer booklet + Paper 2 question booklet + Paper 2 answer booklet (with OAS).

**Extraction approach:** Structurally similar to English but with unique elements. Paper 1 produces 1 question object (composition on grid paper). Paper 2 produces ~40 question objects. OAS page is in the Answers PDF — extract all 25 MCQ answers (Q1–Q25) in one call. For written answer sections (Q26–Q40), extract from the Answer Booklet pages.

For MCQ sections (Q1–Q25): OAS extraction (step 5). For dialogue completion (Q26–Q29): numbers in boxes — simple extraction. For Group A visual text (Q30–Q33): mixed MCQ + short writing. For passage comprehension (Q34–Q40): word-in-blank + full handwritten paragraph extraction.

**Key challenges:**

- **Three PDFs per exam** — most complex linking requirement of any subject. Pipeline must link Questions + Answers + Paper 1 via `exam_id`. At upload, Jarod should group these three files as one exam.
- **Grid paper composition (方格纸)** — unique to Chinese. Each character occupies its own cell with counter marks every 60 characters. The grid structure may actually help the vision LLM read individual CJK characters more accurately than free-form handwriting, but it creates a visually dense regular grid that could confuse boundary detection.
- **Pinyin questions (Q1–Q2)** — test pronunciation knowledge (e.g. diē dǎo vs tiē dǎo). The skill tag must differentiate pinyin from vocabulary from grammar. Pinyin with tone marks requires accurate extraction.
- **Inline MCQ format (短文填空, Q16–Q20)** — options are embedded within running text as "(1 word 2 word 3 word 4 word)" and the child circles their choice. Structurally different from standard listed MCQ. The extraction prompt must handle this format.
- **Dialogue completion (Q26–Q29)** — a phrase bank (numbered 1–8) at the top, followed by a dialogue with blanks. The child writes the phrase number. This is a `dialogue_completion` question type distinct from other short-answer formats.
- **Character-level teacher corrections** — teacher circles individual wrong Chinese characters, which is more granular than English corrections (word or phrase level). Full extraction of every circled character is expensive; for MVP, capture corrections as text in `teacher_answer` or `teacher_feedback`.
- **Bilingual content** — instructions are in English, question content is in Chinese. Headers mix both (e.g. "CHINESE LANGUAGE (PAPER 2)", "INSTRUCTIONS TO CANDIDATES" alongside "华文 (试卷二)"). Vision LLM handles this naturally; prompts should be in English.
- **Mini-rubric on short writing (Q33)** — even a 4-mark short message is scored with 内容 + 表达, same rubric dimensions as the full composition. Use `rubric_scores` JSONB for both.
- **Point-by-point marking on open-ended answers (Q34–Q40)** — teacher marks individual scoring points with 0.5/1 in red at specific locations in the handwritten answer. Similar to Science's mark-number style but on longer written responses. Some questions score 0 (Q39 = 0/4) — strong diagnostic signal for comprehension gaps.

### Higher Chinese

**Paper structure (confirmed from real papers):** Paper 1 (40 marks: Composition 内容 20 + 表达 20) — same format as regular Chinese. Paper 2 (60 marks: 3 sections — 语文应用 20, 阅读理解一 16, 阅读理解二 24). **Three separate PDFs per exam** — Paper 1 answer booklet + Paper 2 question booklet + Paper 2 answer booklet. **No MCQ. No OAS.** Total: 100 marks.

**Extraction approach:** Paper 1 produces 1 question object (composition) — same as regular Chinese. Paper 2 produces 23 question objects, **all written answers**. No OAS extraction step. Every question requires handwriting recognition from the Answer Booklet.

For Section 一 Group A (Q1–Q5): Numbers in boxes (word bank selection) — simple extraction. For Section 一 Group B (Q6–Q10): Characters in boxes (error correction) — read corrected word. For Section 二 (Q11–Q16): Mixed — single words (synonym matching, Q11–Q12), table cells (Q13–Q14), short paragraphs (Q15–Q16). For Section 三 (Q17–Q23): Full paragraph handwriting extraction (longest written answers of any subject).

**Key challenges:**

- **Highest handwriting density of any exam.** Every one of the 23 questions produces handwritten Chinese, from single characters (Q1–Q12) to multi-sentence paragraphs (Q17–Q23). The vision LLM must read dense Chinese handwriting across every Answer Booklet page. This makes HC the hardest exam for extraction accuracy.
- **No MCQ / No OAS** — eliminates the most efficient extraction step. There is no "quick win" like reading 25 bubbles in one call. Every question needs individual handwriting extraction.
- **Table-format answers (Q13–Q14)** — answers are written inside a printed 2×2 table (columns: 表现/原因, rows: before/after). The vision LLM must correctly map handwritten content to the right table cell. Unique extraction challenge not seen in other subjects.
- **Paragraph summary with character limit (Q21)** — "write the gist of paragraph 2 in ≤15 characters." Answer is in grid boxes (15 cells). The character limit makes this a constrained short answer, distinct from open-ended comprehension.
- **Richer teacher corrections than regular Chinese** — red parenthetical model answers (e.g. "(作者原本不轻易相信别人, 但看到妇女那么慌张, 作者非常可怜她, 所以决定借她50元)") provide complete expected answers. Green annotations specify answer type expectations (e.g. "表情" = describe expression). These are high-value for learning but complex to separate from the child's handwriting.
- **0.5-mark granularity** — comprehension questions are scored at half-mark precision (e.g. 0.5/4, 1.5/4). The vision LLM must accurately read these small red numerals. Regular Chinese also uses 0.5 marking, but HC has more questions at this granularity.
- **Same 3-PDF linking as regular Chinese** — but with no OAS page in the Answer Booklet. The Answer Booklet is purely written answers.
- **Shared skill graph with regular Chinese** — HC tests the same skills (vocabulary, comprehension, composition) at a higher difficulty. The skill taxonomy should use the same nodes but may need difficulty-level metadata (foundation vs higher).

---

## Technology Stack

| Component | Tool | Why |
|-----------|------|-----|
| PDF rendering | PyMuPDF (fitz) | Fast, handles both digital and scanned PDFs |
| Page-to-image | PyMuPDF at 300 DPI | High enough quality for vision LLM and OCR |
| Image cropping | Pillow | Crop question regions from page images |
| OCR (supplementary) | Google Cloud Vision (Document Text Detection) | Supplementary text for keyword search; free tier covers ongoing volume |
| Vision LLM (primary extraction) | Gemini 2.5 Flash | Cheap ($0.10/1M input tokens for images), fast, good vision understanding. Handles the 4-layer separation, score extraction, boundary detection |
| Database | Postgres + pgvector | Structured data + embeddings in one system |
| Object storage | GCS or local filesystem | Page images and question crops |
| Pipeline orchestration | Python scripts (simple sequential) | No need for Airflow/Celery at this scale |

### Cost estimate for vision-LLM extraction

At 300 DPI, each page image is ~1–2 MB. Gemini 2.5 Flash processes images at roughly 250–500 tokens per image.

Per document (8-page paper, ~3 LLM calls per page for steps 3–5):
- ~24 LLM calls × ~500 tokens input + structured output
- Cost: well under $0.01 per document at Gemini Flash pricing

For the initial backlog of ~50 scored papers: total LLM cost < $0.50.

At this scale, cost is negligible. The constraint is Jarod's review time, not API spend.

---

## MVP Scope (Phase 1)

**Build in this order:**

### Tier 1 — Usable in days

1. **Upload + register** — PDF upload form, save to object storage, create `documents` row with metadata.
2. **Render pages** — PyMuPDF renders pages to PNG at 300 DPI, stored in object storage.
3. **Page-level score extraction** — Gemini Vision reads score boxes from each page. Pre-fills `pages.earned_marks` and `pages.available_marks`.
4. **Manual question marking** — Jarod marks question boundaries on page images in the dashboard (click corners). Enters question numbers, marks, outcome per question manually.

This alone gives us: documents with page-level scores, manually tagged question objects with marks and outcomes. Enough to compute mastery per skill (once skill tags are added).

### Tier 2 — Reduces manual effort

5. **Vision-LLM question extraction** — Gemini Vision pre-fills question numbers, boundaries, and marks from page images. Jarod reviews/corrects instead of entering from scratch.
6. **Vision-LLM score + outcome extraction** — pre-fills ticks/crosses, child's answer, teacher's correction. Jarod confirms.
7. **LLM skill suggestion** — when tagging, the system suggests skills from the graph. Jarod accepts/edits.

### Tier 3 — Progressive automation

8. **Template learning** — when the system sees a second paper from the same school/format, it pre-applies the known template (question layout, mark scheme, section structure).
9. **LLM error tagging** — system suggests error categories for wrong answers.
10. **Batch ingestion** — process a folder of PDFs with minimal per-document intervention.

**Target:** Ingest 20–30 of Winston's recent scored papers (across all 5 subjects) within the first 2 weeks of Phase 1. At ~15 questions per paper, this creates 300–450 question objects — enough for the Diagnostic Engine to surface meaningful patterns.

---

## Batch Ingestion Strategy

Winston has ~4,000 pages of historical worksheets. Ingesting all of them manually is impractical. Strategy:

1. **Prioritize recent scored papers** — last 6–12 months of WA papers, exams, and practice tests. These have the most relevant scores and highest signal for current mastery. Estimate: ~30–50 papers, ~200–400 pages.
2. **Prioritize by subject** — start with Math (most structured, cleanest extraction), then Science, then English, then Chinese, then Higher Chinese (most handwriting-dense, hardest extraction).
3. **Backfill older content later** — once template profiles and automation improve, batch-process older papers with less manual effort.
4. **Unscored papers** — practice sets and past-year papers populate the question bank for the Planner. Ingest with skill tags but no scores.

---

## Open Questions

### Design decisions

1. **Multi-document exam linking UX.** English needs 2 PDFs per exam. Chinese and Higher Chinese each need 3 PDFs. Should the upload UI auto-detect that files belong to the same exam (matching child + date + subject), or should Jarod explicitly group them? Auto-detection risks false matches; explicit grouping adds friction. A pragmatic middle ground: default to explicit grouping, with a "suggest matches" feature that highlights likely groups.
2. **Review UI design.** Key interactions: view page images, see overlaid question boundaries, edit marks/tags, approve/reject per question. Should this be part of the main dashboard or a dedicated ingestion tool? Given the amount of time Jarod will spend here in Phase 1, it deserves thoughtful UX.
3. **Green correction layer.** Green ink workings (from review sessions with Jarod) appear in Math, Chinese, and Higher Chinese papers. They represent "what Winston learned after the initial attempt." Should corrections be a field on the question object, a separate `correction_attempts` table, or a second question object linked to the original? The choice affects how we track learning progression over time.
4. **Composition transcription depth.** Multi-page handwritten compositions (English, Chinese, Higher Chinese) are hard to transcribe accurately. For diagnostics, do we need full text (expensive) or just score + rubric dimensions + teacher corrections (cheaper)? Grid-paper compositions (Chinese/HC) may be easier to transcribe than English free-form. Decision: start with score-only for MVP, add transcription as a Tier 3 feature.
5. **Student annotations.** Winston annotates Science papers ("changed var", "measured var") and English comprehension passages (underlining, vocabulary notes). These are thinking traces but don't fit the question object model. Ignore for MVP, or capture as `student_annotations` free text?

### Skill graph

6. **Chinese/Higher Chinese: shared or separate skill graphs?** HC tests the same domains (vocabulary, comprehension, composition) at higher difficulty. Options: (a) one skill graph with difficulty metadata per question, (b) separate skill nodes for foundation/higher. This affects mastery computation — an HC comprehension miss is a weaker weakness signal than a foundation miss on the same skill.
7. **Chinese skill taxonomy granularity.** Chinese skills span pinyin (pronunciation), vocabulary (词语), grammar (语法), comprehension (阅读理解), and composition (写作). The graph needs Chinese-language skill names mapped to MOE syllabus standards. How granular? (e.g., distinguish 量词 from 关联词 from 词语运用)

### Extraction accuracy

8. **Teacher feedback extraction reliability.** Qualitative teacher comments are the highest-value diagnostic data across subjects: "too general" / "use evidence" (English), circled wrong characters (Chinese), full model answers in red parentheses (Higher Chinese). How reliably can Gemini Flash extract these handwritten margin notes? Start manual-first for MVP, or attempt automatic extraction from day one? A small accuracy benchmark on 5–10 papers would answer this.
9. **Higher Chinese handwriting extraction.** HC is the most handwriting-dense exam — every one of 23 questions produces handwritten Chinese, from single characters to full paragraphs, all overlaid with teacher corrections. Should HC be the last subject to automate extraction (after Math/Science where accuracy is more tractable)?

### Logistics

10. **Drive folder structure.** How are PDFs currently organized? By child? Subject? Date? Mixed? Determines how much metadata can be inferred vs. manually entered at upload.
11. **Paper template reuse.** All sample papers are from St. Gabriel's. Do WA papers from the same school reuse layouts term after term? If so, template recognition could skip LLM calls for known formats after the first paper.

### Resolved

- ~~**Do Chinese papers use OAS?**~~ **Yes.** Regular Chinese uses OAS for Q1–Q25 (25 MCQ). The OAS is page 9 of the Answer Booklet PDF. **Higher Chinese does not use OAS** — all answers are written.
- ~~**Does Higher Chinese follow the same structure as regular Chinese?**~~ **No.** HC has no MCQ, no OAS, fewer total marks (100 vs 130), fewer pages (26 vs 35), and fundamentally different question types (word-bank cloze, error correction, synonym matching, table comparison, phrase explanation).

---

## Utilities

Pre-processing utilities that prepare raw PDFs for ingestion. Each utility lives in its own subfolder under `ai_study_buddy/utils/` and has a `SPEC.md` (and for pdf_file_manager, a full doc set) there.

### Utility 1: PDF Compressor (`compress_pdf`)

**Location:** [`utils/compress_pdf/`](../utils/compress_pdf/) — `compress_pdf.py` + [`SPEC.md`](../utils/compress_pdf/SPEC.md)

**Purpose:** Reduce storage size of raw scanned PDFs before ingestion. Raw scans from mobile scanning apps can be 5–25 MB per paper. Targets 150 DPI / JPEG quality 72 (matching Ghostscript `/ebook`), preserving RGB color for teacher annotation layers.

**Benchmarks:** Science 5.6 MB → 1.5 MB (3.6×) · English 23.4 MB → 2.9 MB (8.1×)

```bash
python compress_pdf.py abc.pdf              # → _c_abc.pdf next to input
python compress_pdf.py --batch /path/       # → compress all PDFs in directory
```

### Utility 2: PDF File Manager (`pdf_file_manager`)

**Location:** [`utils/pdf_file_manager/`](../utils/pdf_file_manager/) — `pdf_file_manager.py` + [`README.md`](../utils/pdf_file_manager/README.md), [`SPEC.md`](../utils/pdf_file_manager/SPEC.md), and supporting docs (ARCHITECTURE, TESTING, DECISIONS, CHANGELOG).

**Purpose:** Keeps a SQLite registry of PDF files in the study archive. Tracks exams, worksheets, book exercises, activities, notes, and templates (with optional completed variants); keeps on-disk paths and database records in sync. Supports scan roots (e.g. Google Drive folders), scan/discovery, optional compression via `compress_pdf`, classification (`doc_type`, `subject`, metadata), exam grouping, and template/completion linking. Only `main` files are ingested by the pipeline; `_raw_` archives are kept for traceability. All changes are recorded in an append-only operation log.

**Machine interface:** Prefer the Python API and MCP server over the old CLI. The MCP layer is implemented in [`utils/pdf_file_manager/pdf_file_manager_mcp.py`](../utils/pdf_file_manager/pdf_file_manager_mcp.py) with a FastMCP entrypoint in [`utils/pdf_file_manager/pdf_file_manager_mcp_server.py`](../utils/pdf_file_manager/pdf_file_manager_mcp_server.py). This is the intended structured interface for agents and automations.

**CLI status:** The built-in CLI has been removed. Use the Python API directly or the MCP server.

Run the MCP server with:

```bash
python utils/pdf_file_manager/pdf_file_manager_mcp_server.py --db /path/to/registry.db
```

See the [README](../utils/pdf_file_manager/README.md) and [SPEC](../utils/pdf_file_manager/SPEC.md) for the current Python and MCP contracts.
