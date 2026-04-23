# AI Study Buddy — Marking Result Artifact (File-Canonical)

> Status: **Implemented (current package: `ai_study_buddy/marking` `v0.2.11`)** — file-canonical JSON-first workflow is active (`marking_result.v1.4` writer; reads `v1` / `v1.1` / `v1.2` / `v1.3` / `v1.4`), with markdown as derived output.
>
> Related docs: [QUESTION_INDEX_SCHEMA](./L4_QUESTION_INDEX_SCHEMA.md), [INGESTION_PIPELINE](./L4_INGESTION_PIPELINE.md), [DATA_STRATEGY](./L3_DATA_STRATEGY.md)

Current implementation references:

- `ai_study_buddy/marking/README.md`
- `ai_study_buddy/marking/SPEC.md`
- `ai_study_buddy/marking/CHANGELOG.md`

---

## Why This Exists

The current GoodNotes marking workflow produces markdown learning reports as standalone outputs. For the wider AI Study Buddy app, marking output needs to become structured data that other components can reuse (diagnostics, planner, parent summary, gamification, agent tools).

For this proof-of-concept stage:

1. Canonical truth lives in files.
2. Human edits/notes must be first-class.
3. Per-question crop/bbox evidence is out of scope for now.

---

## Core Decision

Use a **JSON marking artifact** as the canonical output of each marking run.  
Markdown learning reports become a **derived view** generated from that JSON.

This keeps the POC simple while creating a stable contract for future DB ingestion.

It also establishes an important boundary for the student-facing product:

- `marking_result` is the canonical record of marking facts
- markdown learning reports are derived views
- student reflection/review state should be stored separately rather than overwriting canonical marking fields

---

## Artifact Layout

Canonical JSON:

`ai_study_buddy/context/marking_results/<student>/<subject_context>/<attempt_basename>.json`

Derived markdown report:

`ai_study_buddy/context/learning_reports/<student>/<subject_context>/<attempt_basename> - Marking Report.md`

`<subject_context>` follows existing report folders (for example `singapore_primary_science`).

### `<attempt_basename>` formation rule (POC decision)

`<attempt_basename>` is derived from the registered attempt file name using this deterministic process:

1. Start with the file basename without extension.
2. Strip leading compression/archive prefixes repeatedly while present:
   - `c_`
   - `_c_`
   - `_raw_`
   - `raw_`
3. Use the resulting normalized stem as the base.
4. Apply collision guard suffix from marking timestamp: `__YYYYMMDD_HHMMSS`.

Examples:

- `c_Science Practice Primary 5 and 6 - 17 Interactions.pdf` -> `Science Practice Primary 5 and 6 - 17 Interactions__20260415_103025`
- `_c_p4.math.wa1.6.pdf` -> `p4.math.wa1.6__20260415_103025`
- `_raw_p4.math.wa1.6.pdf` -> `p4.math.wa1.6__20260415_103025`

Timestamp suffix meaning:

- Suffix encodes the marking run timestamp (local project timezone convention).
- Multiple attempts on the same base name are naturally separated by different timestamps.

---

## Workflow

1. Resolve deterministic context (`attempt`, `template`, `book group`, `answer pages`) via registry.
2. Perform visual grading for requested question scope.
3. Write canonical JSON artifact.
4. Render markdown report from JSON.
5. Allow human review edits directly in JSON (`overall notes` and `question notes`).
6. Re-render markdown at any time from the latest JSON.

Run cleanup facility (implemented in package):

- `remove_marking_run_artifacts(...)` removes one run's canonical JSON, derived report, and marking-asset bundle together.
- CLI wrapper:
  - `python3 -m ai_study_buddy.marking.workflows.remove_run_artifacts <artifact_json> --dry-run`

`*_file_id` backfill rule (migration):

1. During markdown -> JSON migration, attempt to resolve `attempt_file_id`, `template_file_id`, `unit_file_id`, and `answer_file_id` from the corresponding `*_file_path` fields via `pdf_file_manager`.
2. Attempt to derive `unit_label` from resolved unit/template file metadata (fallback to normalized template filename when needed).
3. Attempt to resolve `book_group_id` and `book_label` from file-group membership (`group_type='book'`) using resolved file IDs (prefer unit/template context).
4. Keep path/group context fields as source trace regardless of lookup outcome.
5. If lookup data is unavailable in registry, leave unresolved IDs/labels as `null` (non-blocking).

---

## Implementation Location (Explicit)

Code and instruction layers are separated deliberately:

1. **Core implementation code lives in** `ai_study_buddy/marking/`
   - artifact naming/path logic
   - schema/type validation
   - canonical JSON writer
   - JSON -> markdown renderer
   - taxonomy constants (`error_tags`, diagnosis enums)
2. **Workflow instructions live in** `.cursor/skills/mark-goodnote-completion/`
   - orchestration guidance for agents
   - usage protocol and guardrails
   - should call into `ai_study_buddy/marking/` implementation, not duplicate business logic

Design rule:

- Business logic belongs in `ai_study_buddy/marking/`.
- Skill files document how to use that logic.

---

## Schema (POC v1)

POC simplification: `marking_id` is intentionally omitted from v1 because filesystem path plus timestamped filename already provide unique identity in the file-canonical stage.

```json
{
  "schema_version": "marking_result.v1.4",
  "created_at": "2026-04-15T10:00:00Z",
  "updated_at": "2026-04-15T10:00:00Z",

  "context": {
    "student_id": "winston",
    "student_name": "Winston",
    "subject_context": "singapore_primary_science",
    "attempt_file_id": "file_attempt_123",
    "attempt_file_path": "/abs/path/to/goodnotes.pdf",
    "template_file_id": "file_template_456",
    "template_file_path": "/abs/path/to/template.pdf",
    "book_group_id": "book_group_789",
    "book_label": "Science Practice Primary 5 and 6",
    "answer_file_id": "file_answer_321",
    "answer_file_path": "/abs/path/to/answers.pdf",
    "answer_page_start": 22,
    "answer_page_end": 24,
    "starts_mid_page": false,
    "ends_mid_page": true,
    "question_selection": {
      "raw_text": "Q1-10",
      "canonical_refs": ["Q1", "Q2", "Q3"],
      "section_hint": null
    }
  },

  "summary": {
    "total_marks": 50,
    "earned_marks": 43,
    "percentage": 86.0,
    "overall_assessment": "Strong attempt with specific gaps in force-direction and reasoning items.",
    "human_note": null
  },

  "question_results": [
    {
      "result_id": "Q1",
      "scoring_status": "counted",
      "max_marks": 2,
      "earned_marks": 2,
      "outcome": "correct",
      "student_answer": "(2)",
      "correct_answer": "(2)",
      "feedback": null,
      "error_tags": [],
      "skill_tags": ["Interactions > Interaction of Forces > Magnets"],
      "diagnosis": {
        "mistake_type": null,
        "reasoning": null,
        "confidence": null
      },
      "human_note": null
    },
    {
      "result_id": "Q2",
      "scoring_status": "excluded_disqualified",
      "max_marks": 0,
      "earned_marks": 0,
      "outcome": "disqualified",
      "student_answer": "612.5",
      "correct_answer": null,
      "feedback": "Disqualified due to source mismatch between question stem and mapped answer key.",
      "error_tags": [],
      "skill_tags": [],
      "diagnosis": {
        "mistake_type": null,
        "reasoning": "Question stem/answer-key mismatch; student error diagnosis is not applicable.",
        "confidence": "high"
      },
      "human_note": null
    }
  ],

  "review_meta": {
    "updated_at": null,
    "updated_by": null
  },

  "generation": {
    "produced_by": "mark-goodnote-completion",
    "mode": "manual_visual_with_ai_assist",
    "notes": "POC format: markdown report is generated from this artifact."
  }
}
```

---

## Human Review Facility

Human reviews are co-located with the fields they annotate:

1. `summary.human_note`: high-level parent/tutor review.
2. `question_results[].human_note`: targeted notes per gradable item.
3. `review_meta.updated_at` and `review_meta.updated_by`: audit metadata for latest human edit.

This avoids a separate note-mapping layer and keeps annotations close to the relevant grading data.

## Relationship to Student Review Workspace

The student-facing Review Workspace should read from `marking_result` but should not treat it as the place to persist student reflections.

Guideline:

1. `summary.human_note` and `question_results[].human_note` are for tutor/parent/admin review notes tied to the marking artifact itself.
2. Student-authored reflections, self-corrections, and review-progress state should live in a separate companion artifact (see [`L4_STUDENT_MVP_EXPERIENCE.md`](./L4_STUDENT_MVP_EXPERIENCE.md)).
3. Keeping the student layer separate preserves the factual integrity of canonical marking output while still allowing downstream planner/tutor features to consume student reflection data later.

---

## Gradable Unit Rule (POC decision)

Each element in `question_results` is one **gradable leaf unit** (for example `Q15(a)`).

Implications:

1. `sub_parts` is omitted in POC v1.
2. Parent question grouping is not stored explicitly in the artifact, because it can be derived from `result_id` naming when needed.
3. Totals are computed by summing `question_results[].earned_marks` and `question_results[].max_marks` (each may be an `int` or a non-negative finite `float`, e.g. `1.5` for half marks).

### Scoring semantics upgrade (implemented)

Each row now includes:

1. `outcome`: `correct`, `partial`, `wrong`, or `disqualified`
2. `scoring_status`: `counted` or `excluded_disqualified`

Summary scoring uses only rows where `scoring_status="counted"`.  
Disqualified rows remain in the artifact for traceability but are excluded from score totals.

---

## Mistake Analysis Field (POC decision)

Per gradable result, `diagnosis` captures the marking agent's interpretation of the specific student's mistake:

1. `mistake_type`: normalized category (for example `concept_gap`, `misread_question`, `incomplete_explanation`, `careless_error`).
2. `reasoning`: short explanation of why this mistake type was assigned for this attempt.
3. `confidence`: optional confidence score or qualitative value.

`error_tags` remain available as concise machine tags; `diagnosis` adds explanatory depth.

### `skill_tags` (`question_results[].skill_tags`)

- **Type:** array of strings (empty `[]` is valid).
- **Rendering:** markdown reports use `prettify_skill_tags` (see `ai_study_buddy/marking/core/taxonomy.py`). When **each** element contains ` > ` (full path per element), multiple elements are joined with **`"; "`**; otherwise elements are joined with **` > `** (legacy: one hierarchy level per array index).
- **Authoritative workflow rules:** `.cursor/skills/mark-goodnote-completion/SKILL.md` (Skill Tags Column).

**By `subject_context` (new writes):**

| Context | `skill_tags` policy |
|---------|---------------------|
| `singapore_primary_math` | One string per syllabus topic path: `Strand > Sub-strand > Topic` (vocabulary: `ai_study_buddy/context/subject_understandings/singapore_primary_math/syllabus_understanding.md`). Prefer one element per row; use several full-path strings when a question clearly spans multiple topics. |
| `singapore_primary_science` | One string per unit path: `Theme > Chapter > Topic` (vocabulary + Index: `ai_study_buddy/context/subject_understandings/singapore_primary_science/syllabus_understanding.md`). Use `—` as the third segment when the Index has no topic. |
| `singapore_primary_english`, `singapore_primary_chinese`, `singapore_primary_higher_chinese` | Use **`[]`** for now. |
| Other / future | Legacy multi-segment hierarchy **or** `[]` as agreed per subject. |

**Legacy artifacts:** older JSON may still store three separate strings for one math path, science slug triples, or English vocabulary tags; do not rewrite files in bulk. Prefer the conventions above for new marking runs.

**Question index:** `skill_tags` on `unit_question_index` entries are a separate concern (often slug-style retrieval tags); see [L4_QUESTION_INDEX_SCHEMA](./L4_QUESTION_INDEX_SCHEMA.md). They are not automatically the same shape as marking-result `skill_tags`.

Diagnostic evidence rule:

1. Diagnosis must use all visible evidence for the gradable item, including:
   - final answer
   - intermediate workings / method steps (when available)
   - corrections/annotations that are part of the attempt
2. For math in particular, visible workings are primary evidence for distinguishing:
   - conceptual gaps vs calculation slips
   - wrong method vs incomplete method
   - misread question vs execution error
3. If workings are unavailable or illegible, the diagnosis should state that constraint implicitly via lower confidence and avoid over-claiming root cause.

---

## Rendering Rule

Markdown reports are generated from the JSON artifact and should include:

1. Result summary.
2. Marking table.
3. Report context (attempt/template/answer paths + page range).
4. Human review notes (when present).

Do not treat markdown as canonical source data.

---

## Out of Scope for POC v1

1. Question-region crop references and bbox evidence.
2. Database as canonical storage.
3. Event-sourcing and replay infrastructure.
4. Full version graph for multiple human revisions.

These can be added after question-region review tooling matures.

---

## Migration from Existing Reports

For existing markdown-only reports in `context/learning_reports/`:

1. New runs should write JSON first, then render markdown.
2. Backfill of old reports can be incremental (optional): parse markdown tables into v1 JSON where useful.
3. Until backfill is complete, legacy markdown reports remain read-only historical artifacts.

---

## Migration Implementation Plan

Goal: convert legacy markdown learning reports into canonical `marking_result.v1.x` JSON artifacts without blocking new JSON-first runs.

### Phase 0: Scope and safety (Completed)

1. [x] Inventory existing markdown reports under `context/learning_reports/` by child and subject.
2. [x] Define migration idempotency rule: if target JSON already exists, skip unless `--overwrite` is explicitly set.
3. [x] Define migration log output (success, skipped, failed) for auditability.

### Phase 1: Backfill tooling (Completed)

1. [x] Implement a migration script in `ai_study_buddy/marking/` that:
   - reads legacy markdown reports
   - parses report context, summary, and marking table
   - maps parsed data into package-supported `marking_result.v1.x` (writer emits `v1.4`)
   - writes JSON to `context/marking_results/...` using canonical naming rules.
2. [x] Add a dry-run mode to preview planned outputs.
3. [x] Add a `--limit` option for staged migration.
4. [x] Backfill `*_file_id` fields from `*_file_path` using `pdf_file_manager` lookups (best effort, non-blocking).
5. [x] Backfill `book_group_id` and `book_label` from `pdf_file_manager` file-group membership where resolvable.
6. [x] Backfill `unit_label` from unit/template file metadata (with filename fallback when needed).

### Phase 2: Validation and quality gates (Completed)

1. [x] Validate each produced JSON against the package-supported `marking_result.v1.x` schema contract.
2. [x] Recompute and verify totals (`earned_marks`, `total_marks`, percentage) from parsed rows.
3. [x] Mark uncertain parses (for example malformed markdown rows) with migration warnings in `generation.notes`.
4. [x] Keep original markdown files unchanged.
5. [x] Implement compatibility parsing for context label variants (`exercise` / `test` / `chapter`).
6. [x] Implement disqualified-row migration (`⛔` -> `outcome=disqualified`, `scoring_status=excluded_disqualified`).

### Phase 3: Derived report regeneration (Completed)

1. [x] Regenerate markdown reports from migrated JSON using the new renderer (tooling implemented).
2. [x] Compare regenerated reports against originals for spot-check samples.
3. [x] Keep original report files as historical references until migration confidence is high.

### Phase 4: Operational adoption (Completed)

1. [x] Switch all new marking workflows to JSON-first.
2. [x] Run backfill in batches per student/subject.
3. [x] Publish migration summary counts and unresolved exceptions.

Migration summary (current repository state):

1. Legacy markdown reports discovered: 33
2. Migrated JSON artifacts produced (`marking_result.v1.x`): 33
3. Markdown reports with matching migrated JSON: 33/33
4. Unresolved migration exceptions tracked in this batch: none

---

## Implementation TODO Checklist

1. [x] Finalize and freeze `marking_result.v1.x` field contract used in this document.
2. [x] Create a canonical JSON schema file for `marking_result.v1.x` and add validation tests.
3. [x] Implement `<attempt_basename>` normalizer (strip extension; strip leading `c_` / `_c_` / `_raw_` / `raw_`; append `__YYYYMMDD_HHMMSS` from marking timestamp).
4. [x] Implement artifact path builder at `context/marking_results/<student>/<subject_context>/<attempt_basename>.json` and ensure directories are created deterministically.
5. [x] Implement JSON writer for marking runs (source-of-truth write path).
6. [x] Implement markdown renderer that reads JSON and writes derived learning report.
7. [x] Include co-located human note rendering for `summary.human_note` and `question_results[].human_note`.
8. [x] Update `mark-goodnote-completion` workflow to "JSON first, markdown second".
9. [x] Add diagnosis guidance to marking prompt templates (use final answer + visible workings + corrections/annotations; lower confidence when workings are missing/illegible).
10. [x] Add taxonomy constants and validation for `error_tags`, `diagnosis.mistake_type`, and `diagnosis.confidence`.
11. [x] Add regression tests for score/percentage consistency (`summary.total_marks` equals sum of row `max_marks`; `summary.earned_marks` equals sum of row `earned_marks`).
12. [x] Add idempotent re-render command to regenerate markdown from existing JSON without changing canonical fields.
13. [x] Add a small helper/command for human note editing workflow (or document manual edit protocol).
14. [x] Implement markdown -> `marking_result.v1.x` migration script for legacy learning reports.
15. [x] Add migration dry-run mode and batch controls (`--limit`, student/subject filters).
16. [x] Add migration validation checks (schema, totals, parse warnings).
17. [x] Run pilot migration on a small subset and review output quality.
18. [x] Run full migration in batches and produce migration summary report.
19. [x] Establish package documentation suite for `ai_study_buddy/marking` (`README.md`, `CHANGELOG.md`, `SPEC.md`, `TESTING.md`) and initialize with release version `v0.1.0`.

---

## Future Path (Post-POC)

1. Keep JSON file as interchange artifact.
2. Add optional DB ingestion from JSON (without changing canonical-on-file POC behavior).
3. Add stable versioning semantics (`revision`, `supersedes_marking_id`) when multiple human edits or re-marks become frequent.
