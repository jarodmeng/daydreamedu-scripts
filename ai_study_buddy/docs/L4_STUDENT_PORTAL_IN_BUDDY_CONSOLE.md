# AI Study Buddy — Student Portal in `buddy_console`

> Status: **Active** (June 2026) — product phase 1 shipped in `buddy_console` v0.1.11
>
> Target app: [`buddy_console`](../buddy_console/README.md)
>
> Related docs: [L4_BROWSER_APP_CONSOLIDATION](./L4_BROWSER_APP_CONSOLIDATION.md), [L4_STUDENT_MVP_EXPERIENCE](./L4_STUDENT_MVP_EXPERIENCE.md), [L4_LOCAL_LEARNING_DB](./L4_LOCAL_LEARNING_DB.md), [L3_USER_EXPERIENCE](./L3_USER_EXPERIENCE.md), [L1_ROADMAP](./L1_ROADMAP.md)
>
> **Phase 1 delivery (P1-1 shape):** [`buddy_console/docs/proposal/2-student-marks-by-question-type.md`](../buddy_console/docs/proposal/2-student-marks-by-question-type.md)

---

## Document roles

| Doc | Owns | Does not own |
|-----|------|----------------|
| **This L4** | Portal vision, routes, serve-time policy, product phases after Phase 1, risks, long-term open questions | Per-phase todo/test checklists, file touchpoints, acceptance criteria, “Implemented” status |
| **[Proposal 2](../buddy_console/docs/proposal/2-student-marks-by-question-type.md)** | Phase 1 shipping spec: API contract, touchpoints, acceptance criteria, implementation phases 1–4, final sweep | Tutor/gamification, full portal roadmap beyond marks table |

When the two conflict on **policy or product intent**, this L4 wins. When they conflict on **Phase 1 delivery detail**, proposal 2 wins.

---

### Implementation snapshot

| Area | Status |
|------|--------|
| `buddy_console` route `/student` | **Shipped** (v0.1.11) |
| Phase 1: **Marks by question type** (serve-time backend compute, via API) | **Shipped** |
| Student portal backend read API | **Shipped** — `GET /api/student/marks-by-question-type`; see [proposal 2](../buddy_console/docs/proposal/2-student-marks-by-question-type.md) |
| Live workflow stats + action queue + `/review` deep links | Later phase |
| Auth/multi-user hardening | Out of scope for MVP |

---

## Why the student portal exists

`buddy_console` currently has three operator-first surfaces:

1. `/inventory` (default)
2. `/pdf`
3. `/review`

This is strong for parent/admin operations, but there is no explicit student home route yet. We already have enough data to provide a useful first student portal:

- marked attempt outcomes (`marking_result`, amendment-resolved)
- review progress (`student_review_state`)
- canonical marking + FQI data in `study_buddy.db` / `context/marking_results/**` (same inputs as [`report_marked_completion_fqi_stats.py`](../context/student_understandings/scripts/report_marked_completion_fqi_stats.py))

The goal of this proposal is to add a fourth route, `/student`, as a practical student-facing portal while avoiding a risky full redesign.

**First deliverable:** expose the **Marks by question type** table (amendment-resolved `earned_marks` / `max_marks` by FQI `question_type`) on `/student`, with numbers **computed at HTTP serve time** by the backend — not read from pre-written static JSON under `context/student_understandings/`.

Other report sections (FQI question totals, files-by-mix, mismatches, per-file lists) stay out of Phase 1. Later phases add workflow snapshots, recommendation queues, and `/review` deep links using the same serve-time policy.

---

## Scope

### Product phase 1 (first deliverable)

Ship **`/student`** with per-subject **Marks by question type** (serve-time backend compute; see [serve-time policy](#serve-time-data-policy-normative--all-phases)). Detailed scope, API JSON, touchpoints, and checklists: [proposal 2](../buddy_console/docs/proposal/2-student-marks-by-question-type.md).

Operator exports under `context/student_understandings/**` (`--write-artifacts`) remain for diffing and agents; they are **not** a runtime data source for `/student`.

### Product phases after phase 1

1. **Today snapshot** from live marking/review workflow (DB + canonical artifacts).
2. **Needs attention** queue and **Continue review** actions (deep link into `/review`).
3. Blended ranking for “next best actions” (all computed at serve time).

### Out of scope (all phases for now)

1. Tutor chat, hint ladder, or AI conversation UI.
2. Student write operations that mutate marking facts.
3. Authentication/identity hardening beyond local dev behavior.
4. Parent dashboard and cross-student classroom views.
5. Gamification, rewards, streak engine, and planner automation.
6. Full timeline analytics or mastery-model scoring redesign.

### Non-goals

- Do not replace `/review`; `/student` should route into it.
- Do not make markdown rendering the primary student UX.
- Do not introduce a new canonical artifact schema in MVP.

---

## Product Decisions

### Route model

Add a fourth route:

- `/student` -> student portal home

Existing routes remain unchanged:

- `/inventory` operator hub (default)
- `/pdf` document view
- `/review` detailed attempt review

### Audience and posture

MVP posture is "student-facing read model over the existing local operator stack":

- optimized for a student session with one selected student
- can still be launched by parent/operator
- no hard auth in MVP (consistent with current localhost model)

### Primary user loop

**Phase 1:**

1. Open `/student?student_id=<id>` (optional `&subject=math` to pre-select)
2. Choose a subject (or use URL pre-select)
3. See **marks by question type** for that subject (same semantics as the operator report table)

**Later:**

3. Open a recommended attempt/question in `/review`
4. Return to `/student` for next item and progress context

---

## Data Model and Sources

### Serve-time data policy (normative — all phases)

Student portal UI data must be **generated when the backend serves the request**, not loaded from pre-written static JSON (or markdown) files on disk.

| Rule | Meaning |
|------|---------|
| **No static JSON as UI source** | Endpoints must not read `context/student_understandings/**/*.json` (or similar export files) to populate `/student`. |
| **No frontend file reads** | The browser never fetches paths under `context/`; it only calls backend APIs. |
| **Shared compute logic** | Serve-time aggregation reuses the same Python functions as offline reports (e.g. `build_marked_completion_fqi_stats` in [`report_marked_completion_fqi_stats.py`](../context/student_understandings/scripts/report_marked_completion_fqi_stats.py)), ideally via import rather than copy-paste. |
| **Canonical inputs** | Computation reads **live** sources: `study_buddy.db` (marking artifacts, FQI runs, amendments) and registry/context paths those APIs already use — same as the report script today. |
| **Optional exports** | `report_marked_completion_fqi_stats.py --write-artifacts` may still write `student_understandings/**` for operators, agents, and regression diffs; those files are **out of band** for the portal runtime. |
| **Response metadata** | API `generated_at` is the **compute timestamp** for that HTTP response, not the mtime of an export file. |

This policy applies to Phase 1 and all later `/student` features (workflow counts, action queues, etc.).

### Later-phase data sources

Extend the same serve-time pattern:

1. Workflow and review fields from `study_buddy.db` + `marking.review` (and registry where needed).
2. Action queues ranked in the service layer at request time.
3. Optional in-memory caching with explicit TTL is allowed; **disk export JSON is not** a cache backend for portal responses.

### Read models (by product phase)

| Product phase | Portal surfaces (illustrative) | Contract owner |
|---------------|-------------------------------|----------------|
| **1** | `GET /api/student/marks-by-question-type` → `marks_by_question_type` per subject | [Proposal 2 §4](../buddy_console/docs/proposal/2-student-marks-by-question-type.md) → shipped `buddy_console/SPEC.md` |
| **2+** | `portal/summary`, `workflow`, `next_actions` (serve-time) | Future proposal or L4 amendment when scoped |

All values are serve-time from shared compute (e.g. `build_marked_completion_fqi_stats` → `marking_marks_by_type`), never from `student_understandings/*.json`.

---

## UX (product-level)

### Product phase 1

Single-page **`/student`**: required `student_id`; **four-choice subject picker** (English, Chinese, Math, Science) — default none selected, no data until chosen; optional `subject` URL param pre-selects. For the selected picker, show **Marks by question type** table block(s): Chinese shows standard and higher Chinese as separate blocks on the same page, and higher Chinese is shown only when that student has higher-Chinese markings. `Computed: <generated_at>` footnote. No top-nav link to `/student` in Phase 1.

Screen-level detail: [proposal 2 §4](../buddy_console/docs/proposal/2-student-marks-by-question-type.md#subject-picker-ui--api).

### Product phases after phase 1

Today snapshot, needs-attention queue, **Review now** → `/review`, optional charts and extra report sections.

### UX constraints (all phases)

1. HTML tables/cards — not embedded `context/**/*.md`.
2. Later recommendations need a traceable reason string.
3. Preserve `student_id` / subject filter when navigating away and back.

---

## Delivery of product phase 1

All implementation detail for the first shippable slice lives in **[proposal 2](../buddy_console/docs/proposal/2-student-marks-by-question-type.md)** (P1-1 phases 1–4: backend API → frontend route → package docs → final sweep). Do not duplicate that plan here.

After ship: update the [implementation snapshot](#implementation-snapshot-planned) above; normative HTTP contract lives in `buddy_console/SPEC.md`.

---

## Product roadmap (after phase 1)

| Product phase | Capability |
|---------------|------------|
| **2** | Today snapshot, needs-attention queue, **Review now** → `/review` (serve-time) |
| **3** | Charts, optional extra report sections, session feedback |

Each future slice should get its own package proposal when scoped; amend this L4 only for cross-cutting policy or route changes.

---

## Risks and Mitigations

1. **Risk:** serve-time aggregation is slower than reading a static file.  
   **Mitigation:** acceptable for local MVP; optional short TTL in-process cache later (still recomputed from DB, not from export JSON).
2. **Risk:** duplicate logic between report script and portal service.  
   **Mitigation:** import `build_marked_completion_fqi_stats` (or extract shared module in a follow-up).
3. **Risk:** route complexity in `App.tsx` grows further.  
   **Mitigation:** isolate student portal into route-specific module files.
4. **Risk:** "student portal" is interpreted as production-auth product too early.  
   **Mitigation:** explicitly keep local-MVP trust model and mark auth as out of scope.

---

## Open Questions

Phase 1 decisions (resolved): [proposal 2 §7](../buddy_console/docs/proposal/2-student-marks-by-question-type.md#7-resolved-decisions-phase-1).

Longer-term (Phase 2+ product):

1. Ranking policy for “next best actions” (lowest marks, recent mistakes, unreviewed first, blended).
2. In-process cache TTL for expensive aggregates (must still be serve-time from DB, not export JSON).
