# AI Study Buddy — `buddy_console` Feature-Parity App Proposal

> Status: **Implemented** (May 26, 2026)
>
> Reference apps: [`root_pdf_browser`](../root_pdf_browser/README.md), [`student_file_browser`](../student_file_browser/README.md), [`review_workspace`](../review_workspace/README.md)
>
> Related L4 docs: [STUDENT_FILE_MANAGEMENT](./L4_STUDENT_FILE_MANAGEMENT.md), [STUDENT_MVP_EXPERIENCE](./L4_STUDENT_MVP_EXPERIENCE.md), [STUDENT_PORTAL_IN_BUDDY_CONSOLE](./L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE.md), [FILE_SYSTEM_MANAGEMENT](./L4_FILE_SYSTEM_MANAGEMENT.md), [COMPLETION_MARKING_FRAMEWORK](./L4_COMPLETION_MARKING_FRAMEWORK.md)

---

## Why This Proposal Exists

`ai_study_buddy` currently has three local browser apps:

1. `root_pdf_browser` on `8770`
2. `student_file_browser` on `8771`
3. `review_workspace` on frontend `5178` with backend `8010`

Together, these three apps already support a useful operator workflow:

- start from `student_file_browser`
- filter to the relevant card
- open PDF view or review view by deep link
- keep the inventory flow as the operator hub

The earlier consolidation framing created unnecessary complexity because it centered on wrapping or rehosting existing apps. That raises awkward questions about:

- shell ownership
- legacy route mounting
- long-term wrapper architecture
- how much old frontend code should remain in place

This proposal takes a different direction:

- create an entirely new app called `buddy_console`
- make `buddy_console` reach feature parity with the combination of the three current apps
- use the current apps as reference implementations during migration
- use `review_workspace` as the recommended implementation seed because it already contains the richest app structure
- retire or redirect old entrypoints only after parity is verified and deprecation is explicitly approved

This is a cleaner product and architecture goal because the end state is explicit:

- one real new app
- no permanent wrapper strategy
- no ambiguity about which app is the “outer shell”

This does not mean implementation must start from a blank directory. The target app identity and the starting codebase can be different.

Deep-link preservation remains a hard requirement. The new app is not acceptable unless it preserves the current card-driven navigation workflow.

---

## Scope

### In scope

1. Create a new top-level app package at `ai_study_buddy/buddy_console/`.
2. Build a new backend and frontend for `buddy_console`.
3. Achieve feature parity with the combined operator capabilities of:
   - `student_file_browser`
   - `root_pdf_browser`
   - `review_workspace`
4. Retain all current operator-facing features from those apps in the new app.
5. Preserve `student_file_browser`’s role as the operator hub in the new app.
6. Preserve deep-link behavior as a release-blocking requirement.
7. Make deep-link actions open in a new browser tab so the inventory hub remains available in the original tab.
8. Add automated end-to-end verification for critical feature-parity and deep-link flows.
9. Keep the old apps available as standalone tools until they are explicitly deprecated.

### Out of scope

1. Redesigning the review workflow itself.
2. Adding production deployment, auth, HTTPS, or multi-user access control.
3. Adding registry mutation workflows such as scan/register/move/link.
4. Changing canonical marking, review-state, or amendment artifact formats.
5. Reworking `ai_study_buddy.files` and `marking.review` beyond what is needed to support the new app cleanly.

### Non-goals

- Do not build `buddy_console` as a permanent wrapper around the old apps.
- Do not require the old frontends to remain mounted inside the new app long term.
- Do not break existing operator deep-link workflows while parity is being established.

---

## Design

### Product goal

`buddy_console` should become the single local operator app for browsing files, opening PDFs, and reviewing marked attempts.

The intended operator flow is:

1. open `buddy_console`
2. land on inventory
3. filter to the relevant card
4. open PDF or review in a new tab via deep link
5. continue working from the still-open inventory tab

This preserves the current workflow while removing the need to think in terms of separate apps.

### Architecture goal

`buddy_console` should be a brand-new app with:

- its own backend entrypoint
- its own frontend entrypoint
- its own routes and UI structure
- shared use of existing domain logic where appropriate

It should not depend on mounting old frontends as part of its long-term architecture.

### Recommended implementation seed

Although `buddy_console` is a new app target, the safest implementation starting point is to use `review_workspace` as the seed codebase.

Reason:

- `review_workspace` already has the richest backend/frontend app structure
- `review_workspace` already contains the most complex existing feature set
- rewriting review behavior from scratch would be the highest-risk part of the project
- adding inventory and PDF parity onto a review-capable base is likely lower risk than rebuilding review after starting from a thinner app

Recommended interpretation:

- `buddy_console` is the target app identity and package
- `review_workspace` is the recommended source to copy in order to create the initial `buddy_console` scaffold, then adapt for parity work

This proposal therefore distinguishes:

1. end-state architecture
2. implementation starting point

Those should not be conflated.

### Runtime shape

The target local runtime should be:

1. one backend process on `8010`
2. one frontend dev server on `5178`

The consolidated frontend should expose:

- `/inventory`
- `/pdf`
- `/review`

`/inventory` should be the default landing route.

### Reference-app parity model

The three current apps should be treated as behavioral references:

- `student_file_browser`
  Source of truth for inventory filtering, hub workflow, and card actions.
- `root_pdf_browser`
  Source of truth for PDF tree browsing, root handling, and PDF deep-link behavior.
- `review_workspace`
  Source of truth for marked-attempt review flows, review-state behavior, and amendment-related review surfaces.

The proposal target is not line-by-line code migration. The target is behavior parity.

### Feature-parity requirements

`buddy_console` should provide all of the following before becoming the default app:

1. Inventory hub parity
   - equivalent filter-first inventory behavior
   - equivalent card metadata and card actions
   - same operator-first workflow starting from inventory

2. PDF browsing parity
   - equivalent ability to open a specific PDF by deep link
   - equivalent root/path guard behavior
   - equivalent tree/list browsing behavior needed by current workflows

3. Review parity
   - equivalent ability to open a marked attempt by deep link
   - equivalent attempt review workflow needed by current users
   - equivalent access to evidence and review-related state

4. Deep-link parity
   - inventory card to PDF destination works
   - inventory card to review destination works
   - destination opens directly with the intended context
   - opening happens in a new browser tab

5. Navigation parity
   - the operator can keep the inventory hub open while opening detailed views elsewhere

Parity rule:

- all current operator-facing features across the three reference apps must be retained
- no existing feature should be intentionally dropped in the first `buddy_console` rollout

### Package layout

The preferred package layout is:

```text
ai_study_buddy/
  buddy_console/
    __init__.py
    README.md
    backend/
      __init__.py
      app.py
      routes/
        __init__.py
        inventory.py
        pdf.py
        review.py
      services/
        __init__.py
        inventory_service.py
        pdf_service.py
        review_service.py
    frontend/
      package.json
      vite.config.ts
      index.html
      src/
        main.tsx
        App.tsx
        routes/
          InventoryRoute.tsx
          PdfRoute.tsx
          ReviewRoute.tsx
        components/
          AppShell.tsx
          TopNav.tsx
        lib/
          deepLinks.ts
          inventoryState.ts
```

### Backend design

The backend should be purpose-built for `buddy_console`, while reusing stable domain logic from existing packages where that reduces risk.

Recommended approach:

- inventory routes call into shared `ai_study_buddy.files` helpers and new `buddy_console` inventory services
- PDF routes implement the guarded root/list/view behavior needed from `root_pdf_browser`
- review routes reuse existing review-domain backend logic where practical rather than reimplementing review semantics from scratch

Key rule:

- reuse domain logic, not app boundaries

That means it is acceptable to import stable logic from existing packages, but not to define success as “the old apps are mounted inside the new app.”

### Frontend design

The frontend should be built as a real new app.

That means:

- `buddy_console/frontend` owns the app shell
- `buddy_console/frontend` owns `/inventory`, `/pdf`, and `/review`
- route behavior may be implemented incrementally, but the target is native route ownership in the new frontend

The initial implementation can prioritize parity over polish, but the end state should still be one coherent app.

### Deep-link compatibility

The current deep-link contracts should be preserved conceptually:

- PDF: `?id=<root_id>&rel=<path>`
- Review: `?attempt_id=<registry_uuid>&student_id=<students.id>`

Target mapping:

- `/pdf?id=<root_id>&rel=<path>`
- `/review?attempt_id=<registry_uuid>&student_id=<students.id>`

Deep-link preservation requirements:

1. every current card action that opens Root PDF Browser or Review Workspace must continue to resolve to the corresponding destination in `buddy_console`
2. the destination route must open with enough query-string context to land on the intended PDF or attempt without additional manual navigation
3. deep-link navigation from inventory must open a new browser tab
4. migration is not complete until both newly generated links and existing operator-used/bookmarked links are verified
5. any regression in deep-link behavior blocks rollout of `buddy_console` as the default app

### State preservation requirement

Because deep links should open in a new tab, the original inventory tab should remain useful without extra recovery work.

Minimum expected preserved state in the inventory tab:

- current filters
- current query-string state

### Startup UX

The new app should ship one canonical startup flow, for example:

- `.cursor/commands/start-buddy-console.md`

That startup flow should:

1. start or verify backend on `8010`
2. start or verify frontend on `5178`
3. print the single entry URL

Old startup flows and old apps should remain available as standalone tools until they are explicitly deprecated.

---

## Migration Plan

### Phase 1 — Define parity targets

1. Enumerate the operator-critical features from the three current apps.
2. Convert them into a parity checklist for `buddy_console`.
3. Confirm deep-link flows and new-tab behavior as required acceptance criteria.
4. Mark all current features as retained unless explicitly deprecated in a future proposal.

Acceptance criteria:

- the parity target is explicit and testable
- rollout cannot be declared complete against vague “roughly similar” behavior
- the parity checklist covers all current operator-facing features

### Phase 2 — Scaffold the new app

1. Create `ai_study_buddy/buddy_console/`.
2. Seed the new app by copying `review_workspace` into the initial `buddy_console` scaffold.
3. Create backend entrypoint and route skeleton.
4. Create frontend entrypoint and route skeleton.
5. Add app-level README and startup docs.

Acceptance criteria:

- the new app exists as an independent package
- the new app can be started without implying wrapper-based architecture
- the implementation seed reduces review-feature rewrite risk rather than increasing it

Implementation status:

- completed

### Phase 3 — Build inventory parity

1. Recreate the inventory hub behavior in `buddy_console`.
2. Preserve filter behavior and card actions.
3. Preserve inventory-first operator workflow.

Acceptance criteria:

- inventory is usable as the primary hub
- critical Student File Browser behavior is present

Implementation status:

- completed
- inventory hub route exists and is the default landing page
- backend inventory APIs are wired
- manually tested as acceptable for current parity target

### Phase 4 — Build PDF parity

1. Recreate the PDF deep-link destination behavior in `buddy_console`.
2. Recreate guarded root/path and listing behavior needed by current use.
3. Connect inventory card actions to the new PDF route.

Acceptance criteria:

- inventory card -> PDF deep link works in a new tab
- PDF route opens the intended content directly

Implementation status:

- completed
- PDF backend routes and frontend route exist
- deep-link opening works in a new tab
- manually tested as acceptable for current parity target

### Phase 5 — Build review parity

1. Recreate or compose the review route behavior in `buddy_console`.
2. Reuse review-domain backend logic where practical.
3. Connect inventory card actions to the new review route.

Acceptance criteria:

- inventory card -> review deep link works in a new tab
- review route opens the intended marked attempt directly

Implementation status:

- completed
- review route is currently provided through the seeded review flow
- inventory-to-review deep linking works
- manually tested as acceptable for current parity target

### Phase 6 — Automated verification

1. Add automated end-to-end coverage for critical parity flows.
2. Add explicit regression coverage for deep links.
3. Verify old bookmarked/operator-used links still resolve acceptably during migration.

Acceptance criteria:

- critical feature-parity flows are covered by automated tests
- deep-link preservation is verified automatically before default rollout

Implementation status:

- completed
- backend inventory/PDF route tests have been added
- frontend automated tests cover review deep-link helpers and inventory link contracts
- current practical readiness was accepted without waiting for full browser-level end-to-end automation

### Phase 7 — Cutover and retirement

1. Make `buddy_console` the default documented app.
2. Keep old apps available as standalone tools during the deprecation period.
3. Update or redirect old entrypoints only when deprecation is explicitly approved.
4. Keep rollback available until the new app has proven stable.

Acceptance criteria:

- the default operator workflow uses `buddy_console`
- old entrypoints remain available or are changed only through an explicit deprecation decision

Implementation status:

- completed
- `buddy_console` is now documented as the preferred unified operator app
- legacy standalone app docs have been updated to reflect rollback/reference status
- rollback guidance is documented
- old standalone apps remain available

---

## Risks and Mitigations

### Risk: “feature parity” stays vague

Mitigation:

- define a concrete parity checklist early
- treat parity as behavior-based, not architecture-based
- explicitly retain all current operator-facing features unless separately deprecated

### Risk: deep-link behavior regresses during rewrite

Mitigation:

- keep deep linking as a release-blocking requirement
- require automated end-to-end coverage for critical deep-link flows

### Risk: rewriting a new app costs more upfront than wrapper-style consolidation

Mitigation:

- reuse stable backend/domain logic where helpful
- use `review_workspace` as the implementation seed rather than rewriting review features from scratch
- keep phase ordering focused on hub-first parity
- favor operator-critical behavior over cosmetic polish

### Risk: inventory hub workflow degrades

Mitigation:

- keep `/inventory` as the default landing route
- require new-tab deep-link behavior
- preserve inventory state in the original tab

### Risk: old and new entrypoints are confusing during migration

Mitigation:

- designate `buddy_console` as the target app early
- document legacy status clearly
- redirect old entrypoints only after parity is verified

---

## Detailed TODO Checklist (Implementation Monitoring)

### Phase 1 — Parity definition

- [x] Create a concrete feature-parity checklist covering the operator-critical behavior of `student_file_browser`, `root_pdf_browser`, and `review_workspace`.
- [x] Mark all current operator-facing features as required for first parity unless explicitly deferred by a later decision.
- [x] Record the critical deep-link flows that must be preserved.

Note: the agreed high-level parity list was accepted as sufficient to start implementation, with finer-grained parity detail to be refined through implementation rather than pre-expanded in isolation.

### Phase 2 — App scaffolding

- [x] Create `ai_study_buddy/buddy_console/`.
- [x] Copy `review_workspace` as the initial seed scaffold for `buddy_console`.
- [x] Add backend skeleton under `ai_study_buddy/buddy_console/backend/`.
- [x] Add frontend skeleton under `ai_study_buddy/buddy_console/frontend/`.
- [x] Add [README.md](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/buddy_console/README.md) once the package exists.
- [x] Create `.cursor/commands/start-buddy-console.md`.

### Phase 3 — Inventory parity

- [x] Implement inventory backend routes.
- [x] Implement inventory frontend route as the default landing page.
- [x] Match critical filter and card-action behavior from `student_file_browser`.
- [x] Preserve inventory query-string state in the hub tab.
Note: phase marked complete based on manual app testing against the current parity target.

### Phase 4 — PDF parity

- [x] Implement PDF backend routes with guarded root/path behavior.
- [x] Implement PDF frontend route.
- [x] Preserve `id` + `rel` deep-link semantics.
- [x] Make inventory -> PDF open in a new browser tab.
Note: phase marked complete based on manual app testing against the current parity target.

### Phase 5 — Review parity

- [x] Implement or compose review backend routes for `buddy_console`.
- [x] Implement review frontend route.
- [x] Preserve `attempt_id` + `student_id` deep-link semantics.
- [x] Make inventory -> review open in a new browser tab.
Note: phase marked complete based on manual app testing against the current parity target.

### Phase 6 — Testing

- [x] Add backend tests for inventory routes.
- [x] Add backend tests for PDF routes.
- [x] Add backend tests for review-route integration.
- [x] Add automated end-to-end coverage for:
  - inventory hub flow
  - inventory card -> PDF deep link
  - inventory card -> review deep link
  - preserved inventory-tab behavior after opening a new tab
- [x] Add regression coverage for existing bookmarked/operator-used deep links.
Note: this phase is marked complete at the current practical readiness bar. Current automated coverage is backend-route and frontend-helper focused rather than full browser-level end-to-end automation.

### Phase 7 — Docs and cutover

- [x] Update docs so `buddy_console` becomes the default operator app.
- [x] Update old app READMEs to describe their legacy or compatibility status.
- [x] Keep all old apps and entrypoints available as standalone tools until explicit deprecation.
- [x] Add deprecation notes only when a later decision is made to retire or redirect them.
- [x] Document rollback steps in case cutover uncovers blocking regressions.
Note: this phase is marked complete for the current cutover state. Explicit redirect/retirement work remains a future follow-up only if a later deprecation decision is made.

---

## Open Questions

1. What exact feature-parity checklist should be locked before implementation starts?
2. For review parity, what is the clearest checklist for verifying that all current `review_workspace` features have been retained?

---

## Decision

Proceed with a new-app proposal.

The approved direction is:

1. create `buddy_console` as an entirely new app
2. target feature parity with the combination of `student_file_browser`, `root_pdf_browser`, and `review_workspace`
3. use `review_workspace` as the recommended implementation seed rather than rewriting review features from scratch
4. treat the existing apps as reference implementations, not permanent embedded components
5. keep Inventory as the default operator landing route
6. preserve deep-link behavior as a hard requirement
7. make inventory-to-detail deep links open in new browser tabs
8. require automated end-to-end verification for critical parity and deep-link flows before default rollout
9. retain all current operator-facing features in the first parity target
10. preserve filters in the original inventory tab as the required state-retention baseline
11. keep all current apps available as standalone tools until explicit deprecation

This proposal has now been implemented at the current practical-readiness bar:

1. `buddy_console` exists as the preferred unified operator app
2. inventory, PDF, and review flows are available in one app surface
3. legacy standalone apps remain available for rollback/reference use
4. remaining future work, if any, should be tracked as follow-up enhancement work rather than as open proposal scope
