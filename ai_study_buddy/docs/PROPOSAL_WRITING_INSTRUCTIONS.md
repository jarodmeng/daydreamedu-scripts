# AI Study Buddy — Proposal Writing Instructions

Use this instruction file for every new proposal under `ai_study_buddy/docs/`, especially `L4_*` implementation proposals.

---

## Required Structure

Every proposal must include these sections (in this order unless there is a strong reason to change):

1. `Why This Proposal Exists`
2. `Scope` (in-scope and out-of-scope)
3. `Design` (API/schema/workflow)
4. `Migration Plan` (if existing behavior is affected)
5. `Risks and Mitigations`
6. `Detailed TODO Checklist (Implementation Monitoring)`
7. `Decision`

If one section is intentionally omitted, explicitly state why.

---

## Detailed TODO Checklist Requirement (Mandatory)

Every proposal must include a **detailed checkbox checklist** used to monitor implementation progress.

Checklist rules:

- Use markdown checkboxes (`- [ ]` / `- [x]`).
- Group by phase (for example: scaffolding, implementation, tests, migration, rollout).
- Items must be concrete and verifiable (file/module/function or explicit acceptance criteria).
- Include testing and docs updates as first-class tasks, not optional notes.
- Include at least one rollback/safety task when the proposal changes existing behavior.
- Include owner/status/date placeholders if useful for tracking.

Minimum checklist coverage:

- code changes
- tests
- migration/backward compatibility
- documentation updates
- verification steps

---

## Writing Conventions

- Prefer deterministic language over aspirational wording.
- Separate proposal intent from implementation status.
- Keep APIs explicit (inputs/outputs/types/defaults).
- Mark non-goals clearly to prevent scope creep.
- Keep decisions short and crisp; avoid unresolved prose in the decision section.

---

## Suggested Checklist Template

```md
## Detailed TODO Checklist (Implementation Monitoring)

### Phase 1 — Scaffolding
- [ ] Create module/file X with public API Y
- [ ] Add package exports in Z

### Phase 2 — Implementation
- [ ] Implement behavior A with acceptance criteria ...
- [ ] Implement behavior B with acceptance criteria ...

### Phase 3 — Testing
- [ ] Add unit tests covering ...
- [ ] Add regression tests for ...

### Phase 4 — Migration and Compatibility
- [ ] Add compatibility shim/re-export for ...
- [ ] Update call sites in ...
- [ ] Remove legacy path only after ...

### Phase 5 — Verification and Docs
- [ ] Run verification commands and record result
- [ ] Update docs: ...
- [ ] Confirm proposal reflects final implementation
```

---

## Applicability

This instruction applies to:

- all new `L4_*.md` proposals
- substantial updates to existing proposal docs

It is recommended (but optional) for L1-L3 docs unless they are implementation-tracking documents.

