# Codex session export
**thread_name:** Optimize AI marking workflow  
**session_id:** `019d72bc-8297-7960-a55f-170f7f7581d6`  
**source:** `~/.codex/sessions/2026/04/09/rollout-2026-04-09T22-54-10-019d72bc-8297-7960-a55f-170f7f7581d6.jsonl`  

---

## Session meta

- **cwd:** `/Users/jarodm/github/jarodmeng/daydreamedu-scripts`
- **id:** `019d72bc-8297-7960-a55f-170f7f7581d6`

---

### User (2026-04-09T15:05:22.011Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
context
1) ai_study_buddy/context/ has a bunch of learning reports that are results from AI marking Winston and Emma's attempt on a few units from a few books. they are proofs of concept that the marking and learning reports can be "automated" or assisted by AI.
2) [split_book_answer_by_unit_using_ai](../../split_book_answer_by_unit_using_ai) has a few attempts whereby we used AI to generate mapping between a book's units to their page ranges in the book's answers/worked solution file. the results are stored in the pilot_ground_truth/ subfolder.
3) we added a function in [pdf_file_manager](ai_study_buddy/pdf_file_manager) utility to record the mapping between unit file and answer file page range so that it's easier to find the part of the answer file corresponding to a unit file. the mapping data is imported from the ground truth processed by the AI in the [split_book_answer_by_unit_using_ai](../../split_book_answer_by_unit_using_ai) folder.

my goal is to build a system that can respond to a question like "Emma has done question 1-10 in <book X unit Y>. Help me mark it"

to do that
1) the AI needs to understand how to find Emma's working in a GoodNotes/ registered file
2) trace that GoodNotes/ file to its template file in the DaydreamEdu/ folder (this link data should be in the registry, so the AI needs to understand how to use the registry to find the tempate)
3) find the book to which the unit file belongs to (this data is also in the registry)
4) find the page range of the unit's answer in the book's answer file (now this informaton is in the registry too)
5) visually inspect question 1-10 from Emma's working and also those questions' answers
6) mark and generate a learning report like the ones in the [learning_reports](ai_study_buddy/context/singapore_primary_science/learning_reports) folder.

I wonder what can be done to make this process much more efficient and less costly (in terms of time and tokens).


### Assistant — *commentary* (2026-04-09T15:05:29.359Z)

I’m going to inspect the existing PDF registry workflow and the proof-of-concept folders so I can ground the recommendations in how your repo already models GoodNotes files, templates, books, and answer-page mappings.

### Assistant — *commentary* (2026-04-09T15:05:34.991Z)

I found the repo already has most of the relation types you need, including GoodNotes→template linking and unit→answer-page mappings, so I’m reading that workflow next and then I’ll turn it into a lower-cost system design rather than a generic AI pipeline.

### Assistant — *commentary* (2026-04-09T15:05:46.155Z)

I’ve got the registry side. Next I’m looking at one actual marking report and the implemented API surface so the efficiency ideas match the output shape you already want, not a hypothetical one.

### Assistant — *commentary* (2026-04-09T15:05:51.922Z)

The current setup is already very close to a cheap retrieval pipeline: the expensive part should only be visual marking, while file discovery and page-range lookup can be made deterministic from the registry. I’m checking one more layer in the code to see where you can collapse steps or precompute indexes.

### Assistant — *final_answer* (2026-04-09T15:06:12.473Z)

The biggest win is to make steps `1-4` completely non-AI and only spend vision tokens on `5-6`.

From what’s already in the repo, you’re very close:

- GoodNotes completion -> template is already deterministic via `resolve_goodnotes_template_path`, `link_goodnotes_template_for_file`, and `get_template` in [pdf_file_manager.py](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/pdf_file_manager/pdf_file_manager.py).
- Unit -> book group is already deterministic via `get_file_group_membership` / `get_file_group`.
- Unit -> answer file + answer pages is already deterministic via `get_book_answer_mapping`.
- Your boundary-first answer-mapping workflow in [book_answer_boundary_prompt.md](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/split_book_answer_by_unit_using_ai/prompts/book_answer_boundary_prompt.md) is the right pattern: ask AI only for the ambiguous visual part, then assemble the rest in code.

So I’d redesign the marking flow like this:

1. Build a single deterministic “marking context resolver”.
   Input: student name, book label, unit label, question range, maybe attempt path.
   Output: attempt file, template file, book group, answer file, answer page range, and the exact pages likely containing Q1-10.
   This should be pure `PdfFileManager` logic, no model call.

2. Precompute per-template “question index” once.
   For each template/unit file, store:
   - which pages contain Q1, Q2, ...
   - rough bounding boxes if possible
   - question type: MCQ, short answer, open response
   This is the next big efficiency layer, because “Q1-10” should not require rereading the whole unit every time.

3. Precompute per-answer-file “answer index” once.
   For each mapped unit, store:
   - answer pages
   - question numbers found on each page
   - optional cropped answer regions
   Then marking Q1-10 becomes a narrow retrieval task, not a fresh visual search.

4. Cache rendered page images and OCR/layout artifacts by file hash + page number.
   Do not re-render PDFs on every run.
   Store:
   - page PNG
   - OCR text
   - lightweight layout JSON
   - optional thumbnail crops for each question

5. Use a two-stage marking pipeline.
   Stage A: cheap extraction
   - find student answer for Q1-10
   - find official answer/rubric for Q1-10
   - produce compact JSON
   Stage B: expensive reasoning
   - only grade the extracted question pairs
   - then synthesize the learning report

6. Grade per question, then write the report from structured marks.
   Don’t ask one model call to both inspect pages and write the whole report.
   Use an intermediate schema like:
   - `question_id`
   - `student_answer`
   - `correct_answer`
   - `marks_awarded`
   - `mistake_type`
   - `teaching_point`
   Then generate the markdown report last.

7. Route by question type.
   - MCQ / fill-in / exact short answers: mostly deterministic or cheap model
   - open-ended science explanations: larger multimodal model only when needed
   This will cut cost a lot.

The highest-value new artifact is a reusable `unit_marking_pack` per template/unit:
- template question index
- answer-page mapping
- answer question index
- cached page renders/OCR
- maybe concept links for report writing

Then “Help me mark Emma’s Q1-10” becomes mostly retrieval plus a small grading call.

If you want, I can turn this into a concrete implementation plan and sketch the first utility, probably something like `resolve_marking_context(...)` plus a `unit_marking_pack` JSON format.

### User (2026-04-09T15:08:32.080Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
what does "resolve_marking_context()" do?


### Assistant — *final_answer* (2026-04-09T15:08:41.538Z)

`resolve_marking_context()` would be the deterministic lookup step that turns a user request like:

`Emma has done question 1-10 in Science Practice Primary 5 and 6, unit 17. Help me mark it.`

into a compact machine-usable bundle of facts for the marking pipeline.

In practice, it would do things like:

1. Identify the student attempt file.
   Find Emma’s registered GoodNotes/main file for that unit.

2. Resolve the template file.
   Follow the registry template link, or resolve/link it if needed.

3. Resolve the book group.
   Find which `group_type='book'` group that unit belongs to.

4. Resolve the answer mapping.
   Use `get_book_answer_mapping(...)` to get the answer file and answer page range for that unit.

5. Narrow the marking scope.
   Record that we only need Q1-10, not the full unit.

So the output would be something like:

```json
{
  "student_name": "Emma",
  "student_id": "emma",
  "attempt_file_id": "...",
  "attempt_file_path": "...GoodNotes/...pdf",
  "template_file_id": "...",
  "template_file_path": "...DaydreamEdu/...pdf",
  "book_group_id": "...",
  "book_label": "Science Practice Primary 5 and 6",
  "answer_file_id": "...",
  "answer_file_path": "...Answers.pdf",
  "answer_page_start": 17,
  "answer_page_end": 18,
  "starts_mid_page": false,
  "ends_mid_page": true,
  "question_range": {
    "start": 1,
    "end": 10
  }
}
```

The key idea is: it does no marking itself. It just assembles the exact files and page ranges the later marking steps should use, so the AI doesn’t waste time/tokens figuring out file relationships every run.

If you want, I can sketch the function signature and the exact fields I’d include in the return object.

### User (2026-04-09T15:16:15.123Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
this process is just knowing how to use the registry tool, right?


### Assistant — *final_answer* (2026-04-09T15:16:22.337Z)

Yes, mostly.

`resolve_marking_context()` is not really “AI intelligence” by itself. It’s mainly a thin, reliable layer that knows how to use the registry tool in the right order and package the result for downstream marking.

The value is not that it discovers new information, but that it standardizes these registry steps:

1. Find the student’s attempt file.
2. Get or resolve its template.
3. Find the book group.
4. Get the unit’s answer-file mapping.
5. Return the exact files/pages/questions the marker should inspect.

So conceptually, it is “registry orchestration”.

Why it is still worth naming as a function:
- it prevents every future marking script/prompt/agent from re-implementing the same lookup logic
- it gives you one canonical contract between “file lookup” and “actual marking”
- it keeps the expensive multimodal step focused only on visual grading

So I’d describe it as:

`resolve_marking_context()` = a deterministic adapter over `pdf_file_manager`, not a separate AI component.

If you want, I can propose which parts should stay inside `pdf_file_manager` itself versus which parts should live in a higher-level marking workflow module.

### User (2026-04-09T15:20:42.453Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
what's the signature and output for "resolve_marking_context()"?


### Assistant — *final_answer* (2026-04-09T15:20:54.433Z)

I’d make it explicit, deterministic, and slightly higher-level than `pdf_file_manager`.

A good Python signature would be:

```python
def resolve_marking_context(
    *,
    student_name: str | None = None,
    student_id: str | None = None,
    attempt_file_id_or_path: str | Path | None = None,
    book_label: str | None = None,
    unit_query: str | None = None,
    question_start: int | None = None,
    question_end: int | None = None,
    auto_link_template: bool = False,
) -> MarkingContext:
    ...
```

The idea is that the caller can identify the attempt in one of two ways:

- directly: `attempt_file_id_or_path`
- indirectly: `student_name`/`student_id` + `book_label` + `unit_query`

I’d return a structured object like this:

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass
class QuestionRange:
    start: int | None
    end: int | None


@dataclass
class MarkingContext:
    student_id: str | None
    student_name: str | None

    attempt_file_id: str
    attempt_file_path: str

    template_file_id: str
    template_file_path: str

    book_group_id: str
    book_label: str

    unit_file_id: str
    unit_file_path: str
    unit_label: str | None

    answer_file_id: str
    answer_file_path: str

    answer_page_start: int
    answer_page_end: int
    starts_mid_page: bool
    ends_mid_page: bool
    answer_mapping_source: str | None
    answer_mapping_notes: str | None

    question_range: QuestionRange

    needs_visual_attempt_pages: bool = True
    needs_visual_answer_pages: bool = True
```

Example output:

```json
{
  "student_id": "emma.rs.meng@gmail.com",
  "student_name": "Emma",
  "attempt_file_id": "file_attempt_123",
  "attempt_file_path": "/.../GoodNotes/.../c_Science Practice Primary 5 and 6 - 17 Interactions - Topical Test 1 Forces.pdf",
  "template_file_id": "file_template_456",
  "template_file_path": "/.../DaydreamEdu/.../_c_Science Practice Primary 5 and 6 - 17 Interactions - Topical Test 1 Forces.pdf",
  "book_group_id": "book_group_789",
  "book_label": "Science Practice Primary 5 and 6",
  "unit_file_id": "file_template_456",
  "unit_file_path": "/.../DaydreamEdu/.../_c_Science Practice Primary 5 and 6 - 17 Interactions - Topical Test 1 Forces.pdf",
  "unit_label": "17 Interactions - Topical Test 1 Forces",
  "answer_file_id": "file_answer_999",
  "answer_file_path": "/.../DaydreamEdu/.../_c_Science Practice Primary 5 and 6 - 26 Answers.pdf",
  "answer_page_start": 22,
  "answer_page_end": 23,
  "starts_mid_page": false,
  "ends_mid_page": true,
  "answer_mapping_source": "imported_ground_truth",
  "answer_mapping_notes": "page 23 splits into next unit",
  "question_range": {
    "start": 1,
    "end": 10
  },
  "needs_visual_attempt_pages": true,
  "needs_visual_answer_pages": true
}
```

A couple of design choices I’d recommend:

- Return both `attempt_file_*` and `unit_file_*`.
  Usually the `unit_file` is the template, but keeping both avoids ambiguity.
- Include mapping provenance fields like `answer_mapping_source`.
  That’s useful later if you want to trust `manual_verified` more than `model_generated`.
- Keep `question_start`/`question_end` optional.
  The same resolver can support “mark whole unit” later.

If you want, I can next propose:
1. the validation rules for this function, or
2. a concrete implementation sketch against `PdfFileManager`.

### User (2026-04-09T15:21:38.377Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
where will you put the function? ai_study_buddy/utils/ ?


### Assistant — *final_answer* (2026-04-09T15:21:43.546Z)

I would not put it in `ai_study_buddy/utils/` directly.

Best home is a marking-specific module, because this function is not a general utility and not really part of the low-level PDF registry either. It’s an orchestration layer on top of `pdf_file_manager`.

I’d prefer something like:

`ai_study_buddy/marking/context_resolver.py`

or, if you want to keep the feature scoped tighter at first:

`ai_study_buddy/marking/resolve_marking_context.py`

Why:
- `pdf_file_manager` should stay focused on file registry primitives.
- `resolve_marking_context()` is application logic for the marking workflow.
- `ai_study_buddy/utils/` is usually too vague and tends to become a junk drawer.

A clean layering would be:

- `ai_study_buddy/pdf_file_manager/`
  Registry primitives: find file, get template, get book group, get answer mapping.
- `ai_study_buddy/marking/context_resolver.py`
  Workflow composition: turn a user marking request into a `MarkingContext`.
- `ai_study_buddy/marking/marker.py`
  Actual grading / report generation later.

So short answer: no, I’d avoid `ai_study_buddy/utils/`; I’d create a `marking` package.

### User (2026-04-09T15:22:27.125Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
this makes sense. let's create a marking package


### Assistant — *commentary* (2026-04-09T15:22:31.207Z)

I’m going to inspect the `ai_study_buddy` layout and then scaffold a small `marking` package with a clear home for `resolve_marking_context()` and its types, keeping `pdf_file_manager` as the low-level dependency.

### Assistant — *commentary* (2026-04-09T15:22:37.193Z)

I’ve confirmed there isn’t already an `ai_study_buddy/marking` area, so I’m going to scaffold it cleanly rather than tuck this into `utils`. I’m reading the registry types now so the new package can depend on them without duplicating concepts badly.

### Assistant — *commentary* (2026-04-09T15:22:42.249Z)

I’m going to add the package with real types and a first-pass `resolve_marking_context()` implementation, not just empty files, so we have a usable seam between registry lookup and future marking logic.

### Assistant — *commentary* (2026-04-09T15:22:44.606Z)

I’ve got enough to scaffold the first version cleanly. I’m adding a small `marking` package with types plus a resolver that composes existing `PdfFileManager` reads rather than extending the registry layer itself.

### Assistant — *commentary* (2026-04-09T15:22:56.267Z)

I’m at the edit step now. I’m creating a focused `marking` package with a small public surface: types, a resolver, and package exports. Then I’ll run a quick import/compile check so we know the scaffold is sound.

### Assistant — *commentary* (2026-04-09T15:23:33.700Z)

The package is in place. I’m running a quick syntax/import check now and then I’ll summarize the shape so we can decide whether to add tests or keep iterating on the resolver contract next.

### Assistant — *final_answer* (2026-04-09T15:23:40.960Z)

Created a new `ai_study_buddy.marking` package and gave it a real first-pass resolver instead of a placeholder.

The package exports `resolve_marking_context()`, `MarkingContext`, `QuestionRange`, and a dedicated `MarkingContextResolutionError` from [ai_study_buddy/marking/__init__.py](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/marking/__init__.py). The core orchestration lives in [ai_study_buddy/marking/context_resolver.py](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/marking/context_resolver.py), and the structured return types live in [ai_study_buddy/marking/models.py](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/marking/models.py).

This first version resolves:
- student by `student_id` or exact `student_name`
- attempt file by exact file id/path, or by `student + unit_query (+ optional book_label)`
- linked template file, with optional `auto_link_template=True`
- the owning `book` group
- the unit’s `book_answer_mapping`
- the requested question range

I also verified the new package compiles and imports cleanly with `python3 -m py_compile` and a direct import check.

A typical call now looks like:

```python
from ai_study_buddy.marking import resolve_marking_context

context = resolve_marking_context(
    student_name="Emma",
    book_label="Science Practice Primary 5 and 6",
    unit_query="17 Interactions - Topical Test 1 Forces",
    question_start=1,
    question_end=10,
    auto_link_template=True,
)
```

Next good step would be adding tests for the resolver against your fixture registry, or tightening the unit matching logic if you want more flexible user phrasing.

### User (2026-04-09T15:27:31.838Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
we need to think more carefully about question_start and question_end. this is assuming that each unit has continuously increasing question index. take a look at [c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1 - Marking Report.md](ai_study_buddy/context/singapore_primary_science/learning_reports/emma/c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1 - Marking Report.md)  Marking Table. Sometimes the question index restarts when it's a different section. In this example, the first section is MCQ and the second section is open-ended questions.


### Assistant — *commentary* (2026-04-09T15:27:44.188Z)

You’re right: plain `question_start` / `question_end` bakes in a numbering scheme that the worksheets don’t consistently follow. I’m going back to the report shape and then I’ll tighten the resolver contract so it carries question intent without assuming one global counter.

### Assistant — *commentary* (2026-04-09T15:27:54.121Z)

You’re right: the report makes the flaw very concrete. `Q1-10` only works for the first MCQ block in that file, and the same unit also contains a restarted sequence like `Q1(a)`, `Q2(a)`, `Q6(c)(ii)` in the open-ended section, so a numeric range is the wrong abstraction for the resolver contract.

### Assistant — *commentary* (2026-04-09T15:28:08.877Z)

I’m updating the import check to match the new contract. The resolver should now carry question intent as text and/or canonical labels, instead of pretending every unit has one continuous numeric sequence.

### Assistant — *final_answer* (2026-04-09T15:28:20.713Z)

You were right to flag that. Looking at the Marking Table in [c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1 - Marking Report.md](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/context/singapore_primary_science/learning_reports/emma/c_Science%20Thematic%20Tests%20and%20Exam%20Practice%20Primary%204%20-%2001%20Systems%20Thematic%20Test%201%20-%20Marking%20Report.md), the unit has both a first block `Q1` to `Q10` and then a restarted sequence like `Q1(a)`, `Q2(a)`, `Q6(c)(ii)`. So `question_start` / `question_end` was the wrong contract for the resolver.

I updated the new marking package to stop assuming a single continuous question index. `resolve_marking_context()` now accepts:
- `question_request`: raw user wording like `"MCQ Q1-10"` or `"Section B Q1(a)-Q4(d)"`
- `question_refs`: explicit canonical refs if the caller already knows them, like `["Q1", "Q2", "Q3"]` or `["Q1(a)", "Q1(b)", "Q2(a)"]`
- `section_hint`: optional hint like `"MCQ"` or `"Open-ended"`

Those are packaged into `QuestionSelection` in [ai_study_buddy/marking/models.py](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/marking/models.py), and the resolver now returns `question_selection` instead of `question_range` from [ai_study_buddy/marking/context_resolver.py](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/marking/context_resolver.py). The package export in [ai_study_buddy/marking/__init__.py](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/marking/__init__.py) was updated too, and I re-ran compile/import checks successfully.

A better call shape now is:

```python
context = resolve_marking_context(
    student_name="Emma",
    book_label="Science Thematic Tests and Exam Practice Primary 4",
    unit_query="01 Systems Thematic Test 1",
    question_request="MCQ Q1-10",
    section_hint="MCQ",
)
```

or, when you already know the exact refs:

```python
context = resolve_marking_context(
    student_name="Emma",
    unit_query="01 Systems Thematic Test 1",
    question_refs=["Q1(a)", "Q1(b)", "Q1(c)", "Q2(a)"],
    section_hint="Open-ended",
)
```

The next step I’d recommend is adding a separate question-indexing layer that maps page regions to canonical refs like `Q1`, `Q1(a)`, `Q6(c)(ii)`, because that is the piece that can turn a raw `question_request` into precise visual targets.

### User (2026-04-09T15:32:17.026Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
can this next step be done deterministically in python or does it need AI involvement?


### Assistant — *final_answer* (2026-04-09T15:32:25.241Z)

Partly deterministic, partly not.

The clean split is:

Deterministic in Python:
- Parse and normalize explicit refs like `Q1`, `Q1(a)`, `Q6(c)(ii)`.
- Expand simple user requests if the section is already known, like `"Q1-10"` -> `Q1 ... Q10`.
- Match refs against an already-built question index for a unit.
- Use registry data to fetch the right files, answer pages, and cached artifacts.
- Assemble report inputs once per-question marking results exist.

Usually needs AI or at least OCR/layout extraction:
- Finding where each question actually is on the page in a new unseen worksheet.
- Determining section boundaries like “these `Q1-10` are MCQ, then numbering restarts for open-ended”.
- Matching ambiguous visual numbering when formatting is inconsistent.
- Extracting student answers from handwritten or messy annotated pages.

So the key is:

1. Build the question index once, possibly with AI assistance.
2. Reuse it deterministically afterward.

That means the expensive step does not need to happen every time someone says “mark Emma’s Q1-10”. It only happens the first time a new template/unit is indexed, or when the index is low-confidence.

A practical architecture would be:
- `resolve_marking_context()` stays deterministic.
- `build_question_index(template_file)` can be AI-assisted.
- `resolve_question_selection(context, question_request)` becomes deterministic once the question index exists.
- marking then uses the resolved question regions plus answer regions.

So: for new units, likely yes, some AI involvement. For repeated use on already-indexed units, it should be deterministic in Python.

### User (2026-04-09T15:49:49.167Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
how do we break a unit file into a collection of questions? it seems that question is the atomic element and knowing where each question is in the unit can be useful to save potential duplicated image cropping and visual processing of the same question.


### Assistant — *final_answer* (2026-04-09T15:50:02.521Z)

Yes, I think that’s the right mental model: the unit file should be preprocessed into a set of question objects, and those question objects become the atomic reusable elements for marking.

A good structure is:

1. `Unit`
   One template/unit PDF.

2. `Question`
   A canonical question entity like `Q1`, `Q1(a)`, `Q6(c)(ii)`.

3. `QuestionRegion`
   The exact page(s) and bounding boxes where that question appears in the template, answer file, and eventually student attempt.

I’d model it roughly like this:

```python
@dataclass
class QuestionRef:
    raw_label: str          # "Q6(c)(ii)"
    root: str              # "Q6"
    parts: tuple[str, ...] # ("c", "ii")


@dataclass
class PageRegion:
    page_number: int
    bbox: tuple[int, int, int, int] | None
    role: str              # "question", "answer", "student_answer", "working"


@dataclass
class UnitQuestion:
    ref: QuestionRef
    section_name: str | None
    question_type: str | None
    template_regions: tuple[PageRegion, ...]
    answer_regions: tuple[PageRegion, ...] = ()
```

How to break a unit into questions:

1. Render template pages once.
2. Detect text/layout blocks on each page.
3. Identify question headers like `Q1`, `1.`, `1(a)`, `(a)`, roman numerals, etc.
4. Build a hierarchy:
   `Q6` -> `Q6(c)` -> `Q6(c)(ii)`
5. Convert that into contiguous regions:
   from this question header until the next sibling question header.
6. Store the result as a `question index` for that unit.

That question index is the key reusable artifact.

What can be deterministic vs AI-assisted:

Deterministic / cheap:
- PDF page rendering
- OCR
- parsing visible labels like `Q1`, `Q1(a)`, `Q6(c)(ii)`
- turning ordered labels into spans
- caching crops by `(file_hash, page, bbox)`

Usually AI-assisted or at least heuristic-heavy:
- recognizing section starts when formatting varies a lot
- deciding whether `(a)` belongs under `Q1` or `Q6`
- handling diagrams, tables, or question text split awkwardly across pages
- matching answer-book layout back to template questions

So I’d recommend a hybrid pipeline:

1. Deterministic first pass:
   use OCR + layout + regex parsing to propose question boundaries.
2. AI only for ambiguous cases:
   ask the model to fix unresolved boundaries or nesting.
3. Save the final `question index`:
   so future marking calls reuse it with no repeated detection.

The main reusable outputs should be:

- `unit_question_index.json`
- per-question crops for template
- per-question crops for answer key
- later, per-attempt per-question crops for student work

Then “mark Emma’s Q1-10” becomes:
- resolve unit
- load question index
- resolve which question objects are wanted
- reuse cached crops if present
- only inspect those questions

That will save a lot of duplicate image cropping and multimodal processing.

If you want, I can sketch a concrete on-disk JSON schema for `unit_question_index.json` next.

### User (2026-04-09T15:54:17.572Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
this model perhaps works for math and science questions. but chinese and english has comprehension questions whereby multiple questions share the same stem (i.e. the paragraph).


### Assistant — *final_answer* (2026-04-09T15:54:28.915Z)

Yes, exactly. That means `question` is not always the true atomic visual unit.

For Chinese and English comprehension, the better model is:

1. `PassageSet` or `SharedStemBlock`
   The shared passage / dialogue / image / stimulus.

2. `Question`
   Individual items like `Q1`, `Q2`, `Q3(a)` that depend on that shared stem.

So the hierarchy becomes:

- `Unit`
- `Block`
- `Question`

Where a `Block` can be:
- standalone question block
- shared-stem comprehension block
- cloze passage block
- composition prompt block
- MCQ block

A better data model would be something like:

```python
@dataclass
class UnitBlock:
    block_id: str
    block_type: str          # "standalone", "shared_stem", "cloze", "composition", "mcq_group"
    title: str | None
    stem_regions: tuple[PageRegion, ...]
    question_refs: tuple[str, ...]


@dataclass
class UnitQuestion:
    ref: str
    block_id: str
    prompt_regions: tuple[PageRegion, ...]
    answer_regions: tuple[PageRegion, ...]
```

Why this matters:
- If `Q1-Q5` all depend on the same passage, you should crop/store that passage once.
- When marking, the model should see:
  - the shared stem once
  - the target question only
  - the student’s answer
  - the official answer
- That avoids repeatedly paying tokens for the same paragraph.

So the real reusable atomic assets are probably:

- `Stem asset`
- `Question asset`
- `Answer asset`
- `Student answer asset`

not just “question crop”.

For math/science:
- many blocks will just be `standalone`
- question ~= block, so the simpler model still works

For Chinese/English:
- many questions will point to one shared block

So I’d refine the indexing goal from:

“break a unit into questions”

to:

“break a unit into instructional blocks, then questions within each block”

That generalizes much better across subjects.

A good rule of thumb:
- If multiple questions rely on the same visible context, that context should be a first-class `block`.
- Questions then reference the block instead of duplicating it.

So I’d suggest this hierarchy:

- `UnitIndex`
- `BlockIndex`
- `QuestionIndex`

And then marking can reuse:
- one shared passage crop for `Q1-Q5`
- separate small crops for each subquestion
- one answer block or per-question answer crop as needed

If you want, I can next sketch a subject-agnostic JSON schema for `unit_index.json` that supports both:
- science/math standalone questions
- english/chinese comprehension with shared stems.

### User (2026-04-09T15:55:34.943Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
yes


### Assistant — *final_answer* (2026-04-09T15:55:51.089Z)

A good subject-agnostic shape is: `unit -> blocks -> questions -> regions/assets`.

Something like this would work well:

```json
{
  "schema_version": "1.0",
  "unit_file_id": "file_template_123",
  "unit_file_path": "/.../_c_Science Thematic Tests and Exam Practice Primary 4 - 01 Systems Thematic Test 1.pdf",
  "unit_label": "01 Systems Thematic Test 1",
  "subject": "science",
  "blocks": [
    {
      "block_id": "block_mcq_1",
      "block_type": "mcq_group",
      "title": "Multiple Choice",
      "section_hint": "MCQ",
      "shared_stem_regions": [],
      "question_ids": ["q_q1", "q_q2", "q_q3"]
    },
    {
      "block_id": "block_comp_1",
      "block_type": "shared_stem",
      "title": "Comprehension Passage A",
      "section_hint": "Open-ended",
      "shared_stem_regions": [
        {
          "page": 2,
          "bbox": [120, 180, 1420, 980],
          "asset_id": "asset_stem_block_comp_1_p2"
        }
      ],
      "question_ids": ["q_q1a", "q_q1b", "q_q1c", "q_q2a"]
    }
  ],
  "questions": [
    {
      "question_id": "q_q1",
      "ref": "Q1",
      "parent_ref": null,
      "block_id": "block_mcq_1",
      "question_type": "mcq",
      "prompt_regions": [
        {
          "page": 1,
          "bbox": [100, 220, 820, 380],
          "asset_id": "asset_q1_prompt"
        }
      ],
      "answer_regions": [
        {
          "page": 1,
          "bbox": [950, 180, 1280, 260],
          "asset_id": "asset_q1_answer"
        }
      ]
    },
    {
      "question_id": "q_q1a",
      "ref": "Q1(a)",
      "parent_ref": "Q1",
      "block_id": "block_comp_1",
      "question_type": "short_open",
      "prompt_regions": [
        {
          "page": 2,
          "bbox": [140, 1020, 1180, 1160],
          "asset_id": "asset_q1a_prompt"
        }
      ],
      "answer_regions": [
        {
          "page": 5,
          "bbox": [160, 240, 1320, 420],
          "asset_id": "asset_q1a_answer"
        }
      ]
    }
  ],
  "assets": [
    {
      "asset_id": "asset_stem_block_comp_1_p2",
      "kind": "shared_stem",
      "page": 2,
      "bbox": [120, 180, 1420, 980],
      "image_path": "/.../cache/unit_x/block_comp_1_stem_p2.png",
      "ocr_text": "..."
    }
  ]
}
```

I’d use these core ideas:

- `block`
  The reusable visual/contextual unit.
  Examples: `standalone`, `shared_stem`, `mcq_group`, `cloze`, `composition`, `listening_prompt`, `visual_stimulus`.

- `question`
  The grading unit.
  Examples: `Q1`, `Q1(a)`, `Q6(c)(ii)`.

- `shared_stem_regions`
  First-class regions for passages, dialogues, diagrams, tables, or images shared by multiple questions.

- `prompt_regions`
  The visual area specific to that question.

- `answer_regions`
  Where the official answer for that question lives.

This gives you the right behavior across subjects:

- Math/science:
  many blocks will be `standalone` or `mcq_group`.
- Chinese/English comprehension:
  one `shared_stem` block can support many questions.
- Diagram/data interpretation:
  shared chart/table/image can be a block too.

A few design rules I’d strongly recommend:

- `ref` should stay human-facing: `Q1(a)`, `Q6(c)(ii)`.
- `question_id` should be stable and machine-safe.
- `block_id` should be the join key for shared context reuse.
- `regions` should support multiple pages, since passages and answers can span pages.
- `assets` should be separately addressable so crops/OCR can be cached once and reused.

I’d also add optional confidence fields later, like:

```json
"indexing_confidence": 0.86,
"needs_review": false
```

That will help when some units are AI-indexed and others are manually corrected.

The practical payoff is:

- crop a comprehension passage once
- reuse it for `Q1-Q5`
- crop/store answer regions once
- resolve user requests like `"only the MCQ"` or `"Q1(a)-Q2(c)"` without reprocessing the full unit

If you want, I can next turn this into a concrete Python dataclass model under `ai_study_buddy/marking/`, or write a short design doc for `unit_index.json`.

### User (2026-04-09T15:56:58.827Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
read [docs](ai_study_buddy/docs) , especially [L4_INGESTION_PIPELINE.md](ai_study_buddy/docs/L4_INGESTION_PIPELINE.md) . I think there's a similar idea about breaking a unit file into questions there.


### Assistant — *commentary* (2026-04-09T15:57:02.996Z)

I’m going to read the AI Study Buddy docs, especially the ingestion pipeline doc, and look for the existing decomposition model so we can align the marking package with the repo’s own terminology instead of inventing a parallel one.

### Assistant — *commentary* (2026-04-09T15:57:07.928Z)

I found the relevant docs: the repo already frames ingestion around “question objects,” and it also notes that page-level chunks may be a pragmatic MVP before precise question boundaries. I’m reading the key sections in `L4_INGESTION_PIPELINE.md` and `L3_DATA_STRATEGY.md` now so I can map your newer block/shared-stem idea onto the existing design.

### Assistant — *commentary* (2026-04-09T15:57:14.360Z)

The docs do already contain the same core idea, and they’re a helpful sanity check: the repo’s existing language is “question objects,” with an explicit note that shared comprehension passages may need their own linkage rather than flattening everything into independent questions. I’m grabbing exact line references so I can map your newer block/shared-stem model back onto those docs precisely.

### Assistant — *final_answer* (2026-04-09T15:57:28.733Z)

Yes, the docs already contain the same core idea, and they actually give us a good way to ground the newer design.

The strongest signals are:

- [L3_DATA_STRATEGY.md#L23](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/docs/L3_DATA_STRATEGY.md#L23) says the first-class unit should be the “question object,” not PDFs or pages.
- [L3_DATA_STRATEGY.md#L102](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/docs/L3_DATA_STRATEGY.md#L102) already proposes chunking digital PDFs by question-number cues like `Q1`, `1(a)`, `Section B`, `[5]`.
- [L3_DATA_STRATEGY.md#L130](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/docs/L3_DATA_STRATEGY.md#L130) explicitly treats “section boundaries, question numbering, mark brackets” as a page-level extraction step before creating question objects.
- [L4_INGESTION_PIPELINE.md#L45](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/docs/L4_INGESTION_PIPELINE.md#L45) defines the target output as a question object per question or sub-part.
- [L4_INGESTION_PIPELINE.md#L104](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/docs/L4_INGESTION_PIPELINE.md#L104) already has `passage_ref`, which is the repo’s existing hook for shared comprehension stems.
- [L3_EXAM_FORMATS.md#L93](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/docs/L3_EXAM_FORMATS.md#L93) calls out that English comprehension passage is a shared reference for questions 66–75.
- [L3_EXAM_FORMATS.md#L118](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/docs/L3_EXAM_FORMATS.md#L118) and [L3_EXAM_FORMATS.md#L150](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/docs/L3_EXAM_FORMATS.md#L150) show Chinese formats where whole groups of questions share a passage, visual text, cloze passage, or table.

So your newer “block/shared-stem” idea is not a departure from the docs. It is really a refinement of what `passage_ref` was already hinting at.

My read is:

- The docs’ current canonical unit is still the `question object`.
- But the docs already acknowledge that some questions depend on a shared passage/stimulus.
- So the right evolution is not to replace question objects, but to formalize the missing middle layer.

I’d frame it like this:

- Keep `question object` as the grading/retrieval unit.
- Add an explicit `block` or `stimulus` layer for shared context.
- Treat `passage_ref` as the first sign of that model, but expand it so it can represent more than just prose passages.

Concretely, the doc-backed hierarchy becomes:

- `document`
- `page`
- `block` / `stimulus`
- `question object`

Where `block` can cover:
- comprehension passage
- visual text
- cloze passage
- dialogue prompt
- table/chart/diagram
- MCQ group section

Then each question object links to one optional shared block instead of duplicating that context.

So yes: the similar idea is already there in the docs. The main gap is that it’s still expressed as `question object + passage_ref`, whereas your recent discussion suggests the docs should probably be upgraded to an explicit `block/shared-stem` model.

If you want, I can next draft a small doc update proposal for [L4_INGESTION_PIPELINE.md](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/docs/L4_INGESTION_PIPELINE.md) that introduces `block` / `stimulus` cleanly without fighting the existing `question_objects` design.

### User (2026-04-09T15:58:06.818Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
ye


### Assistant — *commentary* (2026-04-09T15:58:11.921Z)

I’m going to update the ingestion docs so the existing `question_objects` model explicitly supports shared-stem blocks instead of leaving that idea implicit in `passage_ref`. Then I’ll summarize the proposed doc shape and any remaining open edges.

### Assistant — *commentary* (2026-04-09T15:58:14.491Z)

I have the exact spots. I’m going to make a focused doc update in `L4_INGESTION_PIPELINE.md` and `L3_DATA_STRATEGY.md`: keep question objects as the first-class grading unit, but add an explicit shared-stimulus/block layer so comprehension, cloze, and visual-text groups fit the schema cleanly.

### Assistant — *commentary* (2026-04-09T15:58:51.032Z)

The doc update is in. I’m doing a quick pass over the changed sections to make sure the terminology is consistent and the new `stimulus_blocks` layer complements `question_objects` instead of replacing it.

### Assistant — *final_answer* (2026-04-09T15:58:56.408Z)

Updated the docs to make the shared-stimulus idea explicit while keeping `question_objects` as the main unit.

In [L3_DATA_STRATEGY.md](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/docs/L3_DATA_STRATEGY.md#L23), I added a “shared stimuli + questions” refinement and a `stimulus block` concept for passages, cloze text, visual texts, tables, and diagrams. The key rule there is now:

- question object = atomic grading/retrieval unit
- stimulus block = reusable shared context linked to one or more questions

In [L4_INGESTION_PIPELINE.md](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/docs/L4_INGESTION_PIPELINE.md#L45), I updated the proposed schema and flow to support that:
- added a `stimulus_blocks` table
- replaced the older implicit `passage_ref` idea with `question_objects.stimulus_id`
- changed Step 6 from “Extract Question Structure” to “Extract Structure”
- changed Step 8 to crop shared stimuli once and link them to question objects
- updated the review UI description to show shared stimulus boundaries and linked question groups

This lines up well with the existing exam-format docs, especially English and Chinese comprehension passages.

The next natural step would be to mirror this in code by adding marking-side dataclasses for `StimulusBlock` and `QuestionObject`, or to draft a small `unit_index.json` schema that matches the updated docs.

### User (2026-04-09T16:03:13.313Z)

# Context from my IDE setup:

## Open tabs:
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
what's the output format conforming to the schema?


### Assistant — *final_answer* (2026-04-09T16:03:32.136Z)

A good schema-conforming output would be a structured JSON document with:

- document-level metadata
- page records
- `stimulus_blocks`
- `question_objects`

Something like this:

```json
{
  "document": {
    "id": "doc_001",
    "filename": "c_English Paper 2 Booklet B.pdf",
    "child": "winston",
    "subject": "english",
    "paper_type": "exam",
    "grade": "p6",
    "date": "2026-02-19",
    "page_count": 26,
    "has_oas": false,
    "status": "review"
  },
  "pages": [
    {
      "id": "page_12",
      "page_number": 12,
      "page_type": "question",
      "image_path": "gs://.../pages/page_12.png",
      "ocr_text": "Section I Comprehension ...",
      "earned_marks": 6,
      "available_marks": 10,
      "is_scanned": true
    }
  ],
  "stimulus_blocks": [
    {
      "id": "stim_001",
      "document_id": "doc_001",
      "page_id": "page_12",
      "stimulus_type": "passage",
      "display_label": "Section I passage",
      "printed_text": "Mina visited the rehabilitation centre ...",
      "bbox": {
        "x1": 0.08,
        "y1": 0.14,
        "x2": 0.91,
        "y2": 0.58
      },
      "crop_path": "gs://.../stimuli/stim_001.png",
      "extraction_method": "vision_llm",
      "review_status": "unreviewed"
    }
  ],
  "question_objects": [
    {
      "id": "q_066",
      "document_id": "doc_001",
      "page_id": "page_12",
      "stimulus_id": "stim_001",
      "section": "I",
      "question_type": "open_ended",
      "question_number": "66",
      "sub_part": null,
      "display_label": "Q66",
      "question_text": "Why did Mina visit the centre?",
      "max_marks": 2,
      "earned_marks": 1,
      "has_method_marks": false,
      "outcome": "partial",
      "child_answer": "She wanted to help the people there.",
      "teacher_answer": "She visited to help and learn more about the residents.",
      "mcq_options": null,
      "mcq_chosen": null,
      "mcq_correct": null,
      "rubric_scores": null,
      "teacher_feedback": "too general",
      "skill_tags": ["reading_comprehension", "answer_with_text_evidence"],
      "error_tags": ["too_general", "missing_text_evidence"],
      "question_crop": "gs://.../questions/q_066_question.png",
      "working_crop": "gs://.../questions/q_066_working.png",
      "feedback_crop": "gs://.../questions/q_066_feedback.png",
      "correction_crop": null,
      "bbox": {
        "x1": 0.10,
        "y1": 0.60,
        "x2": 0.90,
        "y2": 0.78
      },
      "extraction_method": "vision_llm",
      "review_status": "unreviewed"
    },
    {
      "id": "q_067",
      "document_id": "doc_001",
      "page_id": "page_12",
      "stimulus_id": "stim_001",
      "section": "I",
      "question_type": "open_ended",
      "question_number": "67",
      "sub_part": "a",
      "display_label": "Q67(a)",
      "question_text": "What does the phrase '...' tell you about Mina?",
      "max_marks": 1,
      "earned_marks": 1,
      "has_method_marks": false,
      "outcome": "correct",
      "child_answer": "She is caring.",
      "teacher_answer": null,
      "mcq_options": null,
      "mcq_chosen": null,
      "mcq_correct": null,
      "rubric_scores": null,
      "teacher_feedback": null,
      "skill_tags": ["inference"],
      "error_tags": [],
      "question_crop": "gs://.../questions/q_067a_question.png",
      "working_crop": "gs://.../questions/q_067a_working.png",
      "feedback_crop": "gs://.../questions/q_067a_feedback.png",
      "correction_crop": null,
      "bbox": {
        "x1": 0.10,
        "y1": 0.79,
        "x2": 0.90,
        "y2": 0.92
      },
      "extraction_method": "vision_llm",
      "review_status": "unreviewed"
    }
  ]
}
```

A few important points:

- `stimulus_id` is `null` for standalone math/science questions.
- Multiple `question_objects` can point to the same `stimulus_blocks` row.
- `bbox` should use one consistent format everywhere.
  I’d recommend normalized page fractions `0..1`, as in the example.
- `question_number` + `sub_part` should carry the canonical identity.
  Example: `question_number="67"`, `sub_part="a"`.

If you want, I can turn this into:
1. a formal JSON schema file, or
2. Python dataclasses in `ai_study_buddy/marking/`.

### User (2026-04-09T16:08:05.044Z)

# Context from my IDE setup:

## Open tabs:
- README.md: archive/question_splitter/README.md
- README.md: ai_study_buddy/pdf_file_manager/README.md
- 07-book-answer-mapping.md: ai_study_buddy/pdf_file_manager/docs/proposals/07-book-answer-mapping.md

## My request for Codex:
there's a [question_splitter](../../../archive/question_splitter) utility. can we build on top of it? I think v1 will be to make it work for math/science questions.


### Assistant — *commentary* (2026-04-09T16:08:09.032Z)

I’m going to inspect `question_splitter` and see how close it already is to the question-object shape we’ve been discussing, with math/science as the first target rather than trying to generalize to comprehension immediately.

### Assistant — *commentary* (2026-04-09T16:08:14.083Z)

I found a promising fit already: `question_splitter` is doing OCR-based question-start detection, full-width vertical segmentation, multi-page question outputs, and even top-of-page shared “stem” reassignment. I’m reading its README and one sample manifest now so I can tell you concretely whether it’s a good v1 base for math/science question objects.

### Assistant — *commentary* (2026-04-09T16:08:20.369Z)

This is looking usable for a math/science v1. It already produces the exact primitive we need first: stable question-level segments with page spans, crop rectangles, and even duplicated shared “stem” crops when a top-of-page instruction applies to multiple questions. I’m checking one more artifact, `segments_index.csv`, because that will tell us how much of the question-object schema we can derive without rewriting the splitter.

### Assistant — *final_answer* (2026-04-09T16:08:33.706Z)

Yes. `question_splitter` looks like a strong base for a math/science v1.

Why it fits well:
- It already finds question starts via OCR.
- It already groups subparts by default, which matches “question object per question or sub-part” well enough for a first pass.
- It already outputs per-question multi-page crops/PDFs.
- It already records exact crop rectangles in `segments_index.csv`.
- It already has a primitive shared-context mechanism via `stem` reassignment for “refer to Questions 13 and 14” style instructions.

So for math/science v1, I would build on top of it rather than replace it.

**What it can already provide**
From `question_splitter`, we can derive much of a v1 question object:
- `question_number` from `q_index`
- `question_crop` from generated PNG/PDF
- `bbox` from `segments_index.csv`
- multi-page question spans
- `stimulus`-like shared crop from rows with `role='stem'`

That maps pretty naturally onto the schema we were discussing.

**What it does not yet do**
It is still only a splitter, not a full ingestion/indexer. It does not yet produce:
- `question_type`
- `max_marks`
- `section`
- `sub_part` as a normalized field
- `stimulus_blocks` as first-class structured records
- OCR text per question crop
- linkage to registry / template / answer mapping
- student-answer / teacher-mark extraction

So the right move is not “turn `question_splitter` into the whole system,” but:

`question_splitter` -> structural segmentation engine
then build a thin ingestion layer on top.

**Recommended v1 plan**
1. Keep `question_splitter` as the segmentation backend.
2. Add a wrapper that converts its outputs into `unit_index.json` or `question_objects.json`.
3. Limit scope to math/science template/unit PDFs first.
4. Treat `role='stem'` segments as early `stimulus_blocks`.
5. Add light post-processing for:
   - `question_number`
   - optional `sub_part`
   - page spans
   - normalized bbox format
   - question asset paths
6. Leave marking extraction and answer extraction for the next stage.

**Why math/science first**
That matches the tool’s current assumptions:
- left-margin numeric question starts
- mostly monotonic numbering
- full-width vertical crops work reasonably well
- shared stems are rarer and simpler than English/Chinese comprehension

**My recommendation**
Yes, build on top of it for v1.

I’d define v1 as:
- input: one registered template/unit PDF
- run `question_splitter`
- output: normalized question index for math/science
- optional support for simple shared stems using existing `STEM` logic

Then later:
- English/Chinese need a richer `stimulus_blocks` model
- comprehension passages and cloze sections will need more than left-margin question-start detection

If you want, I can next sketch the exact adapter layer:
`question_splitter output -> unit_index.json`
using the current `manifest.json` and `segments_index.csv` formats.
