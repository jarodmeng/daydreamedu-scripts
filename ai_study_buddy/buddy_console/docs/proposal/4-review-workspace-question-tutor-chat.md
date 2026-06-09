# Proposal: Buddy Console — Review Workspace question tutor chat

**Status:** Implemented (`buddy_console` **v0.2.0**, 2026-06-09)  
**Target release:** `buddy_console` **v0.2.0**  
**Tracked by:** [L4_REVIEW_WORKSPACE_QUESTION_TUTOR_CHAT](../../../docs/L4_REVIEW_WORKSPACE_QUESTION_TUTOR_CHAT.md)  
**Depends on:** `buddy_console` review surface v0.1.16+; `marking.review` (`detail_service`, `amendment_service`, `note_service`, `repository`); `cursor-sdk`; backend `CURSOR_API_KEY`; FastAPI SSE  
**Related:** [L4_STUDENT_MVP_EXPERIENCE](../../../docs/L4_STUDENT_MVP_EXPERIENCE.md); [marking/review/](../../../marking/review/); [proposal 3](./3-review-workspace-supervised-redo-tab.md) (evidence viewer — unchanged)

**Scope vs GitHub issues:** Design and delivery live here + L4. Open issues only for post-ship bugs.

---

## Document roles

| Doc | Owns |
|-----|------|
| **[L4](../../../docs/L4_REVIEW_WORKSPACE_QUESTION_TUTOR_CHAT.md)** | Product intent, pedagogy, stale-context rules, runtime choice, risks |
| **This proposal** | API contract, file touchpoints, delivery phases, acceptance criteria, verification |

---

## 1. Summary

Add an **Ask AI** chat panel to Review Workspace (`/review`). Each `(attempt_id, result_id)` gets a persisted tutor thread. The backend:

1. Builds a **context bundle** (resolved marking, amendments, all labeled review notes, attempt page image path). Marking, amendments, and review notes are **DB-first** via `get_attempt_detail` / `StudentReviewRepository` (same as Review Workspace; see L4 read-source policy).
2. Runs **Cursor SDK local agent** (`model="auto"`) with `Agent.resume` for multi-turn.
3. Streams assistant text via **SSE**.
4. Persists **`tutor_chat.v1`** under `context/tutor_chats/` (gitignored).
5. Surfaces **stale-context** when amendments or review notes change after the session snapshot.

---

## 2. Problem

| Symptom | Cause |
|---------|--------|
| Student cannot ask “why was I wrong?” in-app | No chat in Review Workspace |
| Parent assembles context manually in Cursor | Marking JSON + PNG + notes not wired to a tutor |
| No per-question transcript | Informal chats are not persisted |

---

## 3. Scope

### In scope

See [L4 scope](../../../docs/L4_REVIEW_WORKSPACE_QUESTION_TUTOR_CHAT.md#scope).

### Out of scope

See [L4 out of scope](../../../docs/L4_REVIEW_WORKSPACE_QUESTION_TUTOR_CHAT.md#out-of-scope).

---

## 4. API contract

Base: existing review API host (`:8010`). All routes require a marked attempt (same as amendments).

### 4.1 `GET /api/student/attempts/{attempt_id}/questions/{result_id}/tutor-chat`

Returns the **latest** session for this question (by `updated_at`).

**200:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    { "role": "student", "content": "Why was I wrong?", "at": "2026-06-09T10:00:00Z" },
    { "role": "assistant", "content": "…", "at": "2026-06-09T10:00:15Z" }
  ],
  "stale_context": {
    "marking": false,
    "review_notes": false
  }
}
```

**404:** no session yet (UI shows empty chat).

**404:** attempt not found / not marked / invalid `result_id`.

### 4.2 `POST /api/student/attempts/{attempt_id}/questions/{result_id}/tutor-chat/sessions`

Start a new session (new `session_id`, new `cursor_agent_id` on first message).

**200:**

```json
{ "session_id": "…" }
```

### 4.3 `POST /api/student/attempts/{attempt_id}/questions/{result_id}/tutor-chat`

**Request:**

```json
{
  "message": "Why was I wrong?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "refresh_context": false
}
```

- `session_id` optional — omit to use latest or create implicit new session.
- `refresh_context: true` — rebuild bundle before inference (clears stale flag).

**Response:** `text/event-stream` (SSE).

Events:

| `event` | `data` (JSON) |
|---------|----------------|
| `status` | `{ "phase": "started" \| "running" }` — `started` once when inference begins; `running` on start and every ~15s until tokens (Phase 4.5) |
| `token` | `{ "text": "partial" }` |
| `done` | `{ "session_id": "…", "stale_context": { … }, "message": { "role": "assistant", "content": "…", "at": "…" } }` |
| `error` | `{ "code": "startup_failed" \| "run_failed", "message": "…" }` |

**400:** empty `message`.

**503:** `CURSOR_API_KEY` missing when tutor routes enabled.

### 4.4 `GET /api/student/attempts/{attempt_id}/questions/{result_id}/tutor-chat/context-preview`

Returns the assembled bundle (no inference). **404** unless `BUDDY_CONSOLE_TUTOR_CHAT_DEBUG=1`.

### 4.5 Stale context

Computed on every `GET` and before every `POST`:

```python
stale_context.marking = (
    live_amendment_updated_at != snapshot.amendment_updated_at
    or live_fingerprint != snapshot.resolved_question_fingerprint
)
stale_context.review_notes = (
    live_review_state_updated_at != snapshot.review_state_updated_at
)
```

`resolved_question_fingerprint` = SHA-256 of `json.dumps(resolved_row, sort_keys=True, ensure_ascii=True)`.

---

## 5. File touchpoints

### New files

| Path | Role |
|------|------|
| `ai_study_buddy/marking/review/tutor_chat_context_service.py` | Build labeled bundle |
| `ai_study_buddy/marking/review/tutor_chat_stale.py` | Fingerprints + drift |
| `ai_study_buddy/marking/review/tutor_chat_repository.py` | Read/write `context/tutor_chats/` |
| `ai_study_buddy/marking/review/tutor_chat_service.py` | Cursor SDK + SSE |
| `ai_study_buddy/schemas/marking/tutor_chat.v1.schema.json` | Artifact schema |
| `ai_study_buddy/marking/tests/test_tutor_chat_*.py` | Unit + API tests |
| `ai_study_buddy/buddy_console/backend/_spike_cursor_sdk_context.py` | Phase 0 one-off |
| `ai_study_buddy/buddy_console/frontend/src/TutorChatPanel.tsx` | Optional extract from `App.tsx` |

**Frontend scope:** `buddy_console/frontend` only. Do **not** require `review_workspace/frontend` parity for ship or acceptance (legacy rollback app; see [review_workspace README](../../../review_workspace/README.md) §Maintenance policy).

### Modified files

| Path | Change |
|------|--------|
| `ai_study_buddy/marking/review/api_routes.py` | Four tutor routes |
| `ai_study_buddy/buddy_console/backend/requirements.txt` | `cursor-sdk` |
| `ai_study_buddy/buddy_console/frontend/src/App.tsx` | `WorkspaceView` chat panel + flag |
| `ai_study_buddy/buddy_console/frontend/vite.config.ts` | Document `VITE_REVIEW_TUTOR_CHAT` if needed |
| `.gitignore` | `ai_study_buddy/context/tutor_chats/` |
| `buddy_console/SPEC.md`, `DATA_MODEL.md`, `TESTING.md`, `CHANGELOG.md` | Contract + smoke |

### Pedagogy ref injection (optional MVP)

| `subject_context` | File to inject (if exists) |
|-------------------|----------------------------|
| `singapore_primary_math` | `math_error_types.md`, `math_question_skill.md` (under `…/singapore_primary_math/`) |
| `singapore_primary_science` | `…/skill_understanding.md` |
| others | skip in v1 |

Truncate very large files with a header note if over ~8k chars (implementation choice; log once).

---

## 6. Environment variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `CURSOR_API_KEY` | Backend | Cursor SDK auth (**required** when tutor routes active) |
| `VITE_REVIEW_TUTOR_CHAT` | Frontend build | `1` shows chat panel |
| `BUDDY_CONSOLE_TUTOR_CHAT_DEBUG` | Backend | `1` enables `context-preview` |
| `BUDDY_CONSOLE_DISABLE_TUTOR_CHAT` | Backend | `1` → tutor routes 404 (rollback) |

---

## 7. Resolved decisions (June 2026)

| # | Decision |
|---|----------|
| 1 | MVP inference = **Cursor SDK local**, `model="auto"` |
| 2 | **All** review notes in bundle with `[QUESTION — …]` / `[ATTEMPT]` / `[STUDENT_SUBJECT — …]` labels |
| 3 | **No** message/session caps |
| 4 | Transcripts **filesystem-only** (no operator UI) |
| 5 | **Stale banner** when amendments or review notes drift; refresh on next send |

---

## 8. Delivery phases

### Phase 0 — Spike

- [x] `_spike_cursor_sdk_context.py` — two-turn `Agent.create` + in-session follow-up; ~19–23s/turn (2026-06-09)
- [x] Results in `buddy_console/TESTING.md` §Tutor chat — Phase 0 Cursor SDK spike

### Phase 1 — Context

- [x] `tutor_chat_context_service.py` + tests (2026-06-09)
- [x] `tutor_chat_stale.py` + tests
- [x] `context-preview` route (debug-gated)

### Phase 2 — Persistence

- [x] Schema + `tutor_chat_repository.py` + tests
- [x] `.gitignore`

### Phase 3 — API + SDK

- [x] `tutor_chat_service.py` — SSE, persist `cursor_agent_id`
- [x] `api_routes.py` routes
- [x] `requirements.txt` + `cursor-sdk`
- [x] API tests with mocked SDK

### Phase 4 — Frontend

- [x] Chat panel + SSE client + stale banner
- [x] `VITE_REVIEW_TUTOR_CHAT=1` dev workflow in README
- [x] `npm run build`

### Phase 4.5 — In-progress progress UX

- [x] SSE `status` heartbeats during inference (`tutor_chat_service.py`)
- [x] Elapsed timer, escalating status copy, expectation hints
- [x] **Stop** + 2-minute client timeout (`TutorChatPanel.tsx`, `tutorChatProgress.ts`)
- [x] API tests for `status` / heartbeat
- [ ] **Deferred:** incremental `token` streaming during SDK run

### Phase 5 — Sweep

- [x] Update L4 implementation snapshot
- [x] `SPEC.md`, `DATA_MODEL.md`, `TESTING.md`, `CHANGELOG.md` v0.2.0
- [x] Manual smoke test — incorrect questions in `/review` (operator, 2026-06-09)
- [ ] Remaining acceptance: stale banner after amend; feature-flag / API rollback

---

## 9. Acceptance criteria

1. With `VITE_REVIEW_TUTOR_CHAT=1`, **Ask AI** appears on a marked attempt’s review card.
2. Sending “Why was I wrong on this question?” yields a streamed reply referencing the student’s marked answer and diagnosis.
3. Switching `result_id` loads a different thread (or empty state).
4. **New conversation** creates a new `session_id`; old file remains on disk.
5. After saving an amendment to the active question, chat shows stale banner; **Refresh & continue** then next reply uses amended outcome.
6. With flag off, no chat UI; tutor API returns 404 when `BUDDY_CONSOLE_DISABLE_TUTOR_CHAT=1`.
7. While waiting for a reply, status pill shows elapsed seconds; **Stop** cancels the browser wait; after 2 minutes without `done`, a timeout message appears and input re-enables.
8. SSE includes `status` events before `token` / `done` on `POST`.
9. `pytest ai_study_buddy/marking/tests/test_tutor_chat_*` green; `npm run build` green.

---

## 10. Verification commands

```bash
# Backend
export CURSOR_API_KEY="…"
export BUDDY_CONSOLE_TUTOR_CHAT_DEBUG=1
python3 -m uvicorn ai_study_buddy.buddy_console.backend.app:app --reload --port 8010

# Context preview (replace ids)
curl -s "http://localhost:8010/api/student/attempts/<attempt_id>/questions/Q4/tutor-chat/context-preview" | jq .

# Frontend
cd ai_study_buddy/buddy_console/frontend
VITE_REVIEW_TUTOR_CHAT=1 npm run dev

# Tests
pytest ai_study_buddy/marking/tests/test_tutor_chat_context_service.py -q
pytest ai_study_buddy/marking/tests/test_tutor_chat_api.py -q
cd ai_study_buddy/buddy_console/frontend && npm run build
```

---

## 11. Rollback

1. Set `BUDDY_CONSOLE_DISABLE_TUTOR_CHAT=1` on backend.
2. Unset `VITE_REVIEW_TUTOR_CHAT` on frontend build.
3. Review Workspace otherwise unchanged; transcript files remain under `context/tutor_chats/` for manual cleanup.
