# AI Study Buddy — Singapore Primary Exam Formats & Visual Structure

> Status: **Exploratory** — background/reference material for ingestion and diagnostics.
>
> Related docs: [DATA_STRATEGY](./L3_DATA_STRATEGY.md), [INGESTION_PIPELINE](./L4_INGESTION_PIPELINE.md).

---

## Scope

This document is a **high-level** overview: how papers differ across subjects at a glance, and where to find **per-subject** exam-format notes (structure, visuals, scoring signals, pipeline implications).

**Default focus (subject understandings):** **Standard** (mainstream) **Mathematics** and **Science** — i.e. not Foundation Mathematics / Foundation Science unless you add separate notes later. SEAB lists Standard vs Foundation as different syllabus codes; see [PSLE formats examined](https://www.seab.gov.sg/psle/psle-formats-examined-in-2026/). **Math and Science national formats changed from 2026**; **school prelims** are often still **past-year–style** papers, so their **question counts and mark splits** may lag the current SEAB PDFs until schools update their sets.

Detailed write-ups live under `context/subject_understandings/`:

| Subject | Detailed understanding |
|---------|------------------------|
| Math | [math_exam_format.md](../context/subject_understandings/singapore_primary_math/math_exam_format.md) |
| Science | [science_exam_format.md](../context/subject_understandings/singapore_primary_science/science_exam_format.md) |
| English | [english_exam_format.md](../context/subject_understandings/singapore_primary_english/english_exam_format.md) |
| Chinese (Standard) | [chinese_exam_format.md](../context/subject_understandings/singapore_primary_chinese/chinese_exam_format.md) |
| Higher Chinese | [higher_chinese_exam_format.md](../context/subject_understandings/singapore_primary_chinese/higher_chinese_exam_format.md) |

SEAB also publishes **Foundation Chinese Language** (Foundation MT track) as its own syllabus — not documented in these notes yet; do not confuse with “Standard” 华文 above. See [PSLE formats examined](https://www.seab.gov.sg/psle/psle-formats-examined-in-2026/).

---

## What the worksheets actually look like (summary)

Observations are drawn from real samples across core subjects, including **Standard** and **Higher** Chinese — from Winston's P5 and P6 exams and weighted assessments at St. Gabriel's Primary School.

- **Math (PSLE, SEAB from 2026):** **Paper 1** = Booklet A (10×1 + 8×2 MCQ) + Booklet B (12×2 short answer) = **50**; **Paper 2** = 5×2 + structured/long-answer block = **50**; **100** total, **2 h 30 min**. Older school prelims often showed **45 + 55**. See [math_exam_format.md](../context/subject_understandings/singapore_primary_math/math_exam_format.md).
- **Science (PSLE, SEAB from 2026):** Booklet A **30** MCQ × 2 = **60**; Booklet B **10–11** structured OE = **40**; **100** marks; **1 h 45 min**. Older samples may show **28** MCQ. See [science_exam_format.md](../context/subject_understandings/singapore_primary_science/science_exam_format.md).
- **English (PSLE):** **200** marks total (P1 50 + P2 90 + Listening 20 + Oral 40); **Paper 1** situational + continuous writing; **Paper 2** Booklet A (25 MCQ) + Booklet B (65 OE). See [english_exam_format.md](../context/subject_understandings/singapore_primary_english/english_exam_format.md).
- **Chinese (Standard):** Full PSLE **200** marks (试卷一 40 + 试卷二 90 + 口试 50 + 听力 20); scanned workbooks usually show **written 130** only (试卷一+二). Paper 2 blueprint: **40** items / **90** marks (SEAB). See [chinese_exam_format.md](../context/subject_understandings/singapore_primary_chinese/chinese_exam_format.md).
- **Higher Chinese:** Paper 1 composition; Paper 2 **no MCQ/OAS** — all handwritten; **100 marks**. See [higher_chinese_exam_format.md](../context/subject_understandings/singapore_primary_chinese/higher_chinese_exam_format.md).

---

## Cross-subject comparison

| Dimension | Math | Science | English | Chinese (Standard) | Higher Chinese |
|-----------|------|---------|---------|---------------------|----------------|
| Pages per exam | **Varies** by school/paper (not canonical) | **Varies** by school/paper (not canonical) | **Varies** by school/paper (not canonical) | **Varies** by school/paper (not canonical) | **Varies** by school/paper (not canonical) |
| Total marks | **100** (50 + 50) SEAB 2026; older prelims often 45 + 55 | **100** (60 + 40) SEAB 2026; older prelims may differ | **200** PSLE (50 + 90 + 20 + 40); written bundle **140** | **200** full PSLE; **130** written (40 + 90) | 100 (40 + 60) |
| Question types | MCQ (P1A + OAS), short answer (P1B), structured/long (P2) | MCQ (**30** + OAS), structured OE (Booklet B) | MCQ, cloze, editing, transformation, comprehension, **composition**; + listening/oral papers | MCQ, **inline cloze**, dialogue completion, open-ended, **grid-paper composition**; + oral/listening | 综合填空, 字词改正, comprehension OE, **grid-paper composition** |
| Handwriting density | Light (MCQ) to very heavy (P2) | Light (MCQ) to moderate (OE) | Light (MCQ/cloze) to very heavy (composition) | Light (MCQ) to heavy (open-ended + grid-paper composition) | **Very heavy** — every answer is handwritten |
| Answer format | OAS + "Ans:" / workings + `[n]` mark tags (P2) | OAS bubbles + written sentences | OAS + word-in-box + sentence rewriting + multi-page essays | OAS + numbers-in-boxes + paragraph answers + **grid-paper composition** | **No OAS.** Numbers/characters in boxes + paragraph answers + **grid-paper composition** |
| Diagrams | Printed (P1A); student models + printed (P1B/P2) | Printed (experiments, graphs) | Printed (comic strips, visual texts) | Printed (visual text: notice/poster) — minimal | None — pure text passages |
| Scoring | OAS ticks + page boxes + bracket marks | OAS ticks + mark numbers + page score boxes | **Rubric-based** (composition) + per-item (language sections) + per-section score boxes | **Rubric-based** (composition 内容+表达) + point-marking (0.5/1) on open-ended + per-section 得分 boxes | **Rubric-based** (composition) + per-section circled scores + **0.5 granularity** point-marking on comprehension |
| Teacher feedback | Ticks/crosses, method marks | Mark numbers in red | **Qualitative comments** ("too general", "use evidence") + grammar corrections in colored ink | **Character-level corrections** (circled wrong characters) + point-marking (0.5/1) + brief margin notes | **Extensive**: red model answers in parentheses + green corrections + point annotations (表情 etc.) + character-level corrections on composition |
| Diagnostic value of cover page | P1 / P2 breakdown + total | Section breakdown (BA/BB) | **Full 9-section skill-level breakdown** | MCQ/written split (Q1–25 vs Q26–40) + Paper 1 rubric (内容+表达) | Paper 2: total only (out of 60). Paper 1: rubric (内容+表达) |

---

## Implications for extraction

Moved to [L4_INGESTION_PIPELINE](./L4_INGESTION_PIPELINE.md) so implications are maintained directly alongside implementation flow and pipeline step design.
