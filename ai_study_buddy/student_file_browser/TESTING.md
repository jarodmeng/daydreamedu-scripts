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
5. Open a card **View PDF**; **Copy path**; link to Review Workspace for a marked completion.
