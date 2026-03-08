# Testing plan

Tests are defined at the **utility level**: one test suite for the pdf_file_manager, with unit and integration tests. No end-to-end tests against the real DaydreamEdu drive; all tests use temporary DBs and temp directories.

---

## Test levels

| Level | What | Examples |
|-------|------|----------|
| **Unit** | Pure logic and small helpers with minimal or mocked I/O | Path → subject, student, is_template inference (`_infer_from_path`); metadata merge; validation (e.g. `subject` allowed values); `operation_log` payload shape. Use an in-memory SQLite DB or mocks where needed. |
| **Integration** | `PdfFileManager` methods against a real SQLite DB and real (temp) files on disk | Schema creation and migrations; `register_file` then `get_file`; `scan_for_new_files` on a temp dir with a few PDFs; `compress_and_register` with a temp PDF using the real `compress_pdf`; `update_metadata`, `find_files` filters; file groups and relations; `get_operation_log` after a few operations. |

**Out of scope:** Tests that touch the real registry path or real scan roots (e.g. `~/.../DaydreamEdu`). Manual or one-off scripts against real data are not part of this plan.

---

## Test data strategy

- **Database:** Use a temporary SQLite file (e.g. `tempfile.NamedTemporaryFile(suffix=".db")` or `:memory:`) for every test or test class. Never use `ai_study_buddy/db/pdf_registry.db` or `PDF_REGISTRY_PATH` in tests.
- **Files:** Create temporary directories and, when tests need PDFs, the **DaydreamEdu fixture** under `tests/fixtures/daydreamedu_fixture/` (scaled-down repo layout with two real PDFs in `Singapore Primary Science/winston.ry.meng@gmail.com/P5/Exam/`; see that folder's README). Copy the fixture into a temp dir before scan/compress so the fixture stays pristine. Use `tempfile.TemporaryDirectory()` (or the equivalent) so tests don’t leave artifacts.
- **compress_pdf:** Tests always use the **real** `compress_pdf` utility (no mocks). Integration tests that call `compress_and_register` or `scan_for_new_files` depend on it.

---

## When to add tests

| Phase | Add tests for |
|-------|----------------|
| **1. Foundation** | Schema creation (tables exist, constraints); `PdfFileManager` init with default and custom path; that a C/U/D helper writes a row to `operation_log` (e.g. via one minimal mutating path if you add it, or a dedicated “test write” used only in tests). |
| **2. Config & file lifecycle** | `add_student` / `list_students`; `add_scan_root` / `remove_scan_root` / `list_scan_roots`; `register_file` (path, file_type inference, duplicate path); `compress_and_register` (register-if-missing, then compress; use real `compress_pdf`); `scan_for_new_files` on a temp dir (with and without `dry_run`). |
| **3. Read / update / delete** | `get_file`, `find_files` (each filter); `update_metadata` (merge behaviour, validation); `rename_file` / `move_file` (disk + DB); `delete_file` (with/without `keep_related`); `open_file` (path exists vs missing). |
| **4. Relations & groups** | `link_files` / `unlink_files`, `get_related_files`; `link_to_template` / `unlink_template` (including validation), `get_template` / `get_completions`; file group CRUD and `suggest_groups` (with fixture data). |
| **5. Audit & CLI** | `get_operation_log` (filters, `log_id`); CLI smoke tests (invoke subcommands with `--help` or minimal args against temp DB/dirs; no real drive). |

Prefer adding tests in the same phase as the feature (or immediately after) so each phase is verifiable before moving on.

---

## Phase 1: tests that confirm success

These tests give confidence that Phase 1 (Foundation) is complete. All use a **temporary** DB path (e.g. `tempfile.NamedTemporaryFile(suffix=".db", delete=False)` then unlink after, or `:memory:`).

| # | Test | What it proves |
|---|------|----------------|
| **1** | **Schema exists after init** | Create `PdfFileManager(db_path=<temp path>)`. Query SQLite: `SELECT name FROM sqlite_master WHERE type='table' ORDER BY name`. Assert the list equals `['file_group_members', 'file_groups', 'file_relations', 'operation_log', 'pdf_files', 'scan_roots', 'students']` (or equivalent for your schema). Proves: DB file is created and all seven tables exist. |
| **2** | **Schema shape (operation_log)** | Using the same DB, `PRAGMA table_info(operation_log)`. Assert columns include `id`, `operation`, `file_id`, `group_id`, `performed_at`, `performed_by`, `before_state`, `after_state`, `notes`. Proves: operation log table is fit for use. |
| **3** | **Schema shape (pdf_files)** | `PRAGMA table_info(pdf_files)`. Assert columns include `id`, `path`, `file_type`, `doc_type`, `student_id`, `subject`, `is_template`, `metadata`, `has_raw`, etc. Proves: core file table matches spec. |
| **4** | **Custom DB path** | Create `PdfFileManager(db_path=<path_to_new_file>)`. Assert the file exists at that path and contains the tables (e.g. same as test 1). Proves: manager uses the given path and creates schema. |
| **5** | **Default DB path** | Create `PdfFileManager()` (no args). Assert a DB is created at the default location (e.g. from env or repo-relative `ai_study_buddy/db/pdf_registry.db`). Proves: default config works. |
| **6** | **Operation log write** | Call the code path that writes to `operation_log` (e.g. an internal `_log_operation(operation='test', ...)` or the same helper that future C/U/D will use). Then run `SELECT operation, file_id, performed_at FROM operation_log`. Assert one row with the expected `operation`. Proves: every future C/U/D can record history. |

**Passing all six** means: the DB and schema are correct, the manager can be constructed with default or custom path, and the logging hook is in place. Phase 1 is then safe to call done.

---

## Phase 2: tests that confirm success

These tests give confidence that Phase 2 (Config & file lifecycle) is complete. Use a **temporary** DB. For tests that need PDFs, use the **DaydreamEdu fixture** (`tests/fixtures/daydreamedu_fixture/`): copy the fixture (or the relevant subtree) into a **temp directory** so the fixture itself is not modified, then use that temp dir as the scan root or pass paths inside it to `register_file` / `compress_and_register`. Use the **real** `compress_pdf` utility (no mocks).

### Students

| # | Test | What it proves |
|---|------|----------------|
| **2.1** | **add_student then list_students** | `add_student("w", "Winston", email="w@x.com")`; `list_students()` returns a list of one; that entry has `id`, `name`, `email`. Proves: student row is created and readable. |
| **2.2** | **list_students empty at first** | New manager, `list_students()` returns empty list. Proves: no stray data. |

### Scan roots

| # | Test | What it proves |
|---|------|----------------|
| **2.3** | **add_scan_root then list_scan_roots** | `add_scan_root("/tmp/foo", student_id="w")`; `list_scan_roots()` returns one item with that path and `student_id`. Proves: scan root stored and listed. |
| **2.4** | **remove_scan_root** | Add a root, then `remove_scan_root("/tmp/foo")`; `list_scan_roots()` is empty. Proves: removal works. |

### register_file

| # | Test | What it proves |
|---|------|----------------|
| **2.5** | **register_file creates row and log** | Create a temp PDF on disk. `register_file(path)`; assert one row in `pdf_files` (path, `file_type='unknown'` for normal name), and one `operation_log` row with `operation='register'`. Proves: file registered, log written. |
| **2.6** | **register_file missing path** | `register_file("/nonexistent/file.pdf")` raises `FileNotFoundError`. Proves: guard rail. |
| **2.7** | **register_file duplicate path** | Register same path twice; second call raises `AlreadyRegisteredError`. Proves: no duplicate registrations. |
| **2.8** | **register_file infers file_type raw** | Temp file named `_raw_foo.pdf`; after `register_file(path)`, `pdf_files` row has `file_type='raw'`. Proves: filename inference. |
| **2.8b** | **register_file infers file_type main for _c_** | Temp file named `_c_foo.pdf`; after `register_file(path)`, `pdf_files` row has `file_type='main'`. Proves: _c_ prefix = main (no compress). |
| **2.12b** | **scan _c_ prefix registers without compressing** | Put only a `_c_*.pdf` in scan root; run scan. Assert one main row, no compress step (file still at _c_ path, has_raw=0). Proves: _c_ files are register-only. |
| **2.9** | **register_file accepts optional args** | `register_file(path, doc_type="exam", student_id="w", subject="math")`; row has those values. Proves: optional params stored. |

### compress_and_register

| # | Test | What it proves |
|---|------|----------------|
| **2.10** | **compress_and_register with unregistered path** | Temp PDF not in registry. Call `compress_and_register(path)` using the real `compress_pdf`. Assert one `pdf_files` row `file_type='main'`; `has_raw` and raw file presence depend on whether compression met `min_savings_pct`. `operation_log` has `register` and `compress`. Proves: register-if-needed then compress. |
| **2.11** | **compress_and_register already main** | Register a file, set its `file_type` to `'main'` (or use a path that was already compressed). `compress_and_register(path)` raises `ValueError`. Proves: no double compress. |

### scan_for_new_files

| # | Test | What it proves |
|---|------|----------------|
| **2.12** | **scan dry_run does not write** | Add scan root pointing at a temp dir; put one PDF in that dir. `scan_for_new_files(dry_run=True)`. Assert `pdf_files` is still empty (no rows added). Assert return value indicates one file would be processed (e.g. length 1 or one “would process” item). Proves: dry_run is read-only. |
| **2.13** | **scan without dry_run registers and compresses** | Same setup; `scan_for_new_files(dry_run=False)`. Assert one row in `pdf_files` (the main file); `student_id` set from scan root if root had `student_id`. Proves: full scan flow. |
| **2.14** | **scan with no roots raises** | New manager, no roots added. `scan_for_new_files()` (no override) raises `ConfigError` (or equivalent) pointing to config add-root. Proves: guard rail. |

**Passing all 14** (2.1–2.14) means: students and scan roots are configurable, `register_file` and its guards work, `compress_and_register` does register-then-compress (using the real `compress_pdf`), and `scan_for_new_files` respects dry_run and requires roots. Phase 2 is then safe to call done.

---

## Phase 3: tests that confirm success

These tests give confidence that Phase 3 (Read / update / delete) is complete. Use a **temporary** DB. For tests that need PDFs on disk, use the **DaydreamEdu fixture** copied into a temp dir (same as Phase 2). All parameters (e.g. `subject`) follow the spec (allowed values: `english`, `math`, `science`, `chinese`).

### get_file

| # | Test | What it proves |
|---|------|----------------|
| **3.1** | **get_file by id returns PdfFile** | Register a file (fixture PDF in temp dir). `get_file(registered_id)` returns a `PdfFile` with matching `id`, `path`, `name`. Proves: lookup by UUID works. |
| **3.2** | **get_file unknown id returns None** | New manager, no files. `get_file("nonexistent-uuid")` returns `None`. Proves: no false positives. |

### find_files

| # | Test | What it proves |
|---|------|----------------|
| **3.3** | **find_files no filters returns all** | Register two files. `find_files()` returns both (order unspecified). Proves: baseline query. |
| **3.4** | **find_files file_type filter** | Register one `main`, one `raw` (or one `unknown`). `find_files(file_type="main")` returns only main. Proves: `file_type` filter. |
| **3.5** | **find_files doc_type filter** | Register files with different `doc_type`. `find_files(doc_type="exam")` returns only exam. Proves: `doc_type` filter. |
| **3.6** | **find_files student_id filter** | Register files with different `student_id`. `find_files(student_id="w")` returns only that student’s. Proves: `student_id` filter. |
| **3.7** | **find_files subject filter** | Register files with `subject="math"` and `subject="science"`. `find_files(subject="math")` returns only math. Proves: `subject` filter. |
| **3.8** | **find_files query (name substring)** | Register a file with a distinct name. `find_files(query="distinct")` returns it; `find_files(query="nonexistent")` returns empty. Case-insensitive. Proves: `query` on name. |
| **3.9** | **find_files is_template and has_raw** | One file `is_template=True`, one `has_raw=True`. Filters return the expected subset. Proves: boolean filters. |

### update_metadata

| # | Test | What it proves |
|---|------|----------------|
| **3.10** | **update_metadata updates single fields** | Register a file. `update_metadata(file_id, doc_type="exam", subject="science")`. `get_file(file_id)` shows new `doc_type` and `subject`. Proves: fields updated, log entry written. |
| **3.11** | **update_metadata merges metadata dict** | File has `metadata={"a": 1}`. `update_metadata(file_id, metadata={"b": 2})`. Result has `metadata={"a": 1, "b": 2}`. Proves: merge, not replace. |
| **3.12** | **update_metadata invalid subject raises** | `update_metadata(file_id, subject="invalid")` raises `ValueError` (message mentions allowed values). Proves: validation. |

### rename_file / move_file

| # | Test | What it proves |
|---|------|----------------|
| **3.13** | **rename_file renames on disk and in DB** | Register a file in temp dir. `rename_file(file_id_or_path, new_name="newname.pdf")`. File on disk is `newname.pdf`; `get_file` shows new `name` and `path`. `operation_log` has `rename`. Proves: disk + DB + log. |
| **3.14** | **rename_file destination exists raises** | Rename to a path that already exists (e.g. another registered file). Raises `ValueError`; no changes. Proves: guard rail. |
| **3.15** | **move_file moves on disk and in DB** | Register a file in temp dir; create a subdir. `move_file(file_id_or_path, new_dir)`. File is under `new_dir`; `path` updated. `operation_log` has `move`. Proves: disk + DB + log. |
| **3.16** | **move_file destination exists raises** | Move to a dir that already contains a file with the same name. Raises `ValueError`. Proves: guard rail. |

### delete_file

| # | Test | What it proves |
|---|------|----------------|
| **3.17** | **delete_file removes file and row** | Register a file. `delete_file(file_id_or_path)`. File absent on disk; no row in `pdf_files`; `operation_log` has `delete` with before_state. Proves: full removal. |
| **3.18** | **delete_file keep_related=False cascades to raw** | Create a main file with raw (via `compress_and_register`). `delete_file(main_id, keep_related=False)`. Both main and raw gone from disk and DB; delete log for both (second with `performed_by='cascade'` or equivalent). Proves: cascade. |
| **3.19** | **delete_file keep_related=True leaves raw** | Main + raw as above. `delete_file(main_id, keep_related=True)`. Main gone; raw file and row still present; main’s `has_raw` no longer referenced. Proves: keep_related. |
| **3.20** | **delete_file file already absent on disk** | Register a file, then delete the file from disk manually. `delete_file(file_id)`. No exception; row removed from DB; log entry written (warning optional). Proves: graceful handling. |

### open_file

| # | Test | What it proves |
|---|------|----------------|
| **3.21** | **open_file path exists** | Register a file that exists on disk. `open_file(file_id_or_path)` completes without error (subprocess/platform-dependent; may skip on headless CI or assert no exception). Proves: happy path. |
| **3.22** | **open_file path missing raises** | Register a file, then remove it from disk. `open_file(file_id_or_path)` raises `FileNotFoundError`. Proves: guard rail. |

**Passing all Phase 3 tests** (3.1–3.22) means: `get_file` and `find_files` (all filters) work, `update_metadata` merges and validates, `rename_file` and `move_file` update disk and DB with guards, `delete_file` removes (with/without cascade) and handles missing disk, and `open_file` checks path existence. Phase 3 is then safe to call done.

---

## Phase 4: tests that confirm success

These tests give confidence that Phase 4 (Relations & groups) is complete. Use a **temporary** DB and the **same DaydreamEdu fixture** as Phase 2/3 (copy to temp dir). **No fixture layout change is required:** raw↔main relations come from `compress_and_register`; template↔completed and file groups are created in-test via the API; `suggest_groups` uses multiple registered files (same PDF copied with different names) classified with `doc_type='exam'`, `student_id`, `subject`, and `metadata.exam_date`.

### get_related_files / link_files / unlink_files

| # | Test | What it proves |
|---|------|----------------|
| **4.1** | **get_related_files after compress** | `compress_and_register` one PDF (min_savings_pct=0). `get_related_files(main_id)` returns one tuple (raw PdfFile, relation_type). Proves: raw_source/main_version visible. |
| **4.2** | **link_files creates relation and has_raw** | Register two files (one main, one raw path). Manually `link_files(main_id, raw_id, 'raw_source')`. Assert `get_related_files(main_id)` includes raw; main's `has_raw` is True. Proves: manual link. |
| **4.3** | **unlink_files removes relation** | After a link, `unlink_files(main_id, raw_id)`. `get_related_files(main_id)` empty; main's `has_raw` False. Proves: unlink. |

### link_to_template / unlink_template / get_template / get_completions

| # | Test | What it proves |
|---|------|----------------|
| **4.4** | **link_to_template and get_template** | Two main files; one `is_template=True`, one `is_template=False`. `link_to_template(completed_id, template_id)`. `get_template(completed_id)` returns template. Proves: link + get_template. |
| **4.5** | **get_completions** | Same setup. `get_completions(template_id)` returns list containing the completed file. Proves: get_completions. |
| **4.6** | **unlink_template** | After link, `unlink_template(completed_id)`. `get_template(completed_id)` is None; `get_completions(template_id)` empty. Proves: unlink. |
| **4.7** | **link_to_template validation** | `link_to_template(completed_id, template_id)` when completed already linked, or template has `is_template=False`, or completed has `is_template=True`, raises `ValueError`. Proves: validation. |

### File group CRUD

| # | Test | What it proves |
|---|------|----------------|
| **4.8** | **create_file_group and get_file_group** | `create_file_group("Test", group_type="exam")`. `get_file_group(group_id)` returns group with empty members. Proves: create + get. |
| **4.9** | **add_to_file_group and list_file_groups** | Add two main files to group. `get_file_group(group_id).members` has two; `list_file_groups()` includes group. Proves: add + list. |
| **4.10** | **add_to_file_group with raw raises** | Try `add_to_file_group(group_id, raw_file_id)`. Raises `ValueError`. Proves: only main files. |
| **4.11** | **remove_from_file_group** | Add file, then `remove_from_file_group(group_id, file_id)`. Member gone; group still exists. Proves: remove. |
| **4.12** | **set_file_group_anchor and get_file_group_membership** | Add file, `set_file_group_anchor(group_id, file_id)`. Group's `anchor_id` set. `get_file_group_membership(file_id)` returns groups containing this file. Proves: anchor + membership. |
| **4.13** | **delete_file_group** | Create group, add member. `delete_file_group(group_id)`. Group gone; member file still in registry (get_file). Proves: group deleted, files kept. |

### suggest_groups

| # | Test | What it proves |
|---|------|----------------|
| **4.14** | **suggest_groups returns candidates** | Register 2+ files (copy fixture PDF to temp with different names). Set each: `doc_type='exam'`, `student_id='w'`, `subject='science'`, `metadata={'exam_date': '2025-11-12'}`. `suggest_groups()` returns at least one suggestion with 2+ candidate_files and matching match_basis. Proves: suggest. |
| **4.15** | **suggest_groups unclassified excluded** | Same 2 files but leave one with `doc_type='unknown'`. Suggestions only include classified; or empty if none match. Proves: only exam + metadata. |

### open_file_group

| # | Test | What it proves |
|---|------|----------------|
| **4.16** | **open_file_group no anchor raises** | Create group, add member, do not set anchor. `open_file_group(group_id)` raises `ConfigError`. Proves: guard. |
| **4.17** | **open_file_group with anchor** | Set anchor. Mock subprocess (like Phase 3 open_file). `open_file_group(group_id)` completes without error. Proves: happy path. |

**Passing all Phase 4 tests** (4.1–4.17) means: raw↔main and template↔completed relations work, file group CRUD and membership do too, `suggest_groups` returns candidates from classified exam files, and `open_file_group` enforces anchor. Phase 4 is then safe to call done.

---

## Phase 5: tests that confirm success

These tests give confidence that Phase 5 (Audit & CLI) is complete. Use a **temporary** DB. For `get_operation_log`, perform a few operations (e.g. register, update_metadata, create_file_group) then assert on the log. CLI tests invoke the CLI script (if present) with `--help` or minimal args and a temp DB via `--db`; no real drive.

### get_operation_log

| # | Test | What it proves |
|---|------|----------------|
| **5.1** | **get_operation_log no filters returns all ordered** | Register a file, create a group. `get_operation_log()` returns entries; order is `performed_at ASC`. Proves: baseline query and ordering. |
| **5.2** | **get_operation_log filter by file_id** | Register a file (get its id). `get_operation_log(file_id=id)` returns only entries for that file. Proves: file_id filter. |
| **5.3** | **get_operation_log filter by operation** | Perform register and update_metadata. `get_operation_log(operation='register')` returns only register entries. Proves: operation filter. |
| **5.4** | **get_operation_log filter by group_id** | Create a group, add a file. `get_operation_log(group_id=group_id)` returns only entries for that group. Proves: group_id filter. |
| **5.5** | **get_operation_log log_id returns one or empty** | Get any log entry id from a previous call. `get_operation_log(log_id=that_id)` returns a list of length 1 with that entry. `get_operation_log(log_id='nonexistent-uuid')` returns empty list. Proves: log_id lookup. |
| **5.6** | **get_operation_log since filter** | Perform two operations; note time in between or use a past `since`. Assert entries after `since` are included (or all if since is old). Proves: since filter. |

### CLI smoke tests

| # | Test | What it proves |
|---|------|----------------|
| **5.7** | **CLI --help exits 0** | Run the CLI (e.g. `python pdf_file_manager.py --help` or `python -m pdf_file_manager --help`) from the utility directory. Assert exit code 0 and output contains help. Skip if no CLI entry point. Proves: CLI invocable. |
| **5.8** | **CLI log --help with temp DB** | Run `python pdf_file_manager.py --db <temp.db> log --help`. Exit 0. Proves: --db accepted, log subcommand exists. |

**Passing all Phase 5 tests** (5.1–5.8) means: `get_operation_log` supports all filters and log_id, and the CLI can be invoked with a temp DB. Phase 5 is then safe to call done.

---

## How to run

- **Runner:** Use **pytest** (or the repo’s existing test runner if one is standard). Place tests in a `tests/` directory under `pdf_file_manager/` (e.g. `tests/test_manager.py`, `tests/test_inference.py`).
- **Isolation:** Each test (or each class) should create its own temp DB and temp dirs; no shared state with the real registry or real scan roots.
- **CI:** If the repo runs CI, add a step that runs the pdf_file_manager test suite (e.g. `pytest ai_study_buddy/utils/pdf_file_manager/tests/`).

---

## Summary

- **Level:** Utility-level plan only (unit + integration for this utility).
- **No E2E** against real DaydreamEdu; all tests use temp DB and temp dirs.
- **When:** Tests added per phase so each phase is testable before the next.
- **Where:** Tests in `tests/` under the utility; plan lives in this file and a short pointer in README.
