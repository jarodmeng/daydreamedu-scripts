# Proposal: Buddy Console — Review Workspace supervised redo evidence tab

**Status:** Implemented (**buddy_console** v0.1.16, 2026-06-07)  
**Target release:** `buddy_console` **v0.1.16**  
**Tracked by:** No dedicated `TODO.md` item yet  
**Depends on:** `buddy_console` review surface v0.1.15+ (Attempt / Answer / Template tabs); `marking` `detail_service.py` + PDF raster helpers (PyMuPDF / `marking.assets`); `PdfFileManager.get_template`; `ai_study_buddy.files` v0.3.11+ (`Review` subtree exclusion on inventory — unchanged); `resolve_goodnotes_root()`  
**Related:** [L4_STUDENT_MVP_EXPERIENCE](../../../docs/L4_STUDENT_MVP_EXPERIENCE.md); [L4_COMPLETION_MARKING_FRAMEWORK](../../../docs/L4_COMPLETION_MARKING_FRAMEWORK.md); [L4_FILE_FRAMEWORK](../../../docs/L4_FILE_FRAMEWORK.md); [goodnotes-leaf-registry-report](../../../../.cursor/commands/goodnotes-leaf-registry-report.md); [pdf_file_manager proposal 05 — GoodNotes registration](../../../pdf_file_manager/docs/proposals/05-goodnotes-exam-registration.md); [marking proposal 16 — v3 workflow](../../../marking/docs/proposal/16-mark-student-work-multi-agent-v3-workflow.md) (`redo-practice` — **out of scope** here); [buddy_console ARCHITECTURE.md](../../ARCHITECTURE.md); [review_workspace ARCHITECTURE.md](../../../review_workspace/ARCHITECTURE.md); [TODO.md P1-1](../../../TODO.md) (proposal standard)

**Scope vs GitHub issues:** Design and phased delivery live in this proposal. Open a GitHub issue only for post-ship bugs or follow-ups (e.g. `review_workspace` standalone app parity).

---

## Document roles

| Doc | Owns |
|-----|------|
| **[L4 student MVP experience](../../../docs/L4_STUDENT_MVP_EXPERIENCE.md)** | Four-panel Review Workspace layout, evidence viewer modes, `question_page_map` page jump |
| **`files` v0.3.11** | GoodNotes `Review` segment **excluded** from operator inventory / leaf-registry reports |
| **This proposal** | **Supervised redo evidence:** fourth **Review** tab, attempt→template→Review resolution, lazy render into **`context/review_redo/`**, API payload — **no marking** |

---

## 1. Summary

During Review Workspace sessions, a supervisor may have the student **redo incorrect questions on a fresh GoodNotes import of the linked template**. GoodNotes Auto Backup writes those PDFs under a sibling **`Review/`** leaf folder (same L1–L3 path as the original attempt, with `Review` as the leaf directory). The PDF is **full-length** (same page count as template and original attempt); only the incorrect question page(s) contain new supervised handwriting.

This proposal adds a fourth evidence mode — **Review** — beside existing **Attempt**, **Answer**, and **Template** tabs on the `/review` surface. Delivery is **two steps**:

| Step | When | Work | Cost |
|------|------|------|------|
| **i** | Review Workspace **loads** for a marked attempt | Resolve whether a Review redo PDF exists; if yes, show the **Review** tab | Cheap (`get_template` + one `stat`) |
| **ii** | Operator **clicks Review** tab (first time) | Rasterize Review PDF into **`context/review_redo/`** if needed; return image URLs | Paid once per PDF (~0.5–5 s cold; then cached on disk) |

The tab reuses the marking artifact’s **`question_page_map`** for active-question page jump (same page indices as Attempt). **No marking** of Review PDFs — validation is live during review.

**Non-goals:** automated marking of Review PDFs, `redo-practice` v3 mode, `completion_series` / Attempt #2 picker entries, inventory cards for Review exports, scanning all `Review/` folders, or per-question page mapping tables in `student_review_state`.

---

## 2. Problem

| Symptom | Cause |
|---------|--------|
| Supervised redo work exists on disk under `GoodNotes/…/Review/` but is invisible in Review Workspace | Only Attempt / Answer / Template image pools are loaded today |
| Review exports are excluded from Student File Browser / inventory by design | `is_goodnotes_excluded_relative_path` treats `Review` as post-review backup subtree |
| Prior design assumed Review PDFs were question subsets | Incorrect — workflow re-imports the **whole template**; page alignment with attempt/template is preserved |

### Empirical validation (2026-06, local `g_root`)

| Metric | Result |
|--------|--------|
| Review-folder PDFs on disk | **17** (Winston, Singapore Primary Math) |
| Marked student completions in registry | **362** |
| **Attempt → template → Review** resolver finds Review PDF | **17/17** (100%) |
| False positives (extra Review paths from resolver) | **0** |
| Marked attempts with template but **no** Review PDF | **345** (~95% — cheap `stat` miss on load) |
| Review PDFs registered in `pdf_registry` | **0** (expected; inventory exclusion) |

Resolver approach: start from each **marked attempt**, `get_template(attempt_id)`, derive Review basename from **template** name (`_c_<name>.pdf` → `c_<name>.pdf`), build Review directory from **attempt path** mirrored under `GoodNotes/…/<L3>/Review/`. Do **not** scan Review folders globally.

---

## 3. Supervised redo workflow (normative)

Operator / student flow this proposal supports:

1. Open a **marked** attempt in Review Workspace (`/review?attempt_id=…&student_id=…`).
2. Walk incorrect questions (existing question nav, amendments, review notes).
3. For redo: locate the **linked template** for that attempt (`completed_from` → `_c_<unit>.pdf`).
4. Import the **template** into GoodNotes under the **mirrored folder path**, with a **`Review`** leaf folder (same L1–L3 tree as the attempt, e.g. `…/P6/Exam/Review/` instead of placing the file directly under `…/P6/Exam/`).
5. Jump to the incorrect question’s page (same page number as in the original attempt / template).
6. Student redoes the question **under supervision** — no automated grading required.
7. GoodNotes Auto Backup exports e.g. `GoodNotes/<subject>/<student>/P6/Exam/Review/c_<template_stem>.pdf`.

**Page invariant:** Review PDF page *N* corresponds to attempt page *N* and template page *N*. Therefore `context.question_page_map[].attempt_page_start` from the canonical marking result applies to the Review tab without a separate map.

---

## 4. Scope

### In scope

| Layer | Change |
|-------|--------|
| **Path helper** | `resolve_supervised_review_pdf_for_attempt(attempt, *, manager, goodnotes_root) -> SupervisedReviewRedoResolution` (`available`, `resolved_path`); attempt → template → `stat` under `g_root/…/Review/` |
| **`marking.review.detail_service`** | Step **i** on `get_attempt_detail` (**marked attempts only** — same gate as today): populate `viewer.review_redo`; **no render** on load |
| **`marking.review` API** | Step **ii**: new lazy endpoint to render (if needed) and return `review_images` |
| **`buddy_console` frontend** | **Review** tab when `review_redo.available`; fetch images on first tab click; extend `ViewerMode`; reuse page jump + zoom |
| **`review_workspace`** | Same contract (optional parity if standalone app still shipped) |
| **Tests** | Path resolution unit tests (17/17 fixture shapes); lazy render API tests |
| **Docs** | `buddy_console` README / SPEC / DATA_MODEL / CHANGELOG / TESTING; **`files`** + **`marking`** README / CHANGELOG version bumps |

### Out of scope

| Item | Notes |
|------|--------|
| **`redo-practice` marking / second `marking_result`** | Supervised validation is live; no grader |
| **`completion_series` / Attempt #2 in attempt picker** | Review PDF is evidence for the **same** attempt session |
| **Inventory / leaf-registry inclusion of `Review/` leaves** | Exclusion policy in `files` v0.3.11 remains |
| **Scanning all Review folders** | Resolution is **attempt-scoped** only |
| **Render on attempt detail load** | Deferred to Review tab click (step ii) |
| **New `file_relations` type** | Not needed for v1 (path-only resolution) |
| **Auto-detect new Review exports (watch / poll)** | Post-v1 |
| **`student_review_state` schema for redo pages** | Not needed while page map is shared |
| **Split-view (Attempt + Review side by side)** | Future UX |

---

## 5. Review PDF resolution (normative)

Resolution runs **from the attempt file** (Review Workspace `attempt_id`). Never enumerate `Review/` subtrees.

### Inputs

- **`attempt`:** registered completion main (`PdfFile`) with a marking result.
- **`manager`:** `PdfFileManager` (for `get_template`).
- **`goodnotes_root`:** from `resolve_goodnotes_root()`.

### Output

Frozen dataclass **`SupervisedReviewRedoResolution`** (name tentative):

- **`available: bool`** — whether a Review redo PDF exists on disk.
- **`resolved_path: Path | None`** — absolute path when `available` (API may expose relative to `goodnotes_root`).

### Algorithm (v1)

1. **`template = manager.get_template(attempt.id)`** — if `None`, return unavailable (no template link).
2. **Review directory** — from **`attempt.path`** (not template’s general-scope path):
   - Strip to mirror segments after `GoodNotes` or `DaydreamEdu/completion` (drop `DaydreamEdu/completion` prefix when present).
   - Take directory of attempt file (all segments except basename).
   - **`review_dir = goodnotes_root / <those segments> / "Review"`**
   - Works for **`d_root`** completions (`DaydreamEdu/completion/…`) and **`g_root`** attempts (`GoodNotes/…`).
3. **Review basename** — from **`template.name`** (not attempt basename):
   - Template `_c_<stem>.pdf` → look for **`c_<stem>.pdf`** in `review_dir` (primary GoodNotes convention).
   - Optional fallback: `_c_<stem>.pdf` in `review_dir`.
4. **`stat`** first existing candidate → `available=True`, else unavailable.

### Examples (validated)

| Attempt (registered) | Template | Review PDF (on disk) |
|---------------------|----------|----------------------|
| `DaydreamEdu/completion/…/P6/Exam/_c_P6 Math WA1.pdf` | `_c_P6 Math WA1.pdf` | `GoodNotes/…/P6/Exam/Review/c_P6 Math WA1.pdf` |
| `GoodNotes/…/P6/Exam/c_p6.math.wa1.4.pdf` | `_c_p6.math.wa1.4.pdf` | `GoodNotes/…/P6/Exam/Review/c_p6.math.wa1.4.pdf` |
| `DaydreamEdu/completion/…/P6/Book/<book>/_c_Math Model …_028_…2.7.pdf` | same stem | `GoodNotes/…/P6/Book/<book>/Review/c_Math Model …_028_…2.7.pdf` |

### Failure modes

| Condition | Behavior |
|-----------|----------|
| No template link | `review_redo.available = false`; no Review tab |
| Review PDF missing | `review_redo.available = false`; no Review tab |
| `goodnotes_root` unset | Unavailable; log at debug |
| Review PDF exists but unregistered | **`stat` succeeds** — still show tab; step ii rasterizes into **`context/review_redo/`** (§6; no `register_file`) |

---

## 6. Render cache, lazy raster, and page navigation

### Question structure (reuse template)

- **Authoritative `question_sections.json`:** from the **linked template** FQI run under `context/file_question_info/` (already used by v3 marking). Review redo does **not** need its own detector pass or `file_question_info` run folder.

### Render cache layout (`context/review_redo/`)

Review redo PNGs live in a **dedicated, persistent** tree under `context/` — **not** under `file_question_info/` and **not** a temp directory. Operator may pre-create subject folders (e.g. `context/review_redo/winston/singapore_primary_math/`); implementation creates per-unit leaf folders on first render.

**Normative path:**

```text
<context_root>/review_redo/<student_slug>/<subject_context>/<normal_name>/rendered_pages/page_%03d.png
```

| Segment | Source | Consistent with |
|---------|--------|-----------------|
| `<context_root>` | `STUDY_BUDDY_CONTEXT_ROOT` / `AI_STUDY_BUDDY_CONTEXT_ROOT` when set; else `ai_study_buddy/context/` | `marking_assets/`, `file_question_info/` |
| `<student_slug>` | **`slugify_student(attempt.student_id, student_name)`** from `marking.core.artifact_paths` (e.g. `winston`) | `marking_assets/<student_slug>/…`, `marking_results/<student_slug>/…` |
| `<subject_context>` | Marking `context.subject_context` when present; else infer from attempt subject (e.g. `singapore_primary_math`) | `marking_assets/…/<subject_context>/…` |
| `<normal_name>` | **`normalize_pdf_display_name(template.name)`** from `pdf_file_manager` — same rules as `PdfFile.normal_name` / FQI slug (strip `_c_` / `c_` / `_raw_` only; **keep spaces and punctuation**) | `file_question_info/…/<grade>/<slug>/` slug; `marking_assets/…/<stem>__<timestamp>/` stem (without timestamp suffix) |

**Filename / folder-name policy (normative — match existing context trees):**

- **No extra filesystem sanitization** beyond the helpers above. Unit folders may contain spaces, parentheses, and other characters from the template basename (see on-disk examples under `marking_assets/winston/singapore_primary_math/` and `file_question_info/singapore_primary_math/P6/`).
- **Do not** slugify or strip punctuation from `<normal_name>` — that would diverge from FQI and marking asset stems and break mental mapping between Review redo, template, and attempt.
- **Do not** append a run timestamp to `<normal_name>` — one Review redo cache folder per template unit (unlike `marking_assets/…/<stem>__YYYYMMDD_HHMMSS/` which disambiguates multiple marking runs).
- **Page PNG basenames:** `page_%03d.png` under `rendered_pages/` (same convention as FQI template renders and the **Template** tab — not `page-02.png` from `marking_assets/attempt/` used by the **Attempt** tab).

**Example** (Winston, P6 Math WA1):

```text
ai_study_buddy/context/review_redo/winston/singapore_primary_math/P6 Math WA1/rendered_pages/page_001.png
```

**Static URL** (existing `/review-workspace-static/` mount of `context/`):

```text
/review-workspace-static/review_redo/winston/singapore_primary_math/P6 Math WA1/rendered_pages/page_001.png
```

One leaf folder per **template unit** (one Review redo PDF). Re-render the same folder when the source Review PDF mtime is newer than cached PNGs.

### Raster evidence (Review-specific, deferred)

- Triggered only by step **ii** (Review tab click or lazy API call).
- **Path-only input:** rasterize from the resolved GoodNotes Review PDF path; **no** `register_file`.
- Reuse existing PDF→PNG utilities (`marking.assets.render` / PyMuPDF — same quality convention as FQI `page_%03d.png` naming).
- **Cache-first:** if `rendered_pages/` exists and is **not stale** vs Review PDF mtime, skip raster and list PNGs only.
- **Page indices** align with template/attempt (full PDF raster).

### Performance (local snapshot, 17 Review PDFs)

| Metric | Value |
|--------|-------|
| Page count range | 3–38 (avg ~10) |
| File size range | 0.6–4.1 MB |
| Cold full render (38 pages @ 2×) | ~5 s (PyMuPDF; unregistered PDF) |
| Step **i** on load (no Review PDF) | ~1 `stat` after template lookup |
| Step **i** when 345/362 attempts have no Review | No render; negligible overhead |

### Page jump in UI

- Reuse **`context.question_page_map`** (`attempt_page_start` per `result_id`).
- When **Review** tab is active and user selects question *Q*, jump to `attempt_page_start` in `review_images` (same as Attempt tab).

---

## 7. API contract

### Step i — Attempt detail (`GET /api/student/attempts/{attempt_id}`)

Extend `viewer` (see [DATA_MODEL.md](../../DATA_MODEL.md)). **Do not render** Review pages on this call.

```json
{
  "viewer": {
    "mode_default": "attempt",
    "attempt_images": [],
    "answer_images": [],
    "template_images": [],
    "review_redo": {
      "available": true,
      "resolved_path": "Singapore Primary Math/winston.ry.meng@gmail.com/P6/Exam/Review/c_P6 Math WA1.pdf"
    },
    "review_images": [],
    "answer_page_start": null,
    "answer_page_end": null,
    "marking_asset": "marking_assets/..."
  }
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `review_redo.available` | yes | Drives **Review** tab visibility |
| `review_redo.resolved_path` | when available | Path **relative to `goodnotes_root`** (POSIX segments); API/debug only — **not** shown in production UI (§13 #13) |
| `review_images` | yes | **Always empty on detail load** in v1; populated client-side after step ii |

**Backward compatibility:** clients ignore unknown keys; old clients see empty `review_images` and no tab unless they read `review_redo`.

### Step ii — Lazy review evidence (`GET /api/student/attempts/{attempt_id}/review-evidence`)

New read endpoint (name tentative; document in `SPEC.md`):

1. Re-run the same resolver as step **i** (do not trust a client-supplied path).
2. If unavailable → **404** (see [Lazy endpoint 404](#lazy-endpoint-404-step-ii) below).
3. If available: **path-only** cache-first render (no `register_file`) → return:

```json
{
  "review_images": [
    {
      "name": "page_003.png",
      "page_num": 3,
      "url": "/review-workspace-static/review_redo/winston/singapore_primary_math/P6 Math WA1/rendered_pages/page_003.png"
    }
  ],
  "rendered_at": "2026-06-07T12:00:00+08:00"
}
```

Same image object shape as `template_images` / `attempt_images`. Idempotent: safe to call on every first tab visit; subsequent calls list cached PNGs unless PDF mtime is newer.

### No new write endpoints

Supervised redo does not persist grading outcomes.

---

## 8. Frontend (`/review`)

### Viewer mode

```typescript
type ViewerMode = "attempt" | "answer" | "template" | "review";
```

### Toolbar — step i

- Add **Review** button after **Template**.
- Show when **`viewer.review_redo?.available === true`** — **not** when `review_images.length > 0`.

### Tab click — step ii

- On first switch to `viewerMode === "review"`:
  - If client cache empty → `GET …/review-evidence` (loading spinner / “Rendering pages…”).
  - Store returned `review_images` in component state; reuse on later tab switches.
  - On **404** (stale `available` flag): show error + hide or disable Review tab; do not retry in a loop.
- `viewerImagePool(viewer, mode)` uses cached `review_images` when mode is `review`.

### Unchanged behavior

- Question nav, amendments, review notes, deep links — no change.
- Default mode remains **Attempt** on open.
- Template tab unchanged (pre-loaded `template_images` from detail).

---

## 9. Registry and inventory policy (unchanged)

| Surface | Review-folder PDFs |
|---------|-------------------|
| Student File Browser / Buddy Console **inventory** | **Excluded** (`Review` segment) |
| Review Workspace **Review tab** | **Included** via attempt→template→Review resolver |
| GoodNotes leaf-registry report | **Excluded** leaves |

Do **not** remove `Review` from `is_goodnotes_excluded_relative_path`. Workspace resolves Review PDFs deliberately outside the inventory index. v1 does **not** register Review PDFs (`register_file` deferred indefinitely unless a future need arises).

---

## 10. Package touchpoints

| Package | Files / symbols |
|---------|-----------------|
| **`ai_study_buddy.files`** (preferred) | `resolve_supervised_review_pdf_for_attempt(...)` + tests (`files/tests/`) |
| **`marking.review`** (new helpers) | `review_redo_render_dir(...)`, `render_review_redo_pages(...)`, `list_review_redo_images(...)` — paths under `context/review_redo/` |
| **`marking.review.detail_service`** | Step i: `_review_redo_availability_for_attempt` in `get_attempt_detail`; step ii: list/serve from `review_redo/…/rendered_pages/` |
| **`marking.review.api_routes`** | Step ii: `GET …/review-evidence` handler |
| **`buddy_console/frontend/src/App.tsx`** | Tab gating, lazy fetch, `ViewerMode`, `viewerImagePool` |
| **`review_workspace/frontend`** | Parity if maintained |
| **Docs** | `buddy_console/SPEC.md`, `DATA_MODEL.md`, L4 student MVP evidence modes |

---

## 11. Phased delivery

### Phase 1 — Step i: resolve + tab flag (no render)

**Goal:** Attempt detail exposes `review_redo.available`; no PyMuPDF on load.

#### Todo checklist

- [x] Implement `resolve_supervised_review_pdf_for_attempt` with unit tests (d_root + g_root attempts; book nested paths; no template; missing Review PDF).
- [x] Wire into `get_attempt_detail`: populate `review_redo`; keep `review_images: []`.
- [x] Regression: 17/17 Winston Review PDFs resolve from their marked `attempt_id`s.

#### Test checklist

- [x] Fixture: template linked + Review PDF on disk → `available=true`.
- [x] Fixture: no Review PDF → `available=false`.
- [x] Fixture: no template link → `available=false`.

---

### Phase 2 — Step ii: lazy render endpoint

**Goal:** First Review tab click returns rendered pages; cache reused.

#### Todo checklist

- [x] `GET /api/student/attempts/{attempt_id}/review-evidence` with cache-first raster into `context/review_redo/<student>/<subject>/<normal_name>/rendered_pages/`.
- [x] Path-only raster helper (no `register_file`; document layout in SPEC).
- [x] Mtime stale check: re-render when Review PDF newer than newest PNG.

#### Test checklist

- [x] Cold render → non-empty `review_images`; page count matches PDF.
- [ ] Second call → no re-render when cache fresh (mock or timing assertion).

---

### Phase 3 — Frontend Review tab + lazy load

**Goal:** Operators see Review tab when redo exists; images load on click.

#### Todo checklist

- [x] Tab visible when `review_redo.available`.
- [x] Lazy fetch on first `review` mode; client cache; loading + **404** error state.
- [x] Page jump via `question_page_map` on Review tab.
- [x] `npm run build` passes.

#### Test checklist

- [x] Manual smoke: Winston cohort (≥1 exam, 1 exercise, 1 book unit).
- [x] Attempt without Review redo: three tabs only; no lazy request on load.

---

### Phase 4 — Documentation

#### Todo checklist

- [x] `buddy_console` README, SPEC, DATA_MODEL, CHANGELOG, TESTING.
- [x] **`files`** README, CHANGELOG, `__version__` bump (v0.3.13); **`marking`** README, CHANGELOG version bump (v0.3.20).
- [x] L4 student MVP: **Review** evidence mode + two-step load/render.
- [x] `files/SPEC.md`: cross-link — inventory `Review` exclusion vs workspace resolver.
- [x] Document `context/review_redo/` layout (this proposal §6) in `DATA_MODEL.md` / `SPEC.md`.
- [x] Mark proposal **Implemented** with version.

---

### Phase 5 — Optional follow-ups (post-v1)

- [ ] “Refresh evidence” control when GoodNotes exports a newer Review PDF mid-session.
- [ ] `review_workspace` standalone parity.
- [ ] Split-view mode (Attempt | Review).

---

## 12. Acceptance criteria

1. Opening a marked attempt whose Review redo exists shows a **Review** tab **without** waiting for page render.
2. First click on **Review** loads page images (≤ ~5 s for largest known PDF on cold cache).
3. Second and later tab switches to **Review** use cached images (no full re-render).
4. Selecting a question on **Review** jumps to the same page number as **Attempt** (`question_page_map`).
5. Attempts with no Review redo behave as today (three tabs only; **no** `review-evidence` request on detail load).
6. No new marking artifacts are created.
7. Review-folder PDFs remain absent from inventory index.
8. Attempt→template→Review resolver finds all on-disk Review PDFs in the validated cohort (**17/17**).
9. Rendered PNGs persist under `context/review_redo/<student_slug>/<subject_context>/<normal_name>/rendered_pages/`.
10. `pytest` + `npm run build` green.

---

## 13. Resolved decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | Fourth tab vs per-question panel | **Fourth tab** — full-page alignment; same viewer model as Attempt/Answer/Template |
| 2 | Mark Review PDFs? | **No** — supervised redo |
| 3 | Separate attempt in picker? | **No** — same `attempt_id` |
| 4 | Include Review leaves in inventory? | **No** — keep `files` v0.3.11 exclusion |
| 5 | Page map source | **Reuse** marking `question_page_map` |
| 6 | Question structure source | **Template** `question_sections` under `file_question_info/`; Review redo uses separate PNG cache only |
| 7 | Resolution direction | **Attempt → template → Review path**; do not scan Review folders |
| 8 | Review basename source | **Template** name (`_c_*` → `c_*` in Review folder) |
| 9 | Review directory source | **Attempt path** mirrored under `GoodNotes/…/<L3>/Review/` |
| 10 | When to render? | **Deferred** until Review tab click (step ii) |
| 11 | When to show tab? | **`review_redo.available`** on detail load (step i) |
| 12 | Render unregistered Review PDFs? | **Path-only raster** — no lazy `register_file` |
| 13 | Show `review_redo.resolved_path` in UI? | **Debug only** (tooltip / dev; not prominent chrome) |
| 14 | Background prefetch after detail load? | **No** — render only on Review tab click |
| 15 | Lazy endpoint when unavailable? | **404** — see below |
| 16 | Rendered page storage | **`context/review_redo/<student_slug>/<subject_context>/<normal_name>/rendered_pages/`** — not `file_question_info/`, not temp; segment helpers per §6 |

#### Lazy endpoint **404** (step ii)

The UI should **not** call `…/review-evidence` unless the **Review** tab is visible (`review_redo.available === true` on the loaded attempt detail). In normal use the lazy endpoint returns **200** with `review_images`.

Return **404** when re-running the resolver at request time finds **no** Review redo:

| Situation | Example |
|-----------|---------|
| Attempt not found or not a marked completion candidate | Bad `attempt_id`, template missing from registry |
| No template link | `get_template` returns `None` |
| Review PDF not on disk | Resolver `stat` miss (includes attempts that never had a Review export) |
| `goodnotes_root` unset | Cannot build Review path |
| **Stale availability** | Detail load had `available=true`, but Review PDF was moved/deleted before tab click — re-validation fails |

Return **200** only when the Review PDF exists at request time (then render if needed and return images).

Direct API callers (curl, tests) hitting an attempt without Review redo get **404** — not an empty `review_images` list.

---

## 14. Open questions

None — all design choices resolved in §13.

---

## 15. Pre-implementation final sweep (2026-06-07)

Proposal-level readiness **before** Phase 1 coding (per [TODO.md P1-1](../../../TODO.md)).

| Check | Result |
|-------|--------|
| **Completeness** | §1–13 cover workflow, two-step load/render, API, frontend, phases, acceptance criteria, resolved decisions, 404 semantics |
| **Accuracy** | Resolver validated **17/17** on local Winston math cohort; performance numbers from measured Review PDFs (3–38 pages) |
| **Consistency** | Aligns with `files` v0.3.11 Review inventory exclusion; no marking / no `redo-practice`; same `attempt_id`; Template tab list-only pattern extended with lazy render |
| **API shape** | Step **i** `review_redo.available` + empty `review_images`; step **ii** new route on existing `marking.review.api_routes` prefix |
| **Footguns** | (1) Tab gating must use `review_redo.available`, not `review_images.length`. (2) Review basename from **template**, GoodNotes dir from **attempt path**. (3) PNG cache under **`review_redo/`**, not `file_question_info/` — avoids slug collision with template renders. (4) `<normal_name>` from **template** stem, not Review PDF path alone. (5) Re-validate on lazy call — handle stale **404** in UI. (6) `resolved_path` relative to `goodnotes_root`, debug-only in UI. |
| **Test plan** | Phase 1: path helper + detail payload; Phase 2: lazy endpoint + render cache; Phase 3: manual Winston smoke (exam / exercise / book) |
| **Doc plan** | Phase 4: buddy_console packages + L4 student MVP + `files/SPEC.md` cross-link + **`files`** / **`marking`** README & CHANGELOG version bumps |
| **Out of scope explicit** | Marking, inventory inclusion, Review-folder scan, `register_file`, background prefetch |

---

## 16. References

- [Buddy Console CHANGELOG — Template tab v0.1.11](../../CHANGELOG.md)
- [files CHANGELOG — Review exclusion v0.3.11](../../../files/CHANGELOG.md)
- [goodnotes-leaf-registry-report command](../../../../.cursor/commands/goodnotes-leaf-registry-report.md)
- [marking/review/api_routes.py](../../../marking/review/api_routes.py) — existing attempt detail route; add `review-evidence` alongside
- [marking/review/detail_service.py](../../../marking/review/detail_service.py) — `_template_images_for_attempt` (list-only from `file_question_info/`; Review uses `review_redo/`)
- [PdfFileManager.get_template](../../../pdf_file_manager/pdf_file_manager.py) — `completed_from` lookup
- [normalize_pdf_display_name](../../../pdf_file_manager/pdf_file_manager.py) — `<normal_name>` folder segment
- [slugify_student](../../../marking/core/artifact_paths.py) — `<student_slug>` folder segment (same as `marking_assets/`)
