# Handoff: Math ontology + detector → Science detector

This file summarises the key decisions made when building the Math question-type ontology document and detector agent, so that the same approach can be applied to Science with minimal ramp-up.

---

## Files already built (math)

| File | Purpose |
|------|---------|
| `ai_study_buddy/context/subject_understandings/singapore_primary_math/math_exam_question_types.md` | Golden ontology — 3 canonical types with visual screenshots |
| `ai_study_buddy/schemas/math_questions_section.v1.0.schema.json` | JSON Schema (`math-v1.0`) |
| `.cursor/agents/math-question-section-detector.md` | Detector agent |

---

## Step 1 — Ontology doc (`*_exam_question_types.md`)

The ontology doc defines the **canonical question types** the detector must classify into. For math we identified 3:

| Type | Visual signal | Where it appears |
|------|--------------|-----------------|
| `MCQ` | 4 options (1)–(4), OAS shading, no `Ans:` line | Paper 1 Booklet A only |
| `SAQ` | `Ans:` line, **no `[n]` bracket** per question | P1 Booklet B + Paper 2 Q1–5 |
| `LAQ` | **`[n]` bracket printed on every answer line** | Paper 2 Q6–15 only |

**Key lesson:** Find **one reliable visual signal** that distinguishes the types that look otherwise similar. For math it was the `[n]` bracket. The ontology doc should call this out prominently.

The doc includes:

- A prose description of each type
- A **comparison table** of distinguishing signals
- **Screenshot croppings** from a real exam (section instructions, sample questions) stored under a sibling `*_question_type_croppings/` folder
- A cross-reference link added to the existing `*_exam_format.md`

---

## Step 2 — Schema

**Key differences from Chinese/English schemas (applicable to science too):**

- **No `stem_page_range`** — math questions are self-contained; no shared reading passage precedes them. Science MCQ and OEQ questions are similarly self-contained.
- **No `answers_in_separate_booklet` / `answers_page_range`** — answers are always written in the same booklet as the questions.
- Schema version string is **namespaced separately**: `math-v1.0` (not `v1.x`). Science should use `science-v1.0`.

Each section carries a **`question_info`** array (one element per question index at finest granularity). Each element has:

```json
{
  "question_index": "Q10b",   // required — finest-grained label, pattern ^Q[0-9]+[a-z]?$
  "question_mark": 2,          // required — marks for this item
  "start_page": 7,             // required — page where this question starts (detector renders all pages anyway)
  "end_page": 8,               // optional — only when question visibly spans more than one page
  "question_topic": "..."      // optional — free-form description, keep under 30 words
}
```

The `question_info` array is the **single source of truth** for question indices — there is no separate `question_indices` array.

---

## Step 3 — Detector agent

**Design decisions applicable to science:**

### Sub-part granularity rule
Use the **finest-grained label printed in the paper** for all free-response types. A question with printed `(a)` / `(b)` sub-parts each having their own answer line emits `Q10a`, `Q10b`. A single-part question emits `Q10`. This applies to all non-MCQ types.

### MCQ split rule
When the section instruction states two mark bands (e.g. "Q1–10 carry 1 mark each; Q11–18 carry 2 marks each"), emit them as **two separate MCQ section objects** — not one. The mark boundary comes from the instruction text, not a fixed number. For science all MCQ items carry 2 marks each (uniform band), so this split is not needed.

### WA / non-standard format awareness
WA and school prelim papers may have different section structures, different question counts, or different labels than the PSLE canonical format. Always read section headers and instructions from the actual document. Do not hard-code PSLE question numbers.

### `question_topic`
Free-form, **≤ 30 words**. No forced vocabulary lookup — the detector annotates as a best-effort first pass while it has all pages rendered. Structured taxonomy tagging (mapping to syllabus topics) is a **separate downstream step** and should not distract the detector.

### `start_page` always required
Because the detector renders all pages to identify section boundaries and question types, it can always determine which page each question starts on. `start_page` is therefore **required** on every `question_info` element.

### `end_page` optional
Include only when a question visibly spills across more than one page (e.g. a long scenario with a large diagram and extended working/answer space on the next page). Omit for the common single-page case.

---

## What to expect for science

Science is structurally the closest subject to math among those with detector agents:

- **Booklet A** = MCQ, 4 options, **2 marks each**, OAS shading — directly analogous to math MCQ.
- **Booklet B** = Structured open-ended, **`[n]` brackets** on every answer line, 2–5 marks per question — analogous to math LAQ.
- Science has **no SAQ equivalent** — there is no "2 marks each with no bracket" block; all Booklet B items carry explicit `[n]` brackets.

The current `science_exam_format.md` already exists at:
`ai_study_buddy/context/subject_understandings/singapore_primary_science/science_exam_format.md`

Likely canonical types to confirm against a real sample PDF before writing the ontology doc:

| Candidate type | Analogue in math |
|----------------|-----------------|
| `MCQ` | `MCQ` |
| `OEQ` (Open-Ended Question) | `LAQ` |

**Before creating the ontology doc**, render a real science exam PDF (e.g. `_c_p6.science.prelim.1.pdf` or similar under `Singapore Primary Science/PSLE/Exam/`) and verify:
1. Whether Booklet B items always have `[n]` brackets or sometimes omit them.
2. Whether any items have a shared stimulus/scenario (passage, experiment diagram) followed by multiple sub-questions — if so, a `stem_page_range` analogue might be needed (unlike math).
3. The typical sub-part structure (are sub-parts labeled `(a)`, `(b)` with separate answer lines? Or just one continuous response space?).
4. The SEAB 2026 format uses 30 MCQ (Booklet A). School prelims may still use 28. Always read the cover totals.

---

## Workflow checklist (replicate for science)

1. Read `science_exam_format.md` for the current format spec.
2. Find a sample science exam PDF and render all pages to inspect visually.
3. Identify canonical question types and the key visual signals that distinguish them.
4. Create `science_exam_question_types.md` with prose descriptions, a signals comparison table, and screenshot croppings.
5. Add a cross-reference link in `science_exam_format.md` pointing to the new doc.
6. Create `ai_study_buddy/schemas/science_questions_section.v1.0.schema.json` (use `math_questions_section.v1.0.schema.json` as the template; change `schema_version` const to `"science-v1.0"`; adjust `questionType` enum).
7. Create `.cursor/agents/science-question-section-detector.md` (use `math-question-section-detector.md` as the template; update ontology path, question type list, type-specific detection guidance, and example JSON).
