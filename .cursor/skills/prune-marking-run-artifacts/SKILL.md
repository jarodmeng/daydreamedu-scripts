---
name: prune-marking-run-artifacts
description: Prune artifacts for older or unwanted marking runs. Identifies all companion files for a run (marking assets, marking result, learning report, review-state notes, amendments), performs a dry-run listing, creates a zip bundle of to-be-removed paths, and then executes safe removal via Trash semantics.
---

# Prune Marking Run Artifacts

Use this skill when the user asks to remove older/duplicate marking-run outputs while keeping a selected run.

## What uniquely identifies one marking run

Use this tuple as the run identity:

1. `student_slug`
2. `subject_context`
3. `attempt_basename`

`attempt_basename` is the canonical stem used across outputs and includes the timestamp suffix (`__YYYYMMDD_HHMMSS`), so it uniquely distinguishes multiple runs for the same attempt source.

## Artifact families to identify for a run

Given one marking run identity (`student_slug`, `subject_context`, `attempt_basename`), identify:

1. **Marking assets** directory  
   `ai_study_buddy/context/marking_assets/<student_slug>/<subject_context>/<attempt_basename>/`
2. **Marking result** JSON  
   `ai_study_buddy/context/marking_results/<student_slug>/<subject_context>/<attempt_basename>.json`
3. **Learning report** markdown  
   `ai_study_buddy/context/learning_reports/<student_slug>/<subject_context>/<attempt_basename> - Marking Report.md`
4. **Review notes / review state** companion JSON  
   `ai_study_buddy/context/student_review_states/<student_slug>/<subject_context>/<attempt_basename>.json`
5. **Amendments** companion JSON  
   `ai_study_buddy/context/marking_amendments/<student_slug>/<subject_context>/<attempt_basename>.json`

Notes:
- Items 4 and 5 are companion overlays keyed by the same artifact stem (`attempt_basename`), and may be absent.
- Always treat missing files as normal; do not fail pruning because optional companions are absent.

## Protocol: dry-run first (mandatory)

Before deleting or moving anything:

1. Resolve target run(s) and run to keep (if applicable).
2. Enumerate all existing files/directories in the five artifact families above.
3. Print a dry-run report grouped by run and artifact family:
   - `would_remove` (exact path list)
   - `missing_optional` (expected optional companions not present)
   - totals (file count and directory count)
4. Ask for confirmation when requested by user workflow, otherwise proceed only if user already instructed execution.

## Protocol: archive package for prune operation

After dry-run list is finalized, create **one zip per marking run** (not one combined zip for multiple runs).

Required naming (must identify the run):
- `tmp/prune_marking_run_<student_slug>_<subject_context>_<attempt_basename>.zip`

Example:
- `tmp/prune_marking_run_winston_singapore_primary_math_PP Math PSLE Part D P6 Topical Practice Percentage__20260421_194508.zip`

Requirements:
- Each run zip contains only that run's to-be-removed paths across all artifact families.
- Zip only paths listed in dry-run for that run.
- Preserve relative paths from repo root in the archive.
- Verify each zip was created successfully and is non-empty.

Then move each generated run zip to Trash:

- `mv "<zip_path>" ~/.Trash/`

This keeps the workspace clear while preserving a run-specific recovery package.

## Protocol: execute removal safely

Never use `rm`, `rm -r`, or `rm -rf`.

For each file/directory in `would_remove`, move to Trash:

- files: `mv "<file>" ~/.Trash/`
- directories: `mv "<dir>" ~/.Trash/`

After moves:

1. Verify each path no longer exists at original location.
2. Produce a post-action report:
   - `removed` paths
   - `already_missing` paths
   - `failed` paths (if any)

## Keep-latest heuristic (when pruning duplicates)

If multiple runs exist for the same attempt and the user says "prune older run":

1. Compare `attempt_basename` timestamp suffix.
2. Keep the newest suffix and prune older suffix(es), unless user explicitly chooses otherwise.

If timestamps conflict with user intent, ask which run to keep before execute phase.
