# Testing — `ai_study_buddy.files`

Tests live next to this package under **`ai_study_buddy/files/tests/`**. They use **temporary directories** and **monkeypatched config paths**; they do not read your real DaydreamEdu or GoodNotes sync folders unless you explicitly point tests there (do not).

---

## Running tests

From the **repository root**:

```bash
python3 -m pytest ai_study_buddy/files/tests
```

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
| `tests/conftest.py` | Pytest fixtures that copy fixture trees into `tmp_path` |
| `tests/fixtures/` | Small on-disk trees (see `tests/fixtures/README.md`) |

### Root resolver tests and config paths

`roots.py` resolves local config from fixed paths under `ai_study_buddy/`. In tests, **`_LOCAL_DAYDREAMEDU_ROOT_FILE`** and **`_LOCAL_GOODNOTES_ROOT_FILE`** are monkeypatched to temp files so tests never depend on your real `local_*_root.txt`.

### Leaf-folder tests and fixtures

Profile-shaped trees (`goodnotes_profile_tree`, `daydreamedu_profile_tree`) and a generic `minimal_sorted_tree` live under `tests/fixtures/`. Fixtures copy them into `tmp_path` so the committed trees stay immutable.

---

## Out of scope

- No integration tests against the real SQLite PDF registry (that belongs to `pdf_file_manager` tests).
- No requirement for real Google Drive paths or network access.

See also: [SPEC.md](./SPEC.md) for API behavior under test.
