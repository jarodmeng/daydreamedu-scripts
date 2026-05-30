# AI Study Buddy — Ingestion Pipeline: Implementation Proposal

> Status: **Proposal** — detailed plan for the first component to build.
>
> Related docs: [ARCHITECTURE](./L1_ARCHITECTURE.md) (Ingestion Pipeline component), [DATA_STRATEGY](./L3_DATA_STRATEGY.md) (question objects, storage tiers, OCR strategy), [EXAM_FORMATS](./L3_EXAM_FORMATS.md) (subject-specific paper structures and visual patterns).

---

## Why This Is First

The entire system depends on structured data from study materials (worksheets, weighted assessments, exams, and book-based exercises). The Skill Graph, Student Model, Diagnostic Engine, and Planner all consume question objects. Without the ingestion pipeline, there is nothing to analyze, no mastery to compute, and no plan to generate.

The goal for Phase 1 is not full automation. It's: **get the current multi-student backlog of study documents (scored and unscored) into the system as structured, skill-tagged question objects, fast enough to be useful for near-term exam prep (including Winston's PSLE runway).**

---

## What We Have

- **Registry snapshot (as of 2026-03-31):** 1,242 `main` PDFs spanning 4 subjects (`math`, `english`, `science`, `chinese`), with ~12,964 known pages across 1,218 files (`page_count` missing on 24 files). Main-file doc mix: 287 exams, 137 worksheets, 728 books, 60 activities, 30 notes.
- PDFs live in **Google Drive** (canonical store).
- Most PDFs are **scanned** (image-only, zero extractable text). Some may be digital.
- Mix of scored papers (with teacher marks) and blank/practice papers.
- **Folder structure is now partially standardized** in the registry workflow (subject -> student/scope -> content folder such as `Exam`/`Exercise`/`Book`/`Activity`/`Composition`/`Note`), and path-based inference is already used for `subject`, `doc_type`, `is_template`, and selected metadata fields.
- **Classification is still hybrid:** path inference covers a useful baseline, but ingestion-critical fields (for example `exam_date`, `school`, and some paper metadata) still require human review/confirmation in many cases.

---

## Format-Driven Extraction Implications

The pipeline flow is shaped by format realities in [L3_EXAM_FORMATS](./L3_EXAM_FORMATS.md) and per-subject notes under `context/subject_understandings/`. Keep detailed exam-structure background there; use this section for implementation decisions only.

1. **Vision-LLM-first architecture (steps 2, 4, 5, 6, 7).** OCR stays supplementary because we must parse layered markings, OAS bubbles, and handwritten answer regions.
2. **Dual extraction path by question modality (steps 5 vs 7).** MCQ/OAS and free-response questions need different extraction logic, schemas, and review patterns.
3. **High-yield OAS optimization (step 5).** When OAS exists, extract all MCQ outcomes in one pass; when absent/unreadable, use booklet fallback.
4. **Score hierarchy and reconciliation (steps 3, 4, 7).** Capture cover-page totals/sections, page-level score boxes, and per-question marks, then cross-check consistency across levels.
5. **Diagram-preserving crops are mandatory (step 8).** Printed diagrams/tables/visual texts are often part of the question semantics and must be retained with the question object.
6. **Exam-level multi-document linking (step 1 and post-ingest grouping).** Linking must support variable booklet counts by subject (1/2/3 PDFs) through `exam_id`.
7. **Subject/variant-aware modeling and prompts (steps 1, 6, 7).** Use `subject='chinese'` with `chinese_variant='higher'` and tune extraction prompts for variant-specific formats (for example no-OAS Higher Chinese).
8. **Human-in-the-loop remains core (step 11).** Complex handwriting, rubric scoring, and qualitative teacher feedback require review-first operations, not full automation in Phase 1.

---

## What We Need to Produce

A **question object** per question (or sub-part), stored in Postgres.

Refinement: many English and Chinese formats contain a shared passage, dialogue, visual text, cloze paragraph, or table used by multiple questions. So the long-term schema should support:

- `question_objects` as the atomic grading / retrieval / mastery unit
- a reusable `stimulus_blocks` layer for shared printed context

That lets us crop / OCR / embed a shared passage once, then link many question objects to it.

```sql
CREATE TABLE documents (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  drive_file_id TEXT,
  filename      TEXT NOT NULL,
  child         TEXT NOT NULL,          -- 'winston', 'emma', 'abigail'
  subject       TEXT NOT NULL,          -- 'math', 'english', 'science', 'chinese'
  paper_type    TEXT,                   -- 'wa', 'exam', 'worksheet', 'past_year', 'practice'
  school        TEXT,                   -- 'st_gabriels', 'si_ling', etc. (for template learning)
  grade         TEXT,                   -- 'p6'
  chinese_variant TEXT,                 -- 'standard' | 'higher' (only when subject='chinese'; 'standard' = Standard 华文 — not SEAB Foundation Chinese Language; do not use legacy 'foundation')
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

CREATE TABLE stimulus_blocks (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id       UUID REFERENCES documents(id),
  page_id           UUID REFERENCES pages(id),
  stimulus_type     TEXT NOT NULL,       -- 'passage', 'visual_text', 'cloze_passage', 'dialogue', 'table', 'diagram', 'mcq_group'
  display_label     TEXT,                -- 'Passage A', 'Section I passage', 'Visual text', etc.
  printed_text      TEXT,                -- OCR / extracted text for the shared block
  bbox              JSONB,               -- bounding box on source page
  crop_path         TEXT,                -- shared crop image path
  extraction_method TEXT,                -- 'manual', 'vision_llm', 'template', 'ocr_regex'
  review_status     TEXT DEFAULT 'unreviewed',
  created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE question_objects (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id       UUID REFERENCES documents(id),
  page_id           UUID REFERENCES pages(id),
  stimulus_id       UUID REFERENCES stimulus_blocks(id),
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
  → 6. Extract structure (sections, shared stimuli, questions, sub-parts, marks, boundaries)
  → 7. Extract per-question results (ticks/crosses, answers, teacher corrections)
  → 8. Crop shared stimuli and question regions (question + diagrams, workings, feedback, corrections)
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

**Note:** Not all pages have score boxes. Math **Paper 1 Booklet A** (MCQ) often has no per-page score box (scoring is via OAS); **Booklet B** and **Paper 2** are more likely to have them. Science MCQ pages do not (scoring is via OAS). The LLM returns null for pages without score boxes.

### Step 5: Extract MCQ Answers from OAS (if present)

If the paper has an OAS page, this is the most efficient extraction step in the entire pipeline. Send the OAS page image to Gemini Vision:

> *"This is an Optical Answer Sheet (OAS) from a school exam. It has a grid of numbered rows (1, 2, 3...) with ovals labeled (1), (2), (3), (4). For each row that has a shaded oval, extract: question_number, chosen_option (the shaded number), is_correct (true if there is a red tick next to it). Return as JSON array."*

One LLM call extracts all MCQ answers and their correctness. For example, a PSLE Science Booklet A has **28** MCQs on one OAS; a smaller WA might have 12. Each shaded row yields `question_type = 'mcq'`, `mcq_chosen`, and `outcome` in one call.

**Fallback:** If the OAS is missing or unreadable, MCQ answers can be extracted from the booklet pages (Winston writes his choice in parentheses on each question page).

### Step 6: Extract Structure

This step should produce both:

- **shared stimulus blocks** where relevant
- **question objects** linked to those blocks

The shared-stimulus layer matters most for:

- English comprehension passages
- Chinese 阅读理解 passages
- cloze passages
- visual texts / posters
- tables, charts, and diagrams reused across several questions

Send each question page image to Gemini Vision with a structured extraction prompt:

> *"This is a page from a Singapore primary school [subject] exam. Identify any shared stimulus block visible on the page (passage, dialogue, cloze paragraph, visual text, table, or diagram) and every question or sub-part that depends on it. For each question, extract:*
> - *question_number, sub_part (e.g. 'a', 'b', or null)*
> - *question_type: 'mcq' (multiple choice), 'short_answer' (number/word in answer box), or 'open_ended' (written explanation)*
> - *printed question text (brief summary if long)*
> - *max_marks (from mark allocation like '(3)' or '[2]' or section header)*
> - *approximate bounding box (coordinates as fraction of page dimensions)*
> - *has_diagram (boolean — does this question include a printed diagram, graph, or table?)*
> - *shared_stimulus_id or null if the question is standalone*
>
> *Return as JSON array."*

**Subject-specific prompts matter.** Math papers have "Ans:" lines; **Paper 2** uses square-bracket marks `[n]` per sub-part; **Paper 1 Booklet B** uses short-answer lines and 2-mark items. Science papers have bracketed marks [1], [2] and experiment diagrams. The prompt should be adapted per subject for best results.

For digital PDFs and stable templates, Python should try to detect structure first from text / layout cues and use the vision model only when confidence is low.

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

### Step 8: Crop Shared Stimuli and Question Regions

Using the bounding boxes from step 4, crop each question into separate images:

- **stimulus_crop** — shared passage / visual text / diagram crop used by multiple questions, when applicable
- **question_crop** — the printed question text region only
- **working_crop** — the area where the child wrote workings
- **feedback_crop** — teacher's marks and corrections (if identifiable as a separate region; otherwise the full question block including all layers)
- **correction_crop** — green ink correction workings (if present)

In practice, for the MVP, a single crop of the entire question block (question + workings + feedback) is sufficient. Separating the layers can be a later refinement. But when multiple questions share the same printed context, the shared `stimulus_crop` should be stored once and linked to all dependent question objects.

### Step 9: Skill Tagging

Send the question text + question crop to the LLM along with the subject's skill list:

> *"Given this P6 Math question and the following skill taxonomy, which skills does this question test? Return skill IDs."*

Jarod confirms or corrects. Confirmed tags become training data.

This step depends on the skill graph existing (even as a flat skill list per subject).

### Step 10: Error Tagging

For wrong or partial answers, classify *why* the child got it wrong:

> *"This question was marked [wrong/partial]. Based on the child's workings and the teacher's corrections, what type of error was made? Choose from: careless, concept_gap, misread_question, incomplete_method, wrong_method, missing_units, vocabulary, other. Briefly explain."*

Send the full question block (including workings and teacher feedback) as an image. Jarod reviews.

**MVP simplification:** error tagging can start as a manual field. LLM suggestions are an optimization.

### Step 11: Human Review

The dashboard shows each ingested document with:

- Page images with detected question boundaries overlaid
- Shared stimulus boundaries (passages / visual texts / tables) and linked question groups
- Extracted scores per question (pre-filled by the LLM)
- Suggested skill tags and error tags
- Quick-fix controls: adjust boundaries, edit marks, reassign tags, correct answers

**Status flow:** `processing` → `review` (pipeline done, awaiting Jarod) → `done` (Jarod confirmed).

Corrections are saved. Over time, they inform template learning — when the system sees another St. Gabriel's WA paper, it already knows the layout.

### Step 12: Compute Mastery

Once questions are confirmed, the Student Model updates automatically:

- Record an `attempt` for each skill tag on each confirmed question
- Weight by hint/scaffolding level (unassisted > heavily-hinted)
- Recompute mastery score for affected skills
- Update misconception records if error tags are present

---

## Per-Subject Extraction Notes

Detailed paper structures and visual examples live in [L3_EXAM_FORMATS](./L3_EXAM_FORMATS.md) (overview) and `context/subject_understandings/**/<subject>_exam_format.md`. This section only captures implementation-relevant extraction deltas.

### Math

- **Extraction approach:** Vision-LLM on all question pages; **OAS-first** for Paper 1 Booklet A (MCQ); then "Ans:" lines, ticks/crosses, and page score boxes for Booklet B and Paper 2.
- **Implementation focus:** Preserve model drawings/workings as crops and avoid OCR-only logic for notation-heavy content (fractions, long division). Link **Paper 1** (Q1–30) and **Paper 2** (separate Q1–17) via `exam_id` when bundled in one PDF.

### Science

- **Extraction approach:** OAS-first for MCQ (single high-yield call), then standard per-question extraction for open-ended pages.
- **Implementation focus:** Keep printed diagrams with question crops; support sentence-level answer extraction and mark-number reading.

### English

- **Extraction approach:** Most heterogeneous subject; support multiple `question_type` forms in one exam and link two PDFs via `exam_id`.
- **Implementation focus:** Prioritize cover-page metadata, OAS fallback logic, rubric-score capture for compositions, and `teacher_feedback` extraction for qualitative comments.

### Chinese

- **Extraction approach:** Link **question booklet, answer booklet, and OAS** (however many files the scan produced) via `exam_id`; use OAS for Q1–Q25 then extract written sections from answer booklet pages.
- **Implementation focus:** Handle inline MCQ, dialogue-completion, bilingual prompts, grid-paper composition, and point-level marking (0.5/1) in open-ended answers.

### Higher Chinese

- **Data model note:** Represent as `subject='chinese'` + `chinese_variant='higher'` (no separate subject value).
- **Extraction approach:** Link **question + answer booklets** (however many files); **no OAS** — handwriting extraction for every Paper 2 item.
- **Implementation focus:** Handle highest handwriting density, table-cell answers, constrained character-limit summaries, and finer-grained teacher correction signals.

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

1. **Registry-first intake** — ingest from `pdf_file_manager` `main` files (instead of ad-hoc upload), create `documents` rows with prefilled metadata (`subject`, `doc_type`, template/completion context, grouping hints).
2. **Page materialization** — render pages with PyMuPDF and persist `pages` records + page assets.
3. **Cover/page score prefill** — extract cover metadata and page score boxes where present; leave null where not present.
4. **Review-first question creation** — manual question boundaries + core fields (question number, marks, outcome) in a lightweight review UI.

This gives a reliable baseline: reviewable question objects linked to source documents/pages, with enough confirmed data to start diagnostics and skill tracking.

### Tier 2 — Reduces manual effort

5. **Vision-LLM structure prefill** — prefill question boundaries, numbering, and mark allocations for review.
6. **Vision-LLM outcome prefill** — prefill per-question outcome/marks/answers from ticks, score marks, and corrections.
7. **Skill/error suggestion assist** — propose `skill_tags` and (for wrong/partial) `error_tags`; reviewer confirms edits. (For **marking_result.v1.x** GoodNotes outputs, follow subject-specific `skill_tags` rules in [L4_MARKING_RESULT_ARTIFACT](./L4_MARKING_RESULT_ARTIFACT.md) / mark-goodnote-completion skill — not the loose slug style used on question-index drafts.)

### Tier 3 — Progressive automation

8. **Template/layout reuse** — reuse known layouts for repeated formats (school/paper patterns) to reduce review time.
9. **Batch runs from registry subsets** — process selected cohorts (for example by `doc_type`, subject, student, exam group) with review queues.
10. **Coverage expansion** — extend from scored exam papers to unscored practice/books where useful for question-bank and planner retrieval.

**Phase 1 target (updated):**
- Confirm a production-like path for **multi-student, mixed document types** (scored + unscored) from registry to reviewed question objects.
- Prioritize high-signal exam/WA material first, then expand to worksheets/books for retrieval coverage.
- Deliver enough confirmed question objects across Math/Science/English/Chinese (including Higher Chinese variant) for the Diagnostic Engine and Planner to produce useful outputs.

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

1. **Multi-document exam linking UX.** English often uses 2 PDFs per exam. **Standard** Chinese Language papers may bundle **question booklet + answer booklet + OAS** in one file or split them; Higher Chinese uses separate booklets with no OAS. Should the upload UI auto-detect that files belong to the same exam (matching child + date + subject), or should Jarod explicitly group them? Auto-detection risks false matches; explicit grouping adds friction. A pragmatic middle ground: default to explicit grouping, with a "suggest matches" feature that highlights likely groups.
2. **Review UI design.** Key interactions: view page images, see overlaid question boundaries, edit marks/tags, approve/reject per question. Should this be part of the main dashboard or a dedicated ingestion tool? Given the amount of time Jarod will spend here in Phase 1, it deserves thoughtful UX.
3. **Green correction layer.** Green ink workings (from review sessions with Jarod) appear in Math, Chinese, and Higher Chinese papers. They represent "what Winston learned after the initial attempt." Should corrections be a field on the question object, a separate `correction_attempts` table, or a second question object linked to the original? The choice affects how we track learning progression over time.
4. **Composition transcription depth.** Multi-page handwritten compositions (English, Chinese, Higher Chinese) are hard to transcribe accurately. For diagnostics, do we need full text (expensive) or just score + rubric dimensions + teacher corrections (cheaper)? Grid-paper compositions (Chinese/HC) may be easier to transcribe than English free-form. Decision: start with score-only for MVP, add transcription as a Tier 3 feature.
5. **Student annotations.** Winston annotates Science papers ("changed var", "measured var") and English comprehension passages (underlining, vocabulary notes). These are thinking traces but don't fit the question object model. Ignore for MVP, or capture as `student_annotations` free text?

### Skill graph

6. **Chinese/Higher Chinese: shared or separate skill graphs?** HC tests the same domains (vocabulary, comprehension, composition) at higher difficulty. Options: (a) one skill graph with difficulty metadata per question, (b) separate skill nodes for standard/higher. This affects mastery computation — an HC comprehension miss is a weaker weakness signal than a Standard Chinese miss on the same skill.
7. **Chinese skill taxonomy granularity.** Chinese skills span pinyin (pronunciation), vocabulary (词语), grammar (语法), comprehension (阅读理解), and composition (写作). The graph needs Chinese-language skill names mapped to MOE syllabus standards. How granular? (e.g., distinguish 量词 from 关联词 from 词语运用)

### Extraction accuracy

8. **Teacher feedback extraction reliability.** Qualitative teacher comments are the highest-value diagnostic data across subjects: "too general" / "use evidence" (English), circled wrong characters (Chinese), full model answers in red parentheses (Higher Chinese). How reliably can Gemini Flash extract these handwritten margin notes? Start manual-first for MVP, or attempt automatic extraction from day one? A small accuracy benchmark on 5–10 papers would answer this.
9. **Higher Chinese handwriting extraction.** HC is the most handwriting-dense exam — every one of 23 questions produces handwritten Chinese, from single characters to full paragraphs, all overlaid with teacher corrections. Should HC be the last subject to automate extraction (after Math/Science where accuracy is more tractable)?

### Logistics

10. **Drive folder structure.** How are PDFs currently organized? By child? Subject? Date? Mixed? Determines how much metadata can be inferred vs. manually entered at upload.
11. **Paper template reuse.** All sample papers are from St. Gabriel's. Do WA papers from the same school reuse layouts term after term? If so, template recognition could skip LLM calls for known formats after the first paper.

### Resolved

- ~~**Do Chinese papers use OAS?**~~ **Yes.** **Standard** Chinese Language uses OAS for Q1–Q25 (25 MCQ). The OAS may be bundled with the answer booklet or scanned separately — **page index is not fixed**. **Higher Chinese does not use OAS** — all answers are written.
- ~~**Does Higher Chinese follow the same structure as Standard Chinese?**~~ **No.** HC has no MCQ, no OAS, fewer total marks (100 vs 130), and fundamentally different question types (word-bank cloze, error correction, synonym matching, table comparison, phrase explanation).

---

## Utilities

Pre-processing utilities that prepare raw PDFs for ingestion. Each such utility lives in its own subfolder under `ai_study_buddy/utils/` and has a `SPEC.md` there. The PDF registry tool (`pdf_file_manager`) lives at the `ai_study_buddy` top level — see [PDF File Manager](#pdf-file-manager-pdf_file_manager) below.

### Utility 1: PDF Compressor (`compress_pdf`)

**Location:** [`utils/compress_pdf/`](../utils/compress_pdf/) — `compress_pdf.py` + [`SPEC.md`](../utils/compress_pdf/SPEC.md)

**Purpose:** Reduce storage size of raw scanned PDFs before ingestion. Raw scans from mobile scanning apps can be 5–25 MB per paper. Targets 150 DPI / JPEG quality 72 (matching Ghostscript `/ebook`), preserving RGB color for teacher annotation layers.

**Benchmarks:** Science 5.6 MB → 1.5 MB (3.6×) · English 23.4 MB → 2.9 MB (8.1×)

```bash
python compress_pdf.py abc.pdf              # → _c_abc.pdf next to input
python compress_pdf.py --batch /path/       # → compress all PDFs in directory
```

### PDF File Manager (`pdf_file_manager`)

**Location:** [`pdf_file_manager/`](../pdf_file_manager/) — `pdf_file_manager.py` + [`README.md`](../pdf_file_manager/README.md), [`SPEC.md`](../pdf_file_manager/SPEC.md), and supporting docs (ARCHITECTURE, TESTING, DECISIONS, CHANGELOG).

**Purpose:** Keeps a SQLite registry of PDF files in the study archive. Tracks exams, worksheets, books, activities, notes, and templates (with optional completed variants), and keeps on-disk paths and database records in sync. Supports scan roots (for example Google Drive folders), scan/discovery (direct `*.pdf` children per root), optional compression via `compress_pdf`, classification (`doc_type`, `subject`, metadata including `chinese_variant`), exam/book grouping, and template/completion linking. The ingestion pipeline consumes `main` files from this registry. All state-changing operations are recorded in an append-only operation log.

**Machine interface:** Use the Python API (`PdfFileManager`) as the structured interface for agents and automations.

**CLI status:** The built-in CLI has been removed. Use the Python API directly.

See the [README](../pdf_file_manager/README.md) and [SPEC](../pdf_file_manager/SPEC.md) for the current Python contract.
