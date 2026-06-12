---
name: batch-mark-student-work
description: >-
  Batch queue + detector + mark-student-work-v3-batch-orchestrator (preflight, template
  detector, batch_item_prep, grade_context/validate, batch_item_finalize). Use when the
  user asks to mark, grade, or batch-mark student completions or a completion folder.
---

# Batch mark student work (queue → detector → v3 grade → finalize)

Resumable **folder/queue** driver for student-work marking. **Grading is not implemented in this skill** — after prep you **must** follow [mark-student-work-multi-agent-v3](../mark-student-work-multi-agent-v3/SKILL.md) for Phase 2 (and Phase 3 when needed), then run finalize scripts.

| Layer | Owner |
|-------|--------|
| Queue, policies, skip/pilot | This skill + `utility_scripts/batch_mark_student_work/` |
| Question-section detector | Task → detector from queue `detector` (math / english / science / chinese) |
| Phase A/B bundle prep | `batch_item_prep.py` (v3 workflow APIs) |
| **Phase 2 / Phase 3 grading** | **One** Task → `mark-student-work-v3-batch-orchestrator` (that agent reads v3 skill + spawns graders; writes `debug/` traces) |
| Phase 2 validate + debug persist | `batch_item_validate_phase2.py` → `batch_item_persist_grade_debug.py` |
| Phase E artifact + report | `batch_item_finalize.py` (v3 workflow APIs) |

**Read at session start:**

1. [batch_mark_student_work/README.md](../../../utility_scripts/batch_mark_student_work/README.md) — script reference

**Read when needed:**

- [pdf-file-manager](../pdf-file-manager/SKILL.md) — register/link templates, answer mappings
- Detector agents: `.cursor/agents/math-question-section-detector.md`, `.cursor/agents/english-paper-2-question-section-detector.md`, `.cursor/agents/science-question-section-detector.md`, `.cursor/agents/chinese-paper-2-question-section-detector.md`, `.cursor/agents/higher-chinese-paper-2-question-section-detector.md`

**Do not grade from this skill.** Step 3 uses agent `mark-student-work-v3-batch-orchestrator`, which reads [mark-student-work-multi-agent-v3](../mark-student-work-multi-agent-v3/SKILL.md) and spawns `marking-phase2-fast-pass-grader-v3` Tasks.

## Constants

```bash
REPO=/Users/jarodm/github/jarodmeng/daydreamedu-scripts
BATCH=$REPO/utility_scripts/batch_mark_student_work
```

All commands assume **repo root** as cwd.

## Policy → detector

| `--policy` | When | Task `subagent_type` (detector) | Marking mode |
|------------|------|----------------------------------|--------------|
| `book` | Book units with `book_answer_mapping` | `math-question-section-detector` | `standard_mapped_answer` |
| `exercise` | Math worksheets (P*/WA, topical) | `math-question-section-detector` | `teacher_annotated` |
| `english_exercise` | English Paper 2-style worksheets | `english-paper-2-question-section-detector` | `teacher_annotated` |
| `science_exercise` | Science exam/practice (MCQ + OEQ) | `science-question-section-detector` | `teacher_annotated` |
| `chinese_exercise` | Chinese / 高华 Paper 2 | `chinese-paper-2-question-section-detector` | `teacher_annotated` |

**Marking policy prompt:** presets live in `policies.py` (`PROMPT_BY_POLICY_KIND`). Override with top-level or per-item `marking_policy_prompt` (full string).

- **Detector Tasks:** paste policy text from `work_queue_status.py --ord N` (payload preset) or from the queue row’s `marking_policy_prompt` when set.
- **Grading Task:** authoritative prompt is embedded by `batch_item_grade_context.py` via `policy_prompt_for_item` (per-item `marking_policy_prompt` wins). Do not paraphrase — use the `prompt` field from `/tmp/batch_grade_task_N.json`.

### Bundled answer key (cross-file)

When answer pages live in a **different registered PDF** than the completion’s default linked answer file (e.g. RGPS P2 worksheets 1–3 keyed inside a set3 template), set **both** on the queue item:

- `answer_file_path` — absolute path to the answer-key PDF
- `book_answer_pages` — `{ "start_page", "end_page", "starts_mid_page"?, "ends_mid_page"? }` (1-based in that file)
- `marking_mode`: `standard_mapped_answer` (default when omitted)

`batch_item_prep.py` / `batch_item_finalize.py` render those pages and set `answer_mapping_source=bundled_exercise_answer_key`. `build_work_queue.py` does **not** populate these — hand-edit the queue JSON.

For RGPS supplementary worksheets, set `marking_policy_prompt` to `RGPS_BUNDLED_ANSWER_KEY_POLICY_PROMPT` from `policies.py`.

---

## Mode A — One completion

Use when the user names **one** completion PDF (path or “mark Emma’s P4 Math Revision 1”).

1. **Resolve path** via `PdfFileManager` (register first if missing — [pdf-file-manager](../pdf-file-manager/SKILL.md)).
2. **Preflight** — build a queue for the **parent folder** of that completion:

```bash
python3 $BATCH/build_work_queue.py \
  --folder "<parent_dir_of_completion>" \
  --policy <book|exercise|english_exercise|science_exercise|chinese_exercise> \
  --output $BATCH/queues/ad_hoc_<short_label>.json
```

3. Find **`ord`** for the target row (`completion_path` or `completion_file_id` in queue `items`).
4. If status is `skipped` (already marked), report artifact path and stop unless user wants re-mark.
5. If status is `blocked`, fix registry (template link / book mapping, or add per-item bundled answer key) then rebuild or edit queue.
6. Run **per-item loop** below for that `ord` only.

---

## Mode B — Folder batch

Use when the user names a **folder** of completions or an existing queue file.

1. **Build or refresh queue:**

```bash
python3 $BATCH/build_work_queue.py \
  --folder "<completion_folder>" \
  --policy <book|exercise|english_exercise|science_exercise|chinese_exercise> \
  --output $BATCH/queues/<name>.json
```

2. **Summary:**

```bash
python3 $BATCH/work_queue_status.py --queue $BATCH/queues/<name>.json
```

3. **Pilot (mandatory for new queues):** run the full per-item loop for **one** pending `ord` (prefer first with `needs_detection: false`, else first pending). **Stop for human review** before scaling unless the user waives the gate.
4. **Batch:** repeat for every `status=pending` item (sequential or parallel Task bands by `ord` range).

---

## Per-item loop (one `ord`)

Queue path: `$QUEUE`. Replace `N` with `ord`.

### Step 0 — Context

```bash
python3 $BATCH/work_queue_status.py --queue $QUEUE --ord N
```

Copy the printed **marking_policy** block into detector Task prompts. If the queue row has `marking_policy_prompt`, use that text instead. Grading prompt comes from `batch_item_grade_context.py` (Step 3a), not from retyping here.

### Step 1 — Detector (template only, if `needs_detection`)

Skip when `needs_detection` is false.

- **Task** `subagent_type`: value of queue `detector` (e.g. `math-question-section-detector`).
- **Input PDF:** `template_path` / `template_file_id` from the queue row — **never** the completion PDF.
- Include: marking policy text from the queue row, require validate + `finalize_question_sections_snapshot`.
- Confirm: `ai_study_buddy/context/file_question_info/<subject_context>/<slug>/question_sections.json` exists.

Then:

```bash
python3 $BATCH/mark_done.py --queue $QUEUE --ord N --status pending --detector-done
```

### Step 2 — Prep (v3 Phase A/B, deterministic)

```bash
python3 $BATCH/batch_item_prep.py --ord N --queue $QUEUE > /tmp/batch_meta_N.json
```

Keep `bundle_root`, `sections`, `phase2_batches`, and `artifact_json_path` from stdout (also `bundle/debug/batch_item_meta.json`). Do **not** re-run Phase A/B inline in chat — the script already calls v3 workflow APIs.

### Step 3 — Grade (single v3 orchestrator Task — mandatory)

The parent chat **must not** call `marking-phase2-fast-pass-grader-v3` directly. Grading goes through one orchestrator Task that reads the v3 skill and fans out section graders.

**3a — Build the orchestrator Task spec (deterministic):**

```bash
python3 $BATCH/batch_item_grade_context.py --ord N --queue $QUEUE \
  --meta-json /tmp/batch_meta_N.json \
  --output-phase2 /tmp/phase2_ordN.json \
  --json > /tmp/batch_grade_task_N.json
```

**3b — Launch exactly one grading Task** using fields from `/tmp/batch_grade_task_N.json`:

| Field | Value |
|-------|--------|
| `subagent_type` | `mark-student-work-v3-batch-orchestrator` (from JSON) |
| `description` | e.g. `v3 grade ord N` |
| `prompt` | full `prompt` string from JSON |
| `model` | **omit** |

Wait for the orchestrator to finish. It must write `/tmp/phase2_ordN.json` (or `output_phase2_path` from the spec).

**3c — Validate + persist debug traces (deterministic):**

```bash
python3 $BATCH/batch_item_validate_phase2.py \
  --meta-json /tmp/batch_meta_N.json \
  --phase2-json /tmp/phase2_ordN.json \
  > /tmp/phase2_validate_N.json

python3 $BATCH/batch_item_persist_grade_debug.py \
  --meta-json /tmp/batch_meta_N.json \
  --phase2-json /tmp/phase2_ordN.json \
  --grade-spec-json /tmp/batch_grade_task_N.json \
  --validate-summary-json /tmp/phase2_validate_N.json
```

If validation exits non-zero, **do not finalize** — re-run Step 3b (or fix a failed section inside the orchestrator subagent).

#### Debug folder (batch)

After prep + grade + persist, `bundle/debug/` should include:

| When | File |
|------|------|
| Prep | `batch_item_meta.json`, `context_resolution_provenance.json`, `v3_batch_prep_trace.json` |
| Grade context | `v3_batch_grade_spec.json` |
| Orchestrator agent | `v3_batch_orchestration_trace.json`, `phase2_section_*.json`, `phase2_orchestrator_summary.json` |
| Persist script | `phase2_fast_pass.json`, `phase2_section_execution_trace.json`, `phase2_phase3_routing.json`, `phase2_validate_gate.json` |
| Finalize | `phasee_finalize_prep.json`, `phasee_finalization_trace.json`, `run_state.json` |

Phase 3 files (`phase3_deep_dive.json`, `phase3_question_execution_trace.json`) only when the orchestrator ran with `--with-phase3`; pass `--phase3-enabled` to the persist script.

#### Forbidden in the parent chat (treat as harness failure)

- ❌ `Task` with `subagent_type="marking-phase2-fast-pass-grader-v3"` (graders are spawned **only** by the orchestrator agent)
- ❌ Writing `/tmp/phase2_ordN.json` by hand or from parent-chat transcription
- ❌ Skipping `batch_item_grade_context.py` / `batch_item_validate_phase2.py`
- ❌ Finalizing when phase2 row count ≠ `expected_phase2_row_count` in the grade spec

#### Phase 3 (optional — speed default)

Default batch path is **phase2-only** (`phase3_rows=[]` in finalize). `phase2_phase3_routing.json` still records which questions *would* have escalated.

To run Phase 3: add `--with-phase3` (or explicit remediation wording) to the orchestrator Task prompt from the parent; orchestrator writes `phase3_deep_dive.json`; parent passes `--phase3-enabled` to persist and non-empty phase3 rows to finalize (advanced — not the default loop).

### Step 4 — Finalize (v3 Phase E, deterministic)

```bash
python3 $BATCH/batch_item_finalize.py --ord N \
  --phase2-json /tmp/phase2_ordN.json \
  --meta-json /tmp/batch_meta_N.json \
  --queue $QUEUE
```

This validates, writes marking artifact + learning report, updates queue to `done`, and dual-writes to `study_buddy.db` when enabled.

### On failure

```bash
python3 $BATCH/mark_done.py --queue $QUEUE --ord N --status failed --error "<short reason>"
```

Do not skip finalize scripts; they bind `marking_asset` to the real bundle (v0.3.12+).

---

## Scaling patterns

| Pattern | When |
|---------|------|
| Sequential in chat | &lt;10 items, debugging |
| Parallel Task bands | e.g. ord 4–15, 16–27 — each subagent runs its range **sequentially** |
| Prep/finalize always via scripts | Never hand-write marking JSON paths or timestamps |

After each finalize, optionally spot-check:

- `marking_results/<student>/.../*.json`
- Matching `learning_reports/.../* - Marking Report.md`
- Student File Browser (port 8771) if running

---

## Exit criteria (batch)

```bash
python3 -c "
import json
from collections import Counter
from pathlib import Path
q = json.loads(Path('$QUEUE').read_text())
print(Counter(i['status'] for i in q['items']))
assert Counter(i['status'] for i in q['items']).get('pending', 0) == 0
"
```

Target: all `done`, or explicit `failed` / `skipped` with reasons reported to the user.

---

## Gotchas

1. **Detector on template**, not completion.
2. **GoodNotes `c_*.pdf` vs DaydreamEdu `_c_*.pdf`** — different `file_id`s; skip counts apply to the scanned folder only.
3. **Phase 2 = orchestrator Task only** — parent spawns `mark-student-work-v3-batch-orchestrator`, not graders directly.
4. **Phase 2 invalid `mistake_type`** — finalize normalizes common aliases; prefer valid enum or `null`.
5. **English** — use `english_exercise` policy; indices may use `Q51(2020)` under `english-v1.4`.
6. **Re-mark** — same completion `file_id` may be `skipped` in preflight; user must delete/prune old artifact or use a fresh queue build after prune ([prune-marking-run-artifacts](../prune-marking-run-artifacts/SKILL.md)).
7. **Bundled answer key** — requires both `answer_file_path` and `book_answer_pages` on the queue item; grade against answer-key pages, not red teacher ink on the completion (unless policy says otherwise).
