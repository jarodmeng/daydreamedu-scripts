# Proposal 3: Coverage / diagnostics tools for scan roots (and read‑only registry-derived paths)

**Happy path items:**  
- [Coverage/diagnostics] — Use diagnostics/coverage tools (e.g. a `coverage` CLI) so all relevant leaf folders are in `scan_roots` and the registry does not drift from the filesystem.  
- [Safer migrations — read‑only facility] — Provide a supported way to get registry-derived data (paths, leaf dirs from `pdf_files`) so reporting and diagnostics don’t require raw SQL or a separate DB connection. (Migration *practice* — prefer high‑level APIs, confine SQL to one‑off scripts — is in the learnings howto.)

---

## Motivation

Three archived scripts are effectively “coverage reports”:

- `_daydreamedu_leaf_vs_scan_roots.py`: find leaf dirs under a base path, compare to `scan_roots`, report missing.
- `_summarize_pdf_leaf_dirs_vs_scan_roots.py`: leaf dirs from `pdf_files.path` parents vs `scan_roots`; report leaf dirs with PDFs but not in scan_roots, and scan roots with no PDFs.
- `_scan_science_remaining_leaves.py`: find leaf dirs under Science base not in scan_roots, then add and scan them.

Making “find leaf dirs” and “compare to scan_roots” native (API + CLI) gives a single, supported way to answer “what’s missing?” and “what’s stale?” without maintaining one‑off scripts.

The same coverage report (with `from_registry` and leaf dirs derived from `pdf_files.path`) is also the **supported read‑only facility for registry-derived paths**: scripts that need “all paths in pdf_files” or “leaf dirs from registry” use the coverage API/CLI instead of opening their own SQLite connection or using `_get_connection()`. This proposal therefore covers both coverage/diagnostics and the “safer migrations” read‑only API (formerly a separate proposal).

---

## Current code / functions

- **API**
  - No `find_leaf_dirs` or equivalent in `PdfFileManager`.
  - `list_scan_roots() -> list[ScanRoot]` returns configured roots.
  - File paths are in DB only via `pdf_files.path`; no helper that aggregates “leaf dirs from registered paths.” No public way to get “all registered paths” or “leaf dirs from registry” without raw SQL or a separate connection.
- **Archived scripts**
  - Implement `leaf_dirs(root)` locally (dirs with no subdirs under `root`).
  - Open DB or use manager to get `scan_roots` and sometimes raw SQL for `pdf_files.path` parents (e.g. `_summarize_pdf_leaf_dirs_vs_scan_roots.py` opens its own connection).

---

## Gap

- No built‑in way to get “all leaf directories under a base path.”
- No built‑in comparison of “leaf dirs (from FS or from registry) vs scan_roots” with clear reporting.
- No public way to get registry-derived paths or leaf dirs without opening a separate connection or using private APIs — so reporting scripts cannot stay on the public API.
- No CLI to run this report; users rely on custom scripts.

---

## Implementation plan

1. **Add `find_leaf_dirs(base: Path) -> list[Path]`**
   - Option A: module‑level or static helper (e.g. on `PdfFileManager` or in a small `path_utils` used by the module). Takes a filesystem path, returns sorted list of directories that have no subdirectories (leaf dirs).
   - Option B: keep it private first (e.g. `_find_leaf_dirs`) and use only inside the manager/CLI.
   - Behavior: `rglob("*")` for dirs, filter to those with no child dirs; return sorted; handle OSError per‑path.

2. **Add coverage report API (optional but useful)**
   - e.g. `report_coverage(self, base_path: Path | None = None, from_registry: bool = False) -> CoverageReport`
   - If `base_path` given and `from_registry` False: leaf dirs = `find_leaf_dirs(base_path)`.
   - If `from_registry` True: leaf dirs = set of parent dirs of all `pdf_files.path` (from DB).
   - Scan roots = set of `r.path` from `list_scan_roots()`.
   - Return a small dataclass: e.g. `leaf_dirs`, `scan_roots`, `leaf_not_in_roots`, `roots_without_leaf_pdfs` (or similar), plus counts.
   - If both modes are needed, can be two methods or one with a mode flag.

3. **Add `coverage` CLI subcommand**
   - `pdf_file_manager coverage [--base PATH] [--from-registry] [--db PATH]`
   - `--base`: filesystem path to enumerate leaf dirs under. If omitted and `--from-registry` used, derive leaf dirs only from DB.
   - `--from-registry`: when set, compute leaf dirs from registered `pdf_files.path` parents instead of walking `--base`.
   - Print: counts (leaf dirs, scan roots, intersection, leaf not in roots, roots without PDFs); then list leaf dirs not in scan_roots and optionally scan roots with no PDFs.

4. **Docs**
   - Document `find_leaf_dirs` (if public) and `coverage` CLI in SPEC/ARCHITECTURE and help text.

---

## Test plan

- **`find_leaf_dirs`**
  - Empty dir: returns empty list.
  - Dir with only files: returns `[that_dir]`.
  - Dir with one subdir (and that subdir has no subdirs): returns `[subdir]`.
  - Dir with nested structure: returns only dirs that have no child dirs; count and paths match expected.
  - Symlinks / permission errors: document behavior (e.g. skip or OSError); test on a tree that triggers it if possible.
- **Coverage report API**
  - With empty DB and empty `--base`: no scan roots, no leaf dirs (or only those under base); report reflects that.
  - Add one scan root; run with `--base` containing that path as leaf: intersection >= 1.
  - Register a file in a path not in scan_roots; run with `--from-registry`: that path’s parent appears in “leaf not in scan_roots” (or equivalent).
  - **Registry-derived paths (no raw SQL):** Integration test that “list paths / leaf dirs from registry and compare to scan_roots” can be done using only the coverage report API (no `_get_connection()` or separate connection).
- **CLI**
  - `coverage --base /nonexistent`: exit 0 or non‑zero, no crash; clear message.
  - `coverage --base <path>`: output includes counts and lists; parsing or eyeball check.
  - `coverage --from-registry`: output consistent with DB state (leaf dirs from pdf_files, compared to scan_roots).
- **Regression**
  - Existing tests unchanged; no change to `list_scan_roots` or `pdf_files` schema.
