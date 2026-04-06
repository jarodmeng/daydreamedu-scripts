# Proposal: Globally disable user-reported Pinyin Recall units

**Status:** Implemented  
**Date:** 2026-04-06  
**Context:** Pinyin Recall now operates on reading-level units (`character + reading`), and the 报错 flow already logs those units in `pinyin_recall_report_error`. However, a unit reported as bad by a real user still remains globally schedulable, so the same incorrect content can continue entering future queues for everyone until an operator intervenes manually.

**References:**

- `backend/app.py` — `POST /api/games/pinyin-recall/report-error`, session queue endpoints
- `backend/pinyin_recall.py` — `build_reading_units_for_character`, `build_session_queue`
- `backend/database.py` — enabled-unit totals, pinyin-recall learning state, report-error persistence
- `docs/ARCHITECTURE.md` — reading-unit runtime and profile denominator behavior
- `docs/AUTHENTICATION.md` — real auth vs dev/E2E fallback identities

---

## 1. Problem

1. Real users can identify a bad reading unit via 报错, but today that only creates a log row.
2. Because there is no global disable registry, the same unit can continue entering newly built queues for all users.
3. The app now has runtime reading-unit identity, so we should contain bad content at the same `unit_id` granularity rather than by character.
4. Synthetic/dev users (`local-dev`, `e2e-dev`, `e2e-gha-*`) should not be able to globally disable units during testing.

---

## 2. Goals

1. A single report from a real authenticated user should remove that `unit_id` from future Pinyin Recall circulation globally.
2. “Removed from circulation” means:
   - the unit does not enter newly built queues
   - the unit is excluded from enabled-unit totals used by Profile/progress
3. Keep `pinyin_recall_report_error` append-only for historical/audit use.
4. Reuse the existing `recall_enabled` / `enable_reason` path instead of inventing separate queue-only logic.
5. Keep the behavior deterministic and immediately correct without relying on in-process cache invalidation.

**Non-goals**

- Retroactively editing already-issued in-flight batches or current feedback screens
- Adding an admin UI for re-enabling a disabled unit in this change
- Treating synthetic/dev fallback users as real disabling authorities

---

## 3. Design

### 3.1 Global disabled-unit registry

Add a dedicated table `pinyin_recall_disabled_units` with one row per globally disabled reading unit.

Required fields:

- `unit_id` primary key
- `character`
- `disabled_reason`
- `disabled_source`
- `triggering_report_error_id`
- `disabled_by_user_id`
- `disabled_at`
- optional `notes`

Initial write defaults:

- `disabled_reason = 'reported_by_user'`
- `disabled_source = 'report_error'`
- runtime override `enable_reason = 'disabled_reported_by_user'`

The table is current-state data. `pinyin_recall_report_error` remains append-only event history.

### 3.2 Report-error route behavior

`POST /api/games/pinyin-recall/report-error` should:

1. always insert a row into `pinyin_recall_report_error`
2. globally disable the reported unit only when:
   - the request resolved through real JWT auth
   - `unit_id` is present and non-empty

If the request resolved through `PINYIN_RECALL_DEV_USER`, the row is logged but no global disable happens.

### 3.3 Queue and profile integration

Disabled units are exposed to runtime as recall overrides:

- `unit_id -> { recall_enabled: False, enable_reason: 'disabled_reported_by_user' }`

Those overrides must be applied in:

- `build_session_queue(...)`
- enabled-unit derivation used by Profile/progress
- learning-state reads used for active-load calculations

This ensures a disabled unit:

- does not enter future queues
- does not continue affecting active-load mode selection
- does not inflate enabled-unit totals

### 3.4 Cache decision

Remove the current in-process enabled-unit cache.

Reason:

- enabled-unit state now changes at runtime when a report disables a unit
- the cache mainly served Profile/progress totals, not per-user queue construction
- removing the cache is simpler and safer than building cross-instance invalidation

The distractor index cache and HanziWriter file cache are unrelated and remain unchanged.

---

## 4. Implementation Notes

1. Extend the report-error DB insert helper to return the inserted report row id.
2. Add an idempotent helper to insert into `pinyin_recall_disabled_units`.
3. Add a helper to load global disabled-unit overrides for runtime consumption.
4. Thread those overrides into queue construction and enabled-unit derivation.
5. Update the report-error query utility to show `unit_id` by default for reading-aware triage.

---

## 5. Testing and Rollout

Required coverage:

- real authenticated report disables the unit globally
- synthetic/dev fallback report logs only
- report without `unit_id` logs only
- repeated reports on the same unit are idempotent
- disabled units are excluded from future queue construction
- enabled-unit totals exclude disabled units without relying on cache invalidation

Rollout expectation:

- run the new table creation script in each environment
- ensure the updated report-error table create script includes `unit_id`
- verify the next real-user report removes the unit from newly built queues
