# Testing — Student File Browser

## Unit tests

```bash
python3 -m pytest ai_study_buddy/files/tests ai_study_buddy/student_file_browser/tests -q
```

Package-only:

```bash
python3 -m pytest ai_study_buddy/student_file_browser/tests -q
```

- `tests/test_filters.py` — query string → `FilterCriteria` (including `sort=name|recent`, invalid `sort` coerced to `recent`)
- `tests/test_path_guard.py` — `safe_resolve_under_root`

Inventory sort behaviour is covered in `ai_study_buddy/files/tests/test_on_disk_inventory.py` (`sort_main_pdf_cards`); the browser only maps the `sort` query param and calls `/api/inventory`.

## Manual smoke

1. Configure DaydreamEdu and/or GoodNotes roots.
2. `python3 -m ai_study_buddy.student_file_browser.serve`
3. Open `http://localhost:8771/` (sibling deep links normalize `127.0.0.1` / `::1` to `localhost`)
4. Filter `is_registered=false` when unregistered files exist.
5. Open a card **View PDF**; **Copy path**; **Review Workspace** for a marked completion (opens Review Workspace on that attempt via `?attempt_id=` + `student_id=`).
6. **Scope = template:** student filter disabled; DaydreamEdu template cards visible.
7. **Sort (v0.1.5+):** narrow to one student; toggle **Recent first** / **Name (A–Z)** — grid reorders without a separate **Filter** click; **Reset** restores **Recent first**; `?sort=name` in URL reloads in name order.

## Smoke verification (May 2026)

Manual smoke **passed** with DaydreamEdu and GoodNotes roots, registry DB, and context root configured. Verified: **Filter** with `is_registered=false` surfaces unregistered mains; **Scope = template** disables the student control and lists DaydreamEdu templates; **View PDF** opens Root PDF Browser (:8770) on the correct file via `?id=` + `rel=` (v0.1.6+); **Copy path** works.

**v0.1.1 (2026-05-19):** **Review Workspace** card link opens `http://<same-hostname-as-browser>:5178/?attempt_id=<registry_file_id>&student_id=<id>` directly on the marked attempt (smoke passed via `localhost` file browser → `localhost` review workspace).

**v0.1.2 (2026-05-19):** Server and printed URLs use `localhost`; **View PDF** / **Review Workspace** links from a tab opened at `http://127.0.0.1:8771/` still target `localhost` on ports 8770 / 5178.

**v0.1.5 (2026-05-20):** **Sort** widget (requires `files` v0.3.4); registered cards show registry added date under title. Sort smoke **passed** (Recent first vs Name A–Z).

Re-run the manual steps above after large filesystem/registry changes or before a release if inventory behaviour changed.

HTTP integration tests (`tests/test_serve.py`) are tracked as [TODO.md](../TODO.md) **P2-5** (serve test hook required first).
