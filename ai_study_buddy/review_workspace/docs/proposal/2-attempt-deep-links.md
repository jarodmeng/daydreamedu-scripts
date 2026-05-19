# Proposal: Review Workspace attempt deep links

**Status:** Implemented and smoke-verified (2026-05-19) — `review_workspace` v0.1.4, `student_file_browser` v0.1.1  
**Tracked by:** [TODO.md](../../../TODO.md) **Completed P0-2**  
**Depends on:** `review_workspace` v0.1.3+, `student_file_browser` v0.1.0, `root_pdf_browser` v0.1.6 (View PDF precedent)  
**Related:** [L4_STUDENT_FILE_MANAGEMENT.md](../../../docs/L4_STUDENT_FILE_MANAGEMENT.md) Open Questions §1

---

## 1. Executive Summary

Today, **Student File Browser** card **Review Workspace** opens `http://127.0.0.1:5178/` with no attempt context. The operator must pick the student, find the completion in **My Work**, and click **Open Review Workspace** manually.

**View PDF** already deep-links into **Root PDF Browser** via `?id=` + `rel=`. This proposal adds the symmetric link for review: a URL that opens **Review Workspace** directly on one marked attempt.

The backend already exposes `GET /api/student/attempts/{attempt_id}` where `attempt_id` is the registry `pdf_files.id`. The work is almost entirely **frontend URL bootstrapping** in `review_workspace`, followed by a small **Student File Browser** patch to emit the link from `registry_file_id`.

**Target releases:** `review_workspace` **v0.1.4** and `student_file_browser` **v0.1.1** (patch), in **one commit** — implement workspace deep-link bootstrap first, then browser card action.

---

## 2. Problem Statement

### Current pain

1. **Context switch cost:** Operator finds a marked completion in the file browser, clicks **Review Workspace**, lands on student picker or **My Work**, and must locate the same file again.
2. **Broken handoff:** Two local apps that share the same registry identity (`pdf_files.id`) do not pass that identity across the link.
3. **Inconsistent UX:** **View PDF** is one click to the right file; **Review Workspace** is one click to the app root only.

### Why now

- Student File Browser v0.1.0 shipped with explicit post-MVP deferral for attempt deep links.
- Review Workspace v0.1.3 is stable for attempt detail, amendments, and review state.
- P0-1 flags this as immediate attention.

---

## 3. Scope

### In scope

1. **Review Workspace frontend:** Parse deep-link query params on load; open the workspace screen for a marked attempt when valid.
2. **Review Workspace docs:** README, SPEC (URL contract), CHANGELOG, TESTING manual steps.
3. **Student File Browser:** Change **Review Workspace** card action to include `attempt_id` (registry `file_id`).
4. **Student File Browser docs:** README, SPEC, CHANGELOG, TESTING smoke note.

### Out of scope

1. Backend API changes (existing `GET /api/student/attempts/{attempt_id}` is sufficient).
2. Hash-based routing or a client-side router library (keep query-param bootstrapping like `root_pdf_browser`).
3. Deep links from other surfaces (email, marking CLI, learning DB UI) — may reuse the same URL contract later.
4. Opening unmarked attempts via deep link (card action remains `has_marking=true` only).
5. Cross-origin deployment or auth (loopback dev tools only).

### Non-goals

- Do not add a new REST endpoint solely for “resolve attempt from path.”
- Do not require Student File Browser to proxy Review Workspace APIs.
- Do not block v0.1.4 on full E2E browser automation if unit-level URL parsing tests are sufficient for this slice.

---

## 4. Proposed URL Contract

### Canonical deep link

```text
http://127.0.0.1:5178/?attempt_id=<registry_uuid>
```

- **`attempt_id`** — required for deep open; must equal `pdf_files.id` / Student File Browser `registry_file_id` / Review Workspace list item `attempt_id`.

### Helper param (emitted by Student File Browser)

```text
http://127.0.0.1:5178/?attempt_id=<registry_uuid>&student_id=<students.id>
```

- **`student_id`** — include when the card has a resolved `student_id` (Student File Browser always emits both params in that case). Pre-selects the student in local state before or in parallel with attempt fetch. When absent, derive `student_id` from the attempt detail response (`attempt.student_id`).

**Rationale:** Student File Browser cards already carry resolved `student_id`; passing it avoids a flash of wrong student context if localStorage holds a different last student. It is not required for correctness because attempt detail is authoritative.

### URL sync after in-app navigation (recommended)

Mirror **Root PDF Browser** behavior:

| User action | URL behavior |
|-------------|--------------|
| Open attempt from **My Work** | `history.replaceState` → `?attempt_id=…` (+ `student_id` if known) |
| Back from workspace to **My Work** | Remove `attempt_id`; keep `student_id` if useful |
| Student picker / change student | Clear `attempt_id`; set or keep `student_id` |
| Invalid / missing attempt on load | Show error; strip or leave `attempt_id` (prefer strip after failed fetch) |

Use **`replaceState`**, not `pushState`, for in-app transitions so back-button behavior stays predictable in a single-page app without a router.

### Identity mapping (single source of truth)

| Surface | Field name | Value |
|---------|------------|-------|
| `pdf_registry.db` | `pdf_files.id` | UUID |
| Review Workspace API | `attempt_id` | same UUID |
| Student File Browser card | `registry_file_id` | same UUID |
| Deep link query | `attempt_id` | same UUID |

---

## 5. Review Workspace Frontend Behavior

### Boot sequence

On initial mount (after students list load begins):

1. Read `window.location.search` via `URLSearchParams`.
2. If `attempt_id` is absent → existing behavior (localStorage student → **My Work** or picker).
3. If `attempt_id` is present:
   1. Optionally apply `student_id` to `selectedStudentId` and `localStorage` when it matches a known student.
   2. `GET /api/student/attempts/{attempt_id}` (reuse existing `openAttempt` path).
   3. On **200** and `marking_status === "marked"` → set detail, `screen = "workspace"`, sync URL.
   4. On **200** and `marking_status === "not_marked"` → show clear error (“Attempt is not marked yet”); land on **My Work** for resolved student if possible.
   5. On **404** / network error → show error; do not leave a broken workspace shell.

### Loading / error UX

- Show a dedicated loading state while deep-link fetch runs (avoid flashing picker then workspace).
- Surface API error message or status (e.g. “Attempt not found”).
- Provide **Back to My Work** / **Change student** actions from error state.

### Implementation notes

- Primary file: `review_workspace/frontend/src/App.tsx`.
- Extract small pure helpers (e.g. `parseDeepLinkParams`, `buildAttemptUrl`) for unit tests in `App.test.ts`.
- Do not fetch attempt detail twice on deep-link load (guard against duplicate `useEffect` runs in Strict Mode if needed).

---

## 6. Student File Browser Changes

### Card action

When `item.has_marking === true` and `item.registry_file_id` is set:

```javascript
const q = new URLSearchParams({ attempt_id: item.registry_file_id });
if (item.student_id) {
  q.set("student_id", item.student_id);
}
rw.href = `${siblingAppBaseUrl(REVIEW_WORKSPACE_PORT)}?${q.toString()}`;
```

(`siblingAppBaseUrl` uses `window.location.hostname` so links match `localhost` vs `127.0.0.1` with however the operator opened the file browser.)

- Keep `target="_blank"` (same as today).
- If `has_marking` but `registry_file_id` is missing (should not happen for registered marked cards), fall back to app root and log a console warning in dev.

### Version

Bump **student_file_browser** to **v0.1.1** with CHANGELOG entry referencing P0-1 / this proposal.

---

## 7. Documentation Updates

| Package | Files |
|---------|-------|
| `review_workspace` | `README.md` (deep link example), `SPEC.md` (§ URL / frontend bootstrap contract), `CHANGELOG.md` (v0.1.4), `TESTING.md` (manual deep-link smoke) |
| `student_file_browser` | `README.md`, `SPEC.md` (card action URL), `CHANGELOG.md` (v0.1.1), `TESTING.md` |
| Cross-cutting | `docs/L4_STUDENT_FILE_MANAGEMENT.md` Open Questions §1 → mark **done** when P0-1 ships |

No change to `DATA_MODEL.md` unless we document URL params in an appendix; prefer SPEC for HTTP/URL contracts.

---

## 8. Testing Strategy

### Review Workspace — unit

- Parse valid / empty / malformed `attempt_id` and `student_id`.
- `buildAttemptUrl` round-trip.
- (Optional) mock fetch: deep-link effect calls correct API path.

### Review Workspace — manual smoke

1. Start backend `:8010` and frontend `:5178`.
2. Copy an `attempt_id` from `GET /api/student/attempts?student_id=…`.
3. Open `http://localhost:5178/?attempt_id=<id>` → workspace loads with correct attempt.
4. Repeat with `&student_id=` when localStorage holds a different student.
5. Invalid UUID / unknown id → error UI, no crash.
6. Open attempt from **My Work** → URL updates with `attempt_id`.
7. **Back** → URL clears attempt param; list visible.

### Student File Browser — manual smoke

1. Filter to a marked registered completion.
2. **Review Workspace** opens new tab on correct attempt (not picker).
3. **View PDF** still works (regression).

### Regression

- Existing amendment save/reload flows unchanged.
- Student picker + localStorage last student unchanged when no query params.

### Smoke verification (2026-05-19)

Manual operator smoke **passed**:

1. **Student File Browser → Review Workspace** — marked completion card **Review Workspace** opened a new tab on the correct attempt workspace (no manual search in **My Work**).
2. **Hostname alignment** — card links use the same hostname as the file browser session (`localhost` when the browser was opened via `localhost`); fixed an initial `127.0.0.1` vs `localhost` mismatch that broke the handoff.
3. **Review Workspace bootstrap** — fixed React Strict Mode double-mount leaving the app stuck on **Loading...** during initial load.

Not re-run in this session (deferred to future regression): paste-URL deep link without file browser, invalid `attempt_id`, unmarked attempt URL, in-app URL sync/back navigation.

---

## 9. Open Questions

All resolved **2026-05-19**.

| # | Question | Decision |
|---|----------|----------|
| 1 | Query param name: `attempt_id` vs `id`? | **`attempt_id`** — matches API path segment and list payloads; avoids collision with Root PDF Browser’s `id` (root key). |
| 2 | Include `student_id` in emitted links? | **Yes when the card has `student_id`** — Student File Browser emits both params; Review Workspace accepts `student_id` alone or with `attempt_id`. |
| 3 | Open unmarked attempt via URL (bookmark / debug)? | **No for v0.1.4** — show error + **My Work**; keeps contract aligned with card action. |
| 4 | Use `127.0.0.1` vs `localhost` in Student File Browser? | **Same hostname as file browser** (`window.location.hostname`, port 5178) — avoids `localhost` / `127.0.0.1` origin split during smoke testing. |
| 5 | Frontend tests in Vitest vs Playwright for deep link? | **Vitest** for URL helpers + boot logic; manual smoke for full navigation. |
| 6 | Release packaging? | **One commit** containing both packages; **implement Review Workspace (v0.1.4) first**, then Student File Browser card action (v0.1.1), so no link is emitted before the app can consume it. |

---

## 10. Implementation Plan

Phases are ordered for safe delivery within **one commit**: Review Workspace must accept links before Student File Browser emits them (Phase 1 before Phase 2 in the diff).

### Phase 1 — Review Workspace deep-link bootstrap

**Goal:** App opens directly on a marked attempt when `?attempt_id=` is present.

#### Todo checklist

- [x] Add `parseDeepLinkParams(search: string)` and `buildReviewWorkspaceUrl({ attemptId, studentId? })` helpers.
- [x] On app mount, if `attempt_id` set, fetch attempt detail and enter **workspace** screen on success.
- [x] Apply optional `student_id` to state + localStorage when valid.
- [x] Handle `not_marked`, 404, and fetch errors with explicit UI.
- [x] Sync URL via `replaceState` when opening attempt from **My Work**; clear on back.
- [x] Avoid double-fetch on deep-link load (Strict Mode: no `bootstrapStartedRef` guard).

#### Test checklist

- [x] Vitest: param parsing and URL builder edge cases.
- [ ] Manual: valid deep link opens workspace (paste URL).
- [ ] Manual: wrong id shows error.
- [ ] Manual: in-app open updates URL; back clears `attempt_id`.

#### Success / handoff criteria

- [x] Deep link works without Student File Browser changes (paste URL manually) — covered by card smoke; paste-URL steps not re-run.
- [x] No regression to picker / **My Work** when query string is empty.

---

### Phase 2 — Student File Browser link emission

**Goal:** Card **Review Workspace** uses the Phase 1 URL contract.

#### Todo checklist

- [x] Update `static/app.js` to build `?attempt_id=` + `student_id` when card has both.
- [x] Guard: only when `has_marking && registry_file_id`.
- [x] Use `window.location.hostname` for sibling app links (Review Workspace + Root PDF Browser).
- [x] Bump package version to **v0.1.1**.

#### Test checklist

- [x] Manual: card link opens correct attempt in new tab.
- [ ] Manual: unmarked / unregistered cards do not show Review Workspace action (unchanged).

#### Success / handoff criteria

- [x] Operator path “filter → Review Workspace” is one click to the right attempt.
- [x] Link format matches Phase 1 contract exactly.

---

### Phase 3 — Documentation and cross-references

**Goal:** Operators and agents can discover and rely on the URL contract.

#### Todo checklist

- [x] `review_workspace/README.md` — deep link section + example URL.
- [x] `review_workspace/SPEC.md` — frontend URL bootstrap contract (params, boot behavior, URL sync).
- [x] `review_workspace/CHANGELOG.md` — **v0.1.4** entry.
- [x] `review_workspace/TESTING.md` — deep-link smoke steps.
- [x] `student_file_browser/README.md`, `SPEC.md`, `CHANGELOG.md`, `TESTING.md` — updated card action.
- [x] `docs/L4_STUDENT_FILE_MANAGEMENT.md` — Open Questions §1 marked implemented; remove “app root only” where stale.

#### Test checklist

- [ ] Follow TESTING.md deep-link steps on a clean browser profile (no localStorage).

#### Success / handoff criteria

- [x] A reader can construct a working deep link from docs alone.
- [x] L4 student file management doc matches shipped behavior.

---

### Phase 4 — Final sweep and TODO closure

**Goal:** Confirm the slice is complete, consistent, and ready to merge.

#### What “final sweep” means here

Before marking the proposal done, the implementer should:

1. **Completeness** — every Phase 1–3 checklist item checked or explicitly deferred with reason.
2. **Accuracy** — URL examples in all docs use the same param names and port (`5178`).
3. **Consistency** — `attempt_id` terminology aligned across review_workspace API, file browser `registry_file_id`, and deep links.
4. **Regression** — amendment save/reload and View PDF deep links still work.
5. **Version bumps** — CHANGELOG / README “Current version” lines updated for both packages.
6. **Implementation readiness** — no open questions block shipping unless escalated.

#### Todo checklist

- [x] Run `npm run build` in `review_workspace/frontend` (primary frontend quality gate).
- [x] Run existing pytest suites for packages touched (if any backend tests added).
- [x] Re-read SPEC vs implemented behavior; fix doc drift.
- [x] Complete [TODO.md](../../../TODO.md) **P0-1**: toggle `[x]`, move to **Completed → P0**, preserve timestamp / add completion note if desired.

#### Test checklist

- [x] End-to-end operator smoke: Student File Browser → Review Workspace opens correct attempt.

#### Success / handoff criteria

- [x] **P0-1** closed in TODO.md (Completed **P0-2**).
- [x] Proposal status updated to **Implemented** with release versions noted.
- [x] No remaining “app root only” claims for Review Workspace card action in L4 docs.

---

## 11. Acceptance Criteria (proposal-level)

1. `http://<hostname>:5178/?attempt_id=<registry_uuid>` opens the review workspace for that marked attempt without manual search. **Met** (card smoke).
2. Student File Browser **Review Workspace** button generates the same URL shape using `registry_file_id`. **Met**.
3. Invalid or unmarked attempts fail gracefully with user-visible errors. **Implemented**; error-path smoke not re-run.
4. README / SPEC / CHANGELOG / TESTING updated in both packages. **Met**.
5. [TODO.md](../../../TODO.md) **P0-1** marked complete after Phase 4. **Met** (Completed **P0-2**).

---

## 12. Recommendation

Proceed with **query-param deep linking** on the existing attempt detail API. This is the smallest change that completes the operator handoff started by Root PDF Browser v0.1.6, reuses stable registry identity, and avoids new backend surface area.

Ship in **one commit**: **review_workspace v0.1.4** first (deep-link bootstrap), then **student_file_browser v0.1.1** (card action), so no link is emitted before the app can consume it.
