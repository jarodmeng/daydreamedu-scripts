# Marking Artifact v1.4: Gradable Question -> Attempt Page Mapping

Status: Partially implemented (pilot complete; broad backfill pending)

Audience: Maintainers of `ai_study_buddy/marking`, `ai_study_buddy/context/marking_assets`, `.cursor/skills/mark-goodnote-completion/SKILL.md`, and `.cursor/skills/diagnose-student-school-work/SKILL.md`

## Why This Proposal Exists

The student Review Workspace design now depends on an `active_question_id` model.  
To auto-tune the evidence viewer when the user changes question focus, the backend needs a deterministic mapping from each gradable question (`question_results[].result_id`) to its starting page in the attempt.

Current gap:

1. `marking_result.v1.3` does not carry per-question attempt-page anchors.
2. Most review UIs can only show coarse page defaults (`page 1` or answer-page range), not question-focused navigation.
3. Existing historical artifacts already have strong source material in `context.marking_asset`.

Current repository snapshot (local check, 2026-04-22):

- `ai_study_buddy/context/marking_results/**/*.json`: **140** files
- artifacts with non-empty `context.marking_asset`: **140 / 140**
- assets where the pointed directory exists: **140 / 140**

So the data needed for a best-effort visual backfill is already present in this repo.

## Current Implementation Snapshot (2026-04-22)

Implemented and verified in-repo:

1. Canonical schema/version support is now `marking_result.v1.4` with `context.question_page_map`.
2. Validator/model/writer/docs were updated for `v1.4` (see `marking/CHANGELOG.md`, `README.md`, `SPEC.md`).
3. Operator skills were updated:
   - `.cursor/skills/mark-goodnote-completion/SKILL.md`
   - `.cursor/skills/diagnose-student-school-work/SKILL.md`
   - `.cursor/skills/oneoff-detect-question-starting-page/SKILL.md`
4. A pilot `v1.4` artifact was produced via the one-off skill:
   - `ai_study_buddy/context/marking_results/winston/singapore_primary_math/PP Math PSLE Part D P6 Topical Practice Percentage__20260421_194508.json`
5. Pilot artifact characteristics:
   - `schema_version = "marking_result.v1.4"`
   - populated `context.question_page_map`
   - `source = "manual_visual"` entries with `evidence_image` references

Pending:

1. Broader historical migration/backfill rollout and quality-gate verification.
2. Additional migration test coverage specific to review-only/apply/idempotency flows.

## Scope

### In Scope

1. Introduce schema version `marking_result.v1.4`.
2. Add a canonical per-artifact question-page mapping field.
3. Update core models/validator/writer to read/write/validate this field.
4. Update artifact-generating skills (`mark-goodnote-completion` and `diagnose-student-school-work`) so new marking runs capture mapping at authoring time.
5. Add a one-off operator skill to backfill existing artifacts using AI visual inspection of `marking_assets` attempt PNGs.
6. Add test coverage for schema/model/backfill behavior.
7. Update package docs (`README.md`, `SPEC.md`, `ARCHITECTURE.md`, `TESTING.md`, `CHANGELOG.md`) once implementation lands.

### Out of Scope

1. Per-question bounding boxes or pixel coordinates.
2. Full question object extraction (`question -> bbox -> crop`) for all subjects.
3. Changing scoring semantics or `question_results` row boundaries.
4. Forcing 100% backfill completeness when assets are ambiguous/missing; best-effort with explicit confidence is acceptable.
5. Viewer-side frontend implementation details (covered by student MVP docs, not this package proposal).

## Design

### 1) Canonical schema addition (`v1.4`)

Keep `question_results[]` unchanged for scoring/diagnosis. Add mapping metadata under `context`:

```json
{
  "schema_version": "marking_result.v1.4",
  "context": {
    "...": "...",
    "question_page_map": [
      {
        "result_id": "Q4",
        "attempt_page_start": 2,
        "confidence": "high",
        "source": "ai_visual_backfill",
        "evidence_image": "attempt/attempt-page-02.png",
        "note": null
      },
      {
        "result_id": "Q10",
        "attempt_page_start": 4,
        "confidence": "medium",
        "source": "manual_visual",
        "evidence_image": "attempt/attempt-page-04.png",
        "note": "Question header partly obscured by annotation."
      }
    ]
  }
}
```

Field contract:

1. `context.question_page_map`: array, always present in `v1.4` (may be empty).
2. `result_id`: non-empty string; must match one row in `question_results[].result_id`.
3. `attempt_page_start`: integer `>= 1`.
4. `confidence`: enum `high | medium | low`.
5. `source`: enum `manual_visual | ai_visual_backfill | script_inferred`.
6. `evidence_image`: optional string relative to `context.marking_asset`, usually `attempt/*.png`.
7. `note`: optional string for ambiguity/context.
8. `question_page_map` ordering is not semantically meaningful; consumers must key by `result_id`.

Validation rules:

1. No duplicate `result_id` in `question_page_map`.
2. Every map entry must reference a known `question_results[].result_id`.
3. Unknown `result_id` is hard validation failure.
4. For `schema_version = marking_result.v1.4`, `question_page_map` must exist and be an array (possibly empty).
5. Reader remains backward-compatible with `v1` / `v1.1` / `v1.2` / `v1.3`.
6. `evidence_image` path, when present, must stay under `context.marking_asset` and resolve to a supported image file.
7. Optional strict mode may reject map entries where `confidence=low` and `note` is absent.

Confidence rubric (authoring + backfill consistency):

1. `high`: clear question header/number is visible and uniquely matched on one earliest page.
2. `medium`: likely match but partially occluded/cropped or numbering style is ambiguous.
3. `low`: weak/indirect evidence only; keep `note` mandatory in strict mode.

### 2) Core model/API changes

Code touchpoints:

1. `core/artifact_schema.py`
2. `core/models.py`
3. `schemas/marking_result.v1.schema.json`
4. `core/artifact_writer.py`
5. `api.py` exports (if helper dataclasses are public)

Proposed model additions:

- new dataclass:
  - `QuestionPageMapEntry`
- new context field:
  - `MarkingArtifactContext.question_page_map: tuple[QuestionPageMapEntry, ...] = ()`

Writer behavior:

1. Emit `schema_version = marking_result.v1.4`.
2. If caller omits `question_page_map`, default to empty array.
3. Do not auto-infer page map in writer core by scanning PNGs; keep that as workflow/skill responsibility.

Rationale:

- keeps writer deterministic and light
- avoids expensive visual processing during every artifact write

### 3) One-off AI skill design (no deterministic batch script)

Do not implement a deterministic Python backfill workflow for this task.  
The mapping task is fluid and should be executed by an AI operator procedure encoded as a one-off skill.

Add skill:

`.cursor/skills/oneoff-detect-question-starting-page/SKILL.md`

Skill objective:

- Given a target marking-result JSON, produce/complete `context.question_page_map` by visually mapping each gradable question to its earliest attempt page.

Required skill procedure (authoritative):

1. **Input target artifact**
   - Accept one canonical marking-result JSON path under `context/marking_results/**`.
2. **Extract gradable rows**
   - Build the set of gradable `question_results[].result_id` rows that should be mapped.
3. **Resolve/repair marking assets**
   - Locate `context.marking_asset`.
   - If missing, invalid, or attempt PNG set is incomplete, generate or complete the full attempt PNG assets folder before mapping.
4. **Visual mapping pass**
   - Inspect ordered attempt PNG pages.
   - For each gradable `result_id`, assign earliest page where question first appears.
   - Record `attempt_page_start`, `confidence`, `source`, optional `evidence_image`, optional `note`.
5. **Constrained artifact mutation**
   - Mutate only `context.question_page_map` in the marking-result JSON.
   - Do not modify any other fields.
6. **Validation and reporting**
   - Enforce v1.4 validation rules.
   - Report unresolved rows and reasons.

Mutation boundary (hard rule):

1. Allowed write scope: `context.question_page_map` only.
2. Forbidden writes: scoring fields, diagnosis fields, notes/rationales unrelated to mapping, or any non-mapping context fields.
3. If schema upgrade to `v1.4` is needed, treat it as an explicit, auditable migration step separated from map edits.

Safety behavior:

1. If no confident page found for a result id, skip that entry and record unresolved reason.
2. Do not fabricate placeholders like page `0`.
3. Keep operation idempotent (re-running should not duplicate/contradict existing map rows).

Operational summary metrics (required per run):

- processed marking-result json count
- updated json count
- unchanged json count
- entries added/updated count
- unresolved result-id count
- missing/invalid asset-folder count
- png regeneration/completion actions count
- validation errors

Quality gates before broad apply:

1. Pilot precision target: at least 95% correct page starts on manual audit sample.
2. Low-confidence rate target: no more than 10% of mapped entries.
3. Hard-stop trigger: if pilot quality drops below threshold, do not proceed to broader rollout.

### 4) AI visual backfill execution modes

The one-off skill should support two operation modes:

1. `review-only` mode
   - no JSON writes
   - emits candidate mapping payload + unresolved list for confirmation
2. `apply` mode
   - writes only `context.question_page_map` after confirmation

Recommended default:

- run review-only first
- then apply on approved artifacts

This keeps risk controlled for historical data.

### 5) `mark-goodnote-completion` skill update

Update `.cursor/skills/mark-goodnote-completion/SKILL.md` so new runs capture page mapping during grading.

Required additions:

1. During question-by-question grading, record attempt page for each gradable row.
2. Require final JSON to include `context.question_page_map` for all confidently mapped rows.
3. If uncertain, include `confidence=low` + note, or omit row with explicit mention in `generation.notes`.
4. Keep grading/scoring independent from mapping extraction.

Practical instruction change:

- While building `question_results`, maintain a parallel `question_page_map` list from the same visual pass instead of doing a second pass later.

### 5b) `diagnose-student-school-work` skill update

Update `.cursor/skills/diagnose-student-school-work/SKILL.md` so school-returned completion diagnostics also emit `v1.4`-compatible page mapping.

Required additions:

1. During teacher-annotation-grounded grading, capture earliest attempt page per gradable `result_id`.
2. Require output JSON to include `context.question_page_map` for confidently mapped rows.
3. For uncertain rows, use `confidence=low` with a concise note, or omit with explicit unresolved mention.
4. Keep correctness/marks inference logic independent from page-mapping extraction.

Practical instruction change:

- While producing `question_results` from school-marked evidence, maintain a parallel `question_page_map` stream in the same pass.

### 6) Consumer/read-path expectations

Review Workspace backend can now:

1. look up `active_question_id`
2. resolve page via `context.question_page_map[result_id]`
3. tune viewer start page when mapping exists
4. gracefully fall back when mapping is absent

Fallback policy:

1. mapped page if present
2. current page if user has already navigated
3. attempt page 1 as last fallback

Consumer contract note:

- Backend must not assume map completeness; missing `result_id` mapping is expected and non-fatal.

## Migration Plan

### Stage 1 (Forward-only): Future marking runs on `v1.4`

Goal: ensure all newly generated marking artifacts use `marking_result.v1.4` and include `context.question_page_map` (possibly empty) without waiting for historical migration.

#### 1) Schema/version migration

1. Bump package default schema to `marking_result.v1.4`.
2. Validator accepts: `v1`, `v1.1`, `v1.2`, `v1.3`, `v1.4`.
3. New writes emit `v1.4` with `question_page_map` present (possibly empty).

### Stage 2 (Historical): Backfill and migration of existing artifacts

Goal: migrate and enrich historical `marking_results` artifacts after Stage 1 is stable in production-like usage.

#### 2) Historical artifact backfill

Run one-off skill operation on existing `marking_results` corpus:

1. run one-off skill in review-only mode first
2. run apply mode in batches (for example by student or subject)
3. optional report re-render after JSON updates

#### 3) Incomplete historical data

If `marking_asset` is unavailable or unusable:

1. still upgrade artifact to `v1.4`
2. set `question_page_map = []`
3. record unresolved count in summary output

#### 4) Rollback strategy

If backfill quality is unacceptable:

1. restore from git state before apply run
2. rerun skill in review-only mode and tighten prompts/rubric thresholds
3. apply only high-confidence subset first

## Risks and Mitigations

1. **Visual misassignment risk**
   - Mitigation: confidence field, review-only mode, staged apply, unresolved allowed.
2. **Inconsistent asset layout risk**
   - Mitigation: filename-pattern fallback, explicit skip counters, no hard crash on missing dirs.
3. **Schema drift risk**
   - Mitigation: validator hard checks for result-id membership and duplicate map entries.
4. **Data overwrite risk in bulk backfill**
   - Mitigation: review-only default, strict mutation boundary (`context.question_page_map` only), idempotent update logic, batch apply, git checkpoint before apply.
5. **Over-coupling scoring and mapping**
   - Mitigation: keep mapping metadata separate from `question_results` scoring fields.

## Detailed TODO Checklist (Implementation Monitoring)

Tracking guidance:

1. Keep each phase checklist independently shippable.
2. Mark a phase complete only when all "Definition of done" items are checked.
3. Record pilot metrics in PR notes before Stage 2 completion.

Status legend:

- `[x]` implemented
- `[ ]` not implemented yet

### Stage 1 — Future runs first (`v1.4` for all new artifacts)

### Phase 1 — Contract and schema scaffolding

#### TODO Checklist

- [x] Add proposal sign-off for `question_page_map` field shape and enums.
- [x] Add `marking_result.v1.4` enum support.
- [x] Add `context.question_page_map` schema shape.
- [x] Validate `context.question_page_map` presence/type for v1.4.
- [x] Validate `result_id` uniqueness and membership in `question_results`.
- [x] Validate `attempt_page_start >= 1`, confidence/source enums.
- [ ] Add optional strict-mode validation for `confidence=low` requiring non-empty `note`.

#### Definition of Done Checklist

- [x] Validator accepts `v1` through `v1.4`.
- [x] Invalid sample fixtures fail with expected messages.
- [x] Valid `v1.4` fixture with empty map passes.

### Phase 2 — Model/writer integration

#### TODO Checklist

- [x] Add `QuestionPageMapEntry` dataclass in `core/models.py`.
- [x] Add `MarkingArtifactContext.question_page_map` parse/serialize support.
- [x] Update `core/artifact_writer.py` to emit `schema_version = marking_result.v1.4`.
- [x] Ensure writer defaults `question_page_map` to empty list when omitted.
- [x] Preserve backward read compatibility across `v1` to `v1.4`.

#### Definition of Done Checklist

- [x] Writer output snapshot test shows `schema_version = marking_result.v1.4`.
- [ ] Round-trip parse/write preserves map entries without reordering assumptions.
- [x] Legacy artifacts still load without migration step.

### Phase 3 — Skill workflow updates

#### TODO Checklist

- [x] Update `.cursor/skills/mark-goodnote-completion/SKILL.md`.
- [x] Update `.cursor/skills/diagnose-student-school-work/SKILL.md`.
- [x] Require recording attempt page per gradable question during manual visual marking.
- [x] Require writing `context.question_page_map` in new artifacts.
- [x] Define uncertainty behavior (`low` confidence or unresolved).
- [x] Add confidence rubric examples (`high`/`medium`/`low`) in instructions.
- [ ] Add at least one concrete JSON example snippet with populated map entries.

#### Definition of Done Checklist

- [x] Both skill instructions include an explicit "parallel map capture while grading" step.
- [ ] Example output validates against `v1.4`.
- [ ] Ambiguous cases are documented with expected `note` style.

### Phase 4 — Tests (Stage 1: future-run readiness)

#### TODO Checklist

- [x] Extend `tests/test_artifact_core.py` for v1.4 schema/model validation.
- [x] Add test: duplicate `result_id` in map fails.
- [x] Add test: unknown `result_id` fails.
- [x] Add test: invalid page number (`0`/negative/non-int) fails.
- [x] Add test: invalid enum values fail.

#### Definition of Done Checklist

- [x] Stage 1 test subset is green before enabling `v1.4` by default for new runs.
- [ ] New tests fail before implementation and pass after implementation.
- [x] CI runtime impact stays acceptable for package suite.

### Phase 5 — Documentation and release hygiene (Stage 1: future-run readiness)

#### TODO Checklist

- [x] Update `README.md` for v1.4 write-path behavior for all new runs.
- [x] Update `SPEC.md` with v1.4 contract and `question_page_map` semantics.
- [x] Add `CHANGELOG.md` entry for forward-run `v1.4` adoption.
- [x] Bump package `Current version` in `README.md`.

#### Definition of Done Checklist

- [x] Stage 1 docs are complete before enabling `v1.4` default writes.
- [x] Changelog clearly marks forward-run adoption.
- [ ] Cross-doc links for Stage 1 changes resolve correctly.

### Stage 2 — Historical backfill and migration

### Phase 6 — One-off skill implementation

#### TODO Checklist

- [x] Create `.cursor/skills/oneoff-detect-question-starting-page/SKILL.md`.
- [x] Define explicit input contract: one marking-result JSON path per run.
- [x] Define gradable-question extraction step (`question_results[].result_id`).
- [x] Define marking-asset resolution and completeness checks.
- [x] Define PNG regeneration/completion procedure when assets are missing/incomplete.
- [x] Define AI visual mapping pass (`result_id -> attempt_page_start`).
- [x] Define confidence/source/evidence metadata population.
- [x] Define strict mutation boundary (`context.question_page_map` only).
- [x] Define idempotent update logic for existing map entries.
- [x] Define per-run summary output template and counters.

#### Definition of Done Checklist

- [ ] Re-running apply is idempotent on same artifact.
- [ ] Review-only and apply produce consistent mapping candidates.
- [ ] Missing/incomplete assets trigger completion workflow and are reported.
- [ ] No non-mapping JSON fields are changed in apply mode.

### Phase 7 — Tests (Stage 2: migration/backfill)

#### TODO Checklist

- [ ] Add migration/backfill tests in `tests/test_migration.py` for review-only/apply behavior.
- [ ] Add tests for missing asset directory -> empty map + stable behavior.
- [ ] Add tests for idempotent re-run (no duplicate entries).
- [ ] Add at least one mixed-confidence artifact fixture for migration/backfill tests.

#### Definition of Done Checklist

- [ ] Stage 2 migration test subset is green before broad historical apply.
- [ ] New tests fail before implementation and pass after implementation.
- [ ] CI runtime impact stays acceptable for package suite.

### Phase 8 — Documentation and release hygiene (Stage 2: migration/backfill)

#### TODO Checklist

- [ ] Update `README.md` with one-off skill usage for historical backfill.
- [ ] Update `ARCHITECTURE.md` workflow/module list including one-off skill flow.
- [ ] Update `TESTING.md` with migration/backfill workflow tests.
- [ ] Add `CHANGELOG.md` follow-up note for historical backfill rollout.

#### Definition of Done Checklist

- [ ] Stage 2 docs are complete before running broad historical apply.
- [ ] Documentation examples use final operation-mode names and command wording.
- [ ] Changelog clearly marks migration/backfill impact.
- [ ] Cross-doc links resolve correctly.

### Phase 9 — Verification and rollout

#### TODO Checklist

- [x] Run package tests: `python3 -m pytest ai_study_buddy/marking/tests -q`.
- [ ] Run one-off skill in review-only mode on pilot subset and record summary counts.
- [x] Run one-off skill in apply mode on pilot artifact subset (confirmed with `PP Math PSLE Part D P6 Topical Practice Percentage__20260421_194508.json`).
- [ ] Manually spot-check mapped pages on at least 20 artifacts across math/science/english/chinese.
- [ ] Compute pilot precision and low-confidence rate.
- [ ] Execute full apply only if quality gates are met.
- [ ] Keep rollback checkpoint until Review Workspace page-jump feature is validated.

#### Definition of Done Checklist

- [ ] Pilot metrics satisfy declared thresholds.
- [ ] Full apply summary has no unexplained validation failures.
- [ ] Rollout sign-off documented by maintainer.

## Decision

Adopt `marking_result.v1.4` with `context.question_page_map` as the canonical carrier for gradable-question-to-attempt-start-page mappings.

Implement AI-assisted backfill from existing `marking_asset` attempt PNGs with review-only/apply safety controls.

Update both `mark-goodnote-completion` and `diagnose-student-school-work` so all new marking runs capture `question_page_map` during grading, reducing future backfill burden.
