---
name: diagnose-student-school-work
description: Builds a canonical `marking_result.v1.1` JSON plus the same derived markdown learning report as GoodNotes marking, for **school-returned completion PDFs that have no separate answer key** (e.g. weighted assessments, class quizzes, term tests). Ground truth for right/wrong and marks is inferred **from the completion itself**—especially teacher annotations (often red), student corrections (often green), and printed rubrics—while **student original answers** are transcribed **verbatim from blue/black ink only**. Use when the user wants a learning report in the marking-package style for teacher-marked work that cannot follow `mark-goodnote-completion` because there is no mapped answer PDF.
---

# Diagnose Student School Work (Teacher-Annotated Completion)

This workflow is **not** registry answer-key marking. It reuses the **same artifact contract and report shape** as `../mark-goodnote-completion/SKILL.md` and `ai_study_buddy/marking/` so downstream tools and parents see one consistent “Learning Report”. It applies to **any subject and language**; ink-color conventions are defaults and must be overridden when the user says their paper differs.

## When to use this skill vs `mark-goodnote-completion`

| Situation | Use |
| --- | --- |
| Completion linked to a template **and** mapped answer pages (or an embedded answer range in the paper) | `mark-goodnote-completion` |
| Completion is **the only** authoritative document: teacher marks and comments on the scan, student corrections, **no** separate answer key to compare against | **this skill** |

Typical triggers: learning report for a weighted assessment, class quiz, or exam paper returned as a scan; “teacher marked in red, no answer PDF”; “same marking JSON and report format as the marking package.”

## Canonical outputs (must match marking package)

Authoritative paths, naming, timestamps, and JSON-first discipline are identical to `../mark-goodnote-completion/SKILL.md`:

- **Contract:** `ai_study_buddy/marking/SPEC.md`
- **Path builders / basename rules:** `ai_study_buddy/marking/core/artifact_paths.py`
- **Singapore time** for `created_at` / `updated_at` and `__YYYYMMDD_HHMMSS`: `ai_study_buddy.marking.core.marking_time` (`now_marking_iso`, `to_marking_iso`); use `write_marking_artifact` so times normalize on save.
- **Canonical JSON:** `ai_study_buddy/context/marking_results/<student_slug>/<subject_context>/<attempt_basename>.json`
- **Derived markdown:** `ai_study_buddy/context/learning_reports/<student_slug>/<subject_context>/<attempt_basename> - Marking Report.md`
- **Scratch (renders, crops, `_*.py`):** `ai_study_buddy/context/.marking_scratch/<scratch_slug>/` with the same `scripts/`, `attempt/`, `crops/` layout as the marking skill.

Write JSON first, then render markdown with:

`python3 -m ai_study_buddy.marking.workflows.report_renderer <path-to-artifact.json>`

(or call `render_learning_report_from_json` from Python). Do not hand-author markdown as the source of truth.

## Prerequisite

For registry-backed path resolution and optional template link metadata, read and follow `../pdf-file-manager/SKILL.md` and use `PdfFileManager` (no direct SQLite for normal lookups).

## Core idea: grounded reconstruction, not “marking from key”

1. **Outcome and marks** (✅ / ⚠️ / ❌, `earned_marks` / `max_marks`) are inferred from **visible evidence on the completion**: teacher ticks and crosses, numeric scores, partial-credit symbols, printed per-question mark schemes, and any other explicit marking on the scan.
2. **`correct_answer`** is filled from evidence **on the same document**, not from a separate answer PDF. Priority order:
   1. **Student correction ink** (often green; confirm with the user if another color is used) that replaces or fixes the original blue/black attempt → treat as the **authoritative corrected response** when it fully addresses the error.
   2. **Teacher annotation ink** (often red) when it explicitly states the expected response, acceptable alternatives, or the correct choice.
   3. **Printed answer lines or mark schemes** on the same paper (e.g. an MCQ key printed elsewhere)—only if clearly tied to the question.
   4. **Model-generated reference answer** when the paper shows the item is wrong or incomplete but **does not** supply a correction: prefix clearly in the **language of the paper** (e.g. English `(Reference answer — not written on paper)` or an equivalent the user expects), keep `diagnosis.confidence` conservative, and state in `diagnosis.reasoning` that the reference was not present on the scan.
3. **Teacher comments** in the question area: capture **verbatim** (or as close as legibility allows) in the row’s **`human_note`** so the report preserves instructional value. A short paraphrase may also appear in `diagnosis.reasoning` or `feedback`, but do not drop the verbatim teacher note when it adds nuance.
4. **`student_answer`** must reflect **only the student’s original submission**: **blue/black** ink, plus printed options the student circled or filled **before** correction ink was added. **Never** treat correction or teacher ink as the student’s original answer.
   - **Crossing-out policy (important):** you must track what was crossed out vs retained when interpreting intent, but in canonical output keep only the **final non-crossed-out readable answer** in `student_answer`.
   - Do **not** preserve deleted fragments using strike markup (e.g. `~~...~~`) in JSON/report fields. If edit history matters for diagnosis, mention it briefly in `human_note` (e.g. “先写 X 后划去，最终写 Y”).
   - **Do not fabricate** text: if unreadable, use explicit placeholders such as `[illegible]` or `[no response]` in the paper’s language rather than guessing.
5. **Default ink roles** (override when the user says their institution uses different colors):

| Ink | Role in this workflow |
| --- | --- |
| Blue/black | **Only** source for `student_answer` (original attempt). |
| Red (typical) | Teacher marks, ticks, crosses, scores, expected fixes, and comments—primary evidence for outcome and for `human_note`. |
| Green (typical) | Post-marking **corrections/model wording** (student or teacher, depending on paper convention). Use as corrected/reference evidence, but never merge into `student_answer`. |
| Purple (typical) | Often parent or tutor notes—record if relevant; do not silently merge into `student_answer`. |

This is the **inverse** of the scoring rule in `mark-goodnote-completion`, which ignores red and green for *key-based* scoring. Here those colors are **often essential evidence**—but **`student_answer` stays blue/black final-kept only** regardless.

## Building `question_results`

- Follow **`ai_study_buddy/marking/core/taxonomy.py`** for `error_tags` and `diagnosis.mistake_type` / `diagnosis.confidence`.
- **Wrong and partial rows:** `diagnosis.reasoning` must meet the same quality bar as the marking skill (specific, evidence-based, not boilerplate).
- **Language for `diagnosis.reasoning`:** use the language appropriate to the student and paper. The marking package requires **Simplified Chinese** for `diagnosis.reasoning` only when `subject_context` is **`singapore_primary_chinese`** or **`singapore_primary_higher_chinese`** (same rule as `mark-goodnote-completion`). For other contexts, write in the language the user expects (usually the language of instruction on the paper).
- **`skill_tags`:** same subject policies as the marking skill (see `mark-goodnote-completion` for math, science, English, Chinese, HC, and legacy rules).
- **`scoring_status`:** usually `counted`; use `excluded_disqualified` + `outcome: disqualified` only for items the user asked to skip or that truly cannot be grounded.

## `context` fields when there is no answer file

- **`attempt_file_path`**: required (student completion PDF).
- **`answer_file_path`**, **`answer_page_start`**, **`answer_page_end`**: set to **`null`** when no answer PDF exists.
- **`answer_mapping_source`**: e.g. `"none_school_work"` or `"teacher_annotated_completion"`.
- **`answer_mapping_notes`**: short explicit note in English (unless the user asks otherwise), e.g. “No separate answer key; scores and reference answers reconstructed from teacher annotations and student corrections on the scan.”
- **Template fields:** populate when known from `PdfFileManager` / resolver; otherwise `null` with a one-line explanation in `answer_mapping_notes` or `generation.notes`.

## `generation` block

Use a distinct mode so reports are auditable:

```json
"generation": {
  "produced_by": "<agent or script name>",
  "mode": "school_work_grounded",
  "notes": "Evidence: teacher marks and comments; student corrections; model reference answers only where uncorrected on paper."
}
```

Adjust `notes` per run to list any user-supplied rubric, pages graded, or uncertainties.

## Marks when the paper does not show per-question totals

- Prefer **visible** per-item marks from the teacher.
- **`max_marks` / `earned_marks`** may use **fractions** (e.g. `1.5` for one-and-a-half marks) when the paper shows half marks—the `marking_result` validator accepts non-negative `int` or finite `float` (not booleans).
- If only an **aggregate** score exists (or per-question marks are ambiguous), **stop and ask the user** for how to allocate marks (per-question split, uniform rubric, or which items to exclude). **Do not** assume equal marks per question or any other split without explicit user confirmation.
- If both per-item annotations and an authoritative subtotal/cover total exist but conflict, treat the subtotal/cover total as controlling; then document exactly how row-level `earned_marks` were normalized in `generation.notes` / `summary.human_note` so `summary` totals remain auditable.
- After the user supplies a rubric, record it verbatim (or a precise summary) in `summary.human_note` and/or `generation.notes` so the artifact stays auditable.

## Visual workflow (recommended)

1. Resolve the completion path (and optional registry metadata) via `PdfFileManager` / `resolve_marking_context` when helpful—but **do not** block the run solely because there is no answer mapping.
2. Render attempt pages to PNG under `.marking_scratch/.../attempt/` (PyMuPDF `fitz`, same pattern as the marking skill).
3. Work **from images**, not from memory or filename alone.
4. Optional: store tight **crops** under `crops/` for difficult items (evidence for future humans; not written into canonical JSON paths today).

## Run checklist (quick)

Use this checklist before final handoff:

1. **Ink roles locked:** confirm blue/black = `student_answer` source; red/green only as marking/correction evidence per paper convention.
2. **Cross-outs handled correctly:** differentiate crossed-out vs kept while reading, but record only **final kept** text in `student_answer`; keep edit-history notes brief in `human_note` only when needed.
3. **Evidence-grounded `correct_answer`:** prefer on-paper correction/annotation first; if model reference is needed, label it clearly as not written on paper.
4. **Marks reconciled:** ensure row sums match authoritative subtotals/cover total; if normalization was required, explain the exact rule in `generation.notes` or `summary.human_note`.
5. **Canonical outputs regenerated:** write JSON with `write_marking_artifact`, then render markdown from that JSON; remove superseded duplicate artifacts when user requests cleanup.

## Quality bar (before handing off)

- JSON validates via `validate_marking_artifact_dict` / `write_marking_artifact`.
- Markdown re-renders from JSON without manual edits.
- Every **wrong/partial** row has non-empty, item-specific **`diagnosis.reasoning`** (and for Chinese/HC `subject_context`, that reasoning is in Simplified Chinese per package rules).
- **`student_answer`** is blue/black-only and honest about illegibility.
- **`human_note`** carries **verbatim teacher comments** when present in the item’s area.
- **`correct_answer`** states the **evidence source** when it is not obvious (e.g. `student correction on scan`, `teacher annotation`, `reference answer not on paper`).
- `summary` totals match the sum of counted rows.

## Guardrails

- Do not fabricate student handwriting or teacher comments.
- Do not treat filename or registry metadata as proof of correctness.
- Do not put scratch PNGs under `marking_results/` or `learning_reports/`.
- If the paper is too faint or ambiguous for an item, mark low confidence and narrow the claimed scope rather than guessing.
