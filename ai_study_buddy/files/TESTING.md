# Testing — `ai_study_buddy.files`

Tests live next to this package under **`ai_study_buddy/files/tests/`**. They use **temporary directories** and **monkeypatched config paths**; they do not read your real DaydreamEdu or GoodNotes sync folders unless you explicitly point tests there (do not).

---

## Running tests

From the **repository root**:

```bash
python3 -m pytest ai_study_buddy/files/tests -q
```

**Last recorded run (v0.3.4):** 2026-05-20 — `60 passed` (repo root, `python3 -m pytest ai_study_buddy/files/tests -q`).

To run together with `pdf_file_manager` config tests (students / scan roots only):

```bash
python3 -m pytest ai_study_buddy/files/tests ai_study_buddy/pdf_file_manager/tests/test_config.py
```

---

## Layout

| Path | Purpose |
|------|---------|
| `tests/test_roots.py` | `resolve_daydreamedu_root` / `resolve_goodnotes_root` (env, file, sibling, missing) |
| `tests/test_leaf_folders.py` | Leaf listing and profile wrappers |
| `tests/test_pdf_registry_paths.py` | Registry path index, leaf registration rollups (v0.2+) |
| `tests/test_path_facets.py` | `infer_path_facets` (v0.3) |
| `tests/test_main_pdfs.py` | Main-PDF enumeration under leaf folders (v0.3) |
| `tests/test_on_disk_inventory.py` | `enrich_on_disk_main_pdf`, `filter_main_pdf_cards`, `sort_main_pdf_cards`, `FilterCriteria.sort`, `registry_added_at` (v0.3–v0.3.4) |
| `tests/conftest.py` | Pytest fixtures that copy fixture trees into `tmp_path` |
| `tests/fixtures/` | Small on-disk trees (see `tests/fixtures/README.md`) |

### Root resolver tests and config paths

`roots.py` resolves local config from fixed paths under `ai_study_buddy/`. In tests, **`_LOCAL_DAYDREAMEDU_ROOT_FILE`** and **`_LOCAL_GOODNOTES_ROOT_FILE`** are monkeypatched to temp files so tests never depend on your real `local_*_root.txt`.

### Leaf-folder tests and fixtures

Profile-shaped trees (`goodnotes_profile_tree`, `daydreamedu_profile_tree`) and a generic `minimal_sorted_tree` live under `tests/fixtures/`. Fixtures copy them into `tmp_path` so the committed trees stay immutable.

### Sort order (`test_on_disk_inventory.py`, v0.3.4)

Lightweight `OnDiskMainPdfCard(...)` fixtures (no disk):

| Test | Asserts |
|------|---------|
| `test_sort_main_pdf_cards_name` | Display name A–Z |
| `test_sort_main_pdf_cards_name_tie_path` | Same `normal_name` → `absolute_path` tie-breaker |
| `test_sort_main_pdf_cards_recent` | `registry_added_at` descending |
| `test_sort_main_pdf_cards_recent_unregistered_tail` | Registered before unregistered |
| `test_sort_main_pdf_cards_invalid_coerces_recent` | Unknown `sort` → `recent` behaviour |

`registry_added_at` on enrich is also asserted in `test_enrich_on_disk_main_pdf_populates_completion_series_fields`.

---

## Out of scope

- No integration tests against the real SQLite PDF registry (that belongs to `pdf_file_manager` tests).
- No requirement for real Google Drive paths or network access.

See also: [SPEC.md](./SPEC.md) for API behavior under test.
