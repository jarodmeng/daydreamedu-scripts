# Proposal: Buddy Console — `/student` route (Marks by question type)

**Status:** Implemented (`buddy_console` **v0.1.11**, 2026-06-03)  
**Target release:** `buddy_console` **v0.1.11** (tentative)  
**Tracked by:** [L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE](../../../docs/L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE.md) (product/architecture); no dedicated `TODO.md` item yet  
**Depends on:** [`build_marked_completion_fqi_stats`](../../../context/student_understandings/scripts/report_marked_completion_fqi_stats.py) (import via `importlib` — see §4); `study_buddy.db` + `context/` marking/FQI inputs; `buddy_console` backend on `:8010`, frontend on `:5178`  
**Related:** [L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE](../../../docs/L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE.md); [L4_BROWSER_APP_CONSOLIDATION](../../../docs/L4_BROWSER_APP_CONSOLIDATION.md); [L4_STUDENT_MVP_EXPERIENCE](../../../docs/L4_STUDENT_MVP_EXPERIENCE.md); [TODO.md P1-1](../../../TODO.md) (proposal standard — in progress)

**Scope vs GitHub issues:** Phase 1 delivery lives in this proposal. Portal vision, serve-time policy, and post-phase-1 roadmap: [L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE](../../../docs/L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE.md). Open a GitHub issue only for post-ship bugs or follow-ups.

---

## Document roles

| Doc | Owns |
|-----|------|
| **[L4](../../../docs/L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE.md)** | Why `/student` exists, four-route model, **serve-time policy**, product phases 2+, long-term open questions |
| **This proposal** | **Product phase 1 only:** API, UI, touchpoints, acceptance criteria, delivery phases 1–4 |

**Naming:** This proposal’s **Phase 1–4** are *delivery* steps (backend → frontend → docs → sweep). [L4 **product phase 2+**](../../../docs/L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE.md#product-roadmap-after-phase-1) is a separate roadmap (workflow, review CTAs).

---

## 1. Summary

**Product phase 1** (tracked by L4): ship **`/student`** showing per-subject **Marks by question type** — same table as `## Marks by question type` in operator reports (`marking_marks_by_type` semantics).

**Compute:** serve-time via `build_marked_completion_fqi_stats` per [L4 policy](../../../docs/L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE.md#serve-time-data-policy-normative--all-phases) — no reading `student_understandings/**/*.json` in the API path.

**Out of this proposal:** FQI totals, files-by-mix, mismatch tables, today snapshot, action queue, `/review` deep links, auth (see L4 product phase 2+).

---

## 2. Problem

| Symptom | Cause |
|---------|--------|
| Students/parents cannot see aggregated marks-by-type in the app | No `/student` route |
| No student home in `buddy_console` | Only `/inventory`, `/pdf`, `/review` |
| Risk of serving stale pre-export JSON | Portal must not use static `student_understandings/*.json` as runtime input |

---

## 3. Scope

### In scope (Phase 1 — this proposal)

| Layer | Change |
|-------|--------|
| **Backend** | `GET /api/student/marks-by-question-type?student_id=<id>&subject=<picker>` — serve-time `build_marked_completion_fqi_stats` for mapped subject context(s); returns one or more subject blocks for the selected picker |
| **Frontend** | `/student?student_id=<id>[&subject=<picker>]`; **four-choice subject picker** (English, Chinese, Math, Science); no table until a subject is selected; fetch on selection |
| **Tests** | `buddy_console/tests/test_student_marks_api.py` (fixtures); optional Vitest for table row rendering |
| **Docs** | `README.md`, `SPEC.md`, `CHANGELOG.md`, `TESTING.md`; L4 portal doc status link |

### Out of scope (Phase 1)

| Item | Notes |
|------|--------|
| Other `student_understandings` report sections | FQI totals, type-mix, mismatches, per-file |
| Reading `student_understandings/*.json` in API handler | Forbidden by L4 serve-time policy |
| `GET /api/student/portal/summary` / action queue | Phase 2+ (see L4) |
| Top nav link to `/student` | No — URL/deep link only (§7 #1) |
| Production auth | Localhost trust model unchanged |
| New canonical artifact schema | API view model only; compute reuses existing report builder |

### Not in this folder

Long-term student portal vision (workflow, tutor, gamification) stays in [L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE](../../../docs/L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE.md).

---

## 4. Data contract (normative)

### Serve-time compute

Normative rules: [L4 serve-time policy](../../../docs/L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE.md#serve-time-data-policy-normative--all-phases).

**Import (no duplicate logic):** `report_marked_completion_fqi_stats.py` is a script, not an installed subpackage. Load `build_marked_completion_fqi_stats` with the same `importlib.util.spec_from_file_location` pattern as [`learning_db/tests/test_report_marked_completion_fqi_stats.py`](../../../learning_db/tests/test_report_marked_completion_fqi_stats.py) (one small loader helper in `student_portal_service.py` is enough for Phase 1).

**Runtime paths:**

| Input | Resolution |
|-------|------------|
| `study_db` | `learning_db.core.connection.default_db_path()` (`STUDY_BUDDY_DB_PATH` when set) |
| `context_root` | `AI_STUDY_BUDDY_CONTEXT_ROOT` when set (same as inventory/review); else `default_context_root()` (`STUDY_BUDDY_CONTEXT_ROOT`) |

Pre-flight: if `study_db` is missing or not a file → **503** `Study database unavailable` (inventory-style). SQLite/open errors during compute → **503** with detail.

**Per-request `generated_at`:** set once after all picker contexts finish (ISO-8601 with offset). Do not expose per-call `report["generated_at"]` from the report builder as the API timestamp.

Handler sketch:

```python
contexts = PICKER_TO_CONTEXTS[subject]  # see table below; Chinese → two entries
subjects_out = []
for subject_context in contexts:
    report = build_marked_completion_fqi_stats(
        student_slug=student_id,
        subject_contexts=(subject_context,),  # one context per compute
        study_db=study_db,
        context_root=context_root,
    )
    marks = report["marking_marks_by_type"]
    if marks and int(marks.get("question_count") or 0) > 0:
        subjects_out.append(
            {
                "subject_context": subject_context,
                "display_label": SUBJECT_CONTEXT_LABELS[subject_context],
                "type_order": _marks_type_order(marks["by_type"]),  # MCQ, SAQ, LAQ, then alpha; UNKNOWN last
                "marks_by_question_type": marks,  # includes by_type — required for table rows
            }
        )
generated_at = <ISO-8601 at end of compute>
```

`_marks_type_order` must match markdown row order in the report script (`_ordered_question_types` on `marks["by_type"]` keys — see `report_marked_completion_fqi_stats.py` § `## Marks by question type`). **Do not** use top-level `report["question_types"]` for the marks table; that list reflects FQI totals, not marks rollup keys.

### Subject picker (UI + API)

Four fixed choices (labels for students). Picker value is the URL/API token:

| Picker label | `subject` param | `subject_contexts` passed to `build_marked_completion_fqi_stats` |
|--------------|-----------------|---------------------------------------------------------------------|
| English | `english` | `singapore_primary_english` |
| Chinese | `chinese` | Two UI blocks: **standard** = `singapore_primary_chinese` markings with `high-chinese` FQI **excluded**; **higher** = `singapore_primary_chinese` + `singapore_primary_higher_chinese` markings with `high-chinese` FQI **only** (HC work often lives under the standard path per marking layout) |
| Math | `math` | `singapore_primary_math` |
| Science | `science` | `singapore_primary_science` |

```python
# Chinese uses FQI schema split (see student_portal_service._CHINESE_COMPUTE_SPECS):
# - standard: marking_contexts=(singapore_primary_chinese,), exclude_fqi_schema_prefixes=("high-chinese",)
# - higher: marking_contexts=(singapore_primary_chinese, singapore_primary_higher_chinese),
#           include_fqi_schema_prefixes=("high-chinese",)

PICKER_TO_CONTEXTS = {
    "english": ("singapore_primary_english",),
    "chinese": ("singapore_primary_chinese", "singapore_primary_higher_chinese"),  # display blocks; see schema split above
    "math": ("singapore_primary_math",),
    "science": ("singapore_primary_science",),
}
SUBJECT_CONTEXT_LABELS = {
    "singapore_primary_english": "English",
    "singapore_primary_chinese": "Chinese",
    "singapore_primary_higher_chinese": "Higher Chinese",
    "singapore_primary_math": "Math",
    "singapore_primary_science": "Science",
}
```

**Landing behavior:** picker starts **unselected** (no `subject` in URL). UI shows no marks table and does **not** call the marks API. Prompt: select a subject.

**On select:** update URL (`?student_id=…&subject=math`), fetch API, render table. For `subject=chinese`, always render **standard Chinese first**, then higher Chinese (when present). If only higher Chinese has markings, show that single block.

**Deep link:** `?student_id=winston&subject=math` pre-selects Math and loads data on first paint.

**Block headings (UI):** use each block’s `display_label` — `English` / `Chinese` / `Higher Chinese` / `Math` / `Science` (mapped from `subject_context` in the service).

### API response

`GET /api/student/marks-by-question-type?student_id=<student_slug>&subject=<english|chinese|math|science>`

- **400** if `student_id` or `subject` missing/invalid (`subject` must be one of `english|chinese|math|science`).
- **503** when study DB or context root is unavailable (see pre-flight above).
- **200** with `subjects: []` and `message` when the student has no counted markings in scope for that picker (empty state). Frontend may also show a local empty-state string; `message` is normative for API clients.

**Response shape:** always `{ student_id, subject, generated_at, subjects, message? }`. English, Math, and Science typically return **one** block in `subjects`. Chinese returns **one or two** blocks (standard first, then higher when present).

```json
{
  "student_id": "winston",
  "subject": "math",
  "generated_at": "2026-06-02T22:09:47+08:00",
  "subjects": [
    {
      "subject_context": "singapore_primary_math",
      "display_label": "Math",
      "type_order": ["MCQ", "SAQ", "LAQ"],
      "marks_by_question_type": {
        "question_count": 412,
        "earned_marks": 318.5,
        "max_marks": 420.0,
        "percentage": 75.8,
        "by_type": {
          "MCQ": { "question_count": 40, "earned_marks": 32.0, "max_marks": 40.0, "percentage": 80.0 },
          "SAQ": { "question_count": 280, "earned_marks": 210.5, "max_marks": 280.0, "percentage": 75.2 },
          "LAQ": { "question_count": 92, "earned_marks": 76.0, "max_marks": 100.0, "percentage": 76.0 }
        }
      }
    }
  ]
}
```

Empty example:

```json
{
  "student_id": "winston",
  "subject": "science",
  "generated_at": "2026-06-03T10:00:00+08:00",
  "subjects": [],
  "message": "No counted markings in scope for this subject."
}
```

- `marks_by_question_type` is the full `report["marking_marks_by_type"]` object (rollup + `by_type` per-row stats). Omit blocks when `question_count` is 0.
- `type_order` lists keys to render before **Total**; append `UNKNOWN` after ordered types when present in `by_type` but not in `type_order` (same as markdown).
- For `subject=chinese`, backend computes each context separately; response includes only contexts that have counted markings in scope.
- `student_id` matches `student_slug` (same as inventory `students.id`).

### UI parity

Table columns match markdown report:

| Type | Questions | Earned | Max | % |

Rows: iterate `type_order` (then any `UNKNOWN` row not already listed), one row per type from `marks_by_question_type.by_type`, plus **Total** from top-level rollup (`question_count`, `earned_marks`, `max_marks`, `percentage`).

**Formatting:** match report markdown — percent cells use `—` when `percentage` is `null`; numeric columns show rollup values as returned (already rounded in compute).

Footnote: `Computed: <generated_at>` + short caption that totals use counted rows with amendments applied (same wording as report `## Marks by question type` intro).

**Loading:** serve-time compute can take several seconds on a full student; show a loading state while the fetch is in flight (no in-process cache in Phase 1).

---

## 5. Touchpoints

| File / area | Change |
|-------------|--------|
| `buddy_console/backend/app.py` | Register student portal router |
| `buddy_console/backend/student_portal_api.py` | New — route handler |
| `buddy_console/backend/student_portal_service.py` | New — call `build_marked_completion_fqi_stats`, map response |
| `context/student_understandings/scripts/report_marked_completion_fqi_stats.py` | Source of `build_marked_completion_fqi_stats` (import via loader — no duplicate logic) |
| `learning_db/tests/test_report_marked_completion_fqi_stats.py` | Reference import pattern + amendment-resolved marks tests |
| `learning_db/core/connection.py` | `default_db_path()`; context fallback when `AI_STUDY_BUDDY_CONTEXT_ROOT` unset |
| `buddy_console/backend/inventory_api.py` | Reference for `AI_STUDY_BUDDY_CONTEXT_ROOT` resolution and 503 style |
| `buddy_console/frontend/src/main.tsx` | Resolve `"student"` view |
| `buddy_console/frontend/src/StudentPortalApp.tsx` | New — portal UI |
| `buddy_console/frontend/src/studentPortalApi.ts` | New — fetch helper |
| `buddy_console/tests/test_student_marks_api.py` | New — API tests |

---

## 6. Acceptance criteria (release)

1. `GET /api/student/marks-by-question-type?student_id=winston&subject=math` returns math `marks_by_question_type` from serve-time compute.
2. `GET …&subject=chinese` returns standard Chinese and higher Chinese as separate subject blocks when present; higher Chinese is omitted when no higher-Chinese markings exist.
3. `/student?student_id=winston` shows picker with **no** table until a subject is chosen; `?subject=math` loads table on landing.
4. Handler does **not** open `student_understandings/**/*.json`.
5. Subject with no markings in scope → **200** with `subjects: []` and `message` (empty/warning for that picker only).
6. Frontend does not fetch paths under `context/`.
7. `pytest` green for new API tests; `npm run build` passes.
8. Docs updated; README `/student` no longer marked “planned only”.

---

## 7. Resolved decisions (Phase 1)

| # | Question | Decision |
|---|----------|----------|
| 1 | Expose `/student` in top nav? | **No.** “Top nav” means a persistent header/tab bar on every `buddy_console` view (e.g. links like Inventory \| PDF \| Review \| Student) so operators can switch routes without typing a URL. Phase 1 does **not** add that link; open `/student` via bookmark or deep link only. |
| 2 | Require `student_id` in URL? | **Yes.** `student_id` is required (same trust model as `/review?student_id=…`). No student picker on this screen in Phase 1. |
| 3 | Subject selection | **Four-choice picker:** English, Chinese, Math, Science. Default **none selected** → no API call, no marks table. Selecting a subject fetches and shows data. URL `subject=` may pre-select on load (`english` \| `chinese` \| `math` \| `science`). **Chinese** shows standard and higher Chinese stats on the same page as separate blocks; higher Chinese appears only when that student has higher-Chinese markings. See [§4 Subject picker](#subject-picker-ui--api). |
| 4 | In-process cache for compute? | **No** in Phase 1. |

Phase 2+ (not this proposal): next-action ranking; live workflow stats — see L4.

---

## 8. Pre-implementation final sweep (2026-06-03)

Proposal-level readiness **before** Phase 1 coding (per [TODO.md P1-1](../../../TODO.md)).

| Check | Result |
|-------|--------|
| **Completeness** | §1–7, acceptance criteria, phased plan, touchpoints, API contract; §4 now includes `by_type`, `type_order`, `display_label`, `message`, env paths, import pattern |
| **Accuracy** | `marking_marks_by_type` includes `by_type` per row; table columns match report markdown; example JSON trimmed to math slice shape |
| **Consistency** | Aligns with L4 serve-time policy; no static `student_understandings` JSON in API path; context root aligned with inventory when `AI_STUDY_BUDDY_CONTEXT_ROOT` set |
| **§7 decisions** | All four resolved (see §7) |
| **Test plan** | Phase 1: mock `build_marked_completion_fqi_stats` in `test_student_marks_api.py`; optional parity with `learning_db/tests/test_report_marked_completion_fqi_stats.py`; Phase 2 manual `winston` math deep link |
| **Doc plan** | Phase 3 lists README/SPEC/CHANGELOG/TESTING + L4 snapshot |
| **Out of scope explicit** | Full portal, review links, reading export JSON, top nav |
| **Link hygiene** | Relative links to L4 / `TODO.md` / report script corrected (`../../../…` from `docs/proposal/`) |
| **Known footguns** | (1) Script import needs `importlib`, not `from ai_study_buddy.context…`. (2) `STUDY_BUDDY_CONTEXT_ROOT` vs `AI_STUDY_BUDDY_CONTEXT_ROOT` — §4 documents resolution. (3) Existing `/api/student/attempts/*` review routes are unrelated — new path is `/api/student/marks-by-question-type`. |

**Post-implementation** final sweep: **Phase 4 complete** (2026-06-03; Chinese FQI split verified in UI same day).

---

## 9. Implementation record

Phases use **numbered indices** per [TODO.md P1-1](../../../TODO.md). This section records what shipped.

### Phase 1 — Backend serve-time API

**Goal:** Serve `marks_by_question_type` per subject via `build_marked_completion_fqi_stats`.

#### Todo checklist

- [x] Added `student_portal_service.py`: `importlib` loader, `_marks_type_order`, `SUBJECT_CONTEXT_LABELS`, `_CHINESE_COMPUTE_SPECS` (FQI `high-chinese` split).
- [x] Resolve `study_db` / `context_root` per §4; 503 when DB missing.
- [x] Map picker `subject` → compute specs per §4.
- [x] Require both `student_id` and `subject`; Chinese returns standard + higher blocks when data exists.
- [x] No `student_understandings/**/*.json` reads in service or API layer.
- [x] Added `student_portal_api.py` + `app.include_router(student_portal_router)`.
- [x] 400 / 503 behavior per §4.

#### Test checklist

- [x] Unit tests mock `build_marked_completion_fqi_stats` → API shape matches §4.
- [x] Chinese schema-filter call recording test (`test_chinese_compute_passes_schema_filters`).
- [x] Export JSON ignored (`test_service_ignores_student_understandings_export_json`).
- [x] `pytest ai_study_buddy/buddy_console/tests/test_student_marks_api.py` green.

#### Success / handoff criteria

- [x] Live `curl` / Python smoke for winston math and chinese.
- [x] Reuses report builder; no new canonical schema.

---

### Phase 2 — Frontend `/student` route

**Goal:** Student-visible marks table.

#### Todo checklist

- [x] `main.tsx`: `/student` → `"student"` view.
- [x] `StudentPortalApp.tsx`, `studentPortalApi.ts`, `studentPortalMarks.test.ts`.
- [x] Missing `student_id` empty state.
- [x] Subject picker + URL sync; fetch only when selected.
- [x] Tables via `type_order` + `by_type` + Total + footnote; loading/error/empty.
- [x] Chinese standard/higher blocks; higher omitted when empty.
- [x] Styles in `styles.css` (`student-portal-*`).

#### Test checklist

- [x] Vitest: `formatPercent`, `tableRowTypes`.
- [x] Manual smoke: picker, deep link, Chinese blocks (operator-verified 2026-06-03).
- [x] `npm run build` green.

#### Success / handoff criteria

- [x] §6 acceptance criteria satisfied.
- [x] `/inventory`, `/pdf`, `/review` unchanged (spot-check).

---

### Phase 3 — Documentation and cross-references

**Goal:** Discoverable contract for operators and agents.

#### Todo checklist

- [x] `SPEC.md`: `/student` route + `GET /api/student/marks-by-question-type` (incl. Chinese FQI split).
- [x] `README.md` v0.1.11, deep links.
- [x] `CHANGELOG.md` v0.1.11.
- [x] `TESTING.md` smoke + Chinese parity vs report CLI.
- [x] [L4](../../../docs/L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE.md) snapshot → shipped.
- [x] Report script docstring points at `/student` consumer.

#### Test checklist

- [x] Operator smoke from `TESTING.md`.

#### Success / handoff criteria

- [x] Docs match shipped JSON and behavior.

---

### Phase 4 — Post-implementation final sweep and TODO closure

**Goal:** Confirm release quality; close proposal.

#### Todo checklist

- [x] `pytest ai_study_buddy/buddy_console/tests/` green (15 tests).
- [x] `npm run build` + `npm test -- --run` green.
- [x] SPEC vs `student_portal_api.py` / `student_portal_service.py` aligned.
- [x] Proposal **Status** → **Implemented** (2026-06-03).
- [x] No dedicated `TODO.md` bullet for this slice (tracked via L4 + this proposal).

#### Test checklist

- [x] Serve-time reload: `/student` reflects DB after marking/amendment (policy per L4; operator-verified with Chinese fix).

#### Success / handoff criteria

- [x] Phase 1 product scope complete in **v0.1.11**.
- [x] L4 product phase 2+ (workflow, review CTAs) remains out of scope — see §10.

---

## 10. Later work (not this proposal)

[L4 product roadmap](../../../docs/L4_STUDENT_PORTAL_IN_BUDDY_CONSOLE.md#product-roadmap-after-phase-1) — new package proposal per slice when scoped.
