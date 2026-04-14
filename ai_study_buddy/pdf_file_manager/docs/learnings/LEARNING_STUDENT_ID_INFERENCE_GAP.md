### Overview

This learning documents a metadata gap discovered while auditing the local `pdf_file_manager` registry in March 2026: some files under Winston's student-scoped folders had correct `subject`, `doc_type`, `is_template`, and `metadata`, but `student_id` was still null.

The issue was visible in both `DaydreamEdu` and `GoodNotes` trees and was subtle because other Winston files were already correct. That made it look like partial corruption at first, but the operation log showed a more specific workflow problem.

### What happened

An audit of Winston-scoped paths found:

- `644` files under `.../<student email>/...`
- `490` with `student_id='winston'`
- `154` with `student_id` missing

The missing set clustered into three batches:

- `2026-03-09`: `73` files under `DaydreamEdu/.../Singapore Primary English/<student email>/...`
- `2026-03-10`: `49` files under `DaydreamEdu/.../Singapore Primary Science/<student email>/...`
- `2026-03-11`: `32` files under `GoodNotes/.../<student email>/...`

The operation log showed these files were first created by normal `register`/`compress` activity rather than later metadata updates.

### Root cause

The bug was not a bad one-off migration. It was a gap in inference logic:

- `_infer_from_path(...)` inferred `subject`, `doc_type`, `is_template`, and metadata fields like `grade_or_scope`
- but it did not infer `student_id`
- `scan_for_new_files(roots=[...])` treated explicit roots as `(root_path, None)` rather than consulting configured scan-root metadata
- GoodNotes ad hoc scans had no configured scan roots at all

As a result, any workflow that did not explicitly pass `student_id` could still classify the file correctly while leaving `student_id` null.

### Fix proposal

Make student inference a first-class part of registration and scan processing:

1. Add a helper that maps a path segment containing a registered student email to that student's `student_id`.
2. Use that helper in `register_file(...)` when `student_id` is not explicitly provided.
3. Use that helper in `scan_for_new_files(...)` so explicit-root scans and rescans can repair missing `student_id` values.
4. Preserve explicit values as higher priority:
   - configured `scan_root.student_id`
   - explicit `register_file(..., student_id=...)`
   - inferred-from-path fallback
5. Add regression tests for:
   - explicit-root scans of student folders
   - GoodNotes scans under student folders
   - direct registration of a path under a known student email folder

### Implementation status

Implemented in the utility after this learning was recorded.

**Follow-up (v0.2.8):** Explicit `roots=[...]` scans now join resolved paths to configured `scan_roots`, so a folder added as a scan root with `student_id` keeps that assignment when passed as an override. `dry_run=True` scan results use full path inference on returned `PdfFile` previews (see `CHANGELOG.md` v0.2.8).
