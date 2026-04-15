# Context Resolver MVP Implementation Plan

Status: Implemented (MVP scope)

Audience: Maintainers of `ai_study_buddy/marking` and `mark-goodnote-completion` skill

## 1) Goal

Implement the MVP context resolver contract documented in:

- `ai_study_buddy/marking/SPEC.md` (normative resolver behavior)
- `ai_study_buddy/marking/ARCHITECTURE.md` (architectural boundaries and flow)

Primary target workflow:

- `.cursor/skills/mark-goodnote-completion/SKILL.md`

The resolver must support path-first context resolution for full-attempt marking, including:

1. optional attempt auto-registration (`auto_register_attempt`)
2. optional template auto-link (`auto_link_template`)
3. optional embedded-answer override (`self_answer_pages`)

## 2) Scope

### In scope

- Implement resolver behavior in `core/context_resolver.py`
- Keep `resolve_marking_context(...)` as the single MVP resolver API
- Add/adjust unit tests under `marking/tests/`
- Update `.cursor/skills/mark-goodnote-completion/SKILL.md` to match implemented behavior
- Update package docs where needed (`SPEC.md`, `ARCHITECTURE.md`, `README.md`, `TESTING.md` if required)

### Out of scope (for this MVP plan)

- Question-level scope selection/resolution
- Index-aware resolver APIs
- New artifact schema versions

## 3) Implementation Strategy

Ship in small phases with passing tests at each phase.

### Phase 0 — Baseline and safety

Tasks:

1. Confirm current `resolve_marking_context(...)` callers and expected assumptions.
2. Add a minimal regression test baseline for existing happy-path behavior.
3. Freeze error-message style for new errors (actionable, path-aware).

Acceptance criteria:

- Existing path-based resolver behavior still passes tests.

### Phase 1 — `auto_register_attempt` support

Tasks:

1. Extend resolver signature with:
   - `auto_register_attempt: bool = False`
2. In path-based attempt resolution:
   - if file path is not registered and `auto_register_attempt=False`, raise `NotFoundError`
   - if file path is not registered and `auto_register_attempt=True`, register completion as `main`, then re-resolve
3. Enforce guardrails:
   - reject invalid/non-GoodNotes paths for auto-registration
   - ensure auto-registration does not produce a template attempt

Suggested internal changes:

- Add helper for "resolve or register attempt by path" to keep function readable.

Acceptance criteria:

- Unregistered path resolves successfully only when `auto_register_attempt=True`.
- Registered path behavior remains unchanged.
- Invalid auto-registration attempts fail with clear `MarkingContextResolutionError`.

### Phase 2 — `auto_link_template` integration hardening

Tasks:

1. Keep current `auto_link_template` behavior.
2. Ensure it works correctly after auto-registration path.
3. Improve error clarity when linking fails after an enabled auto-link attempt.

Acceptance criteria:

- Newly registered attempt can auto-link template in same resolver call when enabled.
- Missing template with `auto_link_template=False` still fails fast.

### Phase 3 — `self_answer_pages` override mode

Tasks:

1. Extend resolver signature with:
   - `self_answer_pages: tuple[int, int] | None = None`
2. Validate override input:
   - exactly two integers
   - inclusive 1-based page semantics
   - `begin_page <= end_page`
3. Implement override semantics:
   - use template as answer file
   - set `answer_page_start`/`answer_page_end` from override
   - set `answer_mapping_source` to explicit self-answer override note
4. Keep default registry mapping mode unchanged when override not provided.

Acceptance criteria:

- Override mode bypasses registry answer mapping dependency.
- Output fields match contract exactly.
- Invalid tuples fail with `MarkingContextResolutionError`.

### Phase 4 — Skill contract alignment (required)

Tasks (required):

1. Update `.cursor/skills/mark-goodnote-completion/SKILL.md` to reflect implemented resolver behavior:
   - path-first resolver call remains standard
   - when file may be unregistered, call with `auto_register_attempt=True`
   - when link may be missing, call with `auto_link_template=True`
   - for weighted assessment papers with embedded answers, call with `self_answer_pages=(begin,end)`
2. Add explicit fallback rules in skill:
   - if fuzzy search is not unique, stop and ask user to disambiguate
   - if embedded-answer page range is unknown, ask user for page range before marking
3. Ensure wording distinguishes:
   - completion path discovery (skill)
   - deterministic context assembly (resolver)

Acceptance criteria:

- Skill instructions are fully consistent with implemented resolver flags and failure modes.

### Phase 5 — Documentation and examples

Tasks:

1. Add resolver usage examples to `README.md` or `SPEC.md`:
   - standard mapped-answer call
   - first-touch onboarding call (`auto_register_attempt=True`, `auto_link_template=True`)
   - embedded-answer call with `self_answer_pages`
2. Ensure `ARCHITECTURE.md` remains high-level and points to `SPEC.md` for normative details.

Acceptance criteria:

- New users can invoke resolver correctly from docs without reading source code.

## 4) Test Plan

Add/extend tests in `ai_study_buddy/marking/tests/` for at least:

1. registered path + existing template + mapping (baseline)
2. unregistered path + `auto_register_attempt=False` -> `NotFoundError`
3. unregistered path + `auto_register_attempt=True` -> success
4. auto-register + auto-link combined flow -> success
5. `self_answer_pages` valid override -> answer fields set to template + override pages
6. `self_answer_pages` invalid inputs:
   - wrong tuple length
   - non-integer values
   - begin > end
7. override mode when no book mapping exists -> still success if template exists
8. non-GoodNotes/invalid path auto-register attempt -> `MarkingContextResolutionError`

Test quality bar:

- deterministic assertions on key fields (`answer_*`, `template_*`, IDs)
- clear assertions on exception class and message fragments

## 5) Risks and Mitigations

1. Risk: auto-registration registers wrong file class.
   - Mitigation: enforce path and file-type guardrails before/after registration.
2. Risk: embedded-answer mode hides missing mapping mistakes.
   - Mitigation: include explicit `answer_mapping_source` override note in output.
3. Risk: skill drifts from resolver contract.
   - Mitigation: treat skill update as required deliverable in same implementation cycle.

## 6) Definition of Done

Done means all are true:

1. Resolver supports `auto_register_attempt` and `self_answer_pages` per `SPEC.md`.
2. Existing behavior remains backward compatible for existing callers.
3. Tests cover success + failure paths for all new flags.
4. `.cursor/skills/mark-goodnote-completion/SKILL.md` is updated and aligned.
5. Docs are internally consistent (`SPEC.md`, `ARCHITECTURE.md`, `README.md` as needed).

## 7) TODO Checklist

- [x] Confirm existing `resolve_marking_context(...)` caller assumptions and lock baseline tests.
- [x] Add `auto_register_attempt: bool = False` to resolver signature.
- [x] Implement path-based auto-registration flow for unregistered attempts.
- [x] Enforce auto-registration guardrails (GoodNotes path and non-template attempt constraints).
- [x] Ensure `auto_link_template` works in both pre-registered and newly auto-registered flows.
- [x] Add `self_answer_pages: tuple[int, int] | None = None` to resolver signature.
- [x] Validate `self_answer_pages` input shape and range.
- [x] Implement embedded-answer override mode (template as answer file + override page range + mapping-source note).
- [x] Add/expand resolver tests for all new success and failure paths.
- [x] Update `.cursor/skills/mark-goodnote-completion/SKILL.md` to reflect new resolver flags and fallback rules.
- [x] Add docs usage examples for mapped-answer, onboarding, and embedded-answer flows.
- [x] Verify `SPEC.md`, `ARCHITECTURE.md`, and proposal stay aligned after implementation.

## 8) Implementation Notes

Implemented code paths:

1. `ai_study_buddy/marking/core/context_resolver.py`
   - added `auto_register_attempt` and `self_answer_pages` support
   - added self-answer override mode
   - added `self_answer_pages` validation helper
   - added optional book-group resolution for override mode
2. `ai_study_buddy/marking/core/models.py`
   - made `MarkingContext.book_group_id` and `book_label` optional for embedded-answer mode
3. `ai_study_buddy/marking/tests/test_context_resolver.py`
   - new tests for auto-register, auto-link, override success/failure, and default mapping mode
4. `.cursor/skills/mark-goodnote-completion/SKILL.md`
   - updated skill contract to use resolver flags and embedded-answer flow
5. `ai_study_buddy/marking/README.md`
   - added resolver usage examples for mapped-answer, onboarding, and embedded-answer flows

Validation completed:

- `python3 -m pytest ai_study_buddy/marking/tests/test_context_resolver.py`
- `python3 -m pytest ai_study_buddy/marking/tests`
