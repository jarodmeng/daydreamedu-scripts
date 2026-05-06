# Proposal 1: Reorganize `learning_db` package layout (marking-aligned)

## Status

Implemented (2026-05-06).

Decision update (2026-05-06): strict cleanup approved — full internal migration to `core/`, `read/`, `ingest/`, and `cli/` paths with legacy root module removal.

## Goal

Make the [`learning_db`](../../) package easier to navigate by **mirroring the same structural convention as [`marking`](../../../marking/)**:

- **Reference markdown** stays at the **package root** (`README.md`, `CHANGELOG.md`, `SCHEMA.md`, `OPERATIONS.md`), similar to marking’s `README`, `SPEC`, `ARCHITECTURE`, `TESTING`, `CHANGELOG`.
- **Implementation Python** moves into **purposeful subpackages** (`core/`, `read/`, `ingest/`, `cli/`), similar to marking’s `core/`, `review/`, `assets/`, `file_question_info/`, `workflows/`.

The package root should present a **small, intentional surface** (thin modules and docs), not a flat mix of every subsystem.

## Motivation

Today, many `.py` modules live beside top-level docs under `learning_db/`, which reads as cluttered compared to `marking/`. Consolidating code under subpackages improves scanability and signals boundaries (connection/repository vs reads vs import/dual-write vs CLI-style tools) without changing behavior.

## Non-goals

- Changing SQLite schema, migrations SQL files, or canonical JSON contracts.
- Preserving legacy root-module `python -m ai_study_buddy.learning_db.<module>` entrypoints. (Strict-cleanup decision migrates to explicit submodule entrypoints and updates docs.)
- Moving `migrations/` away from `ai_study_buddy/learning_db/migrations/` (tests and ops assume that location).
- Replacing `validate_actor("script:ai_study_buddy.learning_db…")` strings unless we deliberately migrate audit identity (default: **leave unchanged**).

## Target layout

```text
ai_study_buddy/learning_db/
  __init__.py
  README.md
  CHANGELOG.md
  SCHEMA.md
  OPERATIONS.md
  docs/
    learnings/
    proposal/
      01-package-layout-reorganization.md   # this document
  migrations/
  tests/
  core/
    __init__.py
    connection.py
    config.py
    repository.py
    migrate.py           # implementation (see constraints)
  read/
    __init__.py
    read_documents.py
    read_marking.py
    learning_repository.py
  ingest/
    __init__.py
    dual_write.py
    import_context_json.py
  cli/
    __init__.py
    backup_study_buddy_db.py
    validate_study_buddy_db.py
    field_coverage.py
    reader_parity.py
    dual_write_stats.py
    write_boundary_audit.py
```

Subgroup names are now fixed by agreement (`core/`, `read/`, `ingest/`, `cli/`); the important part remains **clustering by responsibility**.

## Module mapping (agreed plan)

| Current (package root) | Proposed home |
|------------------------|---------------|
| `connection.py`, `config.py`, `repository.py` | `core/` |
| `migrate.py` (implementation) | `core/migrate.py` |
| `read_documents.py`, `read_marking.py`, `learning_repository.py` | `read/` |
| `dual_write.py`, `import_context_json.py` | `ingest/` |
| `backup_study_buddy_db.py`, `validate_study_buddy_db.py`, `field_coverage.py`, `reader_parity.py`, `dual_write_stats.py`, `write_boundary_audit.py` | `cli/` |

## Constraints and compatibility

### `python -m` entrypoints

Use explicit submodule entrypoints:

- `python3 -m ai_study_buddy.learning_db.core.migrate`
- `python3 -m ai_study_buddy.learning_db.ingest.import_context_json`
- `python3 -m ai_study_buddy.learning_db.cli.validate_study_buddy_db`
- `python3 -m ai_study_buddy.learning_db.cli.backup_study_buddy_db`
- `python3 -m ai_study_buddy.learning_db.cli.field_coverage`

Root compatibility shims are removed under strict cleanup. All internal callsites migrate to explicit submodule paths.

### Migration directory resolution

The migrate module resolves SQL via the implementation at [`core/migrate.py`](../../core/migrate.py). `_migration_dir()` must point at package-level **`learning_db/migrations/`** (e.g. `Path(__file__).resolve().parent.parent / "migrations"`).

### Patch targets in tests

[`tests/test_dual_write_semantics.py`](../../tests/test_dual_write_semantics.py) patches dotted paths such as `ai_study_buddy.learning_db.ingest.import_context_json.upsert_marking_result`. Under strict cleanup, patch targets must reference relocated modules directly.

## Surface area (repo files to touch)

Strict cleanup selected: update every internal importer of `ai_study_buddy.learning_db.*` to relocated module paths, then remove root shim modules.

### Inside `learning_db`

- New subpackage `__init__.py` files.
- All moved implementation modules (imports rewritten).
- [`__init__.py`](../../__init__.py) public re-exports adjusted if needed.

### Tests under `learning_db/tests/`

Files that import `learning_db` today (each may need import or patch-path updates):

- `test_dual_write_semantics.py`
- `test_dual_write_snapshots.py`
- `test_dual_write_from_canonical.py`
- `test_file_question_info_persistence.py`
- `test_import_context_json.py`
- `test_import_idempotency.py`
- `test_import_scope.py`
- `test_migrate.py`
- `test_phase2_reads.py`
- `test_reader_parity_module.py`

### `marking/` consumers

Production:

- `marking/core/artifact_lookup.py`
- `marking/core/artifact_writer.py`
- `marking/review/repository.py`
- `marking/review/payload_reader.py`
- `marking/file_question_info/api.py`
- `marking/file_question_info/post_write.py`

Tests:

- `marking/tests/test_artifact_core.py`
- `marking/tests/test_file_question_info.py`

Filesystem reference only (typically **unchanged** if `migrations/` stays put):

- `marking/tests/test_review_workspace_amendments.py` (`Path("…/learning_db/migrations/001_initial_schema.sql")`)

### Documentation

Update path mentions if file locations or narratives change:

- [`README.md`](../../README.md), [`OPERATIONS.md`](../../OPERATIONS.md)
- [`docs/learnings/*.md`](../learnings/)
- [`ai_study_buddy/docs/L4_LOCAL_LEARNING_DB.md`](../../../docs/L4_LOCAL_LEARNING_DB.md)
- Historical pointers in `marking/CHANGELOG.md`, `marking/docs/proposal/14-*.md`, etc.

Verification (suggested):

```bash
rg 'ai_study_buddy\.learning_db' --glob '*.py'
rg 'learning_db/(connection|migrate|dual_write|import_context_json|repository|read_)' --glob '*.md'
PYTHONPATH=. python3 -m pytest ai_study_buddy/learning_db/tests
PYTHONPATH=. python3 -m pytest ai_study_buddy/marking/tests/test_artifact_core.py \
  ai_study_buddy/marking/tests/test_file_question_info.py
```

## Acceptance criteria

- [x] Package root contains only `__init__.py` (plus docs/directories), with no legacy shim modules.
- [x] Documentation uses explicit submodule entrypoints (`core.migrate`, `ingest.import_context_json`, `cli.*`).
- [x] `apply_migrations` continues to apply files from `ai_study_buddy/learning_db/migrations/`.
- [x] `ai_study_buddy/learning_db/tests` and the listed `marking` tests pass.
- [x] No stale relative links in `docs/learnings/` after file moves.

## Implementation phases (detailed)

### Phase 0 – Prep and inventory

- **Todos (checklist)**
  - [x] Inventory current root `.py` modules in `learning_db/` and confirm the mapping table above is complete.
  - [x] Inventory all internal and external import sites and documented `python -m` commands (can lean on the **Surface area** section).
  - [x] Capture a short table of supported `python3 -m ai_study_buddy.learning_db.*` entrypoints in `README.md`/here for quick regression checks.
- **Tests/checks (checklist)**
  - [x] `PYTHONPATH=. python3 -m pytest ai_study_buddy/learning_db/tests`
  - [x] `PYTHONPATH=. python3 -m pytest ai_study_buddy/marking/tests/test_artifact_core.py ai_study_buddy/marking/tests/test_file_question_info.py`
- **Success criteria**
  - All of the above tests pass on the pre-refactor layout.
  - The inventory matches the repo (no surprise imports or commands later).

### Phase 1 – Introduce subpackages and duplicate implementations

- **Todos (checklist)**
  - [x] Create `core/`, `read/`, `ingest/`, and `cli/` subpackages with `__init__.py` files.
  - [x] Copy (not move yet) root implementations into those subpackages following the mapping table.
  - [x] Update internal imports inside the new subpackage modules to use `ai_study_buddy.learning_db.core/read/ingest/cli` as appropriate.
  - [x] In `core/migrate.py`, update `_migration_dir()` to resolve `learning_db/migrations/` via the package, not `__file__`-sibling.
- **Tests/checks (checklist)**
  - [x] Import each new subpackage module in isolation (REPL or tiny smoke tests) to ensure no import cycles or missing dependencies.
  - [x] Re-run the `learning_db` test suite; at this stage, root modules are still the primary entrypoints so behavior should be unchanged.
- **Success criteria**
  - Both root and subpackage implementations coexist; only subpackages are new.
  - No import errors when importing `ai_study_buddy.learning_db.core`, `.read`, `.ingest`, or `.cli`.

### Phase 2 – Flip imports to subpackages

- **Todos (checklist)**
  - [x] Update internal imports across `learning_db/` (including tests) to point at the new subpackages.
  - [x] Update all `marking/` imports to use the new subpackage paths.
  - [x] Update any `patch(\"...\")` targets (especially in dual-write semantics tests) to relocated modules.
- **Tests/checks (checklist)**
  - [x] Re-run all `learning_db` tests.
  - [x] Re-run the targeted `marking` tests that exercise DB paths.
  - [x] Manually exercise each documented `python -m ai_study_buddy.learning_db.*` command from README/OPERATIONS/L4 docs.
- **Success criteria**
  - Internal codepaths no longer import legacy root modules.
  - All test patch targets hit relocated modules directly.

### Phase 3 – Remove legacy root modules

- **Todos (checklist)**
  - [x] Confirm that all logic-bearing code lives under `core/`, `read/`, `ingest/`, or `cli/`.
  - [x] Remove legacy root modules (`migrate.py`, `dual_write.py`, `import_context_json.py`, etc.) after importer migration.
- **Tests/checks (checklist)**
  - [x] `rg` for distinctive implementation-only strings to confirm they do not exist in root modules anymore.
  - [x] Repeat the Phase 2 test matrix.
- **Success criteria**
  - There is a single implementation source of truth per concern (no drift between root and subpackages).
  - Legacy root module files are absent.

### Phase 4 – Documentation and final verification

- **Todos (checklist)**
  - [x] Update `learning_db/README.md`, `CHANGELOG.md`, `OPERATIONS.md`, and `L4_LOCAL_LEARNING_DB.md` to reflect the new directory layout and confirm command examples.
  - [x] Update any `docs/learnings/*.md` that embed file paths (e.g. `field_coverage.py`) to the new locations.
  - [x] Optionally mark this proposal’s status as Implemented and add any deviations from the original mapping.
- **Tests/checks (checklist)**
  - [x] `rg` across `*.md` for old file paths or module names (`learning_db/(connection|migrate|dual_write|import_context_json|repository|read_)`).
  - [x] Final pass of the `learning_db` and targeted `marking` test suites.
- **Success criteria**
  - All docs and diagrams match the implemented layout.
  - No stale references to removed or relocated modules.

## References

- Layout precedent: [`ai_study_buddy/marking/`](../../../marking/)
- Operational context: [`ai_study_buddy/docs/L4_LOCAL_LEARNING_DB.md`](../../../docs/L4_LOCAL_LEARNING_DB.md)
