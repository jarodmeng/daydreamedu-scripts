# AI Study Buddy — Review Workspace question-scoped tutor chat

> Status: **Implemented (feature-flagged)** — Phases 0–5 shipped 2026-06-09 (`buddy_console` v0.2.0, `marking` v0.3.23); Phase 6 manual acceptance partially complete
>
> Target app: [`buddy_console`](../buddy_console/) route `/review` (Review Workspace)
>
> **Package delivery spec:** [`buddy_console/docs/proposal/4-review-workspace-question-tutor-chat.md`](../buddy_console/docs/proposal/4-review-workspace-question-tutor-chat.md)
>
> Related docs: [L4_STUDENT_MVP_EXPERIENCE](./L4_STUDENT_MVP_EXPERIENCE.md), [L4_MARKING_RESULT_ARTIFACT](./L4_MARKING_RESULT_ARTIFACT.md), [L2_AI_AGENTS](./L2_AI_AGENTS.md), [L3_SAFETY_AND_PRIVACY](./L3_SAFETY_AND_PRIVACY.md), [L1_ROADMAP](./L1_ROADMAP.md)
>
> **Depends on:** `buddy_console` review surface (v0.1.16+); `marking.review` detail/amendment/note services; `cursor-sdk` (Python 3.10+); `CURSOR_API_KEY` on backend host
>
> **Shipped in:** `buddy_console` **v0.2.0** (2026-06-09; `VITE_REVIEW_TUTOR_CHAT=1`)

---

## Document roles

| Doc | Owns |
|-----|------|
| **This L4** | Product intent, pedagogy, context bundle policy, artifact boundaries, backend runtime, stale-context rules, risks, decisions |
| **[Proposal 4](../buddy_console/docs/proposal/4-review-workspace-question-tutor-chat.md)** | API contract, file touchpoints, delivery phases, acceptance criteria, verification commands |
| **[L4 student MVP experience](./L4_STUDENT_MVP_EXPERIENCE.md)** | Shipped Review Workspace layout; tutor chat superseded §Out of Scope when flag on |

When this L4 conflicts with **L4_STUDENT_MVP_EXPERIENCE** §Out of Scope (“Tutor chat…”), **this L4 wins** once implementation starts.

---

### Implementation snapshot

| Area | Status |
|------|--------|
| Question-scoped chat panel in Review Workspace UI | **Shipped** (Phase 4, 2026-06-09) |
| Resizable chat panel (sessionStorage height) | **Shipped** (Phase 4, 2026-06-09) |
| Assistant markdown + GFM tables | **Shipped** (Phase 4, 2026-06-09) |
| Context assembler + preview API | **Shipped** (Phase 1, 2026-06-09) |
| `tutor_chat.v1` persistence under `context/tutor_chats/` | **Shipped** (Phase 2, 2026-06-09) |
| Cursor SDK local inference (`model="auto"`, `Agent.resume`) | **Shipped** (Phase 3, 2026-06-09) |
| Stale-context banner (amendments / review notes) | **Shipped** (Phase 4, 2026-06-09) |
| Feature flag `VITE_REVIEW_TUTOR_CHAT` | **Shipped** (Phase 4, 2026-06-09) |
| In-progress progress UX (timer, stop, timeout, SSE `status`) | **Shipped** (Phase 4.5, 2026-06-09) |
| Package ship docs (`CHANGELOG`, `SPEC`, `DATA_MODEL`, `TESTING`) | **Shipped** (Phase 5, v0.2.0) |
| `marking` **v0.3.23** changelog + `README` / `SPEC` | **Shipped** (Phase 5) |
| Manual smoke test (incorrect questions, in-app chat) | **Passed** (Phase 6, operator, 2026-06-09) |
| Manual acceptance (stale banner, flag rollback) | **Pending** (Phase 6) |
| Incremental token streaming during SDK run | **Deferred** (post-MVP) |

---

## Why This Proposal Exists

The Review Workspace supports a **question-at-a-time** review loop: evidence viewer, structured marking, amendments, and `student_review_state` notes. With `VITE_REVIEW_TUTOR_CHAT=1`, students can ask follow-up questions about the active question in-app.

**Ask AI** (shipped behind the feature flag) is a **question-scoped chat panel** in `/review`. The backend assembles a deterministic **context bundle** and runs a **Socratic tutor** via **Cursor SDK local agent** for `(attempt_id, result_id)`, persisting transcripts under `context/tutor_chats/`.

| Input | Source (existing) |
|-------|-------------------|
| Resolved marking row | `marking_result_resolved` from `get_attempt_detail` — **DB-first** via `read_marking_result_payload` / `find_marking_artifacts_for_attempt` |
| Amendments | `amendment_state` — **DB-first** via `StudentReviewRepository.load_raw_amendment` |
| Review notes (all scopes) | `review_state` — **DB-first** via `StudentReviewRepository.load_review_state` (`question_reviews[]`, `attempt_notes[]`, `student_subject_notes[]`) |
| Attempt page image | `viewer.attempt_images[]` + `question_page_map` (filesystem PNG under `context/marking_assets/…`) |
| Subject pedagogy (optional text) | `context/subject_understandings/<subject_context>/…` (filesystem markdown) |

Chat is **one question, one thread** — not a general-purpose tutor home.

---

## Scope

### In scope

1. Collapsible **Ask AI** chat panel in `WorkspaceView`; thread keyed by `(attempt_id, result_id)`.
2. Server-side **context bundle** (no browser reads of `context/`).
3. **Cursor SDK local** agent: `model="auto"`, `LocalAgentOptions(cwd=<repo_root>)`, multi-turn via `Agent.resume`.
4. **SSE streaming** of assistant text to the browser.
5. **`tutor_chat.v1`** companion artifacts (filesystem-only; gitignored).
6. **All review notes** in context with scope labels.
7. **Stale-context warning** when amendments or review notes change after session snapshot.
8. Feature flag `VITE_REVIEW_TUTOR_CHAT=1` until stable.
9. **In-progress progress UX** while the tutor runs: elapsed timer, **Stop**, client timeout, SSE `status` heartbeats (see Phase 4.5).

### Out of scope

1. Tutor chat on `/student`.
2. Hint ladder state machine / mastery updates ([L2_AI_AGENTS](./L2_AI_AGENTS.md)).
3. Mutating `marking_result` or `marking_amendment` from chat.
4. Cloud Cursor agents.
5. Production auth; PDPA retention design ([L3_SAFETY_AND_PRIVACY](./L3_SAFETY_AND_PRIVACY.md)).
6. Message or session caps.
7. In-app transcript browser (filesystem-only v1).
8. Per-question image crops (full attempt page PNG).
9. Voice I/O.
10. Direct multimodal LLM API (fallback only if SDK latency blocks ship).
11. `learning_db` dual-write for tutor transcripts in v1.
12. **Incremental token streaming** during the Cursor SDK run (tokens still arrive in a burst after inference completes in MVP; deferred).

### Non-goals

- Chat supplements review notes; it does not replace the review card.
- Browser never holds `CURSOR_API_KEY`; inference is backend-only.
- Do not use pre-exported `student_understandings/**/*.json` as runtime input.

---

## Design

### Product loop

1. Open marked attempt in `/review`.
2. Navigate to `Qn`.
3. Open **Ask AI**.
4. Backend loads latest session for `(attempt_id, result_id)` or starts new `session_id`.
5. Student message → stale check → context bundle → Cursor SDK `send` → stream reply → persist transcript.
6. On question change, load that question’s thread.

### UI (MVP)

**Placement:** split right panel — review card above, resizable **Ask AI** dock below (`buddy_console/frontend/src/App.tsx` → `WorkspaceView`; height persisted in `sessionStorage`).

**Chrome:** message list (assistant replies rendered as markdown + GFM tables), input, send, **Stop** (while waiting), **New conversation**, loading/error, disclaimer (“AI may be wrong — check with parent/teacher”), stale-context banner with **Refresh & continue**.

**While waiting for a reply:** status pill shows elapsed seconds (`Thinking… 24s` → `Still working…` → `Taking longer than usual…`); optional hint (“First replies often take 20–40 seconds”); subtext after backend SSE `status` heartbeats (“Tutor is working on your question…”); **2-minute client timeout** with recovery message; **Stop** aborts the browser wait (server may still finish).

**Feature flag:** panel hidden unless `import.meta.env.VITE_REVIEW_TUTOR_CHAT === "1"`.

**App ownership:** UI ships in **`buddy_console`** only (`/review`). The legacy standalone `review_workspace` frontend is **not** maintained for new features; its backend remains a thin `marking.review` mount for rollback. See [review_workspace README](../review_workspace/README.md) §Maintenance policy.

### Context bundle (normative)

Assembled in `tutor_chat_context_service.py` from `get_attempt_detail` outputs — never from agent file discovery.

#### Read source policy (normative)

For **marking results**, **amendments**, and **review notes**, `study_buddy.db` (`learning_db`) is the **source of truth**. Tutor chat reuses the same read boundary as Review Workspace — it does not read `context/marking_results/`, `context/marking_amendments/`, or `context/student_review_states/` JSON directly.

| Document family | Reader | DB fetch |
|-----------------|--------|----------|
| Marking result | `read_marking_result_payload` (+ artifact resolution in `find_marking_artifacts_for_attempt`) | `fetch_marking_artifact_raw_json` |
| Amendments | `StudentReviewRepository.load_raw_amendment` | `fetch_marking_amendment_raw_json` |
| Review notes | `StudentReviewRepository.load_review_state` / `load_raw_review_state` | `fetch_student_review_state_raw_json` |

Controlled by [`learning_db/core/config.py`](../learning_db/core/config.py): `LEARNING_DB_ENABLE_READS` (default **on**), `LEARNING_DB_READ_FALLBACK_FILESYSTEM` (default **off**). When reads are on and fallback is off, a DB miss yields empty/not-marked — no silent JSON scan. Filesystem JSON under `context/` remains a compatibility export when `LEARNING_DB_ENABLE_JSON_EXPORT=1`, not the primary read path.

**Not DB-backed in v1:** attempt page PNGs (`context/marking_assets/`), pedagogy markdown (`context/subject_understandings/`), tutor transcripts (`context/tutor_chats/`).

| Block | Source fields |
|-------|----------------|
| `attempt_meta` | `attempt.*`, `marking_result.context` book/unit, `is_partial` |
| `question` | Resolved `question_results[]` row for `result_id` |
| `amendments` | `amendment_state.question_amendments[]` entry for `result_id` (if any) |
| `review_notes_labeled` | See table below |
| `page` | `attempt_page_start` from map; absolute path to PNG under `context/marking_assets/…/attempt/`; optional `SDKImage.from_file` |
| `attempt_summary` | `marking_result.summary` (earned/total, assessment) |
| `pedagogy_refs` | Optional injected markdown by `subject_context` (see proposal 4) |

#### Review notes injection (normative)

Include **all** notes from `review_state` with fixed prefixes. Preserve `author_role` and `updated_at` when present.

| Label | Source | Shape (actual frontend/API) |
|-------|--------|------------------------------|
| `[QUESTION — {result_id}]` | `question_reviews[]` | `result_id`, `review_status`, `note_text`, `author_role?`, `updated_at?` |
| `[ATTEMPT]` | `attempt_notes[]` | `note_text`, `author_role?`, `updated_at?` |
| `[STUDENT_SUBJECT — {subject_context}]` | `student_subject_notes[]` | same as attempt |

**Order:** active question row first, then other `question_reviews` (sorted by `result_id`), then `[ATTEMPT]`, then `[STUDENT_SUBJECT — …]`.

Omit empty `note_text` rows unless `review_status === "reviewed"`.

### Stale-context detection (normative)

Compare live state to `context_snapshot` on the session artifact:

| Drift signal | Live source | Snapshot field |
|--------------|-------------|----------------|
| Amendments | `amendment_state.review_meta.updated_at` | `amendment_updated_at` |
| Resolved marking row | SHA-256 of canonical JSON for resolved `question_results[result_id]` | `resolved_question_fingerprint` |
| Review notes | `student_review_state` raw `updated_at` (from `load_raw_review_state`) | `review_state_updated_at` |

**On drift before send:**

1. API returns `stale_context: { marking?: bool, review_notes?: bool }` on `GET` history and in `POST` response metadata.
2. UI shows banner; student taps **Refresh & continue** (or send auto-refreshes bundle on next `POST` with `refresh_context: true`).
3. Prior transcript messages are kept; only the **next** inference uses refreshed bundle.

### Backend runtime (normative)

| Property | Value |
|----------|--------|
| Package | `cursor-sdk` — add to `buddy_console/backend/requirements.txt` |
| Create | `Agent.create(model="auto", api_key=…, local=LocalAgentOptions(cwd=REPO_ROOT))` |
| First turn | `agent.send(initial_prompt_with_full_bundle)` |
| Follow-up | `Agent.resume(cursor_agent_id)` then `agent.send(student_message)` |
| Stream | `run.iter_text()` buffered until `run.wait()` completes, then SSE `token` events; **`status` heartbeats** every ~15s while inference runs (Phase 4.5) |
| Settings | `local.setting_sources: []` (default) |
| Dispose | `with Agent.create(...) as agent:` |

Store `cursor_agent_id` on the session artifact after first successful run.

**First-turn prompt structure:** system instructions (Socratic policy) + serialized context bundle + “Answer only about this question.”

**Follow-up turns:** student message only (agent retains thread); re-inject refreshed bundle only when `refresh_context` or stale drift detected.

### System prompt policy (MVP)

1. Treat **resolved** marking as authoritative.
2. Use labeled review notes; do not confuse attempt-level vs question-level reflections.
3. Socratic hints before full solutions unless student explicitly asks for the answer.
4. Age-appropriate tone (use grade from attempt path when inferable via `infer_grade_bucket`).
5. Reference the attempt **page image**, not invented diagrams.
6. Encourage updating the question **review note** when the student reaches an insight.
7. **Do not write files** or mutate marking artifacts.

### Companion artifact: `tutor_chat.v1`

**Path (normative):**

```text
context/tutor_chats/<student_id>/<subject_context>/<marking_artifact_stem>/<result_id>/<session_id>.json
```

`<marking_artifact_stem>` = marking result JSON stem (same key as `student_review_states` / `marking_amendments`).

**Gitignore:** add `ai_study_buddy/context/tutor_chats/` to repo `.gitignore`.

```json
{
  "schema_version": "tutor_chat.v1",
  "attempt_id": "<pdf_registry completion file_id>",
  "result_id": "Q4",
  "student_id": "winston",
  "subject_context": "singapore_primary_math",
  "marking_artifact_stem": "PP Math PSLE …__20260421_194508",
  "session_id": "<uuid4>",
  "cursor_agent_id": "<local agent id after first run>",
  "created_at": "ISO-8601Z",
  "updated_at": "ISO-8601Z",
  "messages": [
    { "role": "student", "content": "…", "at": "ISO-8601Z" },
    {
      "role": "assistant",
      "content": "…",
      "at": "ISO-8601Z",
      "model": "auto",
      "runtime": "cursor-sdk-local",
      "run_id": "…"
    }
  ],
  "context_snapshot": {
    "marking_result_path": "marking_results/…json",
    "amendment_updated_at": "ISO-8601Z | null",
    "review_state_updated_at": "ISO-8601Z | null",
    "resolved_question_fingerprint": "<sha256 hex>"
  }
}
```

**Rules:** never write canonical marking or amendments from chat; multiple sessions per question allowed; UI defaults to latest by `updated_at`.

### API summary

Normative request/response shapes and routes: [proposal 4 §4](../buddy_console/docs/proposal/4-review-workspace-question-tutor-chat.md#4-api-contract).

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `…/tutor-chat` | Latest session messages + `stale_context` |
| `POST` | `…/tutor-chat` | Send message (SSE stream) |
| `POST` | `…/tutor-chat/sessions` | Explicit new `session_id` |
| `GET` | `…/tutor-chat/context-preview` | Dev bundle inspect (`BUDDY_CONSOLE_TUTOR_CHAT_DEBUG=1`) |

`attempt_id` = registry completion `file_id`. `result_id` must exist in resolved `question_results`.

**SSE `POST` events (shipped):** `status` (`started`, `running` heartbeats) → `token` (burst after inference) → `done` | `error`. See [proposal 4 §4.3](../buddy_console/docs/proposal/4-review-workspace-question-tutor-chat.md#43-post-apistudentattemptsattempt_idquestionsresult_idtutor-chat).

### Security (MVP)

1. `CURSOR_API_KEY` server-side only.
2. No full child name in application logs (log ids).
3. Scope refusal for off-topic abuse.
4. Transcripts: local disk only in v1.

---

## Migration Plan

| Step | Action | Status |
|------|--------|--------|
| 1 | New modules under `marking/review/`; routes in `api_routes.py` | Done |
| 2 | `cursor-sdk` in backend requirements | Done |
| 3 | `.gitignore` `context/tutor_chats/` | Done |
| 4 | Frontend behind `VITE_REVIEW_TUTOR_CHAT` | Done |
| 5 | On ship: update L4 snapshot, `L4_STUDENT_MVP_EXPERIENCE` out-of-scope, `buddy_console` CHANGELOG | Done (2026-06-09) |

**Rollback:** unset feature flag; optional `BUDDY_CONSOLE_DISABLE_TUTOR_CHAT=1` on backend returns 404 for tutor routes.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Wrong math / contradicts marking | Resolved row + image in bundle; disclaimer in UI |
| SDK latency | Phase 4.5 progress UX (timer, stop, timeout, SSE `status`); incremental token streaming deferred |
| Agent writes repo files | Prompt forbids writes; pre-assembled context; no `setting_sources: all` |
| Large context (all notes) | Labeled sections; active question first; monitor empirically |
| Stale advice after amendments | Stale banner + `refresh_context` on send |
| Key exposure | Backend env only |

---

## Detailed TODO Checklist (Implementation Monitoring)

### Phase 0 — SDK validation

- [x] `ai_study_buddy/buddy_console/backend/_spike_cursor_sdk_context.py` — smoke read + latency note
- [x] `cursor-sdk` in `requirements.txt`; `CURSOR_API_KEY` via `.env.local.example`
- [x] Confirm multi-turn in-session (`agent.send` × 2); ~19–23s/turn; see `buddy_console/TESTING.md`

### Phase 1 — Context + preview

- [x] `marking/review/tutor_chat_context_service.py` — `build_context_bundle(attempt_id, result_id, …)`
- [x] `marking/review/tutor_chat_stale.py` — fingerprint + drift detection
- [x] `GET …/context-preview` gated by `BUDDY_CONSOLE_TUTOR_CHAT_DEBUG`
- [x] `marking/tests/test_tutor_chat_context_service.py`

### Phase 2 — Persistence

- [x] `schemas/marking/tutor_chat.v1.schema.json`
- [x] `marking/review/tutor_chat_repository.py`
- [x] `.gitignore` entry
- [x] `marking/tests/test_tutor_chat_repository.py`

### Phase 3 — Inference API

- [x] `marking/review/tutor_chat_service.py` — Cursor SDK bridge + SSE
- [x] Multi-turn `Agent.resume` with serializable `AgentOptions` + `model="auto"` on send
- [x] Routes in `api_routes.py`
- [x] `cursor-sdk` in `requirements.txt`
- [x] `marking/tests/test_tutor_chat_api.py` (mocked SDK)
- [x] `marking/tests/test_tutor_chat_service.py` (resume options)

### Phase 4 — Frontend

- [x] Chat panel in `WorkspaceView` (`TutorChatPanel.tsx`)
- [x] Resizable chat dock (`useVerticalResizeHandle`, `sessionStorage`)
- [x] SSE client; stale banner; new session
- [x] Assistant markdown (`react-markdown`, `remark-gfm`, `tutorChatMarkdown.ts`)
- [x] `VITE_REVIEW_TUTOR_CHAT`
- [x] `npm run build` green (`buddy_console/frontend` only; tutor chat mirror removed from `review_workspace`)

### Phase 4.5 — In-progress progress UX

- [x] SSE `status` events (`started`, `running` heartbeats ~15s) while Cursor SDK inference runs in a worker thread
- [x] `StreamingResponse` no-cache / `X-Accel-Buffering: no` headers
- [x] Elapsed timer on status pill with escalating copy (Thinking → Still working → Taking longer)
- [x] First-turn / follow-up expectation hint (first 5s)
- [x] **Stop** button (`AbortController` on POST stream)
- [x] **2-minute client timeout** with recovery message; clears stuck `sending` state
- [x] `tutorChatProgress.ts` (`buddy_console/frontend`)
- [x] API tests for `status` events and heartbeat during slow inference

**Deferred (post-MVP, not Phase 4.5):** yield `token` events inside `run.iter_text()` (true incremental streaming).

### Phase 5 — Docs + ship

- [x] [Proposal 4](../buddy_console/docs/proposal/4-review-workspace-question-tutor-chat.md) status → Implemented
- [x] `buddy_console` **v0.2.0** — `CHANGELOG.md`, `README.md`, `SPEC.md`, `DATA_MODEL.md`, `TESTING.md`, `frontend/package.json`
- [x] [docs/README.md](./README.md) snapshot

### Phase 6 — Verification

- [x] Manual: marked attempt(s), incorrect question(s), ask why wrong / how to fix — operator smoke test passed (2026-06-09)
- [ ] Amend outcome → banner → refresh → new reply references amended fields
- [ ] Feature flag off → no chat UI; API 404

---

## Decision

| # | Question | Decision |
|---|----------|----------|
| 1 | Where | **Review Workspace** `/review`, question-scoped |
| 2 | Inference | **Cursor SDK local**, `model="auto"` |
| 3 | Context | Server-side bundle; **all review notes** with scope labels |
| 4 | Marking mutation | **Forbidden** |
| 5 | Storage | `tutor_chat.v1` under `context/tutor_chats/`, gitignored |
| 6 | Caps | **None** |
| 7 | Transcript UI | **Filesystem-only** v1 |
| 8 | Stale amendments/notes | **Warn + refresh** on next send |
| 9 | Hint ladder / mastery | **Deferred** |
| 10 | Package spec | **[Proposal 4](../buddy_console/docs/proposal/4-review-workspace-question-tutor-chat.md)** |
| 11 | In-progress UX while tutor runs | **Shipped** — timer, Stop, 2-min timeout, SSE `status` heartbeats (Phase 4.5) |
| 12 | Incremental token streaming | **Deferred** — tokens still burst after `run.wait()` |

---

## Open Questions

None for MVP — all prior items resolved June 2026 ([proposal 4 §7](../buddy_console/docs/proposal/4-review-workspace-question-tutor-chat.md#7-resolved-decisions-june-2026)).

**Post-MVP follow-up:** incremental `token` streaming during `run.iter_text()` (see Phase 4.5 deferred note).
