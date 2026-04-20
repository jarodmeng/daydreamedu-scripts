---
name: mark-goodnote-completion
description: Mark a student's GoodNotes completion PDF against the registry-linked DaydreamEdu template and mapped answer-page range, then write a canonical JSON marking artifact under `ai_study_buddy/context/marking_results/<student>/<subject_context>/` and a derived markdown learning report under `ai_study_buddy/context/learning_reports/<student>/<subject_context>/`. **Each wrong or partial item must receive a careful, specific diagnosis** (not generic boilerplate): explain the real learning gap using the question, key, and student answer. Per-run renders, crops, and one-off `_*.py` helpers live together under `ai_study_buddy/context/.marking_scratch/<scratch_slug>/` (see `scripts/` subfolder). Use when the user wants a GoodNotes completion graded, marked, compared with worked solutions, or turned into a learning report.
---

# Mark GoodNotes Completion

Use this workflow when the user wants a GoodNotes completion PDF visually graded against either:

- mapped answer pages (registry mapping), or
- embedded answer pages in the same weighted-assessment paper.

This skill is for JSON-first report generation and manual visual marking, not for changing registry data.

## Filesystem layout (canonical vs scratch)

Authoritative naming and paths for **committed / long-lived** artifacts are defined in:

- `ai_study_buddy/marking/SPEC.md` (contract)
- `ai_study_buddy/marking/core/artifact_paths.py` (path builders)

Use this mental model:

### Tier A — Canonical outputs (source of truth + derived report)

These paths are stable and should match the package helpers whenever you use code to write artifacts:

| Artifact | Path |
| --- | --- |
| Canonical JSON (`marking_result.v1.1`; reader also accepts `v1`) | `ai_study_buddy/context/marking_results/<student_slug>/<subject_context>/<attempt_basename>.json` |
| Derived markdown report | `ai_study_buddy/context/learning_reports/<student_slug>/<subject_context>/<attempt_basename> - Marking Report.md` |

Rules:

- `<student_slug>`: lowercase, non-alphanumeric collapsed to `_` (same as `slugify_student` in `artifact_paths.py`).
- `<attempt_basename>`: normalized attempt stem (strip `c_`, `_c_`, `_raw_`, `raw_` prefixes repeatedly) + `__YYYYMMDD_HHMMSS` from `created_at` / marking time — **the JSON stem and the markdown basename (before ` - Marking Report.md`) must match** so pairs are easy to find and re-render.
- **Timestamps (SGT):** Use **Singapore time** (`Asia/Singapore`, `+08:00`) for `created_at` / `updated_at` on canonical JSON. Call `now_marking_iso()` or `to_marking_iso(...)` from `ai_study_buddy.marking` (see `core/marking_time.py`); `write_marking_artifact` normalizes any parseable instant to SGT on save. The `__YYYYMMDD_HHMMSS` suffix is the **Singapore local wall-clock** time for that instant — do **not** use UTC (`Z`) or `datetime.utcnow()` for persisted marking times.
- Do not put PNG crops or page renders inside `marking_results/` or `learning_reports/`; those directories are for JSON and markdown only.

### Tier B — Per-run scratch bundle (renders + crops + one-off scripts; not canonical)

Put **everything** for one marking job that is *not* Tier A JSON/markdown under a **single run directory** so renders and helper code stay easy to find, archive, or delete together:

**Root (required for new work):** `ai_study_buddy/context/.marking_scratch/<scratch_slug>/`

**Legacy only:** older trees at `ai_study_buddy/context/.tmp_<scratch_slug>/` should be **moved into** `.marking_scratch/<scratch_slug>/` (same layout below) when you next touch them; do not add new `.tmp_*` roots at `context/` top level.

Suggested **`<scratch_slug>`**: `<student_slug>__<short_unit_or_book_hint>` in lowercase (e.g. `winston__power_pack_circles`, `emma__math_model_skill_2_5`). Keep it short and unique enough that concurrent jobs do not collide.

Standard **layout** under that directory:

| Path | Contents |
| --- | --- |
| `scripts/` | Per-run **one-off** Python helpers (`_<name>.py`): render PDFs to PNG, crop answer blocks, glue steps before/after `artifact_writer` / `report_renderer`, etc. **Do not** leave new `_*.py` marking drivers under `ai_study_buddy/marking/` package root — co-locate them here next to the PNGs they produce. |
| `attempt/` | Rendered GoodNotes attempt pages (e.g. `attempt-page-NN.png`). |
| `answers/` | Rendered answer PDF pages for the mapped (or embedded) range. |
| `crops/` | Isolated answer-key crops and tighter verification crops (Section 4.5). |

**Imports:** scripts in `scripts/` still import the real package (`ai_study_buddy.marking`, `fitz`, etc.). Run them from the **repository root** with `python3 ai_study_buddy/context/.marking_scratch/<scratch_slug>/scripts/_your_script.py` (or equivalent) so repo imports resolve; inside the script, resolve paths relative to the scratch dir (e.g. `Path(__file__).resolve().parent.parent / "attempt"`) so the folder can be moved without editing.

Renders and crops are **not** canonical; only Tier A JSON (and derived report) are. Prefer placeholder-normalized paths in persisted JSON per `SPEC.md` path-privacy rules.

**Promoting code:** when a script’s logic is reusable across many books, **fold** it into `ai_study_buddy/marking/workflows/` (or `core/`) and delete the one-off copy from `scripts/` — the scratch tree then holds only run-specific knobs (paths, page lists) or nothing until the next job.

### Cleanup and repo hygiene

After JSON + markdown are written and validated:

- Remove or move the **entire** `.marking_scratch/<scratch_slug>/` directory (including `scripts/`) to Trash when no longer needed.
- Do not commit scratch trees; they should remain **untracked** (repo `.gitignore` may list `ai_study_buddy/context/.marking_scratch/` and legacy `ai_study_buddy/context/.tmp_*` if noise becomes a problem).

## Prerequisite

Read and follow the project skill at `../pdf-file-manager/SKILL.md` first.

Use the `PdfFileManager` Python API as the primary interface. Do not query the registry SQLite database directly for normal lookup work.

## Scope

This workflow assumes:

- the student's completion PDF is under a **mirrored student tree**: either `.../GoodNotes/...` **or** student-scoped `.../DaydreamEdu/...` (e.g. DaydreamEdu mirror `Book/` completions such as Winston’s *PP Math PSLE Part B…*)
- the file can be registered as a completion `main` file when missing
- the completion can be linked to a DaydreamEdu template (registry link, or `auto_link_template` using the same `_c_` basename rules as GoodNotes→template resolution)
- answer source is either:
  - linked-template book answer mapping, or
  - explicit embedded answer page range (`self_answer_pages`)

Typical request shapes:

- "mark this GoodNotes completion"
- "compare Winston's work with the answer pages"
- "write a learning report for this completion"
- "grade each gradable question in this GoodNotes file"

## Default Workflow

### 1. Resolve the marking context

Resolve these items before doing any grading:

1. the exact GoodNotes completion file
2. its linked DaydreamEdu template file
3. the mapped answer file
4. the mapped answer page range

Registration/link precondition (required):

- Do not start marking until completion registration and template-link are confirmed (directly or via resolver auto flags).

Preferred interface (authoritative for now):

- Direct `PdfFileManager` calls:
  - `get_file_by_path(...)` or `find_files(...)`
  - `get_template(...)`
  - `get_book_answer_mapping(...)`

Use `ai_study_buddy.marking.resolve_marking_context(...)` as the preferred implementation path when available. Registry calls remain authoritative, but the business logic should live in `ai_study_buddy/marking/` rather than being duplicated ad hoc in the skill flow.

MVP contract for this skill:

1. Use natural-language request details (student, unit, book) only to fuzzy-search **GoodNotes or DaydreamEdu** leaf folders and identify one unique completion PDF path.
2. Once unique completion path is found, call `resolve_marking_context(...)` with:
   - `attempt_file_id_or_path=<unique completion path>`
   - `auto_register_attempt=True` when file may not be registered yet
   - `auto_link_template=True` when template link may be missing
3. For weighted assessment papers where answers are embedded in the same paper, pass:
   - `self_answer_pages=(begin_page, end_page)`
4. Treat resolver output as authoritative for template file, answer file, and answer page range.
5. If fuzzy search is not unique, stop and ask for disambiguation before calling resolver.
6. If embedded-answer mode is needed but answer-page range is unknown, ask the user to provide the page range before marking.

Important reporting discipline:

- distinguish the **attempt** completion path (GoodNotes or student DaydreamEdu) from the **general-scope** DaydreamEdu template path when they differ
- if the completion file has no direct answer mapping, check the linked template file
- state clearly whether the mapping was found directly on the completion or on the linked template

### 2. Render the attempt and answer pages

Render only the pages needed for visual comparison.

Preferred tool: PyMuPDF via `fitz`.

Recommended pattern:

- render all pages of the GoodNotes completion PDF
- render only the mapped answer pages from the answer PDF
- write temporary PNGs under **Tier B**: `ai_study_buddy/context/.marking_scratch/<scratch_slug>/{attempt,answers,crops}/` and place any per-run `_*.py` helpers in `.../<scratch_slug>/scripts/`
- inspect the rendered PNGs as images rather than relying on OCR

Example:

```python
from pathlib import Path
import fitz

pdf = fitz.open(input_pdf)
page = pdf[0]
pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
pix.save(output_png)
```

Visual-first rule:

- treat the page images as the source of truth
- use OCR only if handwriting or printed text is genuinely hard to read
- do not infer answers from the filename or mapping alone

**Ink color interpretation (required):** Completion PDFs can contain multiple writing colors. Use this default interpretation unless the user says otherwise:

- **blue/black ink:** usually the student's original answers and workings. This is the **only** writing color used for scoring.
- **red ink:** usually correctness ticks/crosses, correction marks, mark deductions, or tally marks.
- **green ink:** usually student corrections on previously incorrect answers.
- **purple ink:** usually parent remarks, notes on questions/answers, or general learning comments.

Marking scope rule:

- For grading, ignore **all red, green, and purple** writings; treat them as auxiliary annotations, not the gradable submission.
- Build `question_results` from printed question text plus the student's **blue/black** writing only.
- If the only visible completion of an answer is non-blue/black ink, record that ambiguity in `human_note` and avoid awarding credit from that annotation alone unless the workflow explicitly asks to grade corrections/remarks.
- If colors overlap and original blue/black content cannot be separated confidently, lower confidence and document the ambiguity instead of guessing.
- Future workflows may request extraction of red/green/purple annotations as metadata; that is out of scope for scoring in this skill by default.

### 3. Identify the gradable scope

Before assigning marks, determine exactly which questions in the completion file are gradable.

Use the visible content on the attempt pages to decide:

- which exercise or practice is included
- which question numbers are present
- whether each question has sub-parts like `(a)` and `(b)`
- whether the student wrote enough to grade

Cross-check the **question count** before marking:

- From the attempt pages, list all question labels you can see (for example Q1–Q10, Q33(a), Q33(b)).
- From the isolated answer-key crop for the same exercise, list all corresponding answer entries.
- Confirm that the two lists match exactly in both **labels** and **count** before you start filling `question_results`.
- If the user has asked you to grade only a subset (for example "only Q1–Q5"), explicitly record that subset in `context.question_selection.raw_text` and ensure only those questions appear in `question_results`.
- If you discover additional questions while marking (for example a Q35 on a later page), stop and update the lists so that the final JSON and report cover **all intended questions** and no more.

Do not grade:

- worked examples printed in the template
- **red/green/purple** annotations (including correction-only ink, marking symbols, or parent notes) — exclude from scoring per “Ink color interpretation” above
- decorative annotations or partial notes outside the target exercise
- cropped or ambiguous work that is not legible enough to compare confidently

If the file includes only one practice section, state that scope explicitly in the report notes.

### 4. Compare each gradable question visually

Hard prerequisite:

- **Before marking any question**, double-confirm the target exercise answer key using Section 4.5. Do not begin scoring until that verification is complete.

For each question or sub-part:

1. read the student’s written answer from the attempt pages using **blue/black writing only** and excluding red/green/purple annotations (see “Ink color interpretation” above)
2. read the corresponding worked-solution answer from the mapped answer pages
3. decide whether the result is full credit, partial credit, or zero
4. capture the student's answer in a concise text form
5. capture the correct answer in a concise text form

Default marking guidance:

- use `✅` for full marks
- use `⚠️` for partial credit only when the work clearly earns some credit
- use `❌` for zero marks

When marks are not explicitly printed in the source, use a sensible per-subpart scheme and keep it simple:

- one short numeric-answer sub-part usually gets `1` mark
- if a question naturally has two independent sub-parts, score them separately
- prefer explicit per-row scoring over inventing a complicated rubric

If the correct final answer is visible and Winston's final answer matches, give full credit unless the page clearly requires a method mark that is missing. When uncertain, say so in the notes instead of overstating confidence.

### 4.5. Critical answer-key verification protocol (required)

Before marking any question, verify the **correct-answer list** for the target exercise with this exact protocol:

1. Create an image crop that contains only the target exercise's answer block from the answer page (exclude neighboring exercises as much as possible).
2. Read the cropped image visually and transcribe all answers in order (for example Q1-Q10).
3. Perform a second independent read (either from a fresh tighter crop or another pass on the same crop) and confirm each question value matches the first transcription.
4. If OCR is used, treat OCR output as helper-only; the final authoritative values must come from visual inspection of the crop.
5. If any question remains ambiguous, do not finalize scoring for that row until it is resolved; explicitly note uncertainty in the report.

Non-negotiable rule:

- Do not mark or "double confirm" an answer key from a mixed multi-exercise panel without isolating the target exercise block.

### 5. Write the canonical JSON artifact first

Write the canonical marking artifact under:

`ai_study_buddy/context/marking_results/<student-name-lowercase>/<subject_context>/`

Filename pattern:

`<normalized attempt basename>__YYYYMMDD_HHMMSS.json`

The canonical JSON must follow `marking_result.v1.1` (reader accepts `v1` and `v1.1`) and should include:

- context
- summary
- `question_results` as gradable leaf units
- **`diagnosis` for every result** — for wrong and partial rows this is **mandatory** and must meet the bar in [Diagnosis Guidance](#diagnosis-guidance) (specific, learning-focused, not placeholder text)
- co-located human-note fields

### 6. Render the learning report from JSON

Write the final markdown report under:

`ai_study_buddy/context/learning_reports/<student-name-lowercase>/<subject_context>/`

For this workflow, the relevant math path is usually:

`ai_study_buddy/context/learning_reports/winston/singapore_primary_math/`

Filename pattern:

`<normalized attempt basename>__YYYYMMDD_HHMMSS - Marking Report.md`

Use this exact structure:

```markdown
# Learning Report

## Result

- Student: `Winston`
- Date: `YYYY-MM-DD`
- Score: `x/y`
- Percentage: `z%`
- Overall assessment: One short paragraph.

## Marking Table

Convention: `✅` = full marks, `⚠️` = partial credit, `❌` = zero marks.

| Name | Student answer | Correct answer | Total marks | Obtained marks | Embedding |
| --- | --- | --- | ---: | ---: | --- |
| ✅ Q1(a) | `...` | `...` | 1 | 1 | `Number and Algebra > Ratio > Ratio` |

## Report Context

- Attempt file: `/absolute/path/to/student_completion.pdf` (GoodNotes or DaydreamEdu)
- Template book file: `/absolute/path/to/template.pdf`
- Book answer file: `/absolute/path/to/answers.pdf`
- Answer page range for this exercise: `38-39`
- Mapping source: `...`

## Notes

- This report was produced by manual visual comparison of the GoodNotes attempt pages against the mapped answer pages.
- Gradable scope for this unit file was treated as ...
```

## Skill Tags Column

The markdown report renders `skill_tags` via `prettify_skill_tags`. In canonical JSON, `skill_tags` is an **array of strings** (tuple in code).

Syllabus-aligned tagging (path **per array element**, multiple paths joined with **`"; "`** in the report) is defined **per subject** below. Do **not** mix taxonomies (e.g. do not use math strands for science, or science themes for math).

For **Singapore primary English** (`singapore_primary_english`), **Chinese** (`singapore_primary_chinese`), and **Higher Chinese** (`singapore_primary_higher_chinese` when used), keep **`skill_tags` empty** for now: use `[]` on every `question_results` row (no legacy segments either). The report embedding cell will show blank until a taxonomy is adopted.

### Singapore primary math (`singapore_primary_math`) only

Treat `skill_tags` as an **array of syllabus topics**, not as “hierarchy split across array indices”.

**Canonical shape (each array element):**

```text
<strand> > <sub-strand> > <topic>
```

- Use a **single** space before and after each `>` (i.e. ` > ` between levels).
- **Strand**, **sub-strand**, and **topic** spellings come from  
  `ai_study_buddy/context/subject_understandings/singapore_primary_math/syllabus_understanding.md`  
  (same rules as before: three strands; sub-strand headings; topic from Skills-table **Topic** column or matching `#### Topic:`).

**Examples** — JSON stores **one string per topic path**:

```json
"skill_tags": ["Number and Algebra > Ratio > Ratio"]
```

```json
"skill_tags": ["Measurement and Geometry > Area and Volume > Area of Triangle"]
```

**Multiple topics** (e.g. a single question visibly assesses two digest topics): use **multiple strings**, each a full path. The report joins them with **`"; "`** (semicolon + space), not ` > `, so each path stays readable:

```json
"skill_tags": [
  "Number and Algebra > Whole numbers > Four Operations (whole numbers)",
  "Measurement and Geometry > Geometry > Angles"
]
```

→ table cell: `Number and Algebra > Whole numbers > Four Operations (whole numbers); Measurement and Geometry > Geometry > Angles`

**Rules**

- **Do not** use three separate array entries for strand / sub-strand / topic (old pattern). For math, **one entry = one full path**.
- **Do not** invent non-syllabus middle or tail segments inside a path.
- If mapping is uncertain, prefer **one** closest path and explain in `diagnosis` / `human_note` rather than guessing two unrelated paths.

### Singapore primary science (`singapore_primary_science`) only

Use the same **path-per-element** convention as math: each `skill_tags` entry is one full path string; several entries → joined with **`"; "`** in the report.

**Canonical shape (each array element):**

```text
<theme> > <chapter> > <topic>
```

- Use a **single** space before and after each `>` (i.e. ` > ` between levels).
- **Theme**, **chapter**, and **topic** spellings come from the **Index** table (and matching unit metadata) in:

`ai_study_buddy/context/subject_understandings/singapore_primary_science/syllabus_understanding.md`

**Themes** (top-level): `Diversity`, `Cycles`, `Systems`, `Interactions`, `Energy` — match the digest exactly.

**Chapter** and **topic** are the **Chapter** and **Topic** columns from that Index. Where the Index shows **—** for topic (chapter only), use **`—`** as the third segment so the path still has three levels (e.g. `Systems > Electrical System > —`).

**Examples**

```json
"skill_tags": ["Interactions > Interaction of Forces > Magnets"]
```

```json
"skill_tags": ["Energy > Energy Forms and Uses > Photosynthesis"]
```

```json
"skill_tags": ["Diversity > Diversity of Materials > —"]
```

**Rules**

- **Do not** use three array slots for theme / chapter / topic; **one entry = one full path**.
- **Do not** invent chapters or topics outside the digest (this file is Standard-track outcomes only).
- If a question spans two units, use **two** full-path strings; if uncertain, one path + `human_note`.

### Other subjects (not Singapore primary math, science, English, or Chinese)

Do **not** use math **strand / sub-strand / topic** unless the context is `singapore_primary_math`. Do **not** use science **theme / chapter / topic** unless the context is `singapore_primary_science`.

For contexts **outside** those four (e.g. another subject or future `subject_context` values), you may use **legacy** `skill_tags`: a short ordered list where **array order is the hierarchy** (coarse → fine); `prettify_skill_tags` joins those segments with ` > `—unless the user asks for empty tags there too.

## Diagnosis Guidance

**Careful diagnosis is a first-class deliverable.** Marks and outcomes record *what* was wrong; diagnosis explains *why*, in terms the student can learn from. Rushing this step produces useless reports: repeating the score line, vague phrases ("did not understand"), or the same paragraph for every error. Treat each incorrect or partial row as its own mini-lesson.

For each gradable result, the marking agent should populate:

- `error_tags`
- `diagnosis.mistake_type`
- `diagnosis.reasoning`
- `diagnosis.confidence`

**Per-error specificity (required for wrong and partial rows):**

- tie the explanation to **this** question’s demand (e.g. vocabulary nuance, synthesis strategy, chronology, counterfactual reasoning) — not a one-size template reused across items
- name the **distinction** the student missed (e.g. *compliment* vs *supplement*, *definitional* vs *call to action*, method A vs method B), using the key and student answer as anchors
- for MCQ and cloze, briefly address **why the distractor is tempting** when that clarifies the gap
- align `mistake_type` and `error_tags` with the taxonomy in `ai_study_buddy/marking/core/taxonomy.py` so the row is machine-consistent and human-readable

Evidence rule:

- diagnosis must use the final answer and any visible workings, method steps, or corrections/annotations
- for math in particular, visible workings are important for distinguishing concept gaps from calculation slips, wrong methods, incomplete methods, or misread questions
- if workings are missing or illegible, lower confidence and avoid overstating root cause

Incorrect-answer reasoning rule (required):

- for any row marked incorrect (`❌`) or partial (`⚠️`), `diagnosis.reasoning` must explain both:
  - why the correct answer is correct (text evidence, definition, method step, or key concept), and
  - why the student's selected/written answer is not correct
- do not write diagnosis reasoning as only an answer mismatch restatement (for example, avoid "student chose (1), correct is (2)" without explanation)
- do not leave `diagnosis` null or empty on wrong/partial rows when the schema allows content — if the model cannot yet explain the gap, say what is uncertain rather than omitting diagnosis
- keep the explanation concise and evidence-based; if evidence is limited, state uncertainty explicitly

### Diagnosis language (Chinese / Higher Chinese)

When `subject_context` is **`singapore_primary_chinese`** or **`singapore_primary_higher_chinese`**:

- Write **`diagnosis.reasoning`** in **Modern Standard Chinese (简体中文)** for every wrong (`❌`) and partial (`⚠️`) row, so the student and parents can read the learning feedback in the same language as the paper.
- Keep **`mistake_type`** and **`error_tags`** values in the **English** taxonomy from `ai_study_buddy/marking/core/taxonomy.py` (machine-consistent keys).
- Prefer Chinese as well for row-level **`feedback`** or **`human_note`** when those fields carry instructional content on Chinese/HC papers (optional but recommended for consistency with the report).
- When re-rendering markdown via `report_renderer`, the **Diagnosis** table column maps those English `mistake_type` keys to short **Chinese** labels (e.g. `incomplete_explanation` → `阐述不完整`) so the printed report stays readable end-to-end in Chinese.

## Quality Bar

Before finishing, verify:

- the JSON artifact exists and is the canonical source of truth
- the report path matches the subject and student folder
- the attempt file path is the student completion (GoodNotes or DaydreamEdu), not the template
- the template and answer file paths are correct
- the answer page range matches the registry mapping
- every graded row is visibly supported by both the attempt page and answer page
- the target exercise answer key was isolated in a dedicated crop (not a mixed panel)
- the final key list was checked in two passes, question-by-question
- **every wrong and partial row has a specific, non-boilerplate `diagnosis.reasoning` that would help the student improve on a similar item** (in **Chinese** for `singapore_primary_chinese` / `singapore_primary_higher_chinese`; see [Diagnosis language](#diagnosis-language-chinese--higher-chinese))
- the score totals add up
- the percentage is correct
- the markdown report matches the JSON artifact

## Guardrails

- Do not query the registry SQLite DB directly.
- Do not mark from memory; inspect the rendered pages.
- Do not treat red/green/purple annotations as the student’s original attempt for scoring purposes; score from blue/black student writing only.
- Do not claim a question is wrong unless the mismatch is visible.
- Do not finalize a report until the target exercise answer key is visually verified with the required two-pass isolated-crop protocol.
- Do not silently grade beyond the visible scope of the completion file.
- If the answer mapping or template link is missing, stop and report the missing dependency instead of guessing.
- If handwriting or page coverage is too unclear to grade reliably, say so and limit the report to confident items only.
- Do not leave temporary rendered PNGs in tracked report folders; keep them under **Tier B** `.marking_scratch/<scratch_slug>/` (with co-located `scripts/` for `_*.py`) and clean up the whole run folder after marking.
- Do not treat markdown as canonical data; always write JSON first.
- Do not ship a report with placeholder or copy-paste diagnoses for multiple errors; **each** error deserves its own careful read.

## Output Expectations

In the final user response:

- give the path to the created JSON artifact
- give the path to the created report
- summarize the score briefly
- mention the answer page range used
- mention if any grading decisions were uncertain or excluded
