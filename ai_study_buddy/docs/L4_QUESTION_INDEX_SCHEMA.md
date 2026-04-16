# AI Study Buddy — Unit Question Index Schema

> Status: **Proposal (v2)** — per-template question index produced by a vision LLM in a single pass.
>
> Supersedes: v1 proposal (question_splitter-first, three-level maturity model). Legacy splitter code: `archive/question_splitter/`.
>
> Related docs: [ARCHITECTURE](./L1_ARCHITECTURE.md) (question as atomic unit), [DATA_STRATEGY](./L3_DATA_STRATEGY.md) (question objects, shared stimuli, embeddings), [INGESTION_PIPELINE](./L4_INGESTION_PIPELINE.md) (pipeline steps that produce and consume question objects), [EXAM_FORMATS](./L3_EXAM_FORMATS.md) (subject-specific structures).

---

## Why This Artifact Exists

There is a gap between what the system stores and what downstream components need:

1. **Template PDFs on disk** — the `pdf_file_manager` registry tracks scanned book units, worksheets, and exam booklets as registered PDF files with metadata, group membership, and answer mappings.
2. **Question objects in Postgres** — the `L4_INGESTION_PIPELINE` schema defines `question_objects` rows with text, marks, outcomes, skill tags, and embeddings.

Nothing currently bridges these two layers. The registry knows which files exist and how they relate to each other, but not what questions are inside them. The Postgres schema expects fully enriched, student-specific rows. The missing piece is a **per-template question index** that:

- records where every question lives in a unit PDF (page regions, bounding boxes)
- identifies structural features (sections, multi-part questions with sub-parts)
- captures semantic content (question text, type, marks, skills, answer text)
- provides the `embedding_text` that feeds into pgvector
- is reused across every student attempt and every marking/ingestion run on that template

This is the `unit_question_index`.

---

## Architectural Decision: Vision LLM, Not Deterministic Splitting

The v1 proposal assumed a two-stage pipeline: a deterministic `question_splitter` (Tesseract OCR + regex heuristics) produces structural boundaries at zero AI cost, then a vision LLM enriches those boundaries with semantic content. A pilot test on the 2023 PSLE Science exam papers (see [Pilot](#pilot-2023-psle-science-exam)) invalidated this approach.

### Why deterministic splitting fails

Exam papers and worksheets are unstructured in practice. Different publishers, schools, and exam boards use different layouts, numbering conventions, fonts, and print quality. A regex-and-heuristic approach chases these variations forever:

- **Cover page false positives.** Numbered instruction lists ("1. Write your Index No...", "2. Do not turn over this page...") are indistinguishable from question markers to OCR+regex. In the pilot, this caused Q1–Q5 of Booklet A to be completely missed.
- **Missed questions.** OCR failed to detect Q11 and Q37 — ordinary questions on well-scanned pages — because font weight, spacing, or scan artifacts didn't match the marker regex.
- **STEM over-assignment.** Exam instruction text ("For questions 29 to 40, write your answers in this booklet") matched the shared-stimulus regex and generated bogus STEM entries for every question.
- **No sub-part detection.** Open-ended questions with individually gradeable sub-parts like Q29(a) `[1]`, Q29(b) `[1]` were grouped under the parent question number.

Each of these could be patched, but the fundamental problem is structural: deterministic heuristics cannot robustly handle the variation across hundreds of different worksheets, exam papers, and practice books. Pursuing this path would be a never-ending edge-case debugging exercise.

### Why vision LLM is the right approach

A vision LLM (e.g., Gemini Flash) can look at page images and understand layout, numbering, sub-parts, mark allocations, diagrams, and instruction text in a single pass. It handles variation naturally because it understands the *meaning* of what it sees, not just pattern matches on OCR text.

The cost concern that motivated the deterministic approach dissolves under scrutiny: index generation is a **per-template, one-time** operation. Each template is processed once, then the index is reused for every student attempt. At Gemini Flash pricing, processing a 16-page exam booklet costs roughly $0.01–0.02. This is negligible compared to the per-student marking costs that the index is designed to reduce.

### What this means for the pipeline

- The template inspection pass goes from "not existing" to "generated" — no structural/enriched distinction.
- The `question_splitter` tool (archived under `archive/question_splitter/`) is not part of this pipeline. It may remain useful for other purposes (quick visual previews, page thumbnails) but is not a dependency of the question index.
- Two independent status fields track progress:
  - `review_status`: `"unreviewed"` → `"verified"` (template structure has been human-reviewed)
  - `has_answers`: `false` → `true` (answer enrichment pass has been run)
  
  These are orthogonal — review and answer enrichment can happen in either order.

---

## Who Consumes It

Every downstream component needs question-level data, but in different forms. The index is the common source.

| Consumer | What it reads from the index | When |
|----------|------|------|
| **Marking pipeline** | Question boundaries + answer regions → crop student answers, compare against answer crops | Per marking request |
| **Ingestion pipeline** | Question boundaries → locate per-question teacher marks on scored papers | Per scored paper |
| **Content Service** | `embedding_text` → generate pgvector embeddings for semantic retrieval | Once per template |
| **Tutor Agent** | Question crop + answer text + skill tags → show question, check answers, find similar practice | Per tutoring session |
| **Diagnostic Engine** | Skill tags + question type → aggregate per-skill outcomes across attempts | Continuous |
| **Planner Service** | Skill-tagged questions → assign practice from question bank | Weekly/daily planning |
| **Review UI** | Bounding boxes + extracted text → overlay for human correction | During review |

---

## Index Lifecycle

```
1. Template generation (vision LLM, per-template, once)
   ├── Input:  registered template PDF only
   ├── Tool:   vision LLM (e.g. Gemini Flash) on page images
   ├── Output: unit_question_index.json (review_status: "unreviewed", has_answers: false)
   │           All answer fields are null (answer_text, mcq_correct)
   │           + question crops
   └── Cost:   ~$0.01–0.03 per template (one-time, amortized across all students)

After step 1, the following can happen in either order:

2. Answer enrichment (when answer file is available)
   ├── Input:  index + answer file + page range (from book_answer_mapping)
   ├── Tool:   vision LLM on answer pages, matching by question number
   ├── Output: updated index (has_answers: true)
   │           answer_text, mcq_correct populated
   └── Note:   optional — some templates have no answer key

3. Human review (strongly recommended — see "Review Tool" section below)
   ├── Input:  index + template PDF
   ├── Tool:   question_area_review.py (local web UI: bbox overlay, drag-to-adjust, keyboard-driven)
   ├── Output: reviewed index (review_status: "verified", per-question review_status)
   └── Cost:   ~5 min per template of reviewer time

4. Per-student instantiation (not part of the index)
   ├── Input:  index + student's attempt PDF
   ├── Tool:   marking pipeline or ingestion pipeline
   ├── Output: question_objects rows in Postgres
   └── When:   per student attempt
```

Steps 2 and 3 are independent. The template can be reviewed before answers are added (1→3→2→4), or answers can be added before review (1→2→3→4). Review checks template structure (bboxes, question text, marks); answer enrichment populates answer fields from a separate file. Neither blocks the other.

---

## Schema

### Top level

```json
{
  "schema_version": "3.0",
  "review_status": "unreviewed",
  "has_answers": false,

  "unit_file_id": "file_template_456",
  "unit_file_path": "/.../DaydreamEdu/.../_c_Science Thematic Tests ... - 01 Systems Thematic Test 1.pdf",
  "unit_label": "01 Systems Thematic Test 1",

  "book_group_id": "book_group_789",
  "book_label": "Science Thematic Tests and Exam Practice Primary 4",
  "subject": "science",
  "grade": "p4",

  "answer_file_id": "file_answer_999",
  "answer_file_path": "/.../DaydreamEdu/.../_c_Science Thematic Tests ... - 12 Answers.pdf",
  "answer_page_start": 1,
  "answer_page_end": 2,
  "starts_mid_page": false,
  "ends_mid_page": false,

  "page_count": 8,
  "content_pages": [2, 3, 4, 5, 6, 7, 8],
  "excluded_pages": [1],
  "total_questions": 30,
  "total_marks": 50,

  "exam_context": null,

  "sections": [ ... ],
  "stimulus_blocks": [ ... ],
  "questions": [ ... ],

  "provenance": { ... }
}
```

**Answer fields** (`answer_file_id`, `answer_file_path`, `answer_page_start`, `answer_page_end`) are all null after template generation (step 1). They are populated during answer enrichment (step 2) when the answer file is available and mapped.

**Other top-level fields:**

| Field | Type | Description |
|-------|------|-------------|
| `review_status` | string | `unreviewed` (not yet reviewed) or `verified` (template structure human-reviewed). Tracks template review only, not answers |
| `has_answers` | boolean | `false` after template generation, `true` after answer enrichment |
| `content_pages` | array of int | Pages that contain questions (1-indexed). Excludes covers, blanks, instruction-only pages. |
| `excluded_pages` | array of int | Pages deliberately skipped (covers, blanks). For auditability. |
| `exam_context` | object or null | Links this index to a multi-booklet exam. Null for standalone book units. See [Multi-booklet exams](#multi-booklet-exams). |

### Multi-booklet exams

For exams split across multiple physical booklets (e.g., PSLE Science Booklet A + Booklet B), each booklet gets its own index. The `exam_context` field captures the cross-booklet relationship.

```json
{
  "exam_context": {
    "exam_group_id": "exam_group_psle_2023_science",
    "exam_label": "2023 PSLE Science",
    "booklet_label": "Booklet A",
    "numbering_continues_from": null,
    "numbering_continues_to": "booklet_b_file_id"
  }
}
```

This is optional. Practice book units and standalone worksheets set `exam_context: null`.

### Sections

Sections model the major divisions within a unit where question numbering or format changes. The `number_restart` flag is critical for units where MCQ Q1–Q10 is followed by open-ended Q1(a)–Q8(b) with restarted numbering.

```json
{
  "sections": [
    {
      "section_id": "sec_mcq",
      "label": "Multiple Choice",
      "section_type": "mcq",
      "number_restart": true,
      "marks_per_question": 2,
      "question_ids": ["q1", "q2", "q10"]
    },
    {
      "section_id": "sec_oe",
      "label": "Open-ended",
      "section_type": "open_ended",
      "number_restart": true,
      "marks_per_question": null,
      "question_ids": ["q1_oe", "q2_oe", "q3_oe"]
    }
  ]
}
```

### Stimulus blocks

Shared visual/textual context used by **multiple questions**. Each block is cropped and stored once, then linked to its dependent questions.

**Separation rule:** Only create a stimulus block when the material is shared by two or more **questions** (different question numbers). If a diagram, table, or passage accompanies a single question — even a multi-part question with sub-parts that all reference it — it is part of that question's `prompt_regions`. Do not create a stimulus block for material that is internal to one question.

This keeps the model simple: a stimulus block always means "this context is shared across different questions." In the 2023 PSLE pilot, every diagram/table was either internal to one question or shared across sub-parts of the same question. The result: zero stimulus blocks needed for science/math. Stimulus blocks become important for English/Chinese comprehension, where a passage is shared across multiple independently numbered questions.

```json
{
  "stimulus_blocks": [
    {
      "block_id": "stim_passage_q66_q75",
      "block_type": "passage",
      "label": "Reading comprehension passage: The Lost Garden",
      "summary": "A story about a boy who discovers an abandoned garden behind his grandmother's house",
      "section_id": "sec_comprehension",
      "regions": [
        { "page": 4, "bbox": [0.05, 0.0, 0.95, 0.65] }
      ],
      "printed_text": null,
      "crop_path": "crops/stim_passage_q66_q75.png",
      "linked_question_ids": ["q66", "q67", "q68", "q69", "q70", "q71", "q72", "q73", "q74", "q75"]
    }
  ]
}
```

The `summary` field is a one-line description of the stimulus content, generated by the vision LLM during index generation. It is used to construct `embedding_text` for questions that depend on this stimulus (see [Embedding text construction](#embedding-text-construction)).

Supported `block_type` values:

| `block_type` | Description | Primary subjects |
|------|-------------|------|
| `instruction` | Shared instruction referencing specific questions (e.g. "Refer to the table below for Questions 4 and 5") | Math, Science |
| `passage` | Comprehension passage | English, Chinese |
| `visual_text` | Poster, notice, flyer, dialogue | English, Chinese |
| `cloze_passage` | Passage with blanks | English, Chinese |
| `diagram` | Experiment setup, chart, graph, table | Science |
| `table` | Data table | Science, Math |

### Questions

The core array. Each entry represents one **question** — the printed question number (Q1, Q33, Q40). Multi-part questions contain a `sub_parts` array; single-part questions have `sub_parts: []`.

The atomic unit is the question, not the sub-part. Sub-parts are internal structure for marking granularity. This eliminates the need for `parent_question_id` and simplifies stimulus handling — all diagrams/tables within a question are part of its `prompt_regions`, and `stimulus_blocks` only exist for material shared across different questions (rare for science/math).

```json
{
  "questions": [
    {
      "question_id": "q1",
      "display_label": "Q1",
      "question_number": "1",
      "section_id": "sec_mcq",

      "prompt_regions": [
        { "page": 2, "bbox": [0.05, 0.12, 0.95, 0.28] }
      ],

      "question_type": "mcq",
      "max_marks": 2,
      "is_multi_part": false,
      "sub_parts": [],

      "printed_question_text": "Which of the following plants has a weak stem and climbs to reach sunlight?",
      "mcq_options": ["Bougainvillea", "Morning glory", "Rain tree", "Hibiscus"],
      "mcq_correct": 2,
      "answer_text": "(2)",
      "skill_tags": ["plant_systems", "weak_stems", "support_and_climbing"],
      "embedding_text": "Tests understanding of plants with weak stems that need support to climb. The student must choose which listed plant climbs to reach sunlight. Options contrast a climber (morning glory) with non-climbing plants such as bougainvillea, rain tree, and hibiscus.",

      "question_crop_path": "crops/q1_prompt.png",

      "extraction_method": "vision_llm_gemini_flash",
      "review_status": "unreviewed"
    },
    {
      "question_id": "q33",
      "display_label": "Q33",
      "question_number": "33",
      "section_id": "sec_oe",

      "prompt_regions": [
        { "page": 5, "bbox": [0.05, 0.04, 0.95, 0.72] }
      ],

      "question_type": "open_ended",
      "max_marks": 3,
      "is_multi_part": true,
      "sub_parts": [
        {
          "sub_part_id": "q33a",
          "sub_part_label": "(a)",
          "max_marks": 1,
          "printed_question_text": "State one similarity between the two leaves.",
          "answer_text": "Both have jagged edges.",
          "skill_tags": ["classification", "similarities_and_differences"]
        },
        {
          "sub_part_id": "q33b",
          "sub_part_label": "(b)",
          "max_marks": 1,
          "printed_question_text": "Based on the graph, what is the temperature at point X?",
          "answer_text": "30 degrees Celsius",
          "skill_tags": ["interpreting_graphs", "heat_energy"]
        },
        {
          "sub_part_id": "q33c",
          "sub_part_label": "(c)",
          "max_marks": 1,
          "printed_question_text": "Explain why the metal spoon felt hot.",
          "answer_text": "Heat was conducted from the hot water through the metal spoon.",
          "skill_tags": ["heat_transfer", "conduction"]
        }
      ],

      "printed_question_text": "Study the information below and answer the questions.",
      "answer_text": null,
      "skill_tags": ["heat_energy", "interpreting_graphs", "heat_transfer", "conduction"],
      "embedding_text": "Multi-part science question using a shared visual prompt. Part (a) asks for a similarity between two leaves, testing comparison and classification. Part (b) asks the student to read a graph to identify the temperature at point X. Part (c) asks for an explanation of why a metal spoon became hot, testing heat transfer by conduction.",

      "question_crop_path": "crops/q33_prompt.png",

      "extraction_method": "vision_llm_gemini_flash",
      "review_status": "unreviewed"
    }
  ]
}
```

#### Field reference

**Identity fields:**

| Field | Type | Description |
|-------|------|-------------|
| `question_id` | string | Stable machine-safe ID, unique within the index: `q1`, `q33`, `q40` |
| `display_label` | string | Human-readable label: `Q1`, `Q33`, `Q40` |
| `question_number` | string | The printed question number: `1`, `33`, `40` |
| `section_id` | string | Which section this question belongs to |

**Region fields:**

| Field | Type | Description |
|-------|------|-------------|
| `prompt_regions` | array | Where the question (including all sub-parts and diagrams) appears in the template PDF. Each entry: `{page, bbox}` where bbox is `[x1, y1, x2, y2]` as fractions of page dimensions (0.0–1.0) |

**Structure fields:**

| Field | Type | Description |
|-------|------|-------------|
| `question_type` | string | `mcq`, `short_answer`, `open_ended`, `cloze`, `editing`, `synthesis`, `composition` |
| `max_marks` | integer | Total mark allocation for this question. For multi-part questions, equals the sum of sub-part marks |
| `is_multi_part` | boolean | `true` when the question has individually gradeable sub-parts |
| `sub_parts` | array | Sub-part entries (see below). Empty array for single-part questions |

**Semantic fields:**

| Field | Type | Description |
|-------|------|-------------|
| `printed_question_text` | string | Faithful extraction of the printed lead-in or full question text. For multi-part questions, this is the shared preamble (e.g., "Study the information below") |
| `mcq_options` | array or null | MCQ option texts, in order. Only for single-part MCQ questions |
| `mcq_correct` | integer or null | Correct MCQ option number (1-indexed). Populated during answer enrichment |
| `answer_text` | string or null | The official answer. Populated during answer enrichment. For multi-part questions, null (answers are per-sub-part) |
| `skill_tags` | array of strings | AI-proposed skill/concept tags. For multi-part questions, the union across sub-parts |
| `embedding_text` | string | Retrieval-oriented semantic description generated by the vision LLM for pgvector embedding. It may paraphrase the question, summarize visual givens, and state the concept being tested without revealing the answer (see [Embedding text construction](#embedding-text-construction)) |

**Asset fields:**

| Field | Type | Description |
|-------|------|-------------|
| `question_crop_path` | string or null | Path to the cropped question image (entire question including all sub-parts), relative to the index directory |

**Provenance fields:**

| Field | Type | Description |
|-------|------|-------------|
| `extraction_method` | string | How all fields were produced: `vision_llm_gemini_flash`, `manual` |
| `review_status` | string | `unreviewed`, `accepted`, `corrected` |

#### Sub-part schema

Each entry in `sub_parts` represents one individually gradeable sub-part within a multi-part question. Sub-parts do not have their own regions, crop paths, or embedding text — those belong to the parent question.

| Field | Type | Description |
|-------|------|-------------|
| `sub_part_id` | string | Stable ID: `q33a`, `q33b`, `q40b_ii` |
| `sub_part_label` | string | Printed label: `(a)`, `(b)`, `(c)(ii)` |
| `max_marks` | integer | Mark allocation for this sub-part |
| `printed_question_text` | string | The sub-part's question text |
| `answer_text` | string or null | The official answer for this sub-part |
| `skill_tags` | array of strings | Skill/concept tags specific to this sub-part |

### Provenance (index-level)

```json
{
  "provenance": {
    "created_at": "2026-04-10T15:30:00Z",
    "updated_at": "2026-04-10T16:00:00Z",
    "generation_source": {
      "model": "gemini-2.5-flash",
      "run_id": "gen_20260410_001",
      "pages_processed": 8,
      "pages_excluded": [1],
      "questions_extracted": 30,
      "estimated_cost_usd": 0.015
    }
  }
}
```

---

## Embedding Text Construction

The `embedding_text` field is a retrieval-oriented semantic description of the question. Unlike `printed_question_text`, it is not required to be a faithful copy of the page. It is generated by the vision LLM from the question crop and should describe:

- what information is provided
- what the student is asked to do
- what concept or skill is being tested
- any important visual context (diagram, table, graph, geometry figure, passage summary)

Its job is to help the Content Service generate embeddings that are useful to downstream consumers such as the Tutor Agent and Planner Service for semantic retrieval, similar-practice matching, and fuzzy natural-language search. It must carry enough meaning to retrieve the right questions, but not so much extra detail that the vector is dominated by noise or answer leakage.

### Principles

1. **Store both forms.** Keep `printed_question_text` as the faithful extraction and `embedding_text` as the retrieval-oriented semantic description.
2. **Describe, don't transcribe.** `embedding_text` may paraphrase the printed question if that produces a better retrieval representation.
3. **Include visual meaning.** If the key information is in a graph, table, diagram, geometry figure, or other visual, describe that visual succinctly.
4. **Name the tested concept in natural language.** It is acceptable for `embedding_text` to say what the question is testing ("interpreting a line graph", "heat transfer by conduction", "comparing plant structures") as long as this is expressed as natural language, not raw taxonomy syntax.
5. **Do not reveal the solution.** `embedding_text` should not contain the final answer or enough detail to give it away.

### Rules per question type

**Standalone question (math, science)**

Summarize the givens, the task, and the concept being tested.

Example (MCQ):
> Tests understanding of plants with weak stems that need support to climb. The student must choose which listed plant climbs to reach sunlight. Options contrast a climber with non-climbing plants.

Example (open-ended, no shared context):
> Describes a falling ball and asks what force acts on it while it falls, testing understanding of gravity.

**Visual question (graph, table, geometry, diagram)**

Describe the relevant visual information and the mathematical/scientific task. The description should mention the type of visual, the key labeled quantities or relationships, and what the student must infer or calculate.

Example:
> Uses a line graph showing how temperature changes over time and asks for the temperature at a marked point, testing graph interpretation.

Example:
> Uses a geometry diagram of a triangle with labeled base and height and asks for the area, testing application of the triangle area formula.

**Question with shared stimulus (comprehension, diagram-based)**

Describe the question together with a short summary of the shared stimulus. Do NOT embed the full passage — it would dominate the vector and make all questions from the same passage look identical.

Example:
> Uses a table comparing plant setups with different numbers of roots and water levels. Asks the student to infer the relationship between number of roots and water absorbed, testing interpretation of experimental results.

The `stimulus_summary` on the stimulus block remains useful as source material for generating `embedding_text`, but the final `embedding_text` should read as a coherent semantic description, not a raw concatenation template.

**Cloze / fill-in-the-blank**

Describe the sentence with the blank, the grammatical or vocabulary choice being tested, and the options if they materially distinguish the task.

Example:
> Fill-in-the-blank grammar question about choosing the correct form of "to be" in a past-tense sentence.

**Composition prompt**

Describe the writing task, genre, audience, and explicit constraints.

Example:
> Situational writing task asking the student to write an email to a friend about a school carnival, including three activities and using email format conventions.

### Generation timing

`embedding_text` is generated during template processing (step 1) from the template pages alone. If answer enrichment later adds `answer_text`, the system may optionally regenerate or refine `embedding_text` using the answer as hidden context to better understand what the question is testing, but the resulting text must still not reveal the answer.

### Why not embed the answer?

The answer text is deliberately excluded from `embedding_text`. Reasons:

1. **Retrieval intent differs.** When the Tutor Agent searches for "questions about plant root water absorption," it wants questions that test that concept — not answers that mention it.
2. **Answer leakage risk.** Embedding answers could surface them through similarity search before the child has attempted the question.
3. **Answer text is available separately.** The `answer_text` field is stored on the question for grading/marking — it doesn't need to be in the embedding.

### Why not embed raw skill tags?

Raw skill tags (`plant_systems > roots > water_absorption`) are structured metadata, not natural-language question meaning. They are better served by exact metadata filtering in the Content Service's hybrid retrieval:

1. **Metadata filter** — `skill_tags CONTAINS 'plant_systems'`
2. **Keyword search** — `"roots"`, `"water absorption"`
3. **Embedding search** — semantic similarity via `embedding_text`

Embedding raw skill-tag strings would conflate structured filtering with semantic search, making both less precise. However, `embedding_text` may still mention the tested concept in natural language when that improves retrieval.

---

## Relationship to Existing Artifacts

### book_answer_mapping → answer enrichment

The registry's `book_answer_mapping` (see [Proposal 07](../pdf_file_manager/docs/proposals/07-book-answer-mapping.md)) provides the unit-level answer file and page range. The answer enrichment pass (step 2 of the lifecycle) uses this mapping to inspect the answer pages and populate per-question `answer_text` and `mcq_correct`.

This is decoupled from template generation. The index can exist and be useful without answers — the question structure, regions, text, marks, and skill tags all come from the template alone. Answer enrichment happens when (and if) the answer file is available and mapped.

### resolve_marking_context() → loads the index

The marking pipeline's `resolve_marking_context()` (in `ai_study_buddy/marking/context_resolver.py`) currently returns file-level context: attempt file, template file, answer file, answer page range, and question selection.

With the index available, the resolver (or a subsequent step) can also load the `unit_question_index.json` and resolve `question_selection` to specific `question_id` entries. The marking pipeline then uses the resolved question regions to crop student answers and compare them against answer regions — without re-discovering question boundaries each time.

### question_objects table (Postgres)

The `question_objects` table defined in `L4_INGESTION_PIPELINE.md` is the per-student, per-attempt destination. The index is the template that the ingestion pipeline uses to create these rows:

- `question_objects.question_number` ← `questions[].question_number`
- `question_objects.section` ← `sections[].label`
- `question_objects.question_type` ← `questions[].question_type`
- `question_objects.max_marks` ← `questions[].max_marks`
- `question_objects.question_text` ← `questions[].printed_question_text`
- `question_objects.skill_tags` ← `questions[].skill_tags`
- `question_objects.bbox` ← `questions[].prompt_regions`
- `question_objects.sub_parts` ← `questions[].sub_parts` (for multi-part questions)

Student-specific fields (`earned_marks`, `outcome`, `child_answer`, `error_tags`, etc.) come from the marking pipeline, not from the index. See [Marking Output Schema](#marking-output-schema).

---

## Where Index Files Live

On-disk location, keyed by registry unit file ID:

```
ai_study_buddy/cache/question_indices/<unit_file_id>/
  unit_question_index.json
  crops/
    q1.png
    q4.png
    q33.png
    ...
```

The `unit_file_id` ties the index to a specific registered template in `pdf_file_manager`. If the template PDF changes (new scan, re-compression), the file ID stays stable and the index can be regenerated.

Crop paths in the index are relative to the index directory.

---

## Production Workflow

### Step 1: Template generation

```
Input:
  - registered template PDF (from pdf_file_manager)

Steps:
  1. Render template PDF pages to images
  2. Send page images to vision LLM with structured output schema
     - LLM identifies: question numbers, sub-parts, mark allocations,
       section boundaries, page regions, diagrams, cover/instruction pages
     - LLM extracts: question text, question type, skill tags
     - LLM constructs: retrieval-oriented embedding_text per question
  3. Assemble vision LLM output into unit_question_index.json
     - All answer fields are null (answer_text, mcq_correct)
  4. Generate question crops from bounding boxes (PyMuPDF render + crop)
  5. Write index + crops to cache directory

Output:
  - unit_question_index.json (review_status: "unreviewed", has_answers: false)
  - crops/ directory with question images

Cost:
  - ~$0.01–0.03 per template (one-time)
  - Amortized across all student attempts on this template
```

The vision LLM prompt is the critical piece. It must handle the full range of document layouts (practice books, worksheets, past-year papers, exam booklets) without per-document customization. The prompt should specify the structured output schema and include examples of different formats, but the LLM's visual understanding — not regex heuristics — is what makes it robust.

### Step 2: Answer enrichment (when available)

```
Input:
  - generated index (from step 1)
  - answer file + page range (from book_answer_mapping)

Steps:
  1. Render answer file pages (within the mapped range) to images
  2. Send answer page images to vision LLM, along with question IDs and
     numbers from the existing index
  3. LLM matches each question to its answer in the answer key
  4. Populate answer_text and mcq_correct on each question
  5. Set has_answers to true

Output:
  - updated unit_question_index.json (has_answers: true)

Note:
  - This step is skipped if no answer file is registered or mapped
  - The index is fully usable without answers for structural tasks
    (review tool, question browsing, embedding generation)
  - Marking can proceed without answers if the marking LLM is given
    the answer pages directly (current workflow)
```

### Using the index for marking

```
1. resolve_marking_context(student, book, unit, question_request)
   → returns: MarkingContext (files, pages, question selection)

2. Load unit_question_index.json for the template

3. Resolve question_selection to specific question_ids
   e.g. "MCQ Q1-10" → [q_mcq_1, q_mcq_2, ..., q_mcq_10]

4. For each resolved question:
   a. Apply prompt_regions to student's GoodNotes PDF → crop student answer
   b. Load answer text from the index (or answer pages directly if not enriched)
   c. Grade: compare student answer vs correct answer
   d. Record: marks, outcome, error tags

5. Generate learning report from structured per-question results
```

### Using the index for ingestion (scored papers)

```
1. For a scored paper (teacher-marked exam), load the matching template's index

2. For each question in the index:
   a. Apply prompt_regions to the scored paper → locate question region
   b. Extract: ticks/crosses, score marks, teacher corrections
   c. Create question_objects row in Postgres

3. Generate pgvector embeddings from embedding_text (once per template, reused)
```

---

## Vision LLM Prompts

### Template processing prompt (step 1)

This prompt is sent along with all page images of the template PDF. The LLM returns structured JSON that becomes the `questions` and `sections` arrays in the index. The prompt asks for both a faithful extraction (`printed_question_text`) and a retrieval-oriented semantic description (`embedding_text`).

```
You are analyzing a scanned exam paper or practice worksheet. You will receive all
pages of the document as images.

Your task is to extract every question from this document and return structured JSON.

## What to identify

1. **Cover/instruction pages.** Pages with student name fields, exam instructions,
   "Do not turn over this page" text, or similar administrative content. These are
   NOT questions — list their page numbers in `excluded_pages`.

2. **Sections.** If the document has distinct sections (e.g., "Section A: Multiple
   Choice", "Section B: Open-ended"), identify each section with its label, type,
   and whether question numbering restarts.

3. **Questions.** Each printed question number (1, 2, 3, ...) is one question entry.
   - For multi-part questions (e.g., Q15 with parts (a), (b), (c)), create ONE
     question entry with `is_multi_part: true` and a `sub_parts` array.
   - For single questions with no sub-parts, set `is_multi_part: false` and
     `sub_parts: []`.

4. **Bounding boxes.** For each question, provide `prompt_regions` — the page and
   fractional bounding box `[x1, y1, x2, y2]` (0.0–1.0) covering the ENTIRE
   question including all sub-parts, diagrams, tables, and options. If a question
   spans two pages, provide two entries in `prompt_regions`.

5. **Mark allocations.** Look for marks in brackets like `[2]`, `[1m]`, or in
   headers like `(56 marks)`. For multi-part questions, extract per-sub-part marks.
   `max_marks` at question level must equal the sum of sub-part marks.

6. **Question type.** Classify each question: `mcq`, `short_answer`, `open_ended`.

## What to extract per question

- `question_id`: stable ID like `q1`, `q2`, `q33`
- `display_label`: human label like `Q1`, `Q33`
- `question_number`: the printed number as a string
- `section_id`: which section this belongs to
- `prompt_regions`: array of `{page, bbox}` entries
- `question_type`: `mcq`, `short_answer`, or `open_ended`
- `max_marks`: total marks for this question
- `is_multi_part`: true if it has sub-parts
- `sub_parts`: array (empty if single-part), each with:
  - `sub_part_id`: e.g., `q33a`, `q40b_ii`
  - `sub_part_label`: e.g., `(a)`, `(b)(ii)`
  - `max_marks`: marks for this sub-part
  - `printed_question_text`: the sub-part's question text
  - `skill_tags`: skill/concept tags specific to this sub-part
- `printed_question_text`: the question text (or lead-in for multi-part), copied faithfully from the page
- `mcq_options`: array of option texts (MCQ only, else null)
- `skill_tags`: skill/concept tags (union of sub-part tags for multi-part)
- `embedding_text`: retrieval-oriented semantic description for vector embedding.
  Describe the information given, the task being asked, important visual context,
  and the concept being tested. This may paraphrase the printed text and should
  read like a concise natural-language summary of what the question is about.

## Important rules

- Do NOT treat cover page numbered instructions as questions.
- Every printed question number must appear exactly once in the output.
- Diagrams and tables that accompany a single question are part of that question's
  `prompt_regions` — do NOT create separate stimulus blocks for them.
- `printed_question_text` should be a faithful extraction; `embedding_text` should
  be a concise semantic description for retrieval.
- For visual questions, include the meaning of the chart/table/diagram/geometry
  figure in `embedding_text`, not just the literal text printed around it.
- You may mention the concept being tested in natural language, but do NOT paste
  raw taxonomy strings such as `heat_transfer > conduction`.
- `answer_text` and `mcq_correct` should be null — answers come from a separate file.
- Do NOT reveal the answer in `embedding_text`.
- `extraction_method` should be set to your model identifier (e.g., "vision_llm_gemini_flash").
- `review_status` should be "unreviewed" for all questions.

## Output format

Return a JSON object with these top-level fields:
- `page_count`, `content_pages`, `excluded_pages`
- `total_questions`, `total_marks`
- `sections` array
- `stimulus_blocks` array (empty for science/math)
- `questions` array
```

### Answer enrichment prompt (step 2)

This prompt is sent along with the answer key page images and the list of questions from the existing index. The LLM returns per-question answers.

```
You are reading the answer key pages for an exam or practice worksheet. You will
receive the answer key pages as images.

Here are the questions that need answers (from the previously generated index):

{question_list}

For each question, extract the correct answer from the answer key pages.

## What to extract

For each question_id, return:
- `answer_text`: the correct answer as printed in the answer key.
  - For MCQ: the option number, e.g., "(2)" or "(4)"
  - For open-ended: the model answer text
  - For multi-part questions: provide `answer_text` per sub-part in a `sub_parts`
    array, leave question-level `answer_text` as null
- `mcq_correct`: for MCQ questions, the correct option number (1-indexed integer).
  Null for non-MCQ questions.

## Important rules

- Match answers to questions by question number.
- If an answer is not found in these pages, set `answer_text` to null.
- Do not guess or infer answers — only extract what is explicitly printed.
- Some answer keys only contain MCQ answers. Open-ended answers may not be present.

## Output format

Return a JSON array:
[
  {
    "question_id": "q1",
    "answer_text": "(2)",
    "mcq_correct": 2,
    "sub_parts": []
  },
  {
    "question_id": "q29",
    "answer_text": null,
    "mcq_correct": null,
    "sub_parts": [
      {
        "sub_part_id": "q29a",
        "answer_text": "The number of days decreases as temperature increases."
      },
      {
        "sub_part_id": "q29b",
        "answer_text": "20 degrees Celsius"
      },
      {
        "sub_part_id": "q29c",
        "answer_text": "Higher temperatures shorten the life cycle..."
      }
    ]
  }
]
```

The `{question_list}` placeholder is populated at runtime from the existing index — a compact list of `question_id`, `question_number`, `is_multi_part`, `question_type`, and sub-part IDs. This gives the LLM the structure it needs to match answers without re-discovering questions.

---

## Review Tool

### Motivation

The vision LLM produces bounding boxes that are close but not pixel-accurate. In the 2023 PSLE pilot, the Q1 crop was off by a small margin: the top boundary included the section instruction text, and the bottom boundary cut off option (4). This is a refinement problem — the coordinates are in the right ballpark but need human confirmation or adjustment before downstream consumers can rely on them.

Fixing this isn't something a second AI pass can solve. If the vision LLM couldn't pinpoint the exact boundaries the first time, running it again on the same image won't produce different results. The right approach is to treat the LLM output as a preliminary draft and provide a fast review tool that lets a human scan through every question's crop, confirm it's correct, or nudge the boundaries.

This review step is what transitions an index from `"generated"` (unreviewed LLM output) to `"verified"` (human-confirmed). It should be fast — the LLM did the hard work of identifying questions, extracting text, and proposing regions. The human reviewer is just validating and correcting, not starting from scratch.

### Design goals

1. **Speed.** Reviewing one template (e.g., 28 MCQ questions) should take under 5 minutes. The tool must minimize clicks and keyboard input per question.
2. **Visual.** Show the cropped region alongside the full page so the reviewer can see what's included and what's missing.
3. **Editable.** Let the reviewer drag or nudge bbox edges, or type adjusted coordinates. Changes are written back to the JSON immediately.
4. **Sequential.** Walk through questions in order, but always make it easy to jump to the next `unreviewed` question. Most will be correct — the reviewer should be able to accept and move to the next unresolved item in a single keystroke.
5. **Resumable.** Track which questions have been reviewed. If interrupted, the tool picks up where the reviewer left off (`review_status: "unreviewed"` → `"accepted"` or `"corrected"`).
6. **Standalone.** No external services, database, or app dependencies. The tool is run from the command line, starts a local single-user HTTP server on localhost for the browser UI, reads the index JSON and template PDF, and writes the updated JSON back to disk.

### Spec

**Input:**
- Path to a `unit_question_index.json` file (the generated index)
- The template PDF is resolved from `unit_file_path` in the index

**Interface:** Local web page served by a Python script (localhost). Chosen over a terminal-based tool because bbox adjustment requires visual feedback and mouse interaction for dragging edges.

**Review unit:** The reviewer works at the **question** level, but may inspect one or more `prompt_regions` for that question. A multi-part question still has one review state; the reviewer confirms or corrects the full set of regions that cover the question, including all sub-parts, diagrams, and tables embedded in `prompt_regions`.

**Runtime behavior:**
- Rendered page images may be cached locally next to the index so reopening the tool is fast.
- On page refresh, the tool should reload the current `unit_question_index.json` from disk so externally regenerated indices are picked up without extra reconfiguration.

**Layout per question:**

```
┌─────────────────────────────────────────────────────────┐
│  Q1 (MCQ, 2 marks)                    [Accept] [Next]  │
├──────────────────────┬──────────────────────────────────┤
│                      │                                  │
│   Cropped region     │   Full page with bbox overlay    │
│   (current bbox)     │   (bbox shown as red rectangle)  │
│                      │                                  │
├──────────────────────┴──────────────────────────────────┤
│  bbox: page=2  y1=0.10  y2=0.28  x1=0.04  x2=0.96     │
│  [editable fields]                                      │
│                                                         │
│  Question text: "What is one effect of deforestation?"  │
│  Marks: 2   Type: mcq   Stimulus: none                 │
└─────────────────────────────────────────────────────────┘
```

**Interaction flow:**

1. Open the review tool: `python3 question_area_review.py <path_to_index.json>`
2. Browser opens to `localhost:8765` showing the first unreviewed question.
3. For each question:
   - **Accept (keyboard shortcut: Enter or `a`):** Mark `review_status: "accepted"`, advance to the next `unreviewed` question if one exists.
   - **Adjust bbox:** Drag edges on the full-page view, or edit the coordinate fields directly. The crop preview updates in real time. For multi-region questions, the reviewer can switch among `prompt_regions` and adjust them one at a time.
   - **Save adjustment (keyboard shortcut: `s`):** Mark `review_status: "corrected"`, write the updated bbox to JSON, advance to the next `unreviewed` question if one exists.
   - **Skip (keyboard shortcut: right arrow):** Move to next question without changing status.
   - **Back (keyboard shortcut: left arrow):** Return to previous question.
   - **Next unreviewed:** Jump directly to the next question whose `review_status` is still `"unreviewed"`.
4. Progress bar shows how many questions are reviewed out of total.
5. On exit or completion, the JSON is saved. If all questions are reviewed, `index_status` is updated to `"verified"`.

**What the reviewer checks:**

- **Bounding boxes:** Does the crop include the full question text and all options/diagrams? Does it exclude content from adjacent questions or section headers? For questions with multiple `prompt_regions`, do the regions together cover the full question without duplication or omission?
- **Shared stimulus linkage (only when present):** If the subject/schema actually uses `stimulus_blocks`, is the right shared block linked? Is any cross-question passage/table/diagram missing?
- **Question text:** Is the extracted `printed_question_text` accurate? (Quick visual comparison against the crop.)
- **Marks and type:** Does `max_marks` match the printed mark allocation? Is `question_type` correct?

The reviewer does NOT check skill tags or embedding text — those are best validated through downstream usage, not visual inspection.

**Output:**

- Updated `unit_question_index.json` with corrected bboxes and `review_status` per question.
- `index_status` updated to `"verified"` when all questions have been reviewed.

### Where it lives

```
ai_study_buddy/question_area_review/
  question_area_review.py   # CLI entry point + local web server
  static/
    index.html              # Single-page review UI
    review.js               # Interaction logic, bbox dragging
    review.css              # Layout
```

---

## Marking Output Schema

The marking output mirrors the question index structure: question-level results with a `sub_parts` array for multi-part questions. This is the structured output of the marking pipeline — the data that feeds into learning reports and the `question_objects` table in Postgres.

### Design principle

The marking result for a question has the same shape as the question in the index. A single-part question gets a flat result. A multi-part question gets question-level totals (summed from sub-parts) plus a `sub_parts` array with per-part detail.

### Schema

```json
{
  "marking_id": "mark_20260410_001",
  "student_id": "winston",
  "student_name": "Winston",
  "unit_file_id": "8c29e8f9-b1c5-4bd5-9edc-063784700a58",
  "attempt_file_id": "attempt_file_456",
  "marked_at": "2026-04-10T19:00:00Z",
  "total_marks": 56,
  "earned_marks": 48,

  "marking_results": [
    {
      "question_id": "q1",
      "display_label": "Q1",
      "max_marks": 2,
      "earned_marks": 2,
      "outcome": "correct",
      "student_answer": "(2)",
      "correct_answer": "(2)",
      "is_multi_part": false,
      "sub_parts": [],
      "feedback": null,
      "error_tags": [],
      "skill_tags": ["ecosystems", "deforestation"]
    },
    {
      "question_id": "q29",
      "display_label": "Q29",
      "max_marks": 4,
      "earned_marks": 3,
      "outcome": "partial",
      "student_answer": null,
      "correct_answer": null,
      "is_multi_part": true,
      "sub_parts": [
        {
          "sub_part_id": "q29a",
          "sub_part_label": "(a)",
          "max_marks": 1,
          "earned_marks": 1,
          "outcome": "correct",
          "student_answer": "The number of days decreases.",
          "correct_answer": "The number of days decreases as temperature increases.",
          "feedback": null,
          "error_tags": []
        },
        {
          "sub_part_id": "q29b",
          "sub_part_label": "(b)",
          "max_marks": 1,
          "earned_marks": 1,
          "outcome": "correct",
          "student_answer": "20 degrees Celsius",
          "correct_answer": "20 degrees Celsius",
          "feedback": null,
          "error_tags": []
        },
        {
          "sub_part_id": "q29c",
          "sub_part_label": "(c)",
          "max_marks": 2,
          "earned_marks": 1,
          "outcome": "partial",
          "student_answer": "More mosquitoes because they grow faster.",
          "correct_answer": "Higher temperatures shorten the life cycle, so mosquitoes complete their life cycle faster. This leads to more generations of mosquitoes and therefore more adult mosquitoes.",
          "feedback": "Correct that life cycle is faster, but need to explain the mechanism: shorter life cycle means more generations in the same time period.",
          "error_tags": ["incomplete_explanation"]
        }
      ],
      "feedback": "3 of 4 marks. Part (c) needed fuller explanation of the link between faster life cycles and population increase.",
      "error_tags": ["incomplete_explanation"],
      "skill_tags": ["life_cycles", "interpreting_graphs", "global_warming"]
    }
  ]
}
```

### Field reference

**Result-level fields (per marking run):**

| Field | Type | Description |
|-------|------|-------------|
| `marking_id` | string | Unique ID for this marking run |
| `student_id` | string | Student identifier |
| `student_name` | string | Student display name |
| `unit_file_id` | string | Template file ID (links to the question index) |
| `attempt_file_id` | string | Student's attempt file ID |
| `marked_at` | string | ISO 8601 timestamp |
| `total_marks` | integer | Total marks available |
| `earned_marks` | integer | Total marks earned |

**Per-question fields:**

| Field | Type | Description |
|-------|------|-------------|
| `question_id` | string | Matches `question_id` in the question index |
| `display_label` | string | Human-readable: `Q1`, `Q29` |
| `max_marks` | integer | Total marks for this question (sum of sub-parts if multi-part) |
| `earned_marks` | integer | Marks earned (sum of sub-parts if multi-part) |
| `outcome` | string | `correct` (full marks), `partial` (some marks), `wrong` (zero marks) |
| `student_answer` | string or null | Student's answer. Null for multi-part questions (detail is in sub-parts) |
| `correct_answer` | string or null | Official answer. Null for multi-part questions |
| `is_multi_part` | boolean | Mirrors the question index |
| `sub_parts` | array | Per-sub-part results (see below). Empty for single-part questions |
| `feedback` | string or null | Question-level feedback. For multi-part questions, a summary |
| `error_tags` | array of strings | Error categories (union of sub-part error tags for multi-part) |
| `skill_tags` | array of strings | From the question index (not re-extracted during marking) |

**Per-sub-part fields:**

| Field | Type | Description |
|-------|------|-------------|
| `sub_part_id` | string | Matches `sub_part_id` in the question index |
| `sub_part_label` | string | `(a)`, `(b)`, `(c)(ii)` |
| `max_marks` | integer | Marks available for this sub-part |
| `earned_marks` | integer | Marks earned |
| `outcome` | string | `correct`, `partial`, `wrong` |
| `student_answer` | string | Student's answer for this sub-part |
| `correct_answer` | string | Official answer for this sub-part |
| `feedback` | string or null | Targeted feedback for this sub-part |
| `error_tags` | array of strings | Error categories specific to this sub-part |

### Derivation rules

- `earned_marks` at question level = sum of `sub_parts[].earned_marks` (for multi-part questions)
- `outcome` at question level: `correct` if `earned_marks == max_marks`, `wrong` if `earned_marks == 0`, `partial` otherwise
- `error_tags` at question level = union of `sub_parts[].error_tags`
- `skill_tags` are copied from the question index, not re-generated during marking

### Relationship to learning reports

The existing markdown learning reports (e.g., Winston's Forces test) render one row per gradeable unit:

```
| Q15(a) | gravitational force | gravitational force | 1 | 1 | ... |
| Q15(b) | Paper ball must be... | It must be small... | 1 | 1 | ... |
```

Under this schema, Q15 is one `marking_results` entry with `earned_marks: 5` (summed), and `sub_parts` contains Q15(a) through Q15(d). The report renderer expands the sub-parts array into separate rows for readability, but the structured data groups them under the parent question.

---

## Concrete Example: 2023 PSLE Science Exam

> Real data — extracted by Claude Opus 4.6 from the actual exam PDF pages. Full indices are at:
> - `ai_study_buddy/cache/question_indices/8c29e8f9-b1c5-4bd5-9edc-063784700a58/unit_question_index.json` (Booklet A, 28 MCQ questions, 56 marks)
> - `ai_study_buddy/cache/question_indices/80b23580-b48e-4206-bc3d-7efc2085506a/unit_question_index.json` (Booklet B, 12 open-ended questions with sub-parts, 44 marks)

This is a multi-booklet PSLE exam with **continuous numbering** across two booklets (Q1–Q28 MCQ in Booklet A, Q29–Q40 open-ended in Booklet B). Each booklet has its own index; the `exam_context` field links them.

### Abridged Booklet A index (MCQ)

```json
{
  "schema_version": "3.0",
  "review_status": "unreviewed",
  "has_answers": true,
  "unit_file_id": "8c29e8f9-b1c5-4bd5-9edc-063784700a58",
  "unit_label": "7 2023 PSLE Paper - Booklet A",
  "book_label": "PSLE Examination Papers Yearly 2023-2025",
  "subject": "science",
  "grade": "psle",

  "page_count": 16,
  "content_pages": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
  "excluded_pages": [1],
  "total_questions": 28,
  "total_marks": 56,

  "exam_context": {
    "exam_label": "2023 PSLE Science",
    "booklet_label": "Booklet A",
    "numbering_continues_from": null,
    "numbering_continues_to": "80b23580-b48e-4206-bc3d-7efc2085506a"
  },

  "sections": [{
    "section_id": "sec_mcq",
    "label": "Multiple Choice",
    "section_type": "mcq",
    "number_restart": false,
    "marks_per_question": 2,
    "question_ids": ["q1", "q2", "...", "q28"]
  }],

  "stimulus_blocks": [],

  "questions": [
    {
      "question_id": "q1",
      "display_label": "Q1",
      "question_number": "1",
      "section_id": "sec_mcq",
      "prompt_regions": [{ "page": 2, "bbox": [0.04, 0.10, 0.96, 0.28] }],
      "question_type": "mcq",
      "max_marks": 2,
      "is_multi_part": false,
      "sub_parts": [],
      "printed_question_text": "What is one effect of deforestation?",
      "mcq_options": ["more types of plants and animals", "increase in carbon dioxide", "increase in oxygen", "lower temperature"],
      "mcq_correct": 2,
      "answer_text": "(2)",
      "skill_tags": ["ecosystems", "deforestation", "human_impact_on_environment"],
      "embedding_text": "Multiple-choice science question about the effects of deforestation. The student must identify the environmental effect associated with cutting down forests. The options contrast increased carbon dioxide with distractors about oxygen, temperature, and biodiversity.",
      "extraction_method": "vision_llm_claude_opus",
      "review_status": "unreviewed"
    },
    {
      "question_id": "q4",
      "display_label": "Q4",
      "question_number": "4",
      "section_id": "sec_mcq",
      "prompt_regions": [{ "page": 3, "bbox": [0.04, 0.02, 0.96, 0.94] }],
      "question_type": "mcq",
      "max_marks": 2,
      "is_multi_part": false,
      "sub_parts": [],
      "printed_question_text": "The diagram shows the human digestive system. Which graph correctly shows the amount of undigested food leaving each organ A, B, C, D and E after a heavy meal?",
      "mcq_options": ["Graph 1", "Graph 2", "Graph 3", "Graph 4"],
      "mcq_correct": 4,
      "answer_text": "(4)",
      "skill_tags": ["human_body_systems", "digestive_system", "interpreting_graphs"],
      "embedding_text": "Diagram-based multiple-choice question linking the human digestive system to a graph of undigested food leaving organs A to E after a heavy meal. Tests understanding of digestion together with interpretation of which graph matches the labeled organs.",
      "extraction_method": "vision_llm_claude_opus",
      "review_status": "unreviewed"
    }
  ],

  "provenance": {
    "created_at": "2026-04-10T18:00:00Z",
    "generation_source": {
      "model": "claude-4.6-opus",
      "run_id": "manual_pilot_20260410",
      "pages_processed": 15,
      "pages_excluded": [1],
      "questions_extracted": 28
    }
  }
}
```

### Abridged Booklet B index (open-ended)

```json
{
  "schema_version": "3.0",
  "review_status": "unreviewed",
  "has_answers": false,
  "unit_file_id": "80b23580-b48e-4206-bc3d-7efc2085506a",
  "unit_label": "8 2023 PSLE Paper - Booklet B",
  "book_label": "PSLE Examination Papers Yearly 2023-2025",
  "subject": "science",
  "grade": "psle",

  "page_count": 12,
  "content_pages": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
  "excluded_pages": [1],
  "total_questions": 12,
  "total_marks": 44,

  "exam_context": {
    "exam_label": "2023 PSLE Science",
    "booklet_label": "Booklet B",
    "numbering_continues_from": "8c29e8f9-b1c5-4bd5-9edc-063784700a58",
    "numbering_continues_to": null
  },

  "sections": [{
    "section_id": "sec_oe",
    "label": "Open-ended",
    "section_type": "open_ended",
    "number_restart": false,
    "marks_per_question": null,
    "question_ids": ["q29", "q30", "...", "q40"]
  }],

  "stimulus_blocks": [],

  "questions": [
    {
      "question_id": "q29",
      "display_label": "Q29",
      "question_number": "29",
      "section_id": "sec_oe",
      "prompt_regions": [{ "page": 2, "bbox": [0.05, 0.06, 0.95, 0.88] }],
      "question_type": "open_ended",
      "max_marks": 4,
      "is_multi_part": true,
      "sub_parts": [
        {
          "sub_part_id": "q29a",
          "sub_part_label": "(a)",
          "max_marks": 1,
          "printed_question_text": "Based on the graph, what happens to the number of days for the mosquitoes to complete their life cycle as the temperature increases?",
          "answer_text": null,
          "skill_tags": ["life_cycles", "interpreting_graphs"]
        },
        {
          "sub_part_id": "q29b",
          "sub_part_label": "(b)",
          "max_marks": 1,
          "printed_question_text": "Based on the graph, at which temperature do the mosquitoes take the longest time to complete their life cycle?",
          "answer_text": null,
          "skill_tags": ["life_cycles", "interpreting_graphs"]
        },
        {
          "sub_part_id": "q29c",
          "sub_part_label": "(c)",
          "max_marks": 2,
          "printed_question_text": "Explain how global warming will affect the life cycle of mosquitoes and the number of adult mosquitoes.",
          "answer_text": null,
          "skill_tags": ["life_cycles", "global_warming", "environmental_impact"]
        }
      ],
      "printed_question_text": "Study the graph below showing the relationship between temperature and the number of days for mosquitoes to complete their life cycle.",
      "answer_text": null,
      "skill_tags": ["life_cycles", "interpreting_graphs", "global_warming", "environmental_impact"],
      "embedding_text": "Multi-part science question based on a graph relating temperature to the number of days mosquitoes need to complete their life cycle. The student must interpret the trend, identify the temperature associated with the longest life cycle, and explain how warmer conditions affect mosquito development and adult population size. Tests graph interpretation and understanding of life cycles in an environmental context.",
      "extraction_method": "vision_llm_claude_opus",
      "review_status": "unreviewed"
    },
    {
      "question_id": "q40",
      "display_label": "Q40",
      "question_number": "40",
      "section_id": "sec_oe",
      "prompt_regions": [{ "page": 12, "bbox": [0.05, 0.04, 0.95, 0.95] }],
      "question_type": "open_ended",
      "max_marks": 5,
      "is_multi_part": true,
      "sub_parts": [
        {
          "sub_part_id": "q40a",
          "sub_part_label": "(a)",
          "max_marks": 2,
          "printed_question_text": "Explain why part A of the glass top is hotter than part B.",
          "answer_text": null,
          "skill_tags": ["heat", "heat_transfer", "conduction"]
        },
        {
          "sub_part_id": "q40b_i",
          "sub_part_label": "(b)(i)",
          "max_marks": 2,
          "printed_question_text": "What happened to part A and part B of the glass top when heated?",
          "answer_text": null,
          "skill_tags": ["heat", "thermal_expansion"]
        },
        {
          "sub_part_id": "q40b_ii",
          "sub_part_label": "(b)(ii)",
          "max_marks": 1,
          "printed_question_text": "The glass top cracked after some time. Explain why.",
          "answer_text": null,
          "skill_tags": ["heat", "thermal_expansion", "uneven_heating"]
        }
      ],
      "printed_question_text": "An electric pot is used to heat water. The pot is placed on a thick glass top.",
      "answer_text": null,
      "skill_tags": ["heat", "heat_transfer", "conduction", "thermal_expansion", "uneven_heating"],
      "embedding_text": "Multi-part heat question about an electric pot placed on a thick glass top with regions A and B heated unevenly. The student must explain why one region becomes hotter, describe what happens to the glass when heated, and explain why the glass eventually cracks. Tests conduction, thermal expansion, and the effects of uneven heating.",
      "extraction_method": "vision_llm_claude_opus",
      "review_status": "unreviewed"
    }
  ],

  "provenance": {
    "created_at": "2026-04-10T18:00:00Z",
    "generation_source": {
      "model": "claude-4.6-opus",
      "run_id": "manual_pilot_20260410",
      "pages_processed": 11,
      "pages_excluded": [1],
      "questions_extracted": 12
    }
  }
}
```

### What this example demonstrates

- **Multi-booklet exam**: Two indices linked by `exam_context`. Booklet A's `numbering_continues_to` points to Booklet B's file ID and vice versa.
- **Cover page exclusion**: Both booklets exclude page 1 (`excluded_pages: [1]`).
- **Continuous numbering**: No `number_restart` — Q1–Q28 in Booklet A continues to Q29–Q40 in Booklet B.
- **Question-level atomic unit**: Booklet B has 12 questions (Q29–Q40), not 30 sub-part entries. Each question has `is_multi_part: true` with a `sub_parts` array containing individually gradeable parts with their own marks and skill tags.
- **No stimulus blocks for science/math**: Both booklets have `stimulus_blocks: []`. All diagrams and tables are internal to their question's `prompt_regions`. Stimulus blocks are reserved for cross-question sharing (e.g., English comprehension passages).
- **MCQ embedding text**: Uses a semantic description of the concept being tested and the role of the options, rather than copying the options verbatim.
- **Multi-part embedding text**: Summarizes the shared scenario, the sub-part tasks, and the tested concepts in one retrieval-oriented description.
- **Shared answer key limitation**: The answer key file only contains MCQ answers (Q1–Q28). Booklet B open-ended answers are not in this book, so `answer_text` is null.

---

## Pilot: 2023 PSLE Science Exam

> Tested 2026-04-10 using registered files from book "PSLE Examination Papers Yearly 2023-2025":
> - Booklet A (Q1–Q28, MCQ, 16 pages): `_c_PSLE Examination Papers Yearly 2023-2025 - 07 2023 PSLE Paper - Booklet A.pdf`
> - Booklet B (Q29–Q40, open-ended, 12 pages): `_c_PSLE Examination Papers Yearly 2023-2025 - 08 2023 PSLE Paper - Booklet B.pdf`
> - Answer key: `_c_PSLE Examination Papers Yearly 2023-2025 - 09 Answer Key.pdf` (shared across Specimen, 2023, 2024, 2025 papers)

### Structural observations

**Multi-document exam.** This PSLE Science paper is two booklets (Booklet A: Q1–Q28 MCQ, Booklet B: Q29–Q40 open-ended) with **continuous numbering** across booklets. Each booklet gets its own index; the `exam_context` field links them.

**Shared answer key across exams.** The book group contains one answer key file shared by 4 exams (Specimen, 2023, 2024, 2025). Each exam's booklets map to a page range within this shared answer key via `book_answer_mapping`.

**Booklet A structure.** Page 1 is a cover/instruction page (`excluded_pages: [1]`). Pages 2–16 contain Q1–Q28 (MCQ, 4 options each, many with large diagrams). Each question has `(1)`, `(2)`, `(3)`, `(4)` options and a `(66 marks)` header.

**Booklet B structure.** Page 1 is a cover/instruction page (`excluded_pages: [1]`). Pages 2–12 contain Q29–Q40, each with sub-parts like (a), (b), (c) carrying separate mark allocations in brackets `[1]`, `[2]`.

### Why this pilot led to the vision-LLM-first architecture

The pilot originally tested the `question_splitter` utility in `archive/question_splitter/` (Tesseract OCR + regex heuristics) as the structural source. The results demonstrated that deterministic splitting is not viable:

- **Cover page false positives**: Numbered instruction lists on cover pages were detected as question markers. Booklet A's real Q1–Q5 were missed entirely because the monotonic filter had already consumed those numbers from the instruction list.
- **Missing questions**: Q11 (Booklet A) and Q37 (Booklet B) were not detected by OCR despite being well-scanned. Their content was absorbed into adjacent questions.
- **STEM over-assignment**: Exam instruction text matched the shared-stimulus regex and generated bogus STEM entries for all Q29–Q40.
- **No sub-part detection**: Individually gradeable sub-parts with separate mark allocations were grouped under parent question numbers.

These are not exotic edge cases — they occurred on a single well-scanned official exam paper. The ~25% structural error rate on Booklet A (6 of 28 questions wrong) made clear that pursuing deterministic splitting would be a never-ending debugging exercise across hundreds of different document layouts.

A vision LLM handles all of these naturally: it recognizes cover pages as instructions (not questions), detects question numbers regardless of font weight or spacing, understands mark allocation brackets, and identifies sub-parts. The one-time cost per template ($0.01–0.03) is negligible for a per-template operation.

---

## v1 Scope

### In scope (math/science)

- Sections with `number_restart` handling
- Question-level atomic unit with optional `sub_parts` array for multi-part questions
- Diagrams/tables included in question's `prompt_regions` (stimulus blocks only for cross-question sharing, rare in science/math)
- Question types: `mcq`, `short_answer`, `open_ended`
- `embedding_text` for standalone and diagram-context questions
- Index generation via vision LLM in a single pass
- Multi-booklet exams (Booklet A + Booklet B) with `exam_context` linking and continuous numbering
- Cover page / instruction page exclusion via `excluded_pages`
- Past-year paper books with a shared answer key across multiple exams

### Deferred to v2 (English/Chinese)

- `block_type: "passage"`, `"visual_text"`, `"cloze_passage"` — comprehension passages as stimulus blocks
- Question types: `cloze`, `editing`, `synthesis`, `composition`
- `embedding_text` with stimulus summary for comprehension questions
- Stimulus summary generation (one-line summary of a passage for embedding purposes)
- Multi-page stimulus blocks (comprehension passages spanning pages)
- Grid-paper composition analysis (Chinese)

### Deferred to v3 (scored paper ingestion)

- Extracting student answers and teacher marks using the index as a template
- Producing `question_objects` Postgres rows from the index + student PDF
- Per-student crop generation

---

## Cross-references to update

When this proposal is implemented, the following existing docs should reference it:

| Doc | Update needed |
|-----|---------------|
| [L3_DATA_STRATEGY.md](./L3_DATA_STRATEGY.md) | The "Question Object" section should reference the unit question index as the on-disk schema that formalizes question objects for book/practice units |
| [L4_INGESTION_PIPELINE.md](./L4_INGESTION_PIPELINE.md) | Step 6 (Extract Structure) should note that for book/practice units with a registered template, the unit question index IS the output of this step |
| `ai_study_buddy/marking/` | The `resolve_marking_context()` function should be extended to optionally load and return the unit question index |

---

## Open Questions

### Resolved

1. **Should the index live in the registry (SQLite) or on disk (JSON)?** Resolved: store the index as on-disk JSON keyed by `unit_file_id`. JSON is simpler to inspect, diff, review, cache, and regenerate, and it fits naturally with the cropped image assets stored alongside it. Registry-backed discovery can be added later if needed, but the registry does not need to become the primary storage location for the full index artifact.

2. **Should the index store the embedding vector itself, or just the text?** Resolved: store only the retrieval-oriented `embedding_text` in the index. The actual embedding vector lives in pgvector, where it can be regenerated if the embedding model changes. This keeps the on-disk index portable and inspectable while preserving a clear separation between source artifact and retrieval infrastructure.

3. **Questions that span pages.** `prompt_regions` uses multiple entries when a question crosses a page boundary. The schema already supports this (it's an array). The vision LLM prompt should emit multi-region entries for such questions.

4. **Vision LLM prompt design.** Send the entire document to the vision LLM in one pass. Major vision models (Gemini, Claude, GPT) handle full documents without page-batching. The prompt specifies the structured output schema; no per-document customization or few-shot examples should be needed.

5. **Multi-booklet exam identity.** The `exam_context` field does not need year/board fields. This information is already captured in the registry group label (e.g., "PSLE Examination Papers Yearly 2023-2025") and is redundant to duplicate.
