# AI Study Buddy — Singapore Primary Exam Formats & Visual Structure

> Status: **Exploratory** — background/reference material for ingestion and diagnostics.
>
> Related docs: [DATA_STRATEGY](./L3_DATA_STRATEGY.md), [INGESTION_PIPELINE](./L4_INGESTION_PIPELINE.md).

---

## What the Worksheets Actually Look Like

Based on real samples across all core subjects, including both Chinese variants (foundation and higher) — from Winston's P5 and P6 exams and weighted assessments at St. Gabriel's Primary School.

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
| A: Grammar | MCQ (4 options), fill-in-blank sentence | "The notebook on the table ___ to Benjamin." -> (2) belongs |
| B: Vocabulary | MCQ (4 options), choose word closest in meaning | Contextual vocabulary |
| C: Vocabulary Cloze | Passage with blanks, choose from word bank | Similar to Grammar Cloze but vocabulary-focused |
| D: Comprehension (Visual Text) | MCQ based on a visual text (poster, flyer, etc.) | Read visual text, answer 5 MCQ |

**Booklet B (Written answers, 65 marks):** Sections E–I — five distinct question formats:

| Section | Format | Example |
|---------|--------|---------|
| E: Grammar Cloze | Passage with numbered blanks, choose from word bank | Write letter "(A)", "(P)" in blank |
| F: Editing | Passage with underlined errors, write correction in numbered box | "rekoniced" -> "recognised" |
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
- Teacher markings: green wavy underlines (positive phrasing), red wavy underlines (issues), red circled individual characters (wrong character), brief marginal notes (e.g. "-> 不太作用"). Character-level corrections are unique to CJK composition.
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
| 三 阅读理解 (二) (Reading Comprehension 2) | Q17–Q23 | 24 | Q17–18: **Phrase explanation** — explain meaning of a phrase in context. Q19–23: Open-ended comprehension + opinion (4m each). Q21: **Paragraph summary in <=15 characters** (in grid boxes). | Longest answers; teacher marks individual scoring points at 0.5 granularity |

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

Moved to [L4_INGESTION_PIPELINE](./L4_INGESTION_PIPELINE.md) so implications are maintained directly alongside implementation flow and pipeline step design.

