# Batch marking student work (v3 harness)

Generic batch workflow to mark many completion PDFs in a folder through the same pipeline as interactive marking:

1. **Preflight** — registry lookup, skip already-marked, build a queue JSON under `queues/`
2. **Pilot** — one (or two) completions end-to-end before scaling
3. **Batch** — remaining items via detector → v3 marking → canonical artifacts

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

**Book (Model Drawing):** SAQ-only, 2 marks single-part / 1 mark per (a)/(b) sub-part — see `BOOK_MARKING_POLICY_PROMPT` in `policies.py`.

---

## Scripts (run from repo root)

```bash
cd /Users/jarodm/github/jarodmeng/daydreamedu-scripts
BATCH=utility_scripts/batch_mark_student_work
```

| Script | Purpose |
|--------|---------|
| `build_work_queue.py` | Scan folder → write queue JSON |
| `work_queue_status.py` | Summary; `--ord N` or `--next` for prompt context |
| `mark_done.py` | Manual status update (`--status done\|failed`) |
| `batch_item_prep.py` | Phase A/B: bundle, renders, `debug/batch_item_meta.json` |
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
  3. marking-phase2-fast-pass-grader-v3  → /tmp/phase2_ordN.json
  4. batch_item_finalize.py --ord N --phase2-json ... --meta-json ...
```

```bash
python3 $BATCH/batch_item_prep.py --ord N --queue $BATCH/queues/<name>.json \
  > /tmp/batch_meta_N.json

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

---

## Outputs (per completion)

| Artifact | Location |
|----------|----------|
| Question sections | `ai_study_buddy/context/file_question_info/<subject_context>/<slug>/question_sections.json` |
| Marking bundle | `ai_study_buddy/context/marking_assets/<student>/.../<stem>__<timestamp>/` |
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
