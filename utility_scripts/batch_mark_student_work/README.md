# Batch marking student work (v3 harness)

Generic batch workflow to mark many completion PDFs in a folder through the same pipeline as interactive marking:

1. **Preflight** — registry lookup, skip already-marked, build a queue JSON under `queues/`
2. **Pilot** — one (or two) completions end-to-end before scaling
3. **Batch** — remaining items via detector → `mark-student-work-v3-batch-orchestrator` Task → validate → `batch_item_finalize.py`

**Agent rule:** Phase A/B = `batch_item_prep.py`; Phase E = `batch_item_finalize.py`. **Grading = one Task** to `mark-student-work-v3-batch-orchestrator` (prompt from `batch_item_grade_context.py`). That agent reads `.cursor/skills/mark-student-work-multi-agent-v3/SKILL.md` and spawns section graders. Parent must **not** call `marking-phase2-fast-pass-grader-v3` directly.

Old `_*.py` script names delegate to the public modules below.

Related skills/agents:

- [mark-student-work-multi-agent-v3](../../../.cursor/skills/mark-student-work-multi-agent-v3/SKILL.md)
- [math-question-section-detector](../../../.cursor/agents/math-question-section-detector.md)
- [english-paper-2-question-section-detector](../../../.cursor/agents/english-paper-2-question-section-detector.md)
- [pdf-file-manager](../../../.cursor/skills/pdf-file-manager/SKILL.md)

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Repo root** | Run commands from the monorepo root |
| **PdfFileManager** | Completions registered; each linked to a **template** |
| **Book policy** | Each template needs **`book_answer_mapping`** |
| **Exercise / English** | Usually **no** answer mapping — use `--policy exercise` or `english_exercise` (teacher-annotated) |
| **Completions** | `_c_*.pdf` (DaydreamEdu) and/or `c_*.pdf` (GoodNotes) in the scan folder |
| **Skip rule** | Per **completion `file_id`** — marks on GoodNotes `c_*.pdf` do **not** skip DaydreamEdu `_c_` copies |

---

## Policy presets (`policies.py`)

| `--policy` | Detector (Task `subagent_type`) | Default marking mode |
|------------|----------------------------------|----------------------|
| `book` | `math-question-section-detector` | `standard_mapped_answer` (answer-key pages) |
| `exercise` | `math-question-section-detector` | `teacher_annotated` |
| `english_exercise` | `english-paper-2-question-section-detector` | `teacher_annotated` |

Policy prompt text is stored in the queue JSON (`marking_policy`) and printed by `work_queue_status.py --next`.

**Book:** answer-key mapped (`book_answer_mapping`); standard math types from layout — see `BOOK_MARKING_POLICY_PROMPT` in `policies.py`.

---

## Scripts (run from repo root)

```bash
cd /Users/jarodm/github/jarodmeng/daydreamedu-scripts
BATCH=utility_scripts/batch_mark_student_work
```

| Script | Purpose |
|--------|---------|
| `build_work_queue.py` | Scan folder → write queue JSON |
| `build_priority_template_fqi_detector_queue.py` | Registry + study DB gap → template FQI detector queue |
| `export_priority_fqi_completion_manifest.py` | Completion-level manifest from priority FQI queue |
| `next_priority_detector_batch.py` | Next N pending template-FQI detector tasks (`--json`) |
| `orchestrate_template_fqi_detector_batch.py` | **FQI batch orchestrator CLI** (`status`, `prepare-batch`, `apply-batch`, `finalize-run`) |
| `_apply_priority_detector_batch_results.py` | Apply detector batch results to an FQI detector queue |
| `fqi_detector_marking_reference.py` | Build optional prior-marking prompt block + `prior_marking_reference.json` sidecar |
| `compare_fqi_vs_marking_question_page_map.py` | Compare template FQI vs marking `question_page_map` → manifest |
| `apply_fqi_compare_alignment.py` | Align marking IDs/pages from a compare manifest (index-aligned) |
| `harmonize_marking_ids_from_fqi.py` | Relabel marking `result_id`s via explicit `id_map` or completion manifest |
| `patch_fqi_question_split.py` | Split one FQI `question_info` row; validate + finalize |
| `backfill_question_page_map_from_fqi.py` | Overwrite `question_page_map` pages from FQI (`page_mismatch` rows) |
| `work_queue_status.py` | Summary; `--ord N` or `--next` for prompt context |
| `mark_done.py` | Manual status update (`--status done\|failed`) |
| `batch_item_prep.py` | Phase A/B: bundle, renders, `debug/batch_item_meta.json` |
| `batch_item_grade_context.py` | Emit single orchestrator Task spec (`--json`) for Step 3 |
| `batch_item_validate_phase2.py` | Gate: phase2 row count vs `sections[]` before finalize |
| `batch_item_persist_grade_debug.py` | Copy phase2 + section/routing traces into `bundle/debug/` |
| `batch_item_finalize.py` | Phase E: phase2 JSON → artifact + report + queue update |

Legacy `_*.py` names still work (thin shims).

### Build / refresh a queue

```bash
# Book unit practice (answer-key mapped)
python3 $BATCH/build_work_queue.py \
  --folder "/path/to/completion/.../Book/<book>/" \
  --policy book \
  --output $BATCH/queues/winston_model_drawing.json

# Math exercise worksheets (teacher-annotated)
python3 $BATCH/build_work_queue.py \
  --folder "/path/to/.../P6/Exercise/" \
  --policy exercise \
  --output $BATCH/queues/winston_p6_math_exercise.json

# English exercise worksheets
python3 $BATCH/build_work_queue.py \
  --folder "/path/to/.../P4/Exercise/" \
  --policy english_exercise \
  --output $BATCH/queues/emma_p4_english_exercise.json
```

`--marking-mode` overrides the policy default (`standard` | `teacher_annotated`).  
`--subject` overrides path inference (`math` | `english` | `chinese` | `science`).

### Build template FQI detector queue (DB gap slice)

For marked completions whose linked templates lack `file_question_info` (default filters: Winston P6/PSLE, Emma P4):

```bash
python3 $BATCH/build_priority_template_fqi_detector_queue.py \
  --output $BATCH/queues/my_fqi_gap_queue.json
```

Custom student/grade filters (repeatable; attaches `marking_reference` when completions exist):

```bash
python3 $BATCH/build_priority_template_fqi_detector_queue.py \
  --student-grade 'Abigail Meng:P1' \
  --student-grade 'Emma Meng:P1' \
  --output $BATCH/queues/my_fqi_gap_queue.json
```

Emit detector Tasks with marking context in the prompt (optional sidecar under `file_question_info/.../prior_marking_reference.json`):

```bash
python3 $BATCH/next_priority_detector_batch.py \
  --queue $BATCH/queues/my_fqi_gap_queue.json \
  --write-marking-reference-sidecars \
  --batch-size 5 --json
```

Prior marking is **non-binding** (completion-oriented pages; template PDF is authoritative). It is injected **only** via the per-task detector prompt and optional `prior_marking_reference.json` sidecar — **not** by editing `.cursor/agents/*-question-section-detector.md`.

### Full FQI detector run (manual loop)

Loop batches of **5** until no pending queue items:

```bash
python3 $BATCH/orchestrate_template_fqi_detector_batch.py status --queue $BATCH/queues/my_fqi_gap_queue.json

python3 $BATCH/orchestrate_template_fqi_detector_batch.py prepare-batch \
  --queue $BATCH/queues/my_fqi_gap_queue.json \
  --batch-size 5 --offset 0 \
  --output-task-spec-json /tmp/fqi_detector_batch_tasks.json

# … run detector Tasks from tasks[] …

python3 $BATCH/orchestrate_template_fqi_detector_batch.py apply-batch \
  --queue $BATCH/queues/my_fqi_gap_queue.json \
  --results-json /tmp/fqi_detector_batch_results.json

python3 $BATCH/orchestrate_template_fqi_detector_batch.py finalize-run
```

### FQI vs marking `question_page_map` (after detector run)

```bash
# 1) Compare (writes manifests/…json)
python3 $BATCH/compare_fqi_vs_marking_question_page_map.py \
  --queue $BATCH/queues/my_fqi_gap_queue.json \
  --output $BATCH/manifests/fqi_vs_marking_$(date +%Y-%m-%d).json

# 2) Index-aligned ID + page sync (skips exact_match; handles duplicate FQI ids via position)
python3 $BATCH/apply_fqi_compare_alignment.py \
  --report $BATCH/manifests/fqi_vs_marking_$(date +%Y-%m-%d).json

# 3) Explicit id maps (custom marking ids → schema-valid Qn), e.g. workbook TP-/AM- labels
python3 $BATCH/harmonize_marking_ids_from_fqi.py \
  --id-maps-manifest $BATCH/manifests/my_fqi_id_maps.json

# 4) Page-only backfill for rows still categorized page_mismatch
python3 $BATCH/backfill_question_page_map_from_fqi.py \
  --report $BATCH/manifests/fqi_vs_marking_$(date +%Y-%m-%d).json \
  --category page_mismatch
```

Re-run `compare_fqi_vs_marking_question_page_map.py` until `summary.categories.exact_match` covers the queue.

### Check progress

```bash
python3 $BATCH/work_queue_status.py --queue $BATCH/queues/emma_p4_math_exercise.json
python3 $BATCH/work_queue_status.py --queue $BATCH/queues/emma_p4_math_exercise.json --next
python3 $BATCH/work_queue_status.py --queue $BATCH/queues/emma_p4_math_exercise.json --ord 1
```

Quick counts:

```bash
python3 -c "
import json
from collections import Counter
from pathlib import Path
q = json.loads(Path('$BATCH/queues/emma_p4_math_exercise.json').read_text())
print(Counter(i['status'] for i in q['items']))
"
```

---

## Per-item loop (repeat until no pending)

```text
for each pending ord:
  1. <detector from queue>  (if needs_detection) — on TEMPLATE, not completion
  2. batch_item_prep.py --ord N --queue ...
  3. batch_item_grade_context.py --json → Task mark-student-work-v3-batch-orchestrator
  4. batch_item_validate_phase2.py → batch_item_persist_grade_debug.py
  5. batch_item_finalize.py --ord N --phase2-json ... --meta-json ...
```

```bash
python3 $BATCH/batch_item_prep.py --ord N --queue $BATCH/queues/<name>.json \
  > /tmp/batch_meta_N.json

python3 $BATCH/batch_item_grade_context.py --ord N --queue $BATCH/queues/<name>.json \
  --meta-json /tmp/batch_meta_N.json --output-phase2 /tmp/phase2_ordN.json --json \
  > /tmp/batch_grade_task_N.json

# Task: subagent_type + prompt from /tmp/batch_grade_task_N.json

python3 $BATCH/batch_item_validate_phase2.py \
  --meta-json /tmp/batch_meta_N.json --phase2-json /tmp/phase2_ordN.json \
  > /tmp/phase2_validate_N.json

python3 $BATCH/batch_item_persist_grade_debug.py \
  --meta-json /tmp/batch_meta_N.json \
  --phase2-json /tmp/phase2_ordN.json \
  --grade-spec-json /tmp/batch_grade_task_N.json \
  --validate-summary-json /tmp/phase2_validate_N.json

python3 $BATCH/batch_item_finalize.py --ord N \
  --phase2-json /tmp/phase2_ordN.json \
  --meta-json /tmp/batch_meta_N.json \
  --queue $BATCH/queues/<name>.json
```

On failure:

```bash
python3 $BATCH/mark_done.py --queue $BATCH/queues/<name>.json \
  --ord N --status failed --error "short description"
```

After detector only:

```bash
python3 $BATCH/mark_done.py --queue $BATCH/queues/<name>.json \
  --ord N --status pending --detector-done
```

---

## Queue JSON fields

Top-level: `generated_at`, `source_folder`, `student_email`, `subject`, `policy`, `detector`, `marking_mode`, `marking_policy`, `completion_globs`, `items[]`.

Per item: `ord`, `completion_path`, `completion_file_id`, `template_*`, `book_answer_pages`, `needs_detection`, `needs_marking`, `status`, `marking_artifact_path`, `error`.

Statuses: `pending`, `done`, `failed`, `skipped`, `blocked`.

---

## Saved queues (examples)

| File | Use case |
|------|----------|
| `queues/winston_model_drawing.json` | P6 Model Drawing book (35/35 done) |
| `queues/winston_p6_math_exercise.json` | Winston P6 math exercises |
| `queues/winston_p6_english_exercise.json` | Winston P6 English exercises |
| `queues/emma_p4_math_exercise.json` | Emma P4 math exercises (batch complete) |

FQI detector queues and `_*_session.json` files are **ephemeral** — generate with `build_priority_template_fqi_detector_queue.py`, delete when done.

### Manifests (FQI alignment)

Kept under `manifests/` (examples from the P1/P5 gap batch):

| File | Purpose |
|------|---------|
| `remaining_fqi_vs_marking_question_page_map_2026-05-29.json` | Final compare report (15/15 exact_match) |
| `remaining_fqi_id_maps_2026-05-29.json` | Custom `id_map` for workbook-style marking labels |
| `remaining_fqi_alignment_triage_2026-05-29.json` | Notes for resolved edge cases |

After a large FQI detector batch, optionally export completions:

```bash
python3 $BATCH/export_priority_fqi_completion_manifest.py \
  --queue $BATCH/queues/my_fqi_gap_queue.json \
  --output $BATCH/manifests/fqi_completions_$(date +%Y-%m-%d).json
```

---

## Outputs (per completion)

| Artifact | Location |
|----------|----------|
| Question sections | `ai_study_buddy/context/file_question_info/<subject_context>/<slug>/question_sections.json` |
| Marking bundle | `ai_study_buddy/context/marking_assets/<student>/.../<stem>__<timestamp>/` |
| Bundle debug traces | `.../<bundle>/debug/` — prep, orchestrator, phase2_fast_pass, routing (see batch skill table) |
| Marking result | `ai_study_buddy/context/marking_results/<student>/.../<stem>__<timestamp>.json` |
| Learning report | `ai_study_buddy/context/learning_reports/<student>/.../` |
| Queue state | `utility_scripts/batch_mark_student_work/queues/<name>.json` |

---

## Lessons learned

1. **GoodNotes vs DaydreamEdu** — different `file_id`s; preflight skip applies to the scanned folder only.
2. **`diagnosis.mistake_type`** — use `null`, not `""`, for correct answers.
3. **Invalid mistake_type** — `batch_item_finalize.py` normalizes via `queue_common.normalize_phase2_rows`.
4. **Detector on template** — not the student completion PDF.
5. **English finalize** — `english_finalize_required()` enables English-specific row prep when `subject=english` or `policy=english_exercise`.

---

## Exit criteria (batch complete)

```bash
python3 -c "
import json
from collections import Counter
from pathlib import Path
q = json.loads(Path('$BATCH/queues/emma_p4_math_exercise.json').read_text())
c = Counter(i['status'] for i in q['items'])
assert c.get('pending', 0) == 0
print('OK:', dict(c))
"
```

All items should be `done` (or explicitly `failed` / `skipped`).
