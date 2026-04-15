# Proposal 08: Standardize `PdfFileManager` Imports to Package Path

## Problem

`PdfFileManager` is currently imported in two styles:

- Legacy/bare style: `from pdf_file_manager import PdfFileManager`
- Package style: `from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager`

The legacy style often requires local `sys.path` mutation, which makes execution context fragile (script cwd, test runner path, and module invocation differences). This has led to inconsistent patterns across `marking`, `pdf_file_manager`, scripts, and tests.

## Goals

- Make package-style import the canonical pattern:
  - `from ai_study_buddy.pdf_file_manager.pdf_file_manager import ...`
- Remove unnecessary `sys.path` hacks that only exist to support bare imports.
- Keep migration low-risk with staged rollout and clear compatibility guardrails.
- Keep scripts and MCP entrypoints working during transition.

## Non-goals

- No behavior changes to registry logic, DB schema, or file operation semantics.
- No broad refactor of unrelated import/style issues outside `PdfFileManager` usage.

## Scope Clarification: Commands, Rules, and Skills

Because `pdf_file_manager` is operationally mediated by project commands/rules/skills, this migration includes those surfaces as first-class scope.

Required updates include:

- Cursor skills that instruct usage/import patterns for `PdfFileManager`
- Cursor commands that embed examples/snippets of `pdf_file_manager` invocation
- Workspace rules/agent guidance docs (for example `AGENTS.md`) that prescribe API usage patterns
- Utility docs referenced by skills/commands so guidance remains consistent end-to-end

Implementation must not be considered complete if core code is migrated but operational guidance still teaches legacy import patterns.

## Current State (Observed)

1. **Mixed import styles exist** in production code, scripts, tests, and docs.
2. **`sys.path.insert(...)` scaffolding** appears in multiple files to make legacy imports work.
3. **Some modules are already package-style**, confirming the new direction is viable.
4. **`pdf_file_manager_mcp.py` uses fallback imports** (relative first, then bare import) for runtime flexibility.

## Proposed Approach

### Phase 1: Package Surface and Compatibility

1. Add `ai_study_buddy/pdf_file_manager/__init__.py`.
2. Re-export primary symbols from `.pdf_file_manager` (manager class, key exceptions, key dataclasses).
3. Keep existing module file (`pdf_file_manager.py`) unchanged in behavior.

Why: this creates a clean package boundary and optional future simplification to:

`from ai_study_buddy.pdf_file_manager import PdfFileManager`

without forcing that change immediately.

### Phase 2: Production/Library Import Migration

1. Replace bare imports in app/library code with package-style imports.
2. Remove local path injection blocks that were only needed for bare imports.
3. Prioritize:
   - `ai_study_buddy/marking/migrate_learning_reports.py`
   - `ai_study_buddy/pdf_file_manager/scripts/*.py`
   - MCP server/module entrypoints where safe

### Phase 3: Tests Migration

1. Update test imports to package style.
2. Remove test-time `sys.path` setup that becomes unnecessary.
3. Keep only minimal fixture-related setup not tied to import hacks.

### Phase 4: Docs and Examples

This phase is treated as a **medium version bump** because it standardizes package boundaries and import contracts for downstream users/scripts.

1. Bump version in `README.md` and add a dedicated CHANGELOG entry documenting:
   - package standardization rationale
   - canonical import path(s)
   - deprecation of bare `from pdf_file_manager import ...` style
   - any transitional compatibility behavior and intended removal timeline
2. Update docs/snippets that still show bare imports:
   - `ai_study_buddy/pdf_file_manager/SPEC.md`
   - `ai_study_buddy/pdf_file_manager/docs/learnings/LEARNING_FROM_FIRST_RUN.md`
3. Add one canonical import snippet and note old style is deprecated.
4. Expand `README.md` with a dedicated **Import and Invocation** section that includes:
   - canonical Python import examples
   - recommended script/module invocation (`python3 -m ...`) guidance
   - compatibility notes for direct-file execution during transition
   - migration guidance for existing users (before/after examples)
5. Add or update a short migration note under `docs/learnings/` that captures:
   - why `sys.path` hacks were removed
   - expected behavior changes (if any) in execution context
   - troubleshooting guidance for common import failures
6. Update command/rule/skill documentation that references `pdf_file_manager`, including:
   - `.cursor/skills/pdf-file-manager/SKILL.md`
   - `.cursor/skills/process-book-answer-file/SKILL.md`
   - `.cursor/skills/scan-goodnotes-folder/SKILL.md`
   - `.cursor/commands/daydreamedu-leaf-registry-report.md`
   - `.cursor/commands/goodnotes-leaf-registry-report.md`
   - `AGENTS.md` guidance snippets if import examples are expanded or revised

### Phase 5: Deprecation Cleanup

1. Evaluate whether fallback import branches are still needed (e.g. in MCP helper modules).
2. Remove fallback branches once entrypoints are consistently module/package-invoked.

## Execution Details

### Canonical import target

Use:

`from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager`

and import related symbols from the same module path during migration.

### Handling scripts

Some scripts are run directly via file path. For these:

- Prefer package imports and run from repo root with `python3 -m ...` where practical.
- If direct-file invocation must stay supported in the short term, keep a small guarded compatibility fallback and mark it transitional.

### Handling MCP modules

For modules that currently support multiple invocation modes:

- Keep fallback behavior until runtime mode is confirmed stable.
- Add a TODO comment documenting planned fallback removal after migration validation.

## Risks and Mitigations

1. **Risk: Script breakage from invocation context**
   - Mitigation: migrate scripts incrementally; verify both direct and module invocation where needed.
2. **Risk: Test import failures**
   - Mitigation: migrate `conftest.py` and tests together; run test suite after each batch.
3. **Risk: Hidden dependency on path hacks**
   - Mitigation: remove `sys.path` blocks only after import replacement in same file; run targeted smoke tests.

## Implementation Status (2026-04-15)

This proposal has been implemented in the repository.

- Medium version bump shipped (`README.md` now `v0.3.0`) with `CHANGELOG.md` release entry.
- Runtime/scripts/MCP/tests migrated to package imports.
- Operational docs and Cursor command/skill guidance aligned.
- Validation gate passed:
  - `pytest ai_study_buddy/pdf_file_manager/tests` (226 passed)
  - `pytest ai_study_buddy/marking/tests` (21 passed)
  - grep checks for legacy runtime imports/path hacks are clean.

## Detailed TODO Checklist

### Phase 0: Baseline and Audit

- [x] Create a one-time inventory of all import callsites:
  - `from pdf_file_manager import ...`
  - `import pdf_file_manager`
  - `sys.path.insert(...)` blocks added only for pdf_file_manager imports
- [x] Classify each callsite by category:
  - runtime/library code
  - scripts
  - tests
  - MCP modules
  - docs/skills/commands/rules
- [x] Freeze and share migration scope list so no callsites are missed.

### Phase 1: Package Surface and Compatibility

- [x] Add `ai_study_buddy/pdf_file_manager/__init__.py`.
- [x] Re-export `PdfFileManager` and key public symbols from `.pdf_file_manager`.
- [x] Ensure exports are consistent with current external usage (exceptions, dataclasses used by callers).
- [x] Keep `pdf_file_manager.py` behavior unchanged.
- [x] Add/update inline note in `__init__.py` documenting canonical import direction.

### Phase 2: Runtime/Library Code Migration

- [x] Migrate `ai_study_buddy/marking/migrate_learning_reports.py` to package-style imports.
- [x] Migrate other runtime callsites to package-style imports.
- [x] Remove local `sys.path` mutations that become unnecessary in migrated runtime files.
- [x] Verify no behavior changes beyond import path updates.
- [x] Run focused smoke check for marking/report migration flow.

### Phase 3: Script and MCP Migration

- [x] Migrate `ai_study_buddy/pdf_file_manager/scripts/*.py` to package-style imports where appropriate.
- [x] For scripts that must remain directly executable, keep only minimal, explicit transitional fallback logic.
- [x] Document intended invocation mode (`python3 -m ...` preferred) per script.
- [x] Review `pdf_file_manager_mcp.py` and `pdf_file_manager_mcp_server.py` fallback behavior.
- [x] Add TODO comments for any temporary fallback branches with removal condition. (No temporary fallback retained after migration.)
- [x] Validate MCP server/module import startup after migration.

### Phase 3b: Tests Migration

- [x] Replace legacy imports in `ai_study_buddy/pdf_file_manager/tests/**` with package-style imports.
- [x] Remove no-longer-needed test path hacks from test modules and `conftest.py`.
- [x] Keep fixture path setup only where required for test data, not import resolution.
- [x] Run full `pytest ai_study_buddy/pdf_file_manager/tests`.
- [x] Run `pytest ai_study_buddy/marking/tests` for integration confidence.

### Phase 4: Medium Release Documentation and Guidance Update

- [x] Bump `pdf_file_manager` version in `README.md` (medium release).
- [x] Add top `CHANGELOG.md` entry for import/package standardization.
- [x] Update `README.md` with a dedicated **Import and Invocation** section:
  - canonical import path
  - `python3 -m ...` guidance
  - transitional compatibility notes
  - before/after migration examples
- [x] Update `DECISIONS.md` with an explicit decision record that package-style imports are canonical and bare imports are deprecated (including rationale and compatibility timeline).
- [x] Update `MCP.md` to align server invocation and migration guidance with package-standardized usage (including preferred module invocation and any transitional compatibility notes).
- [x] Update `SPEC.md` import snippets and remove legacy examples.
- [x] Update `docs/learnings/LEARNING_FROM_FIRST_RUN.md` (and add a migration learning note if needed).

### Phase 4b: Skills, Commands, and Rules Alignment

- [x] Update `.cursor/skills/pdf-file-manager/SKILL.md` to canonical import/invocation guidance.
- [x] Update `.cursor/skills/process-book-answer-file/SKILL.md` if it references legacy patterns. (Audit completed; no changes required.)
- [x] Update `.cursor/skills/scan-goodnotes-folder/SKILL.md` if it references legacy patterns. (Audit completed; no changes required.)
- [x] Update `.cursor/commands/daydreamedu-leaf-registry-report.md` examples/instructions.
- [x] Update `.cursor/commands/goodnotes-leaf-registry-report.md` examples/instructions.
- [x] Update `AGENTS.md` snippets if import examples or invocation guidance need alignment. (Audit completed; no changes required.)
- [x] Confirm no command/skill/rule still teaches `from pdf_file_manager import ...`.

### Phase 5: Deprecation Cleanup

- [x] Re-audit for remaining compatibility fallback branches.
- [x] Remove fallbacks that are no longer needed.
- [x] Keep only justified fallback paths with explicit deprecation timeline. (No compatibility fallback branch retained.)
- [x] Add final note in `CHANGELOG.md` if fallback removal is included in this release.

### Final Release Gate (Must-pass)

- [x] Static grep check is clean for runtime code:
  - no `from pdf_file_manager import ...`
  - no `import pdf_file_manager` (unless intentionally retained compatibility layer with comment)
- [x] No `sys.path` mutation remains solely for pdf_file_manager import resolution.
- [x] Test suites pass:
  - `pytest ai_study_buddy/pdf_file_manager/tests`
  - `pytest ai_study_buddy/marking/tests`
- [x] MCP startup/import smoke checks pass.
- [x] Skills/commands/rules/docs are aligned and reviewed.
- [x] Version + changelog + docs updates are included in the same release change set.

## Validation Plan

1. Static check:
   - Search for remaining `from pdf_file_manager import` and `import pdf_file_manager`.
   - Search for `sys.path.insert(...)` blocks tied to pdf_file_manager imports.
2. Operational-guidance check:
   - Audit skills/commands/rules docs for stale bare-import guidance or stale execution instructions.
   - Ensure all operational docs point to canonical package-style imports and intended invocation mode.
3. Tests:
   - `pytest ai_study_buddy/pdf_file_manager/tests`
   - `pytest ai_study_buddy/marking/tests`
4. Smoke checks:
   - Run key scripts that previously relied on bare imports.
   - Verify MCP-related entrypoints still import and start.

## Rollout Plan

1. Land package surface (`__init__.py`) and minimal compatibility re-exports.
2. Migrate production/library callsites.
3. Migrate tests.
4. Ship Phase 4 docs + medium version bump (`README.md` + `CHANGELOG.md`) including skills/commands/rules updates.
5. Remove deprecated fallbacks (separate follow-up if needed).

## Success Criteria

- No runtime code imports `PdfFileManager` via bare `from pdf_file_manager import ...`.
- No `sys.path` mutation remains solely for enabling bare pdf_file_manager imports.
- Test suites for `pdf_file_manager` and `marking` pass.
- Docs show only package-style imports.
- `README.md` version and `CHANGELOG.md` reflect a medium release that formalizes package-style import usage.
- Skills/commands/rules documentation is aligned with the canonical import standard and contains no stale bare-import examples.

## Out of Scope Follow-up (Optional)

- Add a lightweight lint or CI grep check to prevent reintroduction of bare imports.
- Add a short “import conventions” section in `pdf_file_manager/TESTING.md` or `ARCHITECTURE.md`.
