# Proposal 4: Template/completion linking helper

**Happy path item:** [Template linking] — Use template linking (and file groups) as thin layers on top of `find_files` + filename heuristics, with a `link_template_by_paths` or `link-template` CLI so scripts only supply path pairs.

> Historical note: this proposal preserves earlier CLI helper ideas. The built-in `pdf_file_manager` CLI is no longer supported; use the Python `PdfFileManager` API.

---

## Motivation

Several archived scripts (`_bootstrap_p5_math_exam.py`, `_link_p5_worksheet1_template.py`, `_link_p6_wa1_template.py`) implement the same workflow:

- Find template (blank/empty) and completed (filled) files by path (often trying several name variants).
- Set `is_template=True` for template, `is_template=False` for completed.
- Call `link_to_template(completed_id, template_id)`.

The path→file lookup and flag updates are repeated in each script. A small helper (and optional CLI) would centralize the linking pattern so callers only supply the two paths; filename heuristics stay in the caller or in domain‑specific scripts.

---

## Current code / functions

- **API**
  - `get_file_by_path(self, path: str | Path) -> PdfFile | None` — lookup by resolved path.
  - `update_metadata(self, file_id_or_path, ..., is_template=None, ...) -> PdfFile` — set flags.
  - `link_to_template(self, completed_id, template_id, inherit_metadata=True)` — creates `template_for` / `completed_from` relations; validates both files are `main`, template has `is_template=True`, completed has `is_template=False`; optionally inherits metadata.
  - `get_template(self, file_id) -> PdfFile | None` — returns the template for a completed file, if any.
- **CLI**
  - No `link-template` (or similar) command.

---

## Gap

- Callers must manually: resolve paths, call `get_file_by_path` for each path, check both exist, set `is_template` on both, then call `link_to_template`. Easy to forget a step or duplicate logic across scripts.
- No CLI to link one template–completed pair by paths.

---

## Implementation plan

1. **Add `link_template_by_paths(self, completed_path, template_path, inherit_metadata=True) -> FileRelation`**
   - Resolve both paths (Path or str).
   - `template_file = get_file_by_path(template_path)`, `completed_file = get_file_by_path(completed_path)`.
   - If either is None, raise `NotFoundError` with a clear message (or return a result type indicating missing file).
   - If `get_template(completed_file.id)` is already set, raise a clear error or return existing relation (document chosen behavior).
   - Call `update_metadata(template_file.id, is_template=True)` and `update_metadata(completed_file.id, is_template=False)`.
   - Call `link_to_template(completed_file.id, template_file.id, inherit_metadata=inherit_metadata)` and return the relation (or whatever `link_to_template` returns).
   - Reuse existing validation inside `link_to_template` (main files, template flag, etc.).

2. **Add `link-template` CLI subcommand**
   - `pdf_file_manager link-template --template PATH --completed PATH [--no-inherit-metadata] [--db PATH]`
   - Call `link_template_by_paths(completed_path, template_path, inherit_metadata=not args.no_inherit_metadata)`.
   - On success: print a one‑line confirmation. On missing file or already linked: clear error message and non‑zero exit if appropriate.

3. **Docs**
   - Document `link_template_by_paths` in API docs; note that path resolution and “which path is template vs completed” are the caller’s responsibility; domain heuristics (e.g. “(empty)” in name) stay outside.

---

## Test plan

- **Unit tests for `link_template_by_paths`**
  - Both paths point to registered main files; one is template, one is completed: after call, `get_template(completed_id)` returns template; relations exist; `is_template` flags correct.
  - Idempotence: call again with same pair; either raise “already linked” or return existing relation (match chosen behavior).
  - `template_path` not in registry: `NotFoundError` (or equivalent).
  - `completed_path` not in registry: `NotFoundError`.
  - One path is raw file (not main): expect validation error from `link_to_template`.
  - `inherit_metadata=True`: completed file gains template’s subject/doc_type/metadata where missing; `inherit_metadata=False`: no overwrite of completed’s metadata (test with known template/completed pairs).
- **CLI**
  - `link-template --template <path> --completed <path>` with valid pair: exit 0, relation created.
  - With missing path: exit non‑zero, message mentions which path is missing.
  - With already-linked completed: exit non‑zero or 0 with message, no duplicate relation.
- **Regression**
  - Existing `link_to_template` and `update_metadata` tests still pass.
