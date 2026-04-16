# AI Study Buddy — File System Management

> Status: **Proposal (v1)** — introduce a shared `ai_study_buddy.files` package for root resolution and leaf-folder traversal.
>
> Related docs: [ARCHITECTURE](./L1_ARCHITECTURE.md), [DATA_STRATEGY](./L3_DATA_STRATEGY.md), [MARKING_RESULT_ARTIFACT](./L4_MARKING_RESULT_ARTIFACT.md), `ai_study_buddy/pdf_file_manager/README.md`.

---

## Why This Proposal Exists

Multiple workflows need deterministic filesystem traversal under local synced roots:

- DaydreamEdu root (`DAYDREAMEDU_ROOT` or local config)
- GoodNotes root (`GOODNOTES_ROOT` or local config/sibling discovery)

Today, root-resolution and leaf-folder definitions are centered in `pdf_file_manager`, and command prompts replicate traversal logic in prose. This creates duplication and makes non-registry consumers depend on registry-adjacent code for basic path utilities.

This proposal creates a small, registry-agnostic filesystem utility layer under `ai_study_buddy.files`.

---

## Scope

### In scope

- Root resolution helpers for DaydreamEdu and GoodNotes.
- Generic leaf-folder traversal by direct file extensions.
- Policy-based exclusions via one absolute-path list of leaf folders.
- Full call-site migration from `pdf_file_manager` root resolvers to `ai_study_buddy.files`.

### Out of scope

- Registry lookups (`PdfFileManager`, scan roots, registered paths).
- File metadata classification.
- Any mutation workflow (move/compress/register/link).

---

## Package Layout

```text
ai_study_buddy/files/
  __init__.py
  roots.py
  leaf_folders.py
  README.md
  CHANGELOG.md
  SPEC.md
  TESTING.md
  tests/
    __init__.py
    conftest.py
    test_roots.py
    test_leaf_folders.py
    fixtures/
```

### `roots.py`

Owns root discovery for local synced folders:

- `resolve_daydreamedu_root() -> Path | None`
- `resolve_goodnotes_root() -> Path | None`

Resolution order remains consistent with current behavior:

1. environment variable (`DAYDREAMEDU_ROOT` / `GOODNOTES_ROOT`)
2. package-local config file (`local_*_root.txt`)
3. GoodNotes sibling discovery from DaydreamEdu parent (`.../GoodNotes`) for GoodNotes only

### `leaf_folders.py`

Owns generic traversal:

- `list_leaf_folders_under_root(root: Path, *, include_suffixes: set[str], excluded_leaf_folders: set[Path] = set()) -> list[Path]`

Where:

- **Leaf folder** means: a directory containing at least one direct file with suffix in `include_suffixes` (case-insensitive).
- `excluded_leaf_folders` contains absolute folder paths; if a discovered leaf path is in this set, exclude it.
- Parent-folder filtering is represented explicitly by listing excluded leaf folders as absolute paths under the root.

Optional convenience wrappers can encode current defaults:

- `list_daydreamedu_leaf_folders_under_root(...)`
- `list_goodnotes_leaf_folders_under_root(...)`

---

## Policy Profiles (Current Command Parity)

These are not hardcoded into the generic function, but represented as policy defaults:

- **GoodNotes report defaults**
  - include suffixes: `{".pdf"}`
  - excluded leaf folders (absolute): all leaf folders under root that are either:
    - equal to root (`"."`), or
    - under `root / "Coding"`, or
    - under any path containing a segment `Not completed` (case-insensitive)

- **DaydreamEdu report defaults**
  - include suffixes: `{".pdf"}`
  - excluded leaf folders (absolute): all leaf folders under root that are either:
    - equal to root (`"."`), or
    - have final folder name `Note` or `Notes` (case-insensitive)

This preserves deterministic behavior while keeping API generic for future `.md`, `.png`, etc.

---

## API Design Principles

1. **Registry-agnostic by construction**  
   `ai_study_buddy.files` must not import `PdfFileManager`.

2. **Deterministic traversal**  
   Return sorted absolute paths for stability in tests and reports.

3. **Explicit policy**  
   Avoid hidden behavior per root type in the generic function; pass exclusions explicitly or use named wrappers.

4. **Composable**  
   Registry-aware reports should compose as:
   - list qualifying leaf folders (`ai_study_buddy.files`)
   - compare to registry/scan roots (`pdf_file_manager`)

---

## Migration Plan

1. **Create new package**
   - add `ai_study_buddy/files/roots.py` and `leaf_folders.py`
   - export symbols from `ai_study_buddy/files/__init__.py`
   - move local root config files from `ai_study_buddy/pdf_file_manager/` to `ai_study_buddy/`:
     - `local_daydreamedu_root.txt`
     - `local_daydreamedu_root.example.txt`
     - `local_goodnotes_root.txt`
     - `local_goodnotes_root.example.txt`

2. **Full call-site migration (no compatibility shim)**
   - migrate all resolver imports to `ai_study_buddy.files.roots`
   - remove resolver definitions/exports from `pdf_file_manager`
   - fail migration if any resolver imports from `pdf_file_manager` remain

3. **Move command/script consumers**
   - update leaf-registry report commands/scripts to call `ai_study_buddy.files` traversal
   - keep registry comparison logic where it belongs (`pdf_file_manager`)

4. **Add tests**
   - root resolution tests (env var, local file, sibling discovery)
   - leaf traversal tests for:
     - extension filtering
    - excluded leaf folders (absolute paths)
     - deterministic ordering

5. **Verification and finalize**
   - run repository-wide import audit to confirm zero remaining resolver imports from `pdf_file_manager`.

---

## Detailed TODO Checklist (Implementation Monitoring)

### Phase 1 — Package scaffolding
- [x] Create `ai_study_buddy/files/__init__.py` with stable public exports.
- [x] Create `ai_study_buddy/files/roots.py` with `resolve_daydreamedu_root()` and `resolve_goodnotes_root()`.
- [x] Create `ai_study_buddy/files/leaf_folders.py` with `list_leaf_folders_under_root(...)`.
- [x] Move these four local root config files from `ai_study_buddy/pdf_file_manager/` to `ai_study_buddy/` using `mv`:
  - [x] `local_daydreamedu_root.txt`
  - [x] `local_daydreamedu_root.example.txt`
  - [x] `local_goodnotes_root.txt`
  - [x] `local_goodnotes_root.example.txt`

### Phase 2 — Core implementation
- [x] Implement root resolution parity with current behavior: env var -> local file -> (GoodNotes only) sibling discovery.
- [x] Update root resolver local-file lookup paths to the new `ai_study_buddy/local_*_root*.txt` locations.
- [x] Implement case-insensitive suffix filtering for direct files in `list_leaf_folders_under_root`.
- [x] Implement deterministic ordering of returned absolute leaf-folder paths.
- [x] Implement `excluded_leaf_folders` matching as exact absolute-path exclusions.
- [x] Add convenience wrappers for DaydreamEdu/GoodNotes policy defaults.

### Phase 3 — Profile helpers for command parity
- [x] Implement helper to compute GoodNotes excluded leaf folders as absolute paths (root, under `Coding`, any path containing `Not completed` segment).
- [x] Implement helper to compute DaydreamEdu excluded leaf folders as absolute paths (root, leaf basename `Note`/`Notes`).
- [x] Validate helper output against current cursor-command definitions on representative sample trees.

### Phase 4 — Compatibility and migration
- [x] Migrate all resolver imports to `ai_study_buddy.files.roots` (no compatibility re-export).
- [x] Update `pdf_file_manager` docs to reference `ai_study_buddy.files` as canonical owner.
- [x] Update leaf-registry report command implementations to call new traversal utilities.
- [x] Identify and migrate internal imports that should move from `pdf_file_manager` to `ai_study_buddy.files`.
- [x] Remove resolver exports/definitions from `pdf_file_manager` once import audit is clean.

### Phase 5 — Testing
- [x] Add unit tests for root resolution (env var, local file, sibling discovery, missing root).
- [x] Add unit tests for leaf detection with mixed extension cases (`.PDF`, `.pdf`, etc.).
- [x] Add unit tests for `excluded_leaf_folders` absolute-path filtering.
- [x] Add parity tests for GoodNotes and DaydreamEdu policy helper behavior.
- [x] Add regression tests ensuring deterministic return order.

### Phase 6 — Verification and rollout
- [x] Run targeted test suite for `ai_study_buddy.files` and `pdf_file_manager` integration.
- [x] Run end-to-end dry run of both leaf-registry reports and compare output with pre-refactor baseline.
  - **Done (filesystem leg):** On real configured roots, `list_daydreamedu_leaf_folders_under_root(resolve_daydreamedu_root())` returned **91** leaf folders; `list_goodnotes_leaf_folders_under_root(resolve_goodnotes_root())` returned **25** leaf folders. Read-only traversal; no registry mutations. No saved pre-refactor baseline artifact was available; parity is covered by unit tests plus this live smoke.
- [x] Document any expected diffs and confirm they are intentional.
  - **N/A for smoke:** No diff vs frozen baseline file. Intentional scope: package split and config path move only; leaf counts are data-dependent.
- [x] Run repository-wide `rg` check to verify zero imports of `resolve_daydreamedu_root`/`resolve_goodnotes_root` from `pdf_file_manager`.
- [x] Add rollback note: if regressions are found, restore resolver imports in callers from a single migration commit rollback.
  - **Rollback:** Revert the migration commit (or restore `ai_study_buddy/files/` removal and re-add resolver exports in `pdf_file_manager` if you must hotfix without git revert). Prefer `git revert <merge_sha>` so history stays clear.

---

## Risks and Mitigations

- **Risk: behavior drift during extraction**
  - Mitigation: parity tests that validate GoodNotes/DaydreamEdu profiles against current command definitions.

- **Risk: unclear ownership across packages**
  - Mitigation: enforce one-way dependency (`pdf_file_manager` -> `ai_study_buddy.files`, never reverse).

- **Risk: over-generalization too early**
  - Mitigation: keep v1 API minimal (roots + leaf listing only), add new primitives only when a second caller needs them.

---

## Decision

Adopt `ai_study_buddy.files` as the shared filesystem utility package for root resolution and leaf-folder traversal. Keep `pdf_file_manager` focused on registry semantics and compose filesystem traversal from the new package.

