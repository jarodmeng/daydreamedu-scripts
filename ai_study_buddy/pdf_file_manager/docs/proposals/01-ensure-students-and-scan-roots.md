# Proposal 1: Ensure students and scan roots

**Happy path item:** [Ensure students and scan roots] — Configure scan roots for each subject/grade/folder (via `ensure_scan_root` / `ensure_student` or equivalent), optionally with a `student_id` for per‑student copies.

---

## Motivation

Almost every one‑off script in `scripts/archive/` repeats the same setup:

- Ensure a student row exists: `get_student(id)` → if missing, `add_student(id, name, email)`.
- Ensure a scan root exists: `list_scan_roots()` → if path not present, `add_scan_root(path, student_id=...)`.

This boilerplate is duplicated across many scripts and obscures the real workflow (scanning and post‑processing). Idempotent “ensure” helpers would make the intended setup obvious and reduce copy‑paste and mistakes.

---

## Current code / functions

- **Students**
  - `add_student(self, id, name, email=None) -> Student` — inserts a row; fails if id already exists.
  - `get_student(self, student_id) -> Student | None` — returns existing student or None.
- **Scan roots**
  - `add_scan_root(self, path, student_id=None) -> ScanRoot` — inserts a root (path resolved); no dedup by path.
  - `list_scan_roots(self) -> list[ScanRoot]` — returns all roots in `added_at` order.
  - `remove_scan_root(self, path) -> None` — deletes by path.

Callers today must manually check existence and call `add_*` only when missing.

---

## Gap

- No idempotent “ensure student exists” API: callers must do `if get_student(id) is None: add_student(...)`.
- No idempotent “ensure scan root exists” API: callers must do `if not any(r.path == root_str for r in list_scan_roots()): add_scan_root(...)`.
- No batch “ensure multiple roots” helper, so multi‑folder scripts repeat the same loop.

---

## Implementation plan

1. **Add `ensure_student(student_id, name, email=None) -> Student`**
   - If `get_student(student_id)` returns a student, return it unchanged.
   - Else call `add_student(student_id, name, email)` and return the new `Student`.
   - Signature and return type align with existing `add_student` / `get_student`.

2. **Add `ensure_scan_root(path, student_id=None) -> ScanRoot`**
   - Resolve `path` to a canonical absolute path (same as `add_scan_root`).
   - If `list_scan_roots()` contains a root with that path, return that `ScanRoot` (optionally update `student_id` only if we decide that’s desired; initial implementation can leave existing row as‑is).
   - Else call `add_scan_root(path, student_id)` and return the new `ScanRoot`.

3. **Optional: `ensure_scan_roots(entries: list[tuple[Path|str, str|None]]) -> list[ScanRoot]`**
   - Each entry is `(path, student_id)`.
   - For each, call `ensure_scan_root(path, student_id)` and collect results.
   - Reduces boilerplate in scripts that add many roots.

4. **Docs**
   - Document in module docstring or SPEC/ARCHITECTURE that “ensure” helpers are the preferred way to set up students and roots before scanning.

---

## Test plan

- **Unit tests (pytest or existing test harness)**
  - `ensure_student`: call twice with same id; second call returns same student, no duplicate row.
  - `ensure_student`: call with new id; creates row and returns it; `get_student` then returns it.
  - `ensure_scan_root`: call twice with same path; second call returns same scan root, no duplicate path in `scan_roots`.
  - `ensure_scan_root`: call with path not yet a root; creates root and returns it; path appears in `list_scan_roots()`.
  - `ensure_scan_root`: with `student_id`; verify stored `student_id` when creating; when path already exists, document whether we leave existing `student_id` or update (and test that behavior).
  - If implemented: `ensure_scan_roots` with a list of (path, student_id); all paths end up as roots; idempotent on repeat.
- **Regression**
  - Run existing tests that use `add_student` / `add_scan_root`; ensure no breakage.
  - Optionally add a small script or test that performs “ensure then scan” and assert root/student presence.
