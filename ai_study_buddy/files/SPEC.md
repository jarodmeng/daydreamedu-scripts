# Specification — `ai_study_buddy.files`

This document is the **contract** for the public Python API of `ai_study_buddy.files`. It is registry-agnostic: no SQLite, no `PdfFileManager`, no scan-root configuration.

**Version:** align with [README.md](./README.md) (package `v0.1.3` baseline).

---

## 1. Root resolution (`roots.py`)

### 1.1 `resolve_daydreamedu_root() -> pathlib.Path | None`

Returns an **existing directory** or `None`.

**Precedence:**

1. Environment variable **`DAYDREAMEDU_ROOT`**: non-empty string → `Path.expanduser().resolve()`; return if `is_dir()`, else `None`.
2. Else read **`ai_study_buddy/local_daydreamedu_root.txt`** (path derived from package layout: parent of `ai_study_buddy/files/` + filename). First non-empty, non-`#` line → same path rules as (1). First winning line wins.
3. Else `None`.

### 1.2 `resolve_goodnotes_root() -> pathlib.Path | None`

Returns an **existing directory** or `None`.

**Precedence:**

1. **`GOODNOTES_ROOT`**: same rules as `DAYDREAMEDU_ROOT`.
2. Else **`ai_study_buddy/local_goodnotes_root.txt`**: same line rules as DaydreamEdu file.
3. Else if `resolve_daydreamedu_root()` returns `D`, let `S = (D.parent / "GoodNotes").resolve()`. If `S.is_dir()`, return `S`.
4. Else `None`.

**Note:** Step 3 uses whatever DaydreamEdu path step (1) or (2) produced; it does not read a separate “sibling file”.

---

## 2. Leaf folders (`leaf_folders.py`)

### 2.1 Definitions

- **Direct file:** a file entry immediately inside a directory (not in a subdirectory).
- **Leaf folder (for listing):** a directory that contains **at least one** direct file whose suffix (case-insensitive) is in `include_suffixes` after normalization (see 2.2).
- **Traversal:** `os.walk` from `root` (recursive). Every directory that qualifies as a leaf folder is collected.

### 2.2 Suffix normalization

Input set `include_suffixes` is normalized:

- Strip whitespace; lowercase.
- If a token does not start with `.`, prepend `.` (e.g. `pdf` → `.pdf`).
- Empty tokens are dropped.
- If, after normalization, the set is empty, `list_leaf_folders_under_root` returns `[]`.

### 2.3 `list_leaf_folders_under_root(root, *, include_suffixes, excluded_leaf_folders=None) -> list[pathlib.Path]`

- **`root`:** expanded and resolved; if not a directory, returns `[]`.
- **`excluded_leaf_folders`:** optional set of **absolute** directory paths. Any resolved leaf folder path contained in this set is omitted from the result.
- **Return value:** sorted list of **resolved absolute** `Path` objects (lexicographic sort on path string).

### 2.4 Profile wrappers

Both default `include_suffixes` to `{".pdf"}` when omitted.

#### `list_goodnotes_leaf_folders_under_root(root, *, include_suffixes=None, exclude_not_completed=True)`

Builds an internal excluded set from **all** leaves (under the same suffix set), then excludes any leaf that:

- equals `root` (resolved), or
- has any path segment matching regex `^x[A-Z].*$` (segment name only), or
- when **`exclude_not_completed`** is `True` (default): has any path segment equal to `Not completed` (case-insensitive). When `False`, those leaves stay **included** (e.g. browse WIP completion PDFs); root and x-prefix exclusions still apply.

Then calls `list_leaf_folders_under_root` with that excluded set.

#### `list_daydreamedu_leaf_folders_under_root(root, *, include_suffixes=None)`

Builds an internal excluded set: any leaf that equals `root` (resolved) — the root-relative `.` leaf when the sync root contains direct PDFs (`daydreamedu-leaf-registry-report` parity). Then calls `list_leaf_folders_under_root`.

### 2.5 `is_goodnotes_excluded_relative_path(rel: str, *, exclude_not_completed=True) -> bool`

- **Input *rel*:** a path string relative to ``GOODNOTES_ROOT``, using `/` segments (may be normalized by the caller). Empty or whitespace-only means the sync root itself → returns `False`.
- **True** if any non-empty path segment matches `^x[A-Z].*$`, or (when *exclude_not_completed* is `True`) any segment equals `Not completed` case-insensitively.
- **Purpose:** single source for GoodNotes “structural” exclusions when walking a tree (for example `root_pdf_browser`), without duplicating regex rules. Aligns with `list_goodnotes_leaf_folders_under_root` when the same *exclude_not_completed* flag is passed.

---

## 3. Non-goals

- No PDF classification, compression, or registry mutation.
- No automatic creation of `local_*_root.txt` files.
- No network or cloud API access.

---

## 4. Import surface

Canonical imports:

```python
from ai_study_buddy.files import (
    resolve_daydreamedu_root,
    resolve_goodnotes_root,
    is_goodnotes_excluded_relative_path,
    list_leaf_folders_under_root,
    list_daydreamedu_leaf_folders_under_root,
    list_goodnotes_leaf_folders_under_root,
)
```

Submodules may be imported directly (`ai_study_buddy.files.roots`, `ai_study_buddy.files.leaf_folders`) for tests or narrow dependencies.
