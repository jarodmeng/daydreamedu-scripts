# Review: Optimize AI marking workflow (Codex session)

> Reviewed by: Cursor (claude-4.6-opus-high-thinking), 2026-04-10
>
> Source conversation: `codex_export_optimize_ai_marking_workflow.md`

---

## Conversation Summary

The conversation (Apr 9, 2026) was a design session between you and a Codex
agent, working through how to build an efficient AI-assisted marking workflow.

### Starting Point

You laid out the end-to-end goal: respond to a request like
*"Emma has done Q1-10 in <book X unit Y>. Help me mark it."* You identified
6 steps required (find student's GoodNotes file, trace to template, find book,
find answer page range, visually inspect, then mark and generate a learning
report) and asked how to make the process cheaper and faster.

### Key Design Decisions (in order)

1. **Separate deterministic lookup from expensive AI grading.**
The agent's central recommendation was that steps 1-4 (file discovery, template
resolution, book group, answer mapping) should be 100% deterministic Python
using the existing `pdf_file_manager` registry, and only steps 5-6
(visual inspection + marking) should spend vision tokens.

2. **Created `ai_study_buddy/marking/` package.**
A new `marking` package was placed outside `utils/` to keep it at the
"application/workflow" layer rather than the "primitives" layer. It contains:
- `context_resolver.py` - the `resolve_marking_context()` function that
  orchestrates registry lookups
- `models.py` - `MarkingContext` and `QuestionSelection` dataclasses
- `__init__.py` - clean public API

3. **Evolved the question selection model.**
Initially `question_start`/`question_end` (simple numeric range). You caught
that this breaks for units with section-restart numbering (e.g., the Emma
Thematic Test report where MCQ Q1-10 is followed by open-ended Q1(a)-Q8(b)).
Redesigned to `QuestionSelection` with `raw_text`, `canonical_refs`, and
`section_hint`.

4. **Designed a hierarchical Unit -> Block -> Question model.**
You pushed the conversation from "break a unit into questions" to recognizing
that questions are not always the true atomic visual unit. English/Chinese
comprehension passages are shared by multiple questions. This led to the
`Unit -> Block/Stimulus -> Question` hierarchy, where a `Block` (passage,
cloze, visual text, table) can be cropped/stored once and reused across
multiple questions.

5. **Updated existing design docs.**
Added `stimulus_blocks` and `shared-stimulus` concepts to `L3_DATA_STRATEGY.md`
and `L4_INGESTION_PIPELINE.md`, keeping `question_objects` as the grading unit
but adding the missing middle layer.

6. **Identified `question_splitter` (`archive/question_splitter/`) as v1 base for math/science.**
The existing OCR-based splitter already detects question starts, produces
per-question crops with bounding boxes, handles multi-page questions, and has a
basic STEM reassignment mechanism. The plan is to build a thin adapter on top
that converts its output into the new `unit_index.json` schema, starting with
math/science where assumptions (left-margin numeric starts, monotonic
numbering, full-width crops) hold well.

---

## High-Level Thoughts

**What the conversation got right:**

1. **The layering is clean.**
Separating `pdf_file_manager` (registry primitives) ->
`marking/context_resolver` (workflow composition) -> future `marking/marker`
(actual grading) is the right architecture. The resolver function is
essentially just "know how to use the registry in the right order", which is
exactly what it should be.

2. **The stimulus/block concept is well-motivated.**
The jump from flat question lists to `Unit -> Block -> Question` is the single
most important design insight in the conversation. Without it, you would pay
duplicate tokens for the same comprehension passage across every linked
question. The fact that `L4_INGESTION_PIPELINE.md` already had `passage_ref` as
a proto-version of this validates the direction.

3. **"Build the index once, reuse deterministically" is the right cost
strategy.**
The proposed `unit_marking_pack` (question index + cached crops + answer
mapping) means the expensive vision work happens once per template, not once
per marking request.

**What I'd watch out for or push further:**

1. **The `resolve_marking_context` implementation is optimistic about data
completeness.**
The current code assumes the registry has all the links (student -> attempt
file -> template -> book group -> answer mapping). In practice, you will hit
gaps: missing template links, unregistered GoodNotes files, unmapped answer
pages. The error messages are clear, but you may want a "partial context" mode
that returns what it can find and flags what is missing, rather than
hard-failing.

2. **The question indexing step is the real bottleneck, not the resolver.**
The conversation spent significant time on `resolve_marking_context`, which is
essentially solved (it is just registry orchestration). The hard unsolved
problem is `build_question_index(template_file)`: detecting question boundaries,
handling section restarts, and building the block/question hierarchy.
`question_splitter` is a reasonable v1 for math/science, but the gap to
English/Chinese comprehension is large (shared passages, cloze fills,
composition prompts, visual texts). I would prioritize getting the
question-indexing pipeline working for a few real science units end-to-end
before worrying about cross-subject generalization.

3. **The schema is ambitious for v1.**
The full `unit_index.json` with `stimulus_blocks`, normalized bboxes, asset
paths, OCR text, and confidence scores is the right long-term target, but it is
a lot to build at once. A pragmatic v1 might just be: run `question_splitter`
on a template, produce a simple question list with page numbers and crop paths,
and manually verify. The block/stimulus layer can be added when
English/Chinese support is needed.

4. **Student answer extraction is underspecified.**
The conversation focused heavily on template/answer-key indexing but did not go
deep on how to extract the student's handwritten work for each question. That
is arguably the hardest visual task: matching the student's GoodNotes
annotations (which may not align perfectly with the template's question
boundaries) to the indexed questions. This will likely need its own design
pass.

5. **The `question_splitter` is Tesseract-only, which has limits.**
It works for clean printed worksheets with standard numbering, but will struggle
with handwriting-heavy pages, mixed fonts, or non-standard layouts. For v2+
you will likely want a vision-LLM-assisted indexing path for difficult cases,
falling back to `question_splitter` for easy ones, which aligns with the
"deterministic first, AI for ambiguous cases" philosophy from the conversation.

**Bottom line:** The conversation produced a solid architectural skeleton. The
registry-backed deterministic resolver is done and usable. The next high-value
work is getting question indexing working end-to-end for a few real science
units, producing actual `unit_index.json` files that the marking pipeline can
consume.
