# Proposal: Buddy Console — Manual completion date on inventory cards

**Status:** Implemented (`buddy_console` **v0.1.5**, post-implementation sweep **2026-05-28**)  
**Target release:** `buddy_console` **v0.1.5**  
**Tracked by:** Implemented directly (no dedicated `TODO.md` item was created for this slice)  
**Depends on:** `pdf_file_manager` v0.3.22+ (`set_completion_date`, `file_completion_dates`, `get_operation_log`); `buddy_console` inventory hub v0.1.4+; `ai_study_buddy.files` v0.3.6+ (`completion_date` on `OnDiskMainPdfCard`)  
**Related:** [proposal 17 — completion date](../../pdf_file_manager/docs/proposals/17-completion-date.md); [student_file_browser card sort](../../student_file_browser/docs/proposal/2-card-sort-order.md); [buddy_console DATA_MODEL.md](../../DATA_MODEL.md); [buddy_console SPEC.md](../../SPEC.md); [TODO.md P1-1](../../TODO.md) (proposal standard — in progress)

**Scope vs GitHub issues:** Design and phased delivery live in this proposal. Open a GitHub issue only for post-ship bugs or follow-ups (e.g. Student File Browser parity).

---

## 1. Summary

Operators can set or correct a completion’s **Completed** date from the inventory UI. Today the only supported write path is programmatic (`PdfFileManager.set_completion_date` / inference CLIs). This proposal adds a **small, local-only HTTP mutation** on the Buddy Console backend and a **minimal card action** (date input + Save) for **registered completion mains**.

Writes always use `source=manual` per proposal 17. The UI supports **set when missing** and **overwrite** (with confirmation when replacing a non-manual date). Audit trail via `operation_log` + `source_detail` (see §4).

**Primary deliverable:** Buddy Console only (**option A**); `student_file_browser` unchanged for this release.

**PATCH response (#5):** Slim JSON body; frontend **refetches** `GET /api/inventory` with **`appliedState`** query string (same as the inventory `useEffect` load path in `InventoryApp.tsx`).

---

## 2. Problem

| Symptom | Cause |
|---------|--------|
| Wrong or missing **Completed** on a card | Inference failed, was never run, or operator knows a better date |
| Fixing a date requires Python/CLI | No inventory-surface write path |
| **Registered** date is visible but must not be edited as completion | Separate fields; operators need an explicit completion edit affordance |

Registry `added_at` remains read-only in the UI; this proposal does not conflate it with `completion_date`.

---

## 3. Scope

### In scope

| Layer | Change |
|-------|--------|
| **`buddy_console` backend** | `PATCH` endpoint; validate input; `PdfFileManager.set_completion_date(..., source="manual")`; clear `InventoryRuntime.enriched_cache` on success |
| **`buddy_console` frontend** | Date control + Save on eligible cards; confirm when overwriting non-manual source; refetch inventory after success |
| **Tests** | API tests with temp registry DB (`PDF_REGISTRY_PATH`); optional Vitest for confirm/refetch helpers |
| **Docs** | `SPEC.md`, `DATA_MODEL.md`, `CHANGELOG.md`, `TESTING.md`; one-line link in proposal 17 § Consumer changes |

### Out of scope

| Item | Notes |
|------|--------|
| Bulk edit / CSV import | `infer_completion_dates` or scripts |
| Re-run inference from UI | CLI / agent batches |
| Unregistered on-disk files | Need `registry_file_id` |
| Templates, raw files, general-scope mains without `student_id` | See §4 eligibility (`_validate_completion_date_target`) |
| `clear_completion_date` UI | No Clear button; API/CLI only |
| `pdf_file_manager` schema / inference matrix changes | [Proposal 17](../../pdf_file_manager/docs/proposals/17-completion-date.md) |
| Student File Browser route/UI | Option A — Buddy Console only |
| In-app completion-date history UI | Audit via `operation_log` / `source_detail` only |

### Not in `pdf_file_manager` proposal folder

Storage and `set_completion_date` contract stay in **proposal 17**. This document is the **consumer/UI** follow-on.

---

## 4. Data contract (normative — no new registry fields)

### Write

```python
existing = pfm.get_completion_date(registry_file_id)
source_detail: dict = {"set_via": "buddy_console"}
if existing is not None:
    source_detail["previous_completion_date"] = existing.completion_date
    source_detail["previous_source"] = existing.source
    if existing.confidence is not None:
        source_detail["previous_confidence"] = existing.confidence

pfm.set_completion_date(
    registry_file_id,
    completion_date,  # YYYY-MM-DD; normalized by pdf_file_manager
    source="manual",
    confidence=None,
    inference_model=None,
    source_detail=source_detail,
)
```

`set_completion_date` calls `_validate_completion_date_target` internally. Buddy Console should **not** duplicate registry SQL.

### Eligibility (server — align with `PdfFileManager._validate_completion_date_target`)

| Check | Failure |
|-------|---------|
| `get_file(registry_file_id)` exists | 404 |
| `file_type == "main"` | 400 |
| `is_template is False` | 400 |
| `student_id` is set | 400 |

Map `ValueError` from `set_completion_date` → **400** with message body. Map `NotFoundError` (if used) → **404**.

**UI show-edit control** (all required):

- `item.is_registered === true`
- `item.scope === "completion"`
- `item.registry_file_id` is non-null

Templates use `scope === "template"`; unregistered cards lack `registry_file_id`. Do not offer edit on `scope === "template"` even if registered.

### Audit trail

| Layer | What it records |
|-------|------------------|
| **`operation_log`** | Every `set_completion_date` — `before_state` / `after_state` on update; `after_state` on insert. `get_operation_log(file_id=..., operation="set_completion_date")`. |
| **`file_completion_dates.source_detail`** | `set_via: "buddy_console"`; on overwrite `previous_completion_date`, `previous_source`, optional `previous_confidence`. |

**Overwrite policy (UI):** Confirm when `completion_date_source` is truthy and not `"manual"` (§6). Inference `--force-manual` is unrelated to UI saves.

---

## 5. HTTP API (Buddy Console)

### Request

```http
PATCH /api/inventory/items/{registry_file_id}/completion-date
Content-Type: application/json

{ "completion_date": "2026-03-15" }
```

- Path `registry_file_id` = `OnDiskMainPdfCard.registry_file_id` / `pdf_files.id`.
- Body required; `completion_date` must be a string (invalid shapes → 400).

### Response

| Code | When |
|------|------|
| 200 | Success — **slim JSON** (below) |
| 400 | Invalid date, ineligible file, empty body, `ValueError` from registry |
| 404 | Unknown `registry_file_id` |
| 503 | Registry unavailable (same pattern as other inventory routes) |

**200 body (normative):**

```json
{
  "registry_file_id": "<uuid>",
  "completion_date": "2026-03-15",
  "completion_date_source": "manual"
}
```

**Cache:** Set `runtime.enriched_cache = None` (full clear) on success so the next `GET /api/inventory` rebuilds from registry. Simpler than per-card patch; acceptable for rare operator edits.

**Frontend after 200:** Refetch inventory using `toQueryString(appliedState)` → `GET /api/inventory?...` (and optionally `/api/config?...` if filter meta must stay in sync — match existing load effect if needed).

### Implementer touchpoints

| File | Change |
|------|--------|
| `buddy_console/backend/inventory_api.py` | Route handler, Pydantic body model, cache clear, error mapping |
| `buddy_console/backend/app.py` | No change if router already mounted |
| `buddy_console/frontend/src/InventoryApp.tsx` | Edit UI, PATCH, confirm, refetch helper |
| `buddy_console/frontend/src/styles.css` | `.card-completion-date-edit` (or similar) |
| `buddy_console/tests/test_inventory_api.py` | PATCH tests with temp DB + registered completion row |

---

## 6. UI (Buddy Console inventory card)

Near **Completed** / **Registered**: `<input type="date">` + **Save** (compact expand optional).

| Card state | UI |
|------------|-----|
| Eligible, no `completion_date` | Empty input; Save — **no** confirm |
| Eligible, `completion_date_source === "manual"` | Pre-filled; Save — **no** confirm (including date change) |
| Eligible, `completion_date_source` set and not `manual` | Pre-filled; **`window.confirm`** before PATCH — message includes current date, source, new date |
| Not eligible (unregistered, template, missing `registry_file_id`) | No control |

**Timezone:** `type="date"` → `YYYY-MM-DD`; matches proposal 17 calendar-day storage.

**Errors:** Show PATCH error message inline or brief alert; do not refetch on failure.

### Student File Browser

**Option A (decided):** Buddy Console only for this release.

---

## 7. Open questions

All resolved **2026-05-28**.

| # | Question | Decision |
|---|----------|----------|
| 1 | Audit trail? | **Yes** — `operation_log` + `source_detail` per §4; no history UI in this release |
| 2 | Clear date button? | **No** in this release |
| 3 | Confirm overwrite of inferred dates? | **Yes** when `completion_date_source` present and not `manual` |
| 4 | Student File Browser parity? | **Option A** — Buddy Console only |
| 5 | PATCH response? | **Slim JSON** + **refetch** inventory with `appliedState` query string |

---

## 8. Pre-implementation final sweep (2026-05-28)

Proposal-level readiness check **before** Phase 1 coding (per [TODO.md P1-1](../../TODO.md) “final sweep” intent).

| Check | Result |
|-------|--------|
| **Completeness** | §1–7, acceptance criteria, phased plan, touchpoints, eligibility aligned with `_validate_completion_date_target` |
| **Accuracy** | PATCH path, slim 200 body, refetch via `appliedState` / `toQueryString`; cache full clear |
| **Consistency** | Terminology matches proposal 17 (`completion_date` ≠ `registry_added_at`); inventory item fields match `InventoryApp.tsx` `InventoryItem` |
| **§7 resolved** | All five decisions recorded; #5 slim + refetch explicit in §1 and §5 |
| **No contradictions** | No Clear button; no SFB route in this release; confirm only for non-manual source |
| **Test plan** | Phase 1–2 checklists reference `test_inventory_api.py` + manual smoke |
| **Doc plan** | Phase 3 lists SPEC/DATA_MODEL/CHANGELOG/TESTING + proposal 17 link |
| **Out of scope explicit** | Bulk, inference UI, history UI, schema changes |

**Post-implementation** final sweep remains **Phase 4** (pytest, build, mark **Implemented**, optional TODO closure).

---

## 9. Implementation record

Phases use **numbered indices** per [TODO.md P1-1](../../TODO.md). This section records what shipped.

### Phase 1 — Backend mutation + cache

**Goal:** Persist manual dates via HTTP; no UI.

#### Todo checklist

- [x] Added `PATCH /api/inventory/items/{registry_file_id}/completion-date` in `inventory_api.py`.
- [x] Added Pydantic request model: `{ "completion_date": str }`.
- [x] Load existing row via `get_completion_date`; build `source_detail` per §4.
- [x] Call `set_completion_date(..., source="manual")`; map errors to 404/400.
- [x] On success: `runtime.enriched_cache = None` on app `inventory_runtime`.
- [x] Return slim JSON per §5.

#### Test checklist

- [x] Register temp completion main with `student_id`; PATCH sets row; GET inventory shows `completion_date` + `source=manual`.
- [x] 404 bad id; 400 template / raw / missing `student_id` target.
- [x] Overwrite: second PATCH updates row; `get_operation_log` has `set_completion_date` with `before_state` when prior row existed.
- [x] Invalid date string → 400.

#### Success / handoff criteria

- [x] `pytest` green for new tests without frontend.
- [x] No `pdf_file_manager` schema changes.

---

### Phase 2 — Frontend card control

**Goal:** Operator edit path end-to-end.

#### Todo checklist

- [x] `canEditCompletionDate(item)` per §4 UI rules.
- [x] Date input + Save on eligible cards (`InventoryApp.tsx`) with subtle collapsed affordance.
- [x] `needsConfirm(item, newDate)` — true when `completion_date_source` truthy and not `manual`.
- [x] PATCH then refetch: `fetch(\`/api/inventory?${toQueryString(appliedState)}\`)` (reuse `appliedState`, not draft-only).
- [x] Minimal styles in `styles.css`.
- [x] Bumped version to **v0.1.5** in `frontend/package.json` / README / CHANGELOG.

#### Test checklist

- [x] Added Vitest coverage for `needsConfirm` cases.
- [x] Manual: set missing date; overwrite `handwritten_page1` with confirm; edit manual without confirm; **Registered** unchanged; **Completed (recent)** order updates after refetch (operator-verified).

#### Success / handoff criteria

- [x] Operator can complete §10 acceptance criteria without CLI.

---

### Phase 3 — Documentation and cross-references

**Goal:** Discoverable contract for operators and agents.

#### Todo checklist

- [x] Updated `buddy_console/SPEC.md` with `PATCH /api/inventory/items/{registry_file_id}/completion-date`.
- [x] Updated `buddy_console/DATA_MODEL.md` with manual edit + audit note.
- [x] Updated `buddy_console/README.md`, `CHANGELOG.md` (**v0.1.5**), `TESTING.md` with smoke steps.
- [x] Updated `pdf_file_manager/docs/proposals/17-completion-date.md` consumer table with Buddy Console manual edit UI link.
- [x] Added one-line pointer in `student_file_browser/README.md`: manual completion date → Buddy Console.

#### Test checklist

- [x] Operator smoke from `TESTING.md` on real registry.

#### Success / handoff criteria

- [x] Docs match §5–6 behavior; proposal 17 remains storage canonical.

---

### Phase 4 — Post-implementation final sweep and TODO closure

**Goal:** Mark proposal **Implemented**.

#### What “final sweep” means here

1. **Completeness** — Phase 1–3 checklists done or deferred with reason.  
2. **Accuracy** — SPEC examples match shipped route and JSON.  
3. **Consistency** — No doc says `added_at` is editable as completion.  
4. **Regression** — Inventory filter/sort, PDF browser, review deep links still work.  
5. **Version** — README/CHANGELOG **v0.1.5**.  
6. **TODO** — If tracked in [TODO.md](../../TODO.md), close bullet in **Completed**.

#### Todo checklist

- [x] `pytest ai_study_buddy/buddy_console/tests/test_inventory_api.py` (ran full `ai_study_buddy/buddy_console/tests/` suite)
- [x] `npm run build` in `buddy_console/frontend`
- [x] Re-read SPEC vs code
- [x] Proposal **Status** → **Implemented** with date + version
- [x] Close linked TODO item if any (none linked for this slice)

#### Test checklist

- [x] E2E smoke: set date → refetch → sort sensible under **Completed (recent)** (operator-verified)

#### Success / handoff criteria

- [x] §9 acceptance criteria all met
- [x] Proposal status **Implemented**

---

## 10. Acceptance criteria (proposal-level)

1. Set **Completed** on a registered completion with no prior `file_completion_dates` row.
2. Overwrite existing **Completed**; after save `completion_date_source` is `manual`.
3. Overwriting non-manual source requires confirm dialog (§6).
4. **Registered** unchanged; **Completed (recent)** reflects new date after refetch without server restart.
5. Writes only via `PdfFileManager.set_completion_date`; audit via `operation_log` + `source_detail`.
6. PATCH returns slim JSON; grid updates via inventory refetch (not PATCH body merge alone).
7. Buddy Console SPEC / DATA_MODEL / CHANGELOG / TESTING updated; proposal 17 cross-linked.

---

## 11. Risks

| Risk | Mitigation |
|------|------------|
| Stale cache after PATCH | Full `enriched_cache = None`; test follow-up GET |
| Silent overwrite of inference | Confirm when `source != manual` |
| Slow refetch on large index | Acceptable for rare edits; index already cached until mutation |
| Legacy SFB operators expect UI there | README pointer to Buddy Console |

---

## 12. Review signals

| Signal | When |
|--------|------|
| **Draft → ready** | §8 pre-implementation sweep complete (**2026-05-28**) |
| **Ready → implemented** | Completed **2026-05-28** — Phase 4 sweep done; §10 met |
| **Operator sign-off** | `TESTING.md` smoke on live registry |

---

## 13. Future work (not in this release)

- **Clear date** UI → `clear_completion_date`
- **Audit history** UI over `get_operation_log`
- **Student File Browser** parity (shared route module)
- Per-card cache patch instead of full enrich rebuild (optimization only)
