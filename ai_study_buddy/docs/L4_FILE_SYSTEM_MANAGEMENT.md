# AI Study Buddy — File System Management

> Status: **Implemented** — [`ai_study_buddy/files/`](../files/) **v0.2.0** (canonical API: [README](../files/README.md), [SPEC](../files/SPEC.md), [CHANGELOG](../files/CHANGELOG.md)).
>
> Related docs: [ARCHITECTURE](./L1_ARCHITECTURE.md), [DATA_STRATEGY](./L3_DATA_STRATEGY.md), [FILE_FRAMEWORK](./L4_FILE_FRAMEWORK.md), [MARKING_RESULT_ARTIFACT](./L4_MARKING_RESULT_ARTIFACT.md), `ai_study_buddy/pdf_file_manager/README.md`.

---

## Summary

`ai_study_buddy.files` is the shared filesystem utility package for:

- Resolving **DaydreamEdu** and **GoodNotes** sync roots (`roots.py`)
- Listing **leaf folders** (directories with direct files matching chosen suffixes) under policy profiles (`leaf_folders.py`)
- Optionally correlating on-disk leaves with **`pdf_registry.db`** via **`PdfFileManager`** (`pdf_registry_paths.py`)

`pdf_file_manager` owns registry semantics (scan, register, link, metadata). It **imports** `ai_study_buddy.files` for roots and leaf traversal; the dependency does not flow the other way for the core modules.

---

## Background

Multiple workflows need deterministic filesystem traversal under local synced roots:

- DaydreamEdu root (`DAYDREAMEDU_ROOT` or local config)
- GoodNotes root (`GOODNOTES_ROOT` or local config / sibling discovery)

Previously, root resolution and leaf-folder rules lived in `pdf_file_manager` or were duplicated in Cursor command prose. Extracting a registry-agnostic layer reduced coupling and gave non-registry tools (e.g. `root_pdf_browser`) a single import surface.

---

## Scope

### Shipped (v0.1.x–v0.2.0)

- Root resolution: `resolve_daydreamedu_root()`, `resolve_goodnotes_root()`
- Generic leaf traversal: `list_leaf_folders_under_root(...)`
- Profile wrappers: `list_daydreamedu_leaf_folders_under_root(...)`, `list_goodnotes_leaf_folders_under_root(...)` (with `exclude_not_completed` on GoodNotes)
- GoodNotes tree gate for browsers: `is_goodnotes_excluded_relative_path(...)`
- Local root config under `ai_study_buddy/local_*_root*.txt` (moved from `pdf_file_manager/`)
- Registry path correlation helpers in `pdf_registry_paths.py` (imports `PdfFileManager`; used by leaf-registry reports)
- Full call-site migration: no `resolve_*_root` imports from `pdf_file_manager`

### Out of scope (unchanged)

- Registry mutations (move, compress, register, link)
- File metadata classification (`file_type`, naming conventions beyond path sets)
- Non-PDF ingestion pipelines

---

## Package layout

```text
ai_study_buddy/
  local_daydreamedu_root.txt          # gitignored; see *.example.txt
  local_goodnotes_root.txt
  files/
    __init__.py                       # public re-exports
    roots.py
    leaf_folders.py
    pdf_registry_paths.py             # optional; imports PdfFileManager
    README.md
    SPEC.md
    CHANGELOG.md
    TESTING.md
    tests/
      test_roots.py
      test_leaf_folders.py
      test_pdf_registry_paths.py
      fixtures/
```

### `roots.py`

- `resolve_daydreamedu_root() -> Path | None`
- `resolve_goodnotes_root() -> Path | None`

Resolution order:

1. Environment variable (`DAYDREAMEDU_ROOT` / `GOODNOTES_ROOT`)
2. Gitignored file `ai_study_buddy/local_*_root.txt`
3. GoodNotes only: sibling `DaydreamEdu.parent / "GoodNotes"` when DaydreamEdu root is known

### `leaf_folders.py`

- `list_leaf_folders_under_root(root, *, include_suffixes, excluded_leaf_folders=...) -> list[Path]`
- `list_daydreamedu_leaf_folders_under_root(root) -> list[Path]`
- `list_goodnotes_leaf_folders_under_root(root, *, exclude_not_completed=True) -> list[Path]`
- `is_goodnotes_excluded_relative_path(rel, *, exclude_not_completed=True) -> bool`

**Leaf folder:** a directory with at least one **direct** file whose suffix is in `include_suffixes` (case-insensitive). Returns **sorted absolute** paths.

### `pdf_registry_paths.py` (v0.2.0)

Centralizes “filesystem leaf vs registry row” logic for DaydreamEdu / GoodNotes leaf-registry Cursor commands. Examples: `RegistryPathIndex.from_pdf_file_manager()`, `leaf_folder_registry_status`, `partition_*_leaf_folders`, `registration_buckets`. See [SPEC](../files/SPEC.md) and [L4_FILE_FRAMEWORK](./L4_FILE_FRAMEWORK.md).

---

## Policy profiles (command parity)

Profile defaults match `.cursor/commands/*-leaf-registry-report.md` and [L4_FILE_FRAMEWORK](./L4_FILE_FRAMEWORK.md):

| Profile | Suffixes | Exclusions |
|---------|----------|------------|
| **DaydreamEdu** | `{".pdf"}` | Root-as-leaf (`.` only when direct PDFs exist under sync root) |
| **GoodNotes (reports)** | `{".pdf"}` | Root-as-leaf; segment `^x[A-Z].*$`; segment `Not completed` (case-insensitive) when `exclude_not_completed=True` (default) |
| **GoodNotes (browse)** | `{".pdf"}` | Same except `exclude_not_completed=False` — includes WIP `Not completed` subtrees (`root_pdf_browser`) |

The generic `list_leaf_folders_under_root` stays policy-agnostic; wrappers and `is_goodnotes_excluded_relative_path` encode the profiles above.

---

## Design principles

1. **Core modules are registry-agnostic** — `roots.py` and `leaf_folders.py` do not import `PdfFileManager`.
2. **Registry correlation is explicit** — `pdf_registry_paths.py` may import `pdf_file_manager`; callers that only need paths use `roots` / `leaf_folders`.
3. **Deterministic traversal** — sorted absolute paths for stable tests and reports.
4. **Composable reports** — list leaves (`ai_study_buddy.files`) then compare to registry / scan roots (`pdf_registry_paths` + `PdfFileManager`).

---

## Consumers

| Consumer | Uses |
|----------|------|
| `pdf_file_manager` scripts / skills | `resolve_*_root`, leaf lists, `pdf_registry_paths` for reports |
| `.cursor/commands/*-leaf-registry-report.md` | Same policy as package wrappers |
| `root_pdf_browser` | Roots + GoodNotes browse profile (`exclude_not_completed=False`) |

---

## Implementation record

Migration from `pdf_file_manager`-embedded resolvers completed in Phases 1–6 (all checklist items done). Highlights:

- Live smoke (read-only): `list_daydreamedu_leaf_folders_under_root(resolve_daydreamedu_root())` → 91 leaves; `list_goodnotes_leaf_folders_under_root(resolve_goodnotes_root())` → 25 leaves (counts are machine/data-dependent).
- Import audit: zero `resolve_daydreamedu_root` / `resolve_goodnotes_root` imports from `pdf_file_manager`.
- Tests: `pytest ai_study_buddy/files/tests/` (see [TESTING](../files/TESTING.md)).

<details>
<summary>Phase checklist (collapsed)</summary>

### Phase 1 — Package scaffolding
- [x] `__init__.py`, `roots.py`, `leaf_folders.py`
- [x] Moved `local_*_root*.txt` from `pdf_file_manager/` to `ai_study_buddy/`

### Phase 2 — Core implementation
- [x] Root resolution parity; suffix filtering; deterministic ordering; profile wrappers

### Phase 3 — Profile helpers
- [x] GoodNotes / DaydreamEdu exclusion helpers; validated against command definitions

### Phase 4 — Migration
- [x] All resolver imports → `ai_study_buddy.files`; removed from `pdf_file_manager`

### Phase 5 — Testing
- [x] Unit + parity tests for roots, leaves, policies

### Phase 6 — Verification
- [x] Targeted pytest; live smoke; `rg` import audit; rollback note (revert migration commit)

</details>

---

## Version history (package)

| Version | Notes |
|---------|--------|
| **v0.2.0** | `pdf_registry_paths` — registry correlation for leaf-registry reports |
| **v0.1.3** | `is_goodnotes_excluded_relative_path` for tree browsers |
| **v0.1.2** | GoodNotes `exclude_not_completed` keyword on list wrapper |
| **v0.1.1** | Leaf profile parity with L4 framework + registry-report commands |
| **v0.1.0** | Initial package; migration complete |

Full detail: [CHANGELOG](../files/CHANGELOG.md).

---

## Decision (accepted)

`ai_study_buddy.files` is the canonical owner of root resolution and leaf-folder traversal. `pdf_file_manager` focuses on registry semantics and composes filesystem traversal from this package. Optional registry correlation lives in `pdf_registry_paths.py`, not in the core modules.
