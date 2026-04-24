# Hardening `*_file_path` In `marking_result` Artifacts

Status: Proposed

Audience: Maintainers of `ai_study_buddy/marking`, `ai_study_buddy/review_workspace`, and migration/workflow operators touching `ai_study_buddy/context/marking_results/**`.

## 1) Executive Summary

This proposal tightens validation for context file-path fields in canonical marking artifacts:

1. `context.attempt_file_path`
2. `context.template_file_path`
3. `context.unit_file_path`
4. `context.answer_file_path`

Today, schema validation is too permissive for these fields, and runtime validation only checks non-empty truthiness for some paths. This allows non-path text (for example markdown wrappers or inline notes) to be persisted in canonical JSON, which can break downstream path resolution and asset rendering.

This proposal introduces a strict file-path contract, enforces it in both JSON Schema and `validate_marking_artifact_dict(...)`, and provides a safe migration path for historical artifacts.

## 2) Problem Statement

Observed in repo (2026-04-23): one artifact stored an invalid `answer_file_path` with markdown and annotation text appended.

Example invalid value:

```text
`GOODNOTES_ROOT/Singapore Primary Math/<student_email>/P4/Exam/c_p4.math.wa1.6.pdf` (embedded answer key pages)
```

Why this is problematic:

1. Not a plain filesystem/tokenized path string.
2. Violates parser assumptions used by path-resolution and rendering workflows.
3. Mixes metadata commentary with path data.

## 3) Goals

1. Make canonical `*_file_path` fields machine-safe and parseable by contract.
2. Fail fast when non-path text is persisted.
3. Keep metadata notes in designated metadata fields, never in `*_file_path`.
4. Preserve backward compatibility for valid historical artifacts.

## 4) Non-Goals

1. Redesigning `MarkingContext` shape.
2. Changing placeholder token strategy (`GOODNOTES_ROOT`, `DAYDREAMEDU_ROOT`, `<student_email>`).
3. Auto-healing arbitrary malformed values at read time in core validator.

## 5) Proposed Contract For `*_file_path`

Each `*_file_path` must be a non-empty string and satisfy all of the following:

1. Represents exactly one PDF path string and ends with `.pdf`.
2. Contains no markdown syntax wrappers (for example backticks).
3. Contains no inline human annotation text after `.pdf`.
4. Contains no newline/control characters.
5. May be absolute (starts with `/`) or tokenized (`GOODNOTES_ROOT/...` or `DAYDREAMEDU_ROOT/...`).
6. May include `<student_email>` placeholder where expected.

Recommended regex (shared by schema and validator):

```regex
^(?:(?:GOODNOTES_ROOT|DAYDREAMEDU_ROOT|/)[^\r\n`]*\.pdf)$
```

Notes:

1. This pattern intentionally forbids backticks and ensures `.pdf` is terminal.
2. Metadata like "embedded answer key pages" belongs in `context.answer_mapping_source` or `context.answer_mapping_notes`.

## 6) Schema Changes

File: `ai_study_buddy/marking/schemas/marking_result.v1.schema.json`

Proposed changes:

1. Define reusable `$defs.file_path_pdf` string schema with:
   1. `type: "string"`
   2. `minLength: 1`
   3. `pattern: "^(?:(?:GOODNOTES_ROOT|DAYDREAMEDU_ROOT|/)[^\\r\\n`]*\\.pdf)$"`
2. In `context.properties`, explicitly define:
   1. `attempt_file_path: { "$ref": "#/$defs/file_path_pdf" }`
   2. `template_file_path: { "$ref": "#/$defs/file_path_pdf" }`
   3. `unit_file_path: { "$ref": "#/$defs/file_path_pdf" }`
   4. `answer_file_path: { "$ref": "#/$defs/file_path_pdf" }`

Schema-version recommendation:

1. Keep artifact schema version at `marking_result.v1.4` because semantics are unchanged.
2. Treat this as validation hardening, not a data-model feature bump.

## 7) Runtime Validator Changes

File: `ai_study_buddy/marking/core/artifact_schema.py`

Add explicit validation for all four context file-path fields.

Proposed behavior:

1. Field missing or non-string -> validation error.
2. Blank string -> validation error.
3. Backticks/newlines -> validation error.
4. Not ending in `.pdf` -> validation error.
5. Path prefix not in allowed set (`/`, `GOODNOTES_ROOT/`, `DAYDREAMEDU_ROOT/`) -> validation error.

Implementation approach:

1. Add a helper `_is_valid_context_pdf_path(value: str) -> bool` using compiled regex.
2. Call helper for each `*_file_path` in `validate_marking_artifact_dict(...)`.
3. Emit field-specific error messages (for actionable remediation).

## 8) Data Migration Plan

1. Audit all artifacts for invalid `*_file_path` values.
2. Produce inventory report under `ai_study_buddy/context/inventory_reports/`.
3. Apply deterministic normalization only when confidence is high:
   1. Strip surrounding markdown backticks.
   2. Remove trailing annotation text after terminal `.pdf`.
4. Re-validate all touched artifacts with hardened validator.
5. Commit migration with a clear one-time changelog note.

Current known offender (already identified):

1. `emma/singapore_primary_math/p4.math.wa1.6__20260414_121140.json` -> `context.answer_file_path`

## 9) Test Plan

Add/extend tests in `ai_study_buddy/marking/tests/test_artifact_core.py`:

1. Accept valid placeholder paths for all four fields.
2. Reject paths containing backticks.
3. Reject paths with trailing annotation after `.pdf`.
4. Reject non-PDF suffix.
5. Reject newline-containing paths.
6. Reject disallowed prefix.
7. Confirm error messages identify the failing field.

## 10) Rollout Plan

1. Land validator hardening and tests first.
2. Run audit script on existing artifacts.
3. Patch any malformed artifacts.
4. Land schema hardening.
5. Re-run workflow smoke checks that render answer assets from canonical JSON.

## 11) Acceptance Criteria

1. No artifact in `context/marking_results/**` contains malformed `*_file_path`.
2. Hardened validator rejects markdown/annotated path strings.
3. Schema includes explicit `*_file_path` constraints.
4. Existing valid artifacts continue to pass without modification.

## 12) Open Questions

1. Should we permit `GOODNOTES_ROOT` / `DAYDREAMEDU_ROOT` only, or also allow additional future root tokens?
2. Should the migration tool auto-fix only strict backtick/annotation cases, or any regex mismatch with a best-effort parser?
