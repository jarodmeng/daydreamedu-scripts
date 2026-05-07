# ai_study_buddy.files

**Version: v0.2.0**

Small helpers for local synced study material: resolve DaydreamEdu and GoodNotes roots from environment or gitignored config files, and list **leaf folders** (directories with direct files matching chosen suffixes) with optional profile-specific exclusions.

The core modules (`roots`, `leaf_folders`) are **registry-agnostic**. For correlating those on-disk leaves with **`pdf_registry.db`** rows via **`PdfFileManager`**, use **`pdf_registry_paths`** — centralized path-string sets and per-leaf status (same rules as `.cursor/commands/*-leaf-registry-report.md`).

---

## Modules

| Module | Role |
|--------|------|
| [`roots.py`](./roots.py) | `resolve_daydreamedu_root()`, `resolve_goodnotes_root()` |
| [`leaf_folders.py`](./leaf_folders.py) | `list_leaf_folders_under_root()`, profile wrappers for DaydreamEdu / GoodNotes |
| [`pdf_registry_paths.py`](./pdf_registry_paths.py) | `RegistryPathIndex.from_pdf_file_manager()`, leaf vs registry / scan-root helpers (optional; imports `PdfFileManager`) |

Public re-exports: [`__init__.py`](./__init__.py).

---

## Local configuration (not in Git)

Paths are machine-specific. Prefer gitignored files under `ai_study_buddy/` (sibling to this package directory):

| Purpose | Env (highest priority) | File |
|---------|------------------------|------|
| DaydreamEdu root | `DAYDREAMEDU_ROOT` | [`../local_daydreamedu_root.txt`](../local_daydreamedu_root.txt) (copy from [`../local_daydreamedu_root.example.txt`](../local_daydreamedu_root.example.txt)) |
| GoodNotes root | `GOODNOTES_ROOT` | [`../local_goodnotes_root.txt`](../local_goodnotes_root.txt) (copy from [`../local_goodnotes_root.example.txt`](../local_goodnotes_root.example.txt)) |

GoodNotes: if env and local file do not resolve a directory, **`resolve_goodnotes_root()`** may use **sibling discovery**: when `resolve_daydreamedu_root()` returns `D`, use `D.parent / "GoodNotes"` if that path exists and is a directory.

---

## Documentation

| Doc | Contents |
|-----|----------|
| [SPEC.md](./SPEC.md) | Public API contract, defaults, exclusion semantics |
| [TESTING.md](./TESTING.md) | How tests and fixtures are organized; how to run pytest |
| [CHANGELOG.md](./CHANGELOG.md) | Version history for this package |

---

## Quick usage

```python
from pathlib import Path

from ai_study_buddy.files import (
    resolve_daydreamedu_root,
    resolve_goodnotes_root,
    list_leaf_folders_under_root,
    list_daydreamedu_leaf_folders_under_root,
    list_goodnotes_leaf_folders_under_root,
)

dd = resolve_daydreamedu_root()
gn = resolve_goodnotes_root()

if dd is not None:
    leaves = list_daydreamedu_leaf_folders_under_root(dd)
```

Design background: [L4_FILE_SYSTEM_MANAGEMENT.md](../docs/L4_FILE_SYSTEM_MANAGEMENT.md).
