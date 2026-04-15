---
name: mark-goodnote-completion
description: Mark a student's GoodNotes completion PDF against the registry-linked DaydreamEdu template and mapped answer-page range, then write a canonical JSON marking artifact under `ai_study_buddy/context/marking_results/<student>/<subject_context>/` and a derived markdown learning report under `ai_study_buddy/context/learning_reports/<student>/<subject_context>/`. Use when the user wants a GoodNotes completion graded, marked, compared with worked solutions, or turned into a learning report.
---

# Mark GoodNotes Completion

Use this workflow when the user wants a GoodNotes completion PDF visually graded against either:

- mapped answer pages (registry mapping), or
- embedded answer pages in the same weighted-assessment paper.

This skill is for JSON-first report generation and manual visual marking, not for changing registry data.

## Prerequisite

Read and follow the project skill at `../pdf-file-manager/SKILL.md` first.

Use the `PdfFileManager` Python API as the primary interface. Do not query the registry SQLite database directly for normal lookup work.

## Scope

This workflow assumes:

- the student's completion file is under a `GoodNotes/` path
- the completion file is under a `GoodNotes/` path
- the file can be registered as a completion `main` file when missing
- the completion can be linked to a DaydreamEdu template
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

1. Use natural-language request details (student, unit, book) only to fuzzy-search GoodNotes leaf folders and identify one unique completion PDF path.
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

- distinguish the GoodNotes completion path from the DaydreamEdu template path
- if the completion file has no direct answer mapping, check the linked template file
- state clearly whether the mapping was found directly on the completion or on the linked template

### 2. Render the attempt and answer pages

Render only the pages needed for visual comparison.

Preferred tool: PyMuPDF via `fitz`.

Recommended pattern:

- render all pages of the GoodNotes completion PDF
- render only the mapped answer pages from the answer PDF
- write temporary PNGs under `ai_study_buddy/context/.tmp_*`
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

### 3. Identify the gradable scope

Before assigning marks, determine exactly which questions in the completion file are gradable.

Use the visible content on the attempt pages to decide:

- which exercise or practice is included
- which question numbers are present
- whether each question has sub-parts like `(a)` and `(b)`
- whether the student wrote enough to grade

Do not grade:

- worked examples printed in the template
- decorative annotations or partial notes outside the target exercise
- cropped or ambiguous work that is not legible enough to compare confidently

If the file includes only one practice section, state that scope explicitly in the report notes.

### 4. Compare each gradable question visually

Hard prerequisite:

- **Before marking any question**, double-confirm the target exercise answer key using Section 4.5. Do not begin scoring until that verification is complete.

For each question or sub-part:

1. read Winston's written answer from the attempt pages
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

The canonical JSON must follow `marking_result.v1` and should include:

- context
- summary
- `question_results` as gradable leaf units
- `diagnosis` per result
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
| ✅ Q1(a) | `...` | `...` | 1 | 1 | `Topic > skill > subskill` |

## Report Context

- Attempt file: `/absolute/path/to/goodnotes.pdf`
- Template book file: `/absolute/path/to/template.pdf`
- Book answer file: `/absolute/path/to/answers.pdf`
- Answer page range for this exercise: `38-39`
- Mapping source: `...`

## Notes

- This report was produced by manual visual comparison of the GoodNotes attempt pages against the mapped answer pages.
- Gradable scope for this unit file was treated as ...
```

## Skill Tags Column

The markdown report may render a concise display value from `skill_tags`. The canonical JSON should store `skill_tags` as normalized machine tags.

Use the format:

`Topic > skill > subskill`

For this math workflow, examples include:

- `Ratio > unit value > difference between two parts`
- `Ratio > equalizing amounts > transfer is half the difference`

Keep labels short, concrete, and consistent across similar reports.

## Diagnosis Guidance

For each gradable result, the marking agent should populate:

- `error_tags`
- `diagnosis.mistake_type`
- `diagnosis.reasoning`
- `diagnosis.confidence`

Evidence rule:

- diagnosis must use the final answer and any visible workings, method steps, or corrections/annotations
- for math in particular, visible workings are important for distinguishing concept gaps from calculation slips, wrong methods, incomplete methods, or misread questions
- if workings are missing or illegible, lower confidence and avoid overstating root cause

## Quality Bar

Before finishing, verify:

- the JSON artifact exists and is the canonical source of truth
- the report path matches the subject and student folder
- the attempt file path is the GoodNotes completion, not the template
- the template and answer file paths are correct
- the answer page range matches the registry mapping
- every graded row is visibly supported by both the attempt page and answer page
- the target exercise answer key was isolated in a dedicated crop (not a mixed panel)
- the final key list was checked in two passes, question-by-question
- the score totals add up
- the percentage is correct
- the markdown report matches the JSON artifact

## Guardrails

- Do not query the registry SQLite DB directly.
- Do not mark from memory; inspect the rendered pages.
- Do not claim a question is wrong unless the mismatch is visible.
- Do not finalize a report until the target exercise answer key is visually verified with the required two-pass isolated-crop protocol.
- Do not silently grade beyond the visible scope of the completion file.
- If the answer mapping or template link is missing, stop and report the missing dependency instead of guessing.
- If handwriting or page coverage is too unclear to grade reliably, say so and limit the report to confident items only.
- Do not leave temporary rendered PNGs in tracked report folders; keep them under `ai_study_buddy/context/.tmp_*` and clean them up after marking.
- Do not treat markdown as canonical data; always write JSON first.

## Output Expectations

In the final user response:

- give the path to the created JSON artifact
- give the path to the created report
- summarize the score briefly
- mention the answer page range used
- mention if any grading decisions were uncertain or excluded
