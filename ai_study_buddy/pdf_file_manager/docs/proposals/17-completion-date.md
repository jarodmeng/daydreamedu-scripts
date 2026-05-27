# Proposal 17: Student completion date (`completion_date`)

**Status:** Implemented (2026-05-27) — **v0.3.22–v0.3.31**: schema + inference package, operator backfill (**353 / 369** browser completions dated), inventory consumers (`files` v0.3.6, browser packages), unified `infer_completion_date*` + [`scripts/infer_completion_dates.py`](../../scripts/infer_completion_dates.py). **Future work:** coverage report script, optional scan hook, completion-series sort alignment. Inference rules and [decisions](#open-questions-and-decisions) locked. Structure follows [TODO.md P1-1](../../../TODO.md).  
**Audience:** `pdf_file_manager` maintainers, `files` / Student File Browser / buddy_console consumers, marking and L4 file-framework docs  
**Related:** [16-goodnotes-document-timestamps.md](./16-goodnotes-document-timestamps.md), [15-completion-series-derived.md](./15-completion-series-derived.md), [L4_FILE_FRAMEWORK.md](../../../docs/L4_FILE_FRAMEWORK.md), [student file browser sort order](../../../student_file_browser/docs/proposal/2-card-sort-order.md), [`pdf_files.metadata.exam_date`](../../ARCHITECTURE.md) (human exam metadata — distinct from this proposal)

**Summary:** Persist `completion_date` (`YYYY-MM-DD`, SGT semantics) in `file_completion_dates` keyed by `file_id`, with provenance. **Historical backfill:** Phase 2 page-1/2 agent on **`d_root` (~238)**; Phase 3 Goodnotes / `filename_term` on **`g_root` (~131)** + undated `d_root`. **Re-runs (v0.3.31):** unified [`infer_completion_date_for_file`](../../pdf_file_manager.py) / [`infer_completion_dates`](../../pdf_file_manager.py) and CLI [`scripts/infer_completion_dates.py`](../../scripts/infer_completion_dates.py) over the full §4 matrix. **No row** when inference fails — registry `added_at` is not a substitute.

---

## Motivation

Today, inventory and browser UIs treat **`pdf_files.added_at`** (first registry registration time) as the card date and the default **Recent first** sort key (`registry_added_at` on `OnDiskMainPdfCard`). That answers “when did we register this PDF?” — not “when did the student complete this work?”

For most student completions, a **`completion_date`** (calendar date of the student’s work) is more useful for:

- browsing and sorting recent work in the Student File Browser,
- correlating attempts with school terms and weighted assessments,
- ordering completion series and marking timelines,
- future student-facing MVP surfaces.

This proposal adds a **persisted, queryable completion date** per registered completion main, inferred by deterministic rules where possible. When inference fails, **no row is stored** (registry `added_at` remains registration time only).

---

## Problem statement

| Question | Today | Desired |
|----------|-------|---------|
| When was this completion done? | Often unknown in registry; UI shows `added_at` | `completion_date` when inferrable |
| Sort “recent work” | `pdf_files.added_at` descending | `completion_date` descending when a row exists; files without a row sort after dated ones |
| GoodNotes book practice | `added_at` ≈ scan/backup time | Goodnotes notebook `last_modified` (see [proposal 16](./16-goodnotes-document-timestamps.md)) |
| Scanned WA / term papers | `added_at` ≈ scan batch date | Page-1 visual inspection and/or filename term keywords (`school_term_calendar.json`) |

**Distinction (normative):**

| Field | Meaning |
|-------|---------|
| `pdf_files.added_at` | First time this path was registered in `pdf_registry.db` |
| `pdf_files.updated_at` | Last registry row mutation |
| `metadata.exam_date` (optional, human) | Exam paper date supplied by reviewer — not auto-inferred here |
| **`completion_date` (new)** | Best estimate of when the **student finished** the work (calendar date; SGT for inferred values — see §5) |

Do **not** overload `added_at`, `updated_at`, or ad hoc `metadata` keys for this semantics.

---

## Goals

1. Persist **`completion_date`** per completion **`file_id`** (registered `file_type='main'`, `is_template=false`).
2. Support **rule-based inference** by root (`d_root` / `g_root`) and `doc_type`, as outlined in §4.
3. Expose a supported **`PdfFileManager` read API** and batch backfill path.
4. Let **`files` enrichment** surface `completion_date` (+ optional `completion_date_source`) on inventory cards.
5. Let Student File Browser / buddy_console use **`completion_date` for display and `recent` sort** when a `file_completion_dates` row exists; otherwise show only `registry_added_at` (registration), not as `completion_date`.
6. Record **provenance** (`source`, optional `confidence`, `source_detail`) for audit and re-inference.

## Non-goals (v1)

- Exact time-of-day (date-only).
- Inferring completion dates for **templates** (`is_template=true`) or **`file_type='raw'`** rows (raws inherit via linked main when needed).
- Replacing **`metadata.exam_date`** or marking JSON dates.
- Automatic inference on every `scan_for_new_files` (optional Phase 5 hook; v1 is explicit backfill + documented re-run).
- Cross-root deduplication of completion dates.
- Student-facing UI (consumers may follow in `files` / buddy_console after storage ships).
- Fuzzy Goodnotes name matching beyond [proposal 16](./16-goodnotes-document-timestamps.md).

---

## Inference matrix (normative intent)

Apply rules in **priority order** within each cell; first success wins. Only registered **completion mains** are in scope (`is_template=false`, `file_type='main'`, `student_id` set).

**Completion inventory cohort (normative):** The same set of files the **Student File Browser** shows with **Scope = Completion** and default filters (all roots, students, types) — i.e. every registered completion **main** in the on-disk inventory index (`build_main_pdf_index_for_roots` → enrich → `scope=completion`). As of 2026-05-26 this is **~369** files total:

| Slice | Count (approx.) | Phase |
|-------|-----------------|-------|
| **`d_root`** completions (`DaydreamEdu` / `completion/…` paths) | **~238** | **Phase 2** — page-1 visual inspection only |
| — `d_root` non-`book` (`exam`, `exercise`, `activity`, `note`, …) | **~169** | Phase 2 **first** (priority) |
| — `d_root` **`book`** (book practice units) | **~69** | Phase 2 **last** (deprioritized) |
| **`g_root`** completions (`GoodNotes/…` paths) | **~131** | **Phase 3** — Goodnotes `last_modified` (not page-1) |
| **Full browser inventory** | **~369** | Phases 2 + 3 together cover all completions |

Operators may pass narrower batch filters (`student_id`, `root`, `doc_types`); defaults match the slices above.

| Root | `doc_type` | Step 1 | Step 2 | Step 3 | If all fail |
|------|------------|--------|--------|--------|-------------|
| **d_root** | `exam`, `exercise` | Page-1 visual inspection | `filename_term` | — | No row |
| **d_root** | `book` | Page-1 visual inspection | `drive_modified` (mtime) | — | No row |
| **d_root** | `activity`, `note`, … | Page-1 visual inspection | — | — | No row |
| **g_root** | `book`, `exam`, `exercise` | Goodnotes `last_modified` | Goodnotes `updated_at` (if no `last_modified`) | `filename_term` (`exam`/`exercise` only) | No row |

**Phase 2 vs §4 matrix:** Phase 2 batch runs page-1 visual inspection on **`d_root` completions only** (~238). **`g_root` completions are excluded** — they use Goodnotes `last_modified` in Phase 3. Within the 238, process **`doc_type != book` first (~169)**, then **`doc_type = book` last (~69)** — book practice PDFs rarely have a header date (§4.3) and are **deprioritized**. Phase 3 processes **`g_root` (~131)** plus undated **`d_root`** via Goodnotes / `filename_term` per §4 (unless `--force`).

Details below. Worked examples: [P5 English Practice 1](#worked-example-primary-5-english-practice-1-d_root-exercise) (page 1); [P6 COE Practice 3](#worked-example-p6-comprehension-open-ended-practice-3-psle-2022-date-on-page-2) (page 2).

### 4.1 `d_root` — `doc_type` in `exam`, `exercise`

| Step | Method | `source` value | Notes |
|------|--------|----------------|-------|
| 1 | **Visual inspection of page 1**, then **page 2** when page 1 has no date (multimodal agent, not OCR) | `handwritten_page1` | Primary for scanned school work. Use the **main** PDF (compressed `_c_` if registered). **Flow:** inspect page 1; if no student completion date and the PDF has ≥2 pages, inspect page 2; if still none, no row. Record `source_detail.page_index` (`0` or `1`). SGT (`Asia/Singapore`). |
| 2 | **Filename / title heuristics** — keywords such as `WA1`, `WA2`, `WA3`, `EoY`, `EOY`, `EYE`, `Term 1`–`Term 4`, `T1`–`T4` | `filename_term` | Resolves to an **approximate calendar date** via a school-term calendar table (see §5.2). Store evidence in `source_detail`. |

**No row when inference fails:** If steps 1–2 do not produce a date, **do not** insert a `file_completion_dates` row. Do not treat `pdf_files.added_at` as a substitute completion date for these files. Inventory may still show `registry_added_at` separately (registration time). A row appears only after successful inference or an explicit `set_completion_date` (`source=manual`).

### 4.2 `g_root` — `doc_type` in `book`, `exam`, `exercise`

All registered completion mains under `GOODNOTES_ROOT`. Many g_root **exam** / **exercise** files are Goodnotes-native; `last_modified` is often a good proxy. When Goodnotes lookup fails, **exam** / **exercise** may still get a date from filename heuristics (same as §4.1 step 2).

| Step | Method | `source` value | Notes |
|------|--------|----------------|-------|
| 1 | **`get_goodnotes_document_timestamps_for_file(file_id)`** → `timestamps.last_modified` | `goodnotes_last_modified` | All `doc_type` values in this section. Read-only; requires local Goodnotes DBs ([proposal 16](./16-goodnotes-document-timestamps.md)). Use **calendar date in SGT** derived from the UTC ISO timestamp. |
| 2 | Only if step 1’s `last_modified` is **missing** — `timestamps.updated_at` | `goodnotes_updated_at` | Never use `updated_at` when `last_modified` is present, even if `updated_at` is newer. |
| 3 | **Filename / title heuristics** — same keywords as §4.1 step 2 | `filename_term` | **`exam` and `exercise` only**, when steps 1–2 fail. Apply to `normal_name` or basename. Not used for `book` in v1. |

**No row when inference fails:** If no step succeeds (Goodnotes unavailable or unmatched, and—for `book`—no filename path; for `exam`/`exercise`—filename heuristics also fail), **do not** insert a row. Same consumer rules as §4.1 — `registry_added_at` is registration time only, not `completion_date`.

### 4.3 `d_root` — `doc_type` = `book`

| Step | Method | `source` value | Notes |
|------|--------|----------------|-------|
| 1 | Same as §4.1 step 1 (page-1 visual inspection) if present | `handwritten_page1` | Often absent for book unit PDFs |
| 2 | **Filesystem mtime** on registered main path (Google Drive sync on macOS) | `drive_modified` | `completion_date` = calendar date in **SGT** from `stat().st_mtime`. Skip if file missing locally. `confidence`: `medium`. Not filename guessing. |

There is **no** `filename_term` or Goodnotes inference for d_root books — do not invent dates from basename alone.

**Phase 2 batch:** d_root `book` completions (~69 of 238) are **deprioritized** — processed after all non-`book` d_root files (~169).

**No row when inference fails:** If steps 1–2 do not produce a date, **do not** insert a row. Same consumer rules as §4.1 and §4.2.

### 4.4 Other `doc_type` values (`activity`, `note`, …)

v1: page-1 visual inspection only (same path as §4.1 step 1) when applicable; otherwise no row. Expand in a follow-up if needed.

---

## Worked example: `Primary 5 English Practice 1` (d_root exercise)

Real registered completion used to validate §4.1 (probe run 2026-05-26). Shows why **`added_at` must not substitute** for completion date, and how page-1 disambiguation behaves when multiple handwritten dates appear.

### Registry row

| Field | Value |
|-------|--------|
| `file_id` | `7b93423a-d9f4-46a0-bb07-181314af0537` |
| `normal_name` | `Primary 5 English Practice 1` |
| `path` | `…/DaydreamEdu/completion/Singapore Primary English/winston.ry.meng@gmail.com/P5/Exercise/_c_Primary 5 English Practice 1.pdf` |
| Root | **d_root** |
| `doc_type` | **`exercise`** |
| `pdf_files.added_at` | `2026-03-09T06:38:28Z` (registration when scanned/indexed — **not** student completion) |

### Strategy results (§4.1 order)

| Step | Method | Result |
|------|--------|--------|
| — | Goodnotes (§4.2) | **N/A** — `get_goodnotes_document_timestamps_for_file` → `not_goodnotes_root` |
| 1 | `handwritten_page1` | **Match** — see below |
| 2 | `filename_term` | **No match** — basename has “Primary 5” and “Practice 1” but no `WA1`/`WA2`, `Term N`, `EoY`, etc. |

**School-year check:** path `P5` + `student_id=winston` → `2021 + 4 = 2025`, consistent with completion date Oct 2025 (§5.2).

### Page 1 evidence

Scanned worksheet (no native text layer). Header fields (handwritten, blue ink):

| Location | Text | Use |
|----------|------|-----|
| `Date:` line | **22nd Oct 2025** | **Completion date** (student work date) |
| Instruction note | “refer to SLS to self-mark on **25th Oct 2025**” | Follow-up marking date — **not** completion |
| `Class:` | `5GEN` | Context only |
| Margin code | `P5.031` | Aligns with P5 / filename; not a calendar date |

**Disambiguation rule (§5.1):** prefer the date on or immediately after a printed **`Date:`** label over other dates in body/margin notes.

Probe note: naive Tesseract on a rendered page-1 image garbled the header (`Date: _22 eet 2e25`). Production **`handwritten_page1` uses multimodal visual inspection only** (not OCR); see §5.1.

### Inferred row (would persist)

```json
{
  "file_id": "7b93423a-d9f4-46a0-bb07-181314af0537",
  "completion_date": "2025-10-22",
  "source": "handwritten_page1",
  "confidence": "high",
  "inference_model": "claude-4.6-sonnet-medium-thinking",
  "source_detail": {
    "page_index": 0,
    "raw_text": "Date: 22nd Oct 2025",
    "normalized_date": "2025-10-22",
    "timezone": "Asia/Singapore",
    "disambiguation": "preferred Date: label over self-mark note 2025-10-25"
  }
}
```

No `file_completion_dates` row would be written if step 1 failed and step 2 did not apply — **`added_at` (`2026-03-09`) is not used** as a fallback.

---

## Worked example: `P6 Comprehension Open-Ended Practice 3 (PSLE 2022)` (date on page 2)

Real registered completion from the Phase 2 priority batch (operator review 2026-05-26). Illustrates why **page-1-only** inspection misses valid dates when the PDF uses a **cover page** without a `Date:` field.

### Registry row

| Field | Value |
|-------|--------|
| `file_id` | `3966d6d8-1e61-420b-ac5f-97f9ab740c2f` |
| `normal_name` | `P6 Comprehension Open-Ended Practice 3 (PSLE 2022)` |
| `path` | `…/DaydreamEdu/completion/Singapore Primary English/winston.ry.meng@gmail.com/P6/Exercise/_c_P6 Comprehension Open-Ended Practice 3 (PSLE 2022).pdf` |
| Root | **d_root** |
| `doc_type` | **`exercise`** |

### Page 1 (cover) — no completion date

Page 1 is a **St Gabriel’s** cover sheet: subject/topic lines (`Comprehension Open-Ended`, `Term 2 – Practice 1 (PSLE 2022)`), student name, class, and a score (**13/20**). There is **no** handwritten **`Date:`** on this page. Printed **2026** / **PSLE 2022** refer to worksheet series, not when the student finished.

Phase 2 page-1-only pass correctly stored **`completion_date: null`** with `source_detail.reason: "no_date_on_page_1"`.

### Page 2 — completion date

The student **`Date:`** field appears on **page 2** (worksheet header). That date should be inferred on a **page-2 fallback** pass with `source_detail.page_index: 1`.

### Normative flow (after page-2 fallback)

| Step | Page | Result |
|------|------|--------|
| 1 | Page 1 | No date → continue |
| 2 | Page 2 | Read **`Date:`** line → persist `completion_date` with `page_index: 1` |
| 3 | — | If page 2 also has no date → `reason: "no_date_on_pages_1_or_2"`; **no registry row** |

Prepare batch renders `page-01.png` and `page-02.png` (when the PDF has ≥2 pages). The [completion-date-page1-inspector](../../../../.cursor/agents/completion-date-page1-inspector.md) agent inspects page 1 first, then page 2 when `page2_image_path` is present.

---

## Storage design

### Recommendation: dedicated table (preferred)

Store completion dates in a **small side table keyed by `file_id`**, not as a new column on `pdf_files`.

| Approach | Pros | Cons |
|----------|------|------|
| **`file_completion_dates` table (recommended)** | Clear semantics; provenance columns; re-inference without touching core registry rows; optional manual override; FK cascade on file delete | Extra join in inventory enrichment |
| New column `pdf_files.completion_date` | Single-table read | Mixes inferred student date with core registry; awkward provenance; harder to re-run inference idempotently |
| `pdf_files.metadata` JSON | No migration | Weak typing; easy to fork keys; poor query/sort ergonomics |

**No registry fallback rows:** Do **not** insert rows whose only source would be `registry_added_at`. Absence of a row means **no** stored `completion_date` (see §4.1–§4.4). This keeps the table small and makes “we have a real completion date” queryable (`EXISTS` join).

### Schema (v1)

```sql
CREATE TABLE file_completion_dates (
    file_id          TEXT PRIMARY KEY
                     REFERENCES pdf_files(id) ON DELETE CASCADE,
    completion_date  TEXT NOT NULL
                     CHECK (completion_date GLOB '????-??-??'),  -- ISO date YYYY-MM-DD
    source           TEXT NOT NULL
                     CHECK (source IN (
                         'handwritten_page1',
                         'filename_term',
                         'goodnotes_last_modified',
                         'goodnotes_updated_at',
                         'manual'
                     )),
    confidence       TEXT
                     CHECK (confidence IS NULL OR confidence IN ('high', 'medium', 'low')),
    inference_model  TEXT,   -- detector model slug (page-1 agent); not the literal "inherit"
    source_detail    TEXT,   -- JSON: matched text, page index, GN doc id, term keyword, calendar rule id, etc.
    inferred_at      TEXT NOT NULL,  -- UTC ISO-8601 when this row was written/updated by inference
    updated_at       TEXT NOT NULL   -- UTC ISO-8601; bumps on re-inference or manual edit
);

CREATE INDEX idx_file_completion_dates_completion_date
    ON file_completion_dates (completion_date);
```

**Invariants:**

- At most one row per `file_id`.
- Target rows: `pdf_files.is_template = 0`, `pdf_files.file_type = 'main'`, and (for strict v1) `student_id IS NOT NULL`.
- `completion_date` is a **calendar date** (no time component), with **SGT semantics** for inferred values (`timezone` recorded in `source_detail` when relevant).
- `source = 'manual'` is set only via an explicit operator/API override. Batch inference **never** overwrites `source=manual` unless `force_manual=True` (CLI: `--force-manual`).
- Non-`manual` rows require **`confidence`**. **`handwritten_page1`** rows also require **`inference_model`** (actual Cursor model slug used for inspection — never the literal `inherit`).

**Operation log:** New operation types, e.g. `set_completion_date`, `infer_completion_date` (batch), appended to existing `operation_log` for audit.

---

## API (`PdfFileManager`)

### Read

```python
def get_completion_date(file_id: str) -> CompletionDateRecord | None: ...

def get_completion_dates_for_files(file_ids: list[str]) -> dict[str, CompletionDateRecord]: ...

@dataclass(frozen=True)
class CompletionDateRecord:
    file_id: str
    completion_date: str          # YYYY-MM-DD
    source: str
    confidence: str | None        # required for non-manual sources
    inference_model: str | None     # required for handwritten_page1; actual model slug
    source_detail: dict | None
    inferred_at: str
    updated_at: str
```

### Write

```python
def set_completion_date(
    file_id: str,
    completion_date: str,
    *,
    source: str = "manual",
    confidence: str | None = None,
    inference_model: str | None = None,
    source_detail: dict | None = None,
) -> CompletionDateRecord: ...

def clear_completion_date(file_id: str) -> None: ...  # remove row; no stored completion_date until re-inferred or set manually
```

### Inference (single file and batch)

```python
def infer_completion_date_for_file(
    file_id: str,
    *,
    force: bool = False,
    force_manual: bool = False,
    methods: frozenset[str] | None = None,
    work_dir: str | Path | None = None,
) -> CompletionDateRecord | None: ...
# Priority when methods is None: all COMPLETION_DATE_SOURCES.
# Order: handwritten_page1 (cached agent JSON in work_dir) → goodnotes_* (g_root)
#   → filename_term (d_root exam/exercise) → drive_modified (d_root book).
# Returns None when no method produced a date (no row written).

def infer_completion_dates(
    *,
    file_ids: Sequence[str] | None = None,
    student_id: str | None = None,
    root: Literal["d_root", "g_root"] | None = None,
    doc_types: Sequence[str] | None = None,
    methods: frozenset[str] | None = None,
    work_dir: str | Path | None = None,
    dry_run: bool = False,
    force: bool = False,
    force_manual: bool = False,
) -> InferCompletionDatesReport: ...
# Cohort: explicit file_ids OR find_files filters (main, non-template).
# dry_run: walk cohort and count only; no registry writes.
# force: overwrite non-manual rows; force_manual: overwrite source=manual rows.
```

### Operator entrypoints (v0.3.31)

| Entry | When to use |
|-------|-------------|
| **[`scripts/infer_completion_dates.py`](../../scripts/infer_completion_dates.py)** | **Canonical re-run** — full §4 matrix on a cohort (`--root`, `--student-id`, `--doc-type`, `--file-id`, `--dry-run`, `--force`, `--force-manual`, optional `--work-dir`, `--method`). |
| `PdfFileManager.infer_completion_date_for_file` | One file from Python (same matrix as CLI). |
| `scripts/prepare_completion_date_page1_batch.py` + agent + `apply_completion_date_page1_results.py` | **First-time page-1 backfill** — render PNGs, run [completion-date-page1-inspector](../../../../.cursor/agents/completion-date-page1-inspector.md), persist agent JSON. Re-runs can use `infer_completion_dates --method handwritten_page1` instead of the apply script. |
| `scripts/apply_completion_date_goodnotes.py`, `apply_completion_date_filename_term.py`, `apply_completion_date_drive_modified.py` | **Reproducible one-off applies** from the original backfill; superseded for general re-runs by the unified CLI. |
| `scripts/verify_completion_date_school_years.py` | Audit / fix school-year mismatches on cached page-1 JSON and registry rows. |

Example (dry-run on d_root exams):

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.infer_completion_dates \
  --root d_root --doc-type exam --dry-run
```

Implementation modules:

| Module | Responsibility |
|--------|----------------|
| [`completion_date/core.py`](../../completion_date/core.py) | Types, normalization, cohort helpers, school-year guards, apply inference results, batch report types |
| [`completion_date/page1.py`](../../completion_date/page1.py) | **Render page 1–2 to PNG** (PyMuPDF); batch manifest paths; **`merge_page_inspection_payloads`**; **`apply_page1_inspection_result`** — **no in-process vision API** |
| [`completion_date/filename_term.py`](../../completion_date/filename_term.py) | WA/EoY/Term keywords + [`school_term_calendar.json`](../../completion_date/data/school_term_calendar.json) |
| [`completion_date/goodnotes.py`](../../completion_date/goodnotes.py) | Goodnotes `last_modified` → SGT date (proposal 16 lookup) |
| [`completion_date/drive_modified.py`](../../completion_date/drive_modified.py) | PDF `st_mtime` → SGT date for d_root books |
| [`.cursor/agents/completion-date-page1-inspector.md`](../../../../.cursor/agents/completion-date-page1-inspector.md) | **Cursor agent** for page-1 then page-2 visual inspection (`model: inherit`) |
| [`scripts/infer_completion_dates.py`](../../scripts/infer_completion_dates.py) | Operator CLI wrapping `infer_completion_dates` |

**Goodnotes integration:** `infer_completion_date_for_file` calls `get_goodnotes_document_match`; map `status` in `matched_*` only; never guess on `not_found` / `ambiguous`.

---

## Inference details

### 5.1 Page-1 / page-2 handwritten / printed date (`handwritten_page1`)

- Input: resolved on-disk path for the registered **main** file.
- **Render (Python):** [`completion_date/page1.py`](../../completion_date/page1.py) renders **page 1** (index 0) to `page-01.png` for every file. When the PDF has **≥2 pages**, also renders **page 2** (index 1) to `page-02.png` under the batch work dir (e.g. `pdf_file_manager/.completion_date_page1/images/<file_id>/`).
- **Inspect (Cursor agent):** visual inspection is performed by the **[completion-date-page1-inspector](../../../../.cursor/agents/completion-date-page1-inspector.md)** subagent with **`model: inherit`**. **Flow:** inspect `page1_image_path` first; if no completion date and `page2_image_path` is set, inspect page 2; otherwise return null. Minimal context: `file_id`, `normal_name`, `student_id`. **Do not** call vision APIs from `pdf_file_manager` Python for v1.
- **Do not use OCR** (e.g. Tesseract) — handwriting and worksheet layout are unreliable under OCR.
- **Persist (Python):** `scripts/apply_completion_date_page1_results.py` **or** `infer_completion_date_for_file` / `infer_completion_dates` (with `handwritten_page1` in `methods`) reads cached agent JSON under `work_dir` (default `.completion_date_page1/`) and calls `set_completion_date(..., source='handwritten_page1', ...)` or skips when `completion_date` is null. **Prepare** (`prepare_completion_date_page1_batch`) renders PNGs only — **no** vision API inside the manager process.
- **School-year sanity check (apply):** when `student_id` and path `Pn` are known, reject dates whose calendar year is outside **`[expected_school_year - 1, expected_school_year + 1]`** (`expected_school_year = p1_year + (n - 1)` per §5.2). Audit/fix batch: `scripts/verify_completion_date_school_years.py` (`--fix` nulls mismatched cached JSON and clears registry rows).
- **Exam vintage vs path school year (apply + agent):** when the agent inferred **`expected_school_year - 1`** from a printed exam/header year (e.g. `EOY 2024` on a **P5** path in school year **2025**) but the **`Date:`** line has month/day only, **`apply_page1_inspection_result`** bumps the year to **`expected_school_year`** and records `source_detail.year_adjustment`. The page-1 inspector agent must prefer **`expected_school_year`** over header vintage years when both are known (see [worked example: P5 Math EoY](#worked-example-p5-math-eoy-practice-set-1-exam-vintage-year)).
- **Timezone:** calendar date interpreted in **`Asia/Singapore` (SGT)**. Store `completion_date` as `YYYY-MM-DD`; record `"timezone": "Asia/Singapore"` in `source_detail`.
- **Agent output (normative JSON object, no markdown fences):**

```json
{
  "file_id": "<uuid>",
  "completion_date": "2025-10-22",
  "confidence": "high",
  "inference_model": "claude-4.6-sonnet-medium-thinking",
  "source_detail": {
    "page_index": 0,
    "timezone": "Asia/Singapore",
    "evidence": "Date: 22nd Oct 2025",
    "disambiguation": "ignored instruction note 25th Oct 2025"
  }
}
```

When no readable completion date on page 1 only: `"reason": "no_date_on_page_1"` (no `page2_image_path`). When page 2 was inspected and still none: `"reason": "no_date_on_pages_1_or_2"`. **Do not** write a registry row for null.

- **Confidence:** `high` when unambiguous single date; `medium` when multiple dates and disambiguation rules pick one (e.g. prefer dates near **`Date:`** labels); `low` when weak.
- Fail closed: if no date after the page-1/page-2 flow, proceed to the next rule in the matrix (`filename_term` for exam/exercise) — do not write a row from page inspection alone.
- **Worked examples:** [Primary 5 English Practice 1](#worked-example-primary-5-english-practice-1-d_root-exercise) (date on page 1); [P6 Comprehension Open-Ended Practice 3 (PSLE 2022)](#worked-example-p6-comprehension-open-ended-practice-3-psle-2022-date-on-page-2) (cover on page 1, `Date:` on page 2); [P5 Math EoY Practice Set 1](#worked-example-p5-math-eoy-practice-set-1-exam-vintage-year) (exam vintage year ≠ completion year).

*Historical phases: Phase 1 manual API; Phase 2 page-1 agent on **d_root (~238)**; Phase 3 Goodnotes / `filename_term` on **g_root (~131)** + undated `d_root`. **v0.3.31:** unified `infer_*` + CLI for all re-runs over §4.*

### Worked example: `P5 Math EoY Practice Set 1` (exam vintage year)

Winston completion `b6e79345-816a-4496-8539-3c00c50ea731` — path `…/P5/Exam/…`, school year **2025**.

| Signal | Value | Use |
|--------|--------|-----|
| Handwritten `Date:` | **9th Oct** (no year on line) | Day/month for completion |
| Printed header | **EOY 2024 / P5** | **Exam paper vintage** — not when Winston finished |
| Wrong inference | `2024-10-09` with `disambiguation: year from header EOY 2024` | Treat as mistake |
| Correct completion | **`2025-10-09`** | `expected_school_year` for P5 Winston |

**Apply guard:** `adjust_page1_completion_year_for_path_context` rewrites `expected_school_year - 1` → `expected_school_year` when disambiguation/evidence cites header/exam vintage and the `Date:` line lacks that 4-digit year.

### 5.2 Filename / title heuristics (`filename_term`)

Apply to `normal_name` or basename (strip `_c_` / `_raw_` prefixes). Example patterns:

| Pattern | Example | Intended mapping |
|---------|---------|------------------|
| `WA1`, `WA 1`, `Weighted Assessment 1` | `P4 Math WA1` | Term-weighted assessment window (calendar table) |
| `WA2`, `WA3` | … | Same |
| `EoY`, `EOY`, `EYE`, `End of Year` | `P6 Science EoY` | End-of-year window |
| `Term 1` … `Term 4`, `T1` … `T4` | `P5 Term 2 Revision` | Term bucket |

**Requires** a maintained **[`completion_date/data/school_term_calendar.json`](../../completion_date/data/school_term_calendar.json)** (loaded by inference code) with Singapore **school-term date ranges from calendar year 2021 onwards**. Unknown `student_id` for P1 anchoring → filename term inference **fails** (no row).

**School-year model (normative):**

- Each Singapore **school year coincides with the calendar year** (Jan–Dec).
- Anchor **Primary 1** calendar years per student (for deriving school year from path grade when the filename omits a year):

| Student (`students.id`) | P1 calendar year |
|-------------------------|------------------|
| `winston` | **2021** |
| `emma` | **2023** |
| `abigail` | **2025** |

- When the filename/path implies primary level `Pn` but not calendar year:  
  `school_year = p1_year(student_id) + (n - 1)`  
  Example: Winston + `P5` in path → `2021 + 4 = 2025`.

- JSON shape (illustrative): top-level keys = calendar year (`"2021"` … `"2026"`); each year lists terms and assessment windows with ISO `start` / `end` dates sourced from Singapore school-term schedules (MOE-aligned; operator-maintained).

**Requires** term/WA/EoY windows in that file — not a single “current year only” slice.

- **Term keyword groups (first match wins):** Term 4 ← `EoY`, `EOY`, `EYE`, `Term 4`, `期末考试`; Term 2 ← `WA2`, `SA2`, `Term 2`, `测验2`; Term 3 ← `WA3`, `Term 3`, `测验3`; Term 1 ← `WA1`, `Term 1`, `测验1` (plus `T1`–`T4`).
- Store resolved date as **14 calendar days before the MOE term end** for that school year (`school_term_calendar.json`), using `school_year = p1_year(student_id) + (n - 1)` from path `Pn`.
- `confidence`: typically `medium` (filename-only).
- `source_detail`: `{ "matched_keyword": "WA1", "calendar_rule_id": "2025-P5-T3-WA1", "school_year": 2025 }`.

### 5.3 Goodnotes `last_modified` (`goodnotes_last_modified`)

- Eligibility: path under `GOODNOTES_ROOT`, `doc_type` in `book`, `exam`, `exercise`, registered main completion (see §4.2).
- **Timestamp choice:** use `timestamps.last_modified` first. Use `goodnotes_updated_at` (**`updated_at` only**) when `last_modified` is null/missing — never prefer `updated_at` if `last_modified` exists.
- `completion_date` = **calendar date in SGT** (`Asia/Singapore`) from the chosen UTC ISO timestamp.
- `confidence`: `high` when `status` is exact match; `medium` for underscore-restored / raw-source match statuses.
- If Goodnotes DB unavailable: skip (no row); same rules as §4.2.

### 5.4 Consumers when no row exists

- `completion_date` on inventory JSON: **`null`** (or omitted) when there is no `file_completion_dates` row — **not** `pdf_files.added_at`.
- `completion_date_source`: absent / `null` when no row.
- `registry_added_at`: unchanged; still shown separately as registration time.
- **`recent` sort:** cards **with** `completion_date` first (descending); cards **without** sort after (tie-breaker `absolute_path` ascending). Do not use `added_at` as a proxy for completion date in sort or display.

---

## Consumer changes (follow-on packages)

| Package | Change |
|---------|--------|
| **`pdf_file_manager`** | Schema, read/write API, unified `infer_completion_date*` (v0.3.31), [`scripts/infer_completion_dates.py`](../../scripts/infer_completion_dates.py), `completion_date/data/school_term_calendar.json`, legacy `apply_completion_date_*.py`, tests |
| **`files`** | `OnDiskMainPdfCard`: nullable `completion_date`, `completion_date_source`; keep `registry_added_at`; extend `sort_main_pdf_cards` **`recent`** per §5.4 |
| **`student_file_browser` / `buddy_console`** | Card date + tooltip; optional sort label “Completed (recent)” |
| **L4 docs** | Cross-link; clarify vs `added_at` and Goodnotes timestamps |

**Sort (normative update to [card sort proposal](../../../student_file_browser/docs/proposal/2-card-sort-order.md)):**

- `recent`: dated completions first (`completion_date` descending), then undated completions (`absolute_path` ascending within each group)
- unregistered: unchanged (tail block)

---

## Open Questions and decisions

1. **Goodnotes timestamp:** resolved — **`last_modified` first**; **`updated_at` only** when `last_modified` is missing (§4.2, §5.3).
2. **Timezone:** resolved — page-1 and Goodnotes-derived calendar dates use **`Asia/Singapore` (SGT)**.
3. **`school_term_calendar.json`:** resolved — Singapore terms **from 2021**; school year = calendar year; P1 anchors Winston **2021**, Emma **2023**, Abigail **2025**; `school_year = p1_year(student_id) + (n - 1)` when path has `Pn` (§5.2).
4. **Re-inference:** resolved — skip existing rows unless `--force`; never overwrite `source=manual` without `--force-manual`.
5. **Page-1 extraction:** resolved — **multimodal visual inspection** only, **not OCR** (§5.1).
6. **Page-1 execution:** resolved — inspection by **Cursor agent** [completion-date-page1-inspector](../../../../.cursor/agents/completion-date-page1-inspector.md) with **`model: inherit`**; Python only renders PNGs and persists agent JSON via `set_completion_date` — **no in-process vision LLM** in `pdf_file_manager` (§5.1).
7. **Registry fallback rows:** resolved — **no** `file_completion_dates` row and **no** read-time `added_at` substitute for `completion_date` (§5.4).
8. **Completion series sort:** open — [proposal 15](./15-completion-series-derived.md) still orders by `pdf_files.added_at`; align series sort with `completion_date` in a follow-up or separate change.
9. **Post-scan inference:** open — optional hook after `scan_for_new_files` (feature-flagged); defer until Phases 1–4 are stable (see [Future work](#future-work)).

---

## Implementation plan

Phases use **numbered indices** (Phase 1, Phase 2, …) per [TODO.md P1-1](../../../TODO.md). Each phase has a **todo checklist**, **test checklist**, and **success / handoff criteria**.

### Phase 1 — Schema and manual API

**Goal:** Persist and read `completion_date` rows; manual operator overrides; no automated inference yet.

**Todo checklist**

- [x] Add `file_completion_dates` table migration on registry DB open.
- [x] Add `CompletionDateRecord` and `get_completion_date` / `get_completion_dates_for_files`.
- [x] Add `set_completion_date`, `clear_completion_date`.
- [x] Append `set_completion_date` / `clear_completion_date` operation-log types (`infer_completion_date` deferred to Phase 2 batch).
- [x] Reject writes for templates, raw files, or rows without `student_id` (v1 policy).

**Test checklist**

- [x] FK cascade on `pdf_files` delete.
- [x] CHECK rejects invalid `completion_date` / `source` values.
- [x] Manual set/get/clear round-trip.
- [x] `infer` stub returns `None` or not implemented until Phase 2 (page-1 path); full multi-method infer in Phase 3.

**Success / handoff criteria**

- [x] Operators can set and read `completion_date` via `PdfFileManager` for a completion `file_id`.
- [x] No inference paths active yet; registry `added_at` unchanged.

### Phase 2 — `d_root` completion dates (page-1/2 + book `drive_modified`) — **COMPLETE** (2026-05-26)

**Goal:** Run `handwritten_page1` (multimodal, SGT, not OCR) on **`d_root` registered completion mains only** — **~238** files (browser completion inventory minus all `g_root`). Exclude `g_root` from this phase. **Process order:** all **`doc_type != book` first (~169)**, then **`doc_type = book` last (~69)** — d_root book practice is **deprioritized** for page-1 because header dates are uncommon (§4.3); books use **`drive_modified`** (§4.3 step 2).

**Phase 2 backfill record (one-time, 2026-05-26)**

| Slice | Cohort | Methods run | Dated | Still no row |
|-------|--------|-------------|-------|----------------|
| Priority exam/exercise | **169** (manifest in `.completion_date_page1/`) | Page 1 → page 2 agent inspection; apply; school-year sanity check; **`filename_term`** on undated (35 matched) | **153** | **16** |
| Deprioritized `book` | **69** | **`drive_modified`** (`apply_completion_date_drive_modified`) | **69** | **0** |
| **d_root subtotal** | **238** | | **222** | **16** |

- Priority undated list: `.completion_date_page1/null_completion_dates_priority169.csv` (16 files — no header date and no term keyword, e.g. PSLE papers, generic “Practice” titles).
- Sources in registry for the 169: **118** `handwritten_page1`, **35** `filename_term` (term keywords applied during backfill; see Phase 3 for resolver code).
- **No `g_root` files** were processed in Phase 2.

**Todo checklist**

- [x] Add [`.cursor/agents/completion-date-page1-inspector.md`](../../../../.cursor/agents/completion-date-page1-inspector.md) (`model: inherit`; JSON contract §5.1).
- [x] Add [`completion_date/page1.py`](../../completion_date/page1.py): render page 1–2 PNGs; batch manifest (`page1_image_path`, optional `page2_image_path`); `apply_page1_inspection_result` → `set_completion_date` (no vision API).
- [x] Page-2 fallback: agent inspects page 1 first, then page 2 when rendered; `no_date_on_pages_1_or_2` when both lack a date ([P6 COE Practice 3 example](#worked-example-p6-comprehension-open-ended-practice-3-psle-2022-date-on-page-2)).
- [x] School-year sanity check on apply (`check_completion_date_school_year`; `scripts/verify_completion_date_school_years.py`).
- [x] Add `scripts/prepare_completion_date_page1_batch.py`: emit cohort JSON + render images for **d_root** (~238); order non-`book` first, `book` last; `--skip-doc-types book`.
- [x] Add `scripts/apply_completion_date_page1_results.py`: read agent JSON / `results/` dir; persist rows; `infer_completion_date` operation-log entries.
- [x] **Operator / agent batch:** prepare → inspect all **169** priority items → page-2 pass on 49 nulls → apply; **`filename_term`** pass on remaining nulls; **`drive_modified`** on **69** books.
- [x] [`completion_date/drive_modified.py`](../../completion_date/drive_modified.py) + `scripts/apply_completion_date_drive_modified.py` (§4.3 step 2).
- [x] Extend `infer_completion_date_for_file` / `infer_completion_dates` to apply **cached agent results** from work dir when present; otherwise page-1 step is no-op (agent pass required).
- [x] Disambiguation rules live in agent spec (prefer `Date:` — [worked example](#worked-example-primary-5-english-practice-1-d_root-exercise)).

**Test checklist**

- [x] Unit tests: render page 1, apply JSON → row, null JSON → no row; no Tesseract/OpenAI imports in `completion_date/page1.py` (`tests/test_completion_date_page1.py`, `test_completion_date_school_year.py`).
- [x] Agent spec smoke (manual): worked example PNG → `2025-10-22`, `source=handwritten_page1`, `timezone` in `source_detail`.
- [x] Multi-date page (agent/manual): self-mark note date not chosen when `Date:` present (worked example §4.1).
- [x] No OCR (Tesseract) in production code path.
- [x] Scan with no readable date → no row (16 priority files documented).
- [x] Batch dry-run: `g_root` `file_id` skipped; `book` files ordered after non-`book`.
- [x] Operator smoke: **169** priority d_root inspected; **69** books via `drive_modified`.

**Success / handoff criteria**

- [x] d_root exercise with header date (worked example) persists correct row.
- [x] Priority pass (~169 non-book d_root) completed; **16** remain without a row (fail closed).
- [x] **No `g_root` files** in Phase 2 batch.
- [x] d_root **book** slice: **69/69** dated via `drive_modified` (not page-1).
- [x] Remaining priority undated files documented for optional manual / follow-up rules (PSLE titles, generic practice names).

### Phase 3 — Goodnotes, filename calendar, batch inference (`g_root` + undated `d_root`)

**Goal:** Cover remaining completions in the **~369** browser inventory: all **`g_root` (~131)** via Goodnotes per §4.2, plus **`d_root` files still without a row** after Phase 2 via `filename_term` where applicable. Do not run page-1 on `g_root` in this phase (already excluded in Phase 2). Combined `infer_completion_date_for_file` follows §4 order when invoked ad hoc.

**Phase 3 backfill record (one-time, 2026-05-26)**

| Slice | Cohort | Method | Dated | Still no row |
|-------|--------|--------|-------|----------------|
| `g_root` (browser) | **131** | `goodnotes_last_modified` (`apply_completion_date_goodnotes`) | **131** | **0** |
| Undated priority `d_root` exam/exercise | **51** (after Phase 2 page-1/2) | `filename_term` (`apply_completion_date_filename_term`) | **35** | **16** (no term keyword) |
| **Browser completion inventory total** | **369** | Phases 2 + 3 | **353** | **16** |

- Goodnotes match breakdown (131): 122 `matched_leading_underscore_restored`, 8 `matched_raw_source`, 1 `matched_exact`; all used `last_modified` (no `updated_at` fallback needed).
- The **16** undated files are all `d_root` (listed in `.completion_date_page1/null_completion_dates_priority169.csv`) — PSLE titles, generic “Practice” names, 补充练习; no new rule matches without follow-up heuristics or manual rows.
- Registry rows beyond the on-disk browser index (~369) were **not** part of this backfill.

**Todo checklist**

- [x] Add [`completion_date/data/school_term_calendar.json`](../../completion_date/data/school_term_calendar.json) (2021–2026 MOE term end dates; completion = term end − 14 days).
- [x] [`completion_date/goodnotes.py`](../../completion_date/goodnotes.py): `last_modified` → SGT date; `updated_at` only if missing (`tests/test_completion_date_goodnotes.py`).
- [x] [`completion_date/filename_term.py`](../../completion_date/filename_term.py): term keyword groups + P1 anchors + school-year window (`tests/test_completion_date_filename_term.py`, `test_completion_date_school_year.py`).
- [x] One-off apply scripts: `apply_completion_date_goodnotes`, `apply_completion_date_filename_term`, `verify_completion_date_school_years`.
- [x] **Unified** `infer_completion_date_for_file` / `infer_completion_dates`: chain §4 methods (page-1 cache → Goodnotes → `filename_term` → `drive_modified` for d_root book).
- [x] **Unified batch CLI** `scripts/infer_completion_dates.py`: single entry with `--force`, `--force-manual`, `--dry-run`, root/doc_type filters; replaces ad hoc apply scripts for re-runs.
- [ ] **Coverage report** script — moved to [Future work](#future-work) (counts by `source`, `root_id`, still undated).

**Test checklist**

- [x] Goodnotes: matched → row; `not_found` / `ambiguous` → no row (`test_completion_date_goodnotes.py`).
- [x] Goodnotes: both timestamps present → `last_modified` wins (`test_completion_date_goodnotes.py`).
- [x] Filename: `WA1`, `Term 2`, `EYE` → calendar date; generic practice title → no row (`test_completion_date_filename_term.py`).
- [x] Winston `P5` path → school year 2025 for calendar lookup (`test_completion_date_school_year.py`).
- [x] Dry-run on apply scripts writes no registry rows (operator smoke).
- [x] `--force` / `--force-manual` on **unified** `infer_completion_dates`.

**Success / handoff criteria**

- [x] After Phase 2 + Phase 3 backfill, g_root completions get rows from Goodnotes when local DBs exist (**131/131**).
- [x] d_root exam/exercise filenames with WA/Term/EoY/测验 keywords get `filename_term` when page-1 did not set a row (**35** additional rows on priority undated set).
- [x] Browser cohort coverage: **353 / 369** with a row; **16** fail closed (documented).
- [x] Unified infer API + batch CLI for future re-runs without separate apply scripts.

**Remaining (Phase 3 integration — not blocking Phase 4 consumers)**

1. Optional: new heuristics for the **16** undated titles (PSLE year in filename, etc.) — separate from integration work.

### Phase 4 — Inventory and browser consumers

**Goal:** Surface `completion_date` on cards and update **Recent first** sort (§5.4).

**Todo checklist**

- [x] `files`: enrich `OnDiskMainPdfCard` with nullable `completion_date`, `completion_date_source`.
- [x] `files`: update `sort_main_pdf_cards` — dated first (desc), undated after (path tie-break); no `added_at` proxy.
- [x] `student_file_browser` + `buddy_console`: card date, tooltip, sort label.
- [x] Bump `FILES_VERSION` / package versions as needed (`files` v0.3.6, `student_file_browser` v0.1.7, inventory `files_version` 0.3.6).

**Test checklist**

- [x] Inventory JSON: row present → dates set; absent → `completion_date` null, `registry_added_at` still present.
- [x] Sort: two cards — inferred date orders before undated; undated not sorted by `added_at`.
- [x] Manual browser smoke on completion scope filter (Buddy Console v0.1.1, operator-verified 2026-05-27).

**Success / handoff criteria**

- [x] Student File Browser shows completion date when row exists; registration date shown separately.
- [x] **Completed (recent)** sort matches §5.4.
- [x] Buddy Console inventory smoke: completion scope, **Completed (recent)** sort, Completed vs Registered dates, source tooltips (2026-05-27).

### Phase 5 — Documentation updates

**Goal:** Make behavior discoverable and consistent with project docs (required doc phase per [TODO.md P1-1](../../../TODO.md)).

**Todo checklist**

- [x] Update `pdf_file_manager/README.md`, `SPEC.md`, `DATA_MODEL.md`, `CHANGELOG` (v0.3.30).
- [x] Document `data/school_term_calendar.json` maintenance expectations ([`completion_date/data/README.md`](../../completion_date/data/README.md)).
- [x] Update `files/SPEC.md` and `CHANGELOG` for card fields and sort (v0.3.6).
- [x] Update `student_file_browser` / `buddy_console` README/SPEC/DATA_MODEL as applicable.
- [x] Cross-link [L4_FILE_FRAMEWORK.md](../../../docs/L4_FILE_FRAMEWORK.md) and [student file browser sort proposal](../../../student_file_browser/docs/proposal/2-card-sort-order.md).
- [x] Update `.cursor/skills/pdf-file-manager/SKILL.md` for completion-date APIs.

**Test checklist**

- [x] Doc examples use `PdfFileManager` APIs, not direct registry SQL.
- [x] Worked example linked from SPEC or README.
- [x] Resolved decisions in this proposal match shipped behavior.

**Success / handoff criteria**

- [x] A future agent can find APIs and semantics from package + L4 docs.
- [x] `added_at` vs `completion_date` distinction is explicit in docs.

### Phase 6 — Final sweep

**Goal:** Per [TODO.md P1-1](../../../TODO.md), a **final sweep** means checking **completeness, accuracy, and consistency** across the proposal, code, tests, and docs, and confirming readiness to mark the proposal **implemented** (or to list remaining limitations as future work).

**Todo checklist**

- [x] Re-run `pytest` for `pdf_file_manager` (238 tests; unified infer + CLI).
- [ ] Manual smoke: infer + inventory for one g_root book, one d_root WA filename, one page-1 d_root exercise (worked example) — operator on live registry.
- [x] Confirm no registry fallback rows and no read-time `added_at` as `completion_date` (code + docs).
- [x] Confirm Goodnotes path uses `last_modified` before `updated_at` (`completion_date/goodnotes.py`, tests).
- [x] Review [Open Questions](#open-questions-and-decisions) — remaining items under Future work.
- [ ] Check [TODO.md](../../../TODO.md) for bullets this proposal was meant to complete.

**Test checklist**

- [x] `pdf_file_manager` test suite green (incl. `test_infer_completion_dates_cli.py`, batch dry-run).
- [x] Dry-run batch inference on a small cohort (`infer_completion_dates --dry-run`).

**Success / handoff criteria**

- [x] Proposal status **Implemented** (v0.3.22–v0.3.31).
- [x] Remaining items (coverage report script, post-scan hook, series sort) under Future work.

---

## Acceptance criteria

- `file_completion_dates` table and `PdfFileManager` read/write/infer APIs exist.
- Inference follows §4 matrix; **no row** when all steps fail; **no** `added_at` substitute.
- Goodnotes: `last_modified` first; SGT calendar dates.
- Page-1: multimodal visual inspection only; worked example `2025-10-22` reproducible.
- `school_term_calendar.json` covers 2021+ with P1 anchors for winston / emma / abigail.
- Inventory **Recent first** sort and display match §5.4.
- README/SPEC/L4 docs and CHANGELOG updated.

## Risks

| Risk | Mitigation |
|------|------------|
| Visual inspection cost / variability | Cursor agent (`model: inherit`); batch manifest + apply script; store `source_detail`; manual override; Python render-only in [`completion_date/page1.py`](../../completion_date/page1.py). |
| `school_term_calendar.json` drift | Operator-maintained file; `calendar_rule_id` in `source_detail`; version in git. |
| Goodnotes DB unavailable | Skip row; no guess; g_root exam/exercise may still use `filename_term`. |
| Filename heuristics wrong year | Derive `school_year` from student P1 + `Pn`; fail if student unknown. |
| Agents confuse `added_at` and `completion_date` | Separate card fields; docs; nullable `completion_date`. |

## Future work

- **Coverage report** CLI: counts by `source`, `root_id`, still undated (browser cohort).
- Optional `scan_for_new_files` inference hook (feature-flagged).
- Align [completion series](./15-completion-series-derived.md) ordering with `completion_date`.
- New heuristics for the **16** undated d_root completions (PSLE year in filename, etc.).
- Operator manual smoke on live registry (one g_root book, d_root WA, page-1 exercise) — see Phase 6 checklist.

---

## References

- Implemented Goodnotes lookup: [`goodnotes_metadata.py`](../../goodnotes_metadata.py), [proposal 16](./16-goodnotes-document-timestamps.md)
- Current inventory date/sort: [`on_disk_inventory.py`](../../../files/on_disk_inventory.py), [student file browser sort proposal](../../../student_file_browser/docs/proposal/2-card-sort-order.md)
- Completion series ordering (still uses `added_at` today): [proposal 15](./15-completion-series-derived.md) — consider aligning series sort with `completion_date` in a follow-up
