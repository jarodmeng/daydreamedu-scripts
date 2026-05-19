# Testing — Student File Browser

## Unit tests

```bash
python3 -m pytest ai_study_buddy/files/tests ai_study_buddy/student_file_browser/tests -q
```

Package-only:

```bash
python3 -m pytest ai_study_buddy/student_file_browser/tests -q
```

- `tests/test_filters.py` — query string → `FilterCriteria`
- `tests/test_path_guard.py` — `safe_resolve_under_root`

## Manual smoke

1. Configure DaydreamEdu and/or GoodNotes roots.
2. `python3 -m ai_study_buddy.student_file_browser.serve`
3. Open `http://127.0.0.1:8771/`
4. Filter `is_registered=false` when unregistered files exist.
5. Open a card **View PDF**; **Copy path**; **Review Workspace** for a marked completion (opens Review Workspace on that attempt via `?attempt_id=` + `student_id=`).
6. **Scope = template:** student filter disabled; DaydreamEdu template cards visible.

## Smoke verification (May 2026)

Manual smoke **passed** with DaydreamEdu and GoodNotes roots, registry DB, and context root configured. Verified: **Filter** with `is_registered=false` surfaces unregistered mains; **Scope = template** disables the student control and lists DaydreamEdu templates; **View PDF** opens Root PDF Browser (:8770) on the correct file via `?id=` + `rel=` (v0.1.6+); **Copy path** works.

**v0.1.1 (2026-05-19):** **Review Workspace** card link opens `http://<same-hostname-as-browser>:5178/?attempt_id=<registry_file_id>&student_id=<id>` directly on the marked attempt (smoke passed via `localhost` file browser → `localhost` review workspace).

Re-run the manual steps above after large filesystem/registry changes or before a release if inventory behaviour changed.

HTTP integration tests (`tests/test_serve.py`) are tracked as [TODO.md](../TODO.md) **P2-5** (serve test hook required first).
