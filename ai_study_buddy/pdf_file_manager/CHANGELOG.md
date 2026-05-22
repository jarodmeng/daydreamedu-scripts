# Changelog

All notable changes to the pdf_file_manager utility are documented here.

---

## [v0.3.20] — GoodNotes auto-link after scan

- `scan_for_new_files(..., auto_link_goodnotes=True)` (default on) attempts `link_goodnotes_template_for_file` per **newly registered** GoodNotes `c_` / `_c_` main after registration (and after GoodNotes `compress_and_register` when applicable). Failures are **non-aborting**; outcome is on `ScanResult.template_link`.
- `dry_run=True` previews link via `ScanResult.template_link` without registering or linking.
- Helpers: `_preview_goodnotes_template_link`, `_try_link_goodnotes_template_for_file`, `_auto_link_goodnotes_after_scan`.
- Does not auto-register missing DaydreamEdu templates; exact stem match still required (see P1-3 filename policy). Pass `auto_link_goodnotes=False` to skip.

## [v0.3.19] — Registry-derived completion series

- New module `completion_series.py`: `CompletionSeries`, `CompletionSeriesMember`, `build_completion_series`, `series_id_for`, `slugify_student`.
- `PdfFileManager`: `get_completion_series`, `get_completion_series_for_file`, `get_completion_series_member`, `completion_series_id`, `next_attempt_sequence_for_completion`.
- Series order: `pdf_files.added_at` ascending, then resolved `path` (per [proposal 15](docs/proposals/15-completion-series-derived.md)).

## [v0.3.18] — Integrity validator: path-derived metadata drift

- `scripts/validate_pdf_registry_integrity.py` now reports **`path_inferred_metadata_drift`**: registered rows whose stored path-derived fields differ from what the current registered path implies (`subject`, `doc_type`, `student_id`, `is_template`, and invariant metadata keys such as `grade_or_scope`, `content_folder`, and `chinese_variant`).
- The validator now reports **`raw_main_folder_mismatches`** for linked raw/main pairs whose registered paths live in different folders, catching cases where one side was moved without the other.
- Added focused regression tests for both new checks in `tests/test_integrity_validator.py`.

## [v0.3.17] — Integrity validator: dangling `file_relations`

- `scripts/validate_pdf_registry_integrity.py` now reports **`dangling_file_relations`**: rows in `file_relations` whose **`source_id` or `target_id` is missing from `pdf_files`** (orphan edges, e.g. leftover `template_for` / `completed_from` or raw/main links after endpoint rows were removed without FK CASCADE when SQLite `PRAGMA foreign_keys` was off).
- Summary JSON and human-readable output include the new check; non-zero exit when any such row exists (same contract as other checks).
- **Operational hygiene:** remove orphans with  
  `DELETE FROM file_relations WHERE source_id NOT IN (SELECT id FROM pdf_files) OR target_id NOT IN (SELECT id FROM pdf_files);`  
  (after backup); prefer registry deletes through `PdfFileManager` with foreign keys enabled so CASCADE applies.

## [v0.3.16] — GoodNotes template resolver: `template/` branch + `completion/` paths

- `PdfFileManager.resolve_goodnotes_template_path(...)` now searches **`DaydreamEdu/template/<subject>/…`** before the legacy layout (no top-level branch), so mirrored GoodNotes files still resolve after template/completion-branch migration.
- Paths under **`DaydreamEdu/completion/…`** (or with a leading **`template/`** segment in the mirrored tail) strip that branch when deriving the general-scope remainder before probing candidate dirs.
- Docstring documents legacy vs prefab layouts; tests in `tests/test_goodnotes_helper.py` cover template-only and completion-branch cases.

## [v0.3.15] — Wake backup: centralized under `utils/backup` only

- Removed `pdf_file_manager/scripts/run_backup_on_wake.sh` and `install_run_on_wake.sh` (superseded by `ai_study_buddy/utils/backup/`).
- Added `utils/backup/migrate_wakeup_backup_paths.py` (+ `.sh` wrapper) to rewrite `~/.wakeup` after pulling this change if it still referenced the old script paths.

## [v0.3.14] — D_ROOT `template/` / `completion/` layout: scripts and docs

- **Completed operational migration** (outside core API changes): DaydreamEdu on-disk and registry paths now use a branch-first layout under `DAYDREAMEDU_ROOT`: `template/<subject>/…` and `completion/<subject>/…` (see [`docs/proposals/14-d-root-template-completion-top-level-split.md`](./docs/proposals/14-d-root-template-completion-top-level-split.md)).
- **One-off scripts** under `scripts/`:
  - `_migrate_d_root_top_level_branches.py` — dry-run and batched `PdfFileManager` moves + scan-root updates.
  - `_repair_raw_main_relation_dangling_edges.py` — remove orphan `file_relations` raw/main edges (optional post-migration hygiene).
  - `_prune_empty_dirs_d_root.py` — prune empty directories under D_ROOT; `--evict-macos-metadata` removes `.DS_Store` / `.localized` when they block `rmdir` (macOS / Google Drive).
- **Docs:** [`ai_study_buddy/docs/L4_FILE_FRAMEWORK.md`](../docs/L4_FILE_FRAMEWORK.md) on-disk diagram and notes; [`.cursor/commands/daydreamedu-leaf-registry-report.md`](../../.cursor/commands/daydreamedu-leaf-registry-report.md) path layout and cleanup guidance.
- **No change** to `pdf_file_manager.py` library semantics in this patch; strict enforcement of the new path shape in write APIs remains **deferred** (see proposal closure).

## [v0.3.13] — Remove `Archive` from grade/scope inference tokens

- Removed `Archive` from `PdfFileManager._GRADE_SCOPE_SEGMENTS`; accepted grade/scope inference tokens are now `P1`-`P6` and `PSLE`.
- Updated `_infer_from_path(...)` inference docstring/comments and student-mirror rule wording to match the new token set.
- Updated related tests/docs that described grade/scope inference tokens (including proposal/learning notes) so they no longer present `Archive` as an active accepted value.
- Added a historical-context note in `DECISIONS.md` where older decisions still mention `Archive` as part of earlier model assumptions.
- No registry data migration required (no live rows used `metadata.grade_or_scope='Archive'` at change time).

## [v0.3.12] — Canonical normalized file names

- Added canonical helper `normalize_pdf_display_name(name_or_path)` in `pdf_file_manager` as the single source of truth for human-facing filename normalization.
- Added computed `PdfFile.normal_name` (non-persisted) that delegates to the canonical helper.
- Normalization behavior:
  - iterative prefix stripping: `_raw_`, `_c_`, `raw_`, `c_`
  - extension removal via `Path(...).stem`
- Added `has_raw_pdf_prefix(name)` helper and migrated review completion-candidate checks to it.
- Migrated downstream `ai_study_buddy` production modules away from ad hoc prefix stripping to canonical normalization:
  - marking review title fallbacks
  - marking artifact-path normalization usage
  - split-book answer context parsing
  - file-question-info and marking migration workflows
- Added tests in `tests/test_normal_name.py` and updated marking artifact-core normalization expectations.
- No schema/database migration was required.

## [v0.3.11] — Enforce `metadata.unit` as book-only

- `register_file(...)` now raises `InvalidMetadataError` when `metadata.unit` is provided and `doc_type != 'book'`.
- `update_metadata(...)` now validates the effective doc type (existing or newly supplied) and raises `InvalidMetadataError` if the merged metadata would keep/set `unit` on non-book rows.
- `add_to_file_group(..., role=...)` now raises `ValueError` for non-book files; role-to-`metadata.unit` mapping remains supported only for `doc_type='book'`.
- `link_to_template(..., inherit_metadata=True)` behavior is unchanged (secondary metadata copier).
- Tests added/updated:
  - `test_register_file_rejects_unit_metadata_for_non_book_doc_type`
  - `test_update_metadata_rejects_unit_for_non_book_doc_type`
  - `test_add_to_file_group_role_on_non_book_raises`
  - `test_delete_metadata_keys_removes_keys_and_syncs_to_raw` now uses `doc_type='book'`.

## [v0.3.10] — Metadata key deletion API

- Added `delete_metadata_keys(file_id_or_path, keys)` to `PdfFileManager` for explicit metadata-key removal (instead of merge-only nulling via `update_metadata`).
- The new API validates input keys, updates the row metadata JSON, logs `delete_metadata_keys`, and preserves existing metadata keys not targeted for deletion.
- Raw/main parity is maintained: deleting metadata keys on one side of a linked pair propagates the same key deletion to the counterpart.
- Added `test_delete_metadata_keys_removes_keys_and_syncs_to_raw` in `tests/test_update_metadata.py`.

## [v0.3.9] — Canonical doc_type enums and strict validation

- **Canonical `doc_type` set:** `PdfFile.doc_type` is now constrained to the canonical values `exam`, `exercise`, `book`, `activity`, and `note`. Legacy/unused values (`worksheet`, `notes`, `book_exercise`, `practice`, `unknown`) are no longer accepted.
- **Strict validation:** All code paths that accept `doc_type` (including `register_file(...)`, `update_metadata(..., doc_type=...)`, `_refresh_from_path(...)`, and path inference) now route through a single `_normalize_doc_type(...)` helper, which raises `InvalidDocTypeError` on any non-canonical value instead of silently accepting or mapping it.
- **Path inference alignment:** `_infer_from_path(...)` maps content-folder segments to canonical enums (`Exercise` → `exercise`, `Note` → `note`) while preserving `Exam`, `Book`, and `Activity` behaviour. Existing inference tests updated accordingly.
- **Registry migration helper:** Added `scripts/migrate_doc_type_enums.py` for a one-shot migration of existing registries, rewriting `worksheet`→`exercise` and `notes`→`note` and asserting that no rows remain in removed/legacy values. Supports `--dry-run` to preview changes.
- **Docs:** Updated `DATA_MODEL.md` `PdfFile.doc_type` reference to the new enum set and documented strict failure behaviour in this changelog entry.

## [v0.3.8] — Delete integrity hardening for `file_relations`

- **`delete_file`:** Before removing the `pdf_files` row, deletes every `file_relations` row whose `source_id` or `target_id` matches the file id (raw/main, template/completion, etc.), so the registry does not retain orphan edges when SQLite foreign-key cascades are inactive on the connection.
- **`_get_connection`:** Executes `PRAGMA foreign_keys = ON` immediately after opening the SQLite connection, making FK-backed constraints and cascades active for manager-managed operations.
- **Tests:** `test_delete_file_keep_related_false_cascades_to_raw` asserts no `file_relations` reference deleted main/raw ids.
- **Tests:** Added `test_manager_connection_enables_foreign_keys` in `tests/test_schema.py`.
- **Docs:** [SPEC.md](./SPEC.md) § `delete_file` step list updated.
- **Compatibility:** Explicit `delete_file` cleanup remains in place as defense in depth even with FK enforcement enabled.

## [v0.3.7] — Integrity validator: registry health checks

- Extended `validate_pdf_registry_integrity` with additional audits for large-registry hygiene:
  - registered paths that no longer exist on disk
  - general-scope `Book/<name>/` book mains: shared book group, `metadata.unit`, and label consistency
  - student-scope rows missing `student_id` (with path-based inference hint)
  - general-scope mains with `is_template` not true, and student-scope with `is_template` true
- Report `summary` / `checks` JSON and human-readable sections include the new findings.
- Added tests in `tests/test_integrity_validator.py`.

## [v0.3.6] — Book groups: general templates only

- Updated `ensure_book_group_from_path(...)` to treat `group_type='book'` membership as canonical **general-scope template mains only**.
- Added shared student-mirror path predicate logic so `_infer_from_path(...)` and book-group sync use the same rule.
- Student mirror Book paths are now skipped by `ensure_book_group_from_path(...)` (returns `None`): no group creation, no member adds, no anchor updates from student paths.
- Book-group sync now reconciles membership by desired set (add missing, prune stale), so old non-template or wrong-folder members are removed when a general Book folder is synced.
- Added regression coverage for:
  - student path skip/no-create behavior,
  - mixed general+student same-label scans,
  - desired-set prune reconciliation.

## [v0.3.5] — Template resolver: student `DaydreamEdu` paths

- **`resolve_goodnotes_template_path`:** Accepts a student completion path under a `.../DaydreamEdu/...` tree (same layout as the GoodNotes mirror), not only under `GoodNotes`. Still resolves the general-scope `_c_` template in DaydreamEdu; error messages use neutral “mirrored template” / “Completion filename” wording where appropriate.
- **`link_template_by_paths`:** Allows either a `GoodNotes` or (student) `DaydreamEdu` segment in the completion path, consistent with the resolver.
- **Tests:** `test_resolve_goodnotes_template_math_p6_from_daydreamedu_student_completion` in `tests/test_goodnotes_helper.py`.

## [v0.3.4] — `chinese_variant`: `standard` replaces legacy `foundation`

- **Standard 华文 vs 高华:** Stored `metadata.chinese_variant` for mainstream Chinese exam files is **`standard`** (not `foundation`, which collided with SEAB “Foundation Chinese Language”).
- **Strict validation:** The legacy value `"foundation"` in `metadata.chinese_variant` is invalid — **`InvalidMetadataError`** on read (`get_file`, `find_files`, …) and on persist (`register_file`, `update_metadata`, …). Fix rows in SQLite or pass `chinese_variant="standard"`.
- **Inference:** `_infer_from_path` sets `chinese_variant='standard'` for `华文` / `.chinese.` exam filenames (unchanged detection rules).
- **Integrity script:** `validate_pdf_registry_integrity` reports rows with `chinese_variant=foundation`; raw/main drift compares stored JSON as before.
- **Cleanup:** Removed the one-time `migrate_chinese_variant_foundation_to_standard()` helper after registry migration.

## [v0.3.3] — Remove MCP interface, Python API only

- Removed MCP implementation modules from the package (`pdf_file_manager_mcp.py`, `pdf_file_manager_mcp_server.py`).
- Removed MCP-focused tests (`tests/test_mcp_tools.py`, `tests/test_mcp_server.py`).
- Retired `MCP.md` and updated package docs (`README.md`, `SPEC.md`, `TESTING.md`) to document Python `PdfFileManager` as the only supported machine interface.
- Migration note: remove stale `pdf_file_manager` MCP server entries from local Cursor/Codex MCP configuration.

## [v0.3.2] — GoodNotes template resolver: general-scope only

- Updated `resolve_goodnotes_template_path` policy to search only the mirrored **general-scope** DaydreamEdu folder for `_c_` template/source files.
- Removed student-scope DaydreamEdu fallback from resolver behavior to enforce canonical template storage in general scope.
- Updated GoodNotes resolver/linking tests to reflect the policy and added coverage for the same-basename shadowing case.
- Updated docs (`README.md`, `MCP.md`, `SPEC.md`) to document the general-scope-only template lookup rule.

## [v0.3.1] — Filesystem utilities extracted to `ai_study_buddy.files`

- Moved root resolver ownership to `ai_study_buddy/files/roots.py`:
  - `resolve_daydreamedu_root()`
  - `resolve_goodnotes_root()`
- Removed root resolver definitions/exports from `pdf_file_manager` and migrated Python call sites to the new module.
- Added shared leaf-folder traversal helpers in `ai_study_buddy/files/leaf_folders.py`:
  - `list_leaf_folders_under_root(...)`
  - `list_daydreamedu_leaf_folders_under_root(...)`
  - `list_goodnotes_leaf_folders_under_root(...)`
- Moved local root config files from `ai_study_buddy/pdf_file_manager/` to `ai_study_buddy/`:
  - `local_daydreamedu_root.txt` / `.example.txt`
  - `local_goodnotes_root.txt` / `.example.txt`
- Updated docs/commands/skills and backup scripts to use new resolver ownership and new local config file locations.
- Added focused test coverage under `ai_study_buddy/files/tests/` (on-disk fixtures in `files/tests/fixtures/`) for root resolution and leaf-folder traversal.

## [v0.3.0] — Package-standardized imports and invocation

- Standardized `PdfFileManager` usage on package paths:
  - canonical import: `from ai_study_buddy.pdf_file_manager.pdf_file_manager import ...`
  - package re-export: `from ai_study_buddy.pdf_file_manager import ...`
- Added `ai_study_buddy/pdf_file_manager/__init__.py` public exports for manager types and exceptions.
- Migrated runtime, scripts, MCP modules, and test suite away from bare `from pdf_file_manager import ...` imports and related `sys.path` manipulation used only for import resolution.
- Updated operational docs to align with package invocation:
  - `README.md`, `MCP.md`, `SPEC.md`, `DECISIONS.md`, and learning notes
  - Cursor command/skill guidance under `.cursor/` for registry tasks
- Canonical startup guidance now prefers module invocation from repo root (for example `python3 -m ai_study_buddy.pdf_file_manager.pdf_file_manager_mcp_server ...`).
- Bare import style remains deprecated for transitional compatibility and is planned for full removal after migration stabilization.

## [v0.2.12] — Tiered backup retention on wake

- Added `scripts/apply_backup_tiering.py` to enforce tiered backup retention for timestamped registry backups:
  - keep `0-7` day backups as raw `.db` files in the backup root
  - move `7-60` day backups to `coldstorage/` as `.db.zst` files
  - prune backups older than 60 days
- Updated `scripts/run_backup_on_wake.sh` to run both steps on wake:
  1. `backup_pdf_registry.py --timestamp`
  2. `apply_backup_tiering.py --hot-days 7 --cold-days 60`
- Keeps wake-driven backups cloud-friendly while controlling long-term storage growth.

## [v0.2.11] — Scan-root student_id auto-inference

- `add_scan_root(path, student_id=None)` now auto-infers and stores `student_id` from a unique matching registered `students.email` segment in the scan-root path.
- Explicit `student_id` still takes precedence; ambiguous/no-match paths continue to store `student_id=None`.
- `ensure_scan_root(...)` now inherits this behavior when creating a missing scan root, while preserving idempotent no-change behavior for existing rows.
- Added tests for infer-on-add, explicit override precedence, no-email fallback, and ensure-create inference in `tests/test_config.py`.
- Updated `README.md` and `SPEC.md` to document scan-root `student_id` precedence and persistence behavior.

## [v0.2.10] — GoodNotes root resolution

- Added **`resolve_goodnotes_root()`** with **`GOODNOTES_ROOT`**, gitignored **`local_goodnotes_root.txt`** (see [`../local_goodnotes_root.example.txt`](../local_goodnotes_root.example.txt)), and **sibling discovery** (`DaydreamEdu`’s parent + `GoodNotes`) when the DaydreamEdu root is already configured.
- Updated repo [`.gitignore`](../../.gitignore), [`ARCHITECTURE.md`](./ARCHITECTURE.md), [`README.md`](./README.md), [`SPEC.md`](./SPEC.md), and the Cursor [`pdf-file-manager`](../../.cursor/skills/pdf-file-manager/SKILL.md) skill; tests in `tests/test_config.py`.

## [v0.2.9] — Cross-book answer mappings

- Relaxed `book_answer_mappings` validation so registered `doc_type='book'` main files can map across different `group_type='book'` collections.
- Updated focused tests for cross-book mapping behavior in `tests/test_book_answer_mappings.py`.
- Updated `README.md`, `SPEC.md`, and `MCP.md` to document the relaxed constraint.

## [v0.2.8] — Scan dry-run preview and explicit-root student_id

- **`scan_for_new_files(..., dry_run=True)`:** Returned `PdfFile` previews now use the same path inference as a real run (`doc_type`, `subject`, `is_template`, `metadata`, inferred `file_type` where applicable) instead of placeholder `unknown` rows with empty metadata.
- **Explicit `roots=[...]`:** Each resolved path is matched against configured `scan_roots` so a registered scan root’s `student_id` applies when the caller passes that folder explicitly (same precedence as when scanning all configured roots: configured root `student_id`, then email-segment inference).
- Tests: `test_scan_dry_run_explicit_configured_root_uses_scan_root_student_id`, `test_scan_dry_run_explicit_goodnotes_root_infers_student_id_without_configured_scan_root`, `test_scan_dry_run_book_root_reports_inferred_book_metadata` in `tests/test_scan.py`.
- Docs: `README.md`, `SPEC.md`, `ARCHITECTURE.md`, `TESTING.md`, `MCP.md`, `docs/learnings/LEARNING_STUDENT_ID_INFERENCE_GAP.md`.

## [v0.2.7] — Book answer mappings

- Added first-class `book_answer_mappings` support for mapping one registered `doc_type='book'` unit file to an inclusive page range in one registered `doc_type='book'` answer file from the same `group_type='book'` collection.
- Added Python API methods `set_book_answer_mapping`, `get_book_answer_mapping`, `list_book_answer_mappings`, `delete_book_answer_mapping`, and `import_book_answer_mappings_from_json`.
- Added MCP tools `pdf_set_book_answer_mapping`, `pdf_get_book_answer_mapping`, `pdf_list_book_answer_mappings`, and `pdf_delete_book_answer_mapping`.
- Added operation-log entries for create/update/delete of mappings: `book_answer_mapping_set`, `book_answer_mapping_update`, and `book_answer_mapping_delete`.
- Imported the validated pilot ground-truth JSON files for:
  - `Science Practice Primary 5 and 6`
  - `Power Pack Science PSLE`
  - `Power Pack Chinese PSLE`
  - `Power Pack Math PSLE`
  - `Power Pack English PSLE` practice subset
- Updated `README.md`, `ARCHITECTURE.md`, `SPEC.md`, and Proposal 7 to document the new relation and its constraints.

## [v0.2.6] — Registry path repair and `file_type` updates

### 1. `rename_file` external path sync

- When the registry still points at a missing path but the **intended** basename already exists in the same folder (for example after a manual or tool rename to `_c_…` on disk), `rename_file(...)` updates `name` and `path` without calling `mv`, matching the existing “sync DB to disk” branch.
- If that on-disk target is a **file**, the row’s **`size_bytes`** is refreshed from the file on disk so compressed mains do not keep the pre-compress size.

### 2. `update_metadata` and raw/main parity

- **`file_type`:** optional `update_metadata(..., file_type='main'|'raw'|'unknown')` to correct or promote rows (for example `unknown` → `main` after compression) without re-running compression. Invalid values raise `ValueError`.
- **Parity sync:** when linked raw/main pairs are updated, the counterpart is chosen using the **updated** `file_type` on the row being edited, so a single call can set `file_type='main'` together with `doc_type` / `subject` / `metadata` and still propagate those fields to the linked raw.

### 3. MCP

- `pdf_update_metadata` accepts optional `file_type` (same enum as the Python API). Cursor MCP descriptor `pdf_update_metadata.json` updated accordingly.

### 4. Documentation and tests

- `SPEC.md` (API and edge cases), `MCP.md`, and `TESTING.md` updated for the above.
- Implemented **TESTING.md** cases **3.12b** / **3.12c**: `test_update_metadata_file_type_syncs_invariant_fields_to_raw` and `test_update_metadata_invalid_file_type_raises` in `tests/test_update_metadata.py`; `test_rename_file_syncs_db_when_source_missing_on_disk` in `tests/test_file_ops.py`.

---

## [v0.2.5]

### 1. Documentation change

- Documented **local-only** configuration for the DaydreamEdu sync path: environment variable `DAYDREAMEDU_ROOT` and gitignored `local_daydreamedu_root.txt` (with [`../local_daydreamedu_root.example.txt`](../local_daydreamedu_root.example.txt)), plus [`resolve_daydreamedu_root()`](../files/roots.py) in [`../files/roots.py`](../files/roots.py). Updated [`ARCHITECTURE.md`](./ARCHITECTURE.md), [`README.md`](./README.md), and the Cursor [`pdf-file-manager`](../../.cursor/skills/pdf-file-manager/SKILL.md) skill so no personal paths are required in Git.
- Added [`DATA_MODEL.md`](./DATA_MODEL.md) as the dedicated reference for file/group field semantics, including `metadata.unit` vs group `label`/`group_type` and returned data class shapes.
- Refactored [`SPEC.md`](./SPEC.md) to focus on API and operation contract details; moved data-model-heavy guidance and dataclass reference out to `DATA_MODEL.md`.
- Updated [`README.md`](./README.md) docs navigation and cross-links so users and agents can find metadata/group semantics quickly without overloading the overview page.
- Updated [`MCP.md`](./MCP.md) with a concise metadata-vs-groups note for MCP users.

### 2. Unit as canonical function label

- Updated `add_to_file_group(..., role=...)` behavior so `role` is treated as a backward-compatible input and mapped into `pdf_files.metadata.unit` when the file has no unit yet.
- New group-member inserts now keep `file_group_members.role` unset and rely on `metadata.unit` as the canonical per-file function/unit label.

## [v0.2.4] — Direct-child scan roots

- Changed `scan_for_new_files(...)` to scan only direct `*.pdf` children of each supplied root instead of recursing into nested subfolders.
- This prevents accidental capture of nested folders such as `Not completed/` when the caller intended to scan only the selected parent folder.
- Added regression coverage in `tests/test_scan.py` proving nested PDFs are ignored unless their folder is passed explicitly as a scan root.
- Updated `README.md`, `SPEC.md`, and `TESTING.md` to document the new scan-root contract.

## [v0.2.3] — Main/raw metadata parity enforcement

### 1. Missing `student_id` inference

- See [LEARNING_STUDENT_ID_INFERENCE_GAP.md](./docs/learnings/LEARNING_STUDENT_ID_INFERENCE_GAP.md).
- Added fallback `student_id` inference from registered `students.email` path segments in `register_file(...)` and `scan_for_new_files(...)`.
- This closes gaps where explicit-root scans or GoodNotes scans could previously classify files correctly while still leaving `student_id` unset.
- Documented student-id inference precedence in `ARCHITECTURE.md` and `SPEC.md`.

### 2. Main/raw invariant metadata drift

- See [LEARNING_MAIN_RAW_METADATA_DRIFT.md](./docs/learnings/LEARNING_MAIN_RAW_METADATA_DRIFT.md).
- Added raw/main invariant metadata parity enforcement to `update_metadata(...)` so linked raw/main pairs stay synchronized on document-level fields.
- Added `repair_main_raw_metadata_drift()` to backfill existing raw/main drift by copying canonical main-file values onto raw records.
- Added tests covering raw/main parity during compression, parity-preserving metadata updates, and repair of existing drift.
- Documented raw/main invariant metadata expectations and parity behavior in `README.md`, `ARCHITECTURE.md`, and `SPEC.md`.

### 3. Reproducible integrity validation

- Added [`scripts/validate_pdf_registry_integrity.py`](./scripts/validate_pdf_registry_integrity.py) as a standalone validator for the three integrity problems investigated during this release cycle:
  - lingering `doc_type='unknown'` records
  - missing `student_id` in student-scoped folders
  - raw/main invariant metadata drift
- Added `tests/test_integrity_validator.py` to keep the validator reproducible and regression-tested.
- Documented the validator entrypoint in `README.md`.

## [v0.2.2] — Book doc_type/group_type support

- Added `book` as a supported `doc_type` and `group_type`.
- Extended schema bootstrap to migrate existing registries so the new `book` enum values are accepted.
- Extended `_infer_from_path` and `scan_for_new_files` so `.../Book/<book name>/...` folders are scanned as `doc_type='book'` with inferred `metadata.unit`.
- Added automatic syncing of `group_type='book'` file groups from scanned book folders, with only `main` files added as members.
- Added `ensure_book_group_from_path(...)` helper for idempotent book-group creation/sync.
- Added tests covering book inference, book scan behavior, and `book` file-group creation.

## [v0.2.1] — GoodNotes-safe compression and template resolution

- Added `preserve_input` flag to `compress_and_register` to support GoodNotes-safe compression: originals remain at their paths and `_c_` mains are created alongside and linked as raw↔main.
- Updated `scan_for_new_files` to detect `GoodNotes/` paths and automatically use `preserve_input=True` so GoodNotes backups are never renamed or moved.
- Implemented `resolve_goodnotes_template_path` and exposed it via the MCP tool `pdf_resolve_goodnotes_template` to resolve GoodNotes main paths to DaydreamEdu `_c_` templates based on folder mirroring and naming conventions.
- Extended MCP `pdf_compress_and_register` schema to accept `preserve_input`, and documented GoodNotes behaviour in `MCP.md`, `ARCHITECTURE.md`, `SPEC.md`, and `README.md`.
- Added `link_goodnotes_template_for_file` / `link_goodnotes_templates_for_root` and MCP tools to wrap GoodNotes template resolution plus linking with strict registry defaults.

## [v0.2.0] — MCP interface, server hardening, and CLI removal

- Added the MCP machine interface: wrapper/tool contract in `pdf_file_manager_mcp.py` and FastMCP binding/entrypoint in `pdf_file_manager_mcp_server.py`.
- Added MCP-focused tests in `tests/test_mcp_tools.py` and `tests/test_mcp_server.py`.
- Added FastMCP tool metadata, readonly-only server mode, connection docs in `MCP.md`, and a real `FastMCP` registration test.
- Updated current-facing docs to prefer Python API + MCP as the supported interfaces.
- Removed the legacy built-in CLI layer from `pdf_file_manager.py` and deleted the CLI smoke tests to avoid maintaining a second, partial machine interface.

---

## [v0.1.1] — Inference improvements + proposals 1–4

Merges all prior **Unreleased** changes (inference) and implements the four API/CLI proposals from `docs/learnings/LEARNING_FROM_FIRST_RUN.md` and `docs/proposals/`.

- **Path-based is_template inference:** `_infer_from_path` sets `is_template` from the path (student folder vs grade/scope). Scan applies this via `update_metadata`. See ARCHITECTURE § Folder-based inference; tests in `test_inference.py`.
- **Chinese exam variant inference:** For `subject='chinese'` and `doc_type='exam'`, `_infer_from_path` infers `metadata.chinese_variant` from the filename (`higher` / `standard`; invalid legacy `foundation` rejected — see v0.3.4). Documented in ARCHITECTURE § Metadata schemas; tests in `test_inference.py`.
- **Proposal 1 — Ensure students and scan roots:** `ensure_student(student_id, name, email=None)` and `ensure_scan_root(path, student_id=None)`; idempotent helpers. Tests in `test_config.py`.
- **Proposal 2 — Scan CLI:** `pdf_file_manager scan [--root PATH ...] [--dry-run] [--min-savings-pct N] [--progress]`; uses configured scan roots when `--root` omitted; `ConfigError` when no roots. Tests in `test_cli.py`.
- **Proposal 3 — Coverage / read‑only registry paths:** `find_leaf_dirs(base)` (static), `report_coverage(base_path=None, from_registry=False)` returning `CoverageReport`; `coverage` CLI with `--base` and `--from-registry`. Tests in `test_coverage.py` and `test_cli.py`.
- **Proposal 4 — Template linking by path:** `link_template_by_paths(completed_path, template_path, inherit_metadata=True)`; `link-template` CLI with `--template`, `--completed`, `--no-inherit-metadata`. Tests in `test_relations.py` and `test_cli.py`.

---

## [v0.1.0] — 5-phase build and test plan

First working version: SQLite registry, manager, operation log, config and file lifecycle, read/update/delete, relations and groups, audit log query, and minimal CLI. Delivered via a 5-phase build and test plan; all phase tests pass.

### Phase 1 — Foundation

- **Schema:** Seven tables (`students`, `pdf_files`, `file_relations`, `file_groups`, `file_group_members`, `operation_log`, `scan_roots`) with constraints; schema in `schema.sql` in the utility folder.
- **PdfFileManager:** Init with default DB path (env `PDF_REGISTRY_PATH` or repo-relative `ai_study_buddy/db/pdf_registry.db`) or custom path; auto-create DB and schema on first use.
- **Operation log:** Every C/U/D writes to `operation_log` via `_log_operation` (operation, file_id, group_id, performed_at, performed_by, before_state, after_state, notes).

### Phase 2 — Config & file lifecycle

- **Students:** `add_student`, `get_student`, `list_students`.
- **Scan roots:** `add_scan_root`, `remove_scan_root`, `list_scan_roots`.
- **Register:** `register_file(path, ...)` — path must exist; infers `file_type` from `_raw_` prefix; optional doc_type, student_id, subject, metadata; raises `AlreadyRegisteredError` if path already registered.
- **Compress and register:** `compress_and_register(file_id_or_path, ...)` — register if missing, then move to `_raw_<name>`, call real `compress_pdf`, insert main + raw rows and relations when savings ≥ threshold; otherwise restore and mark main.
- **Scan:** `scan_for_new_files(roots=None, dry_run=False)` — walk roots (or configured), skip registered paths; for `_raw_` files register and link to main; for others run `compress_and_register`; populate `student_id` from root when set.

### Phase 3 — Read / update / delete

- **Read:** `get_file(file_id)`, `find_files(query=..., file_type=..., doc_type=..., student_id=..., subject=..., is_template=..., has_raw=...)`.
- **Update:** `update_metadata(file_id_or_path, ...)` — merge metadata; validate `subject` (english, math, science, chinese); log `update_metadata`. `rename_file`, `move_file` — disk + DB + log; raise `ValueError` if destination exists.
- **Delete:** `delete_file(file_id_or_path, keep_related=False, ...)` — snapshot relations and group members, log delete, remove from groups (clear anchor if needed), remove file from disk, delete row; cascade to raw when `keep_related=False`.
- **Open:** `open_file(file_id_or_path)` — resolve path; raise `FileNotFoundError` if missing; open via platform command (e.g. macOS `open`).

### Phase 4 — Relations & groups

- **Raw ↔ main:** `get_related_files(file_id)`, `link_files(source_id, target_id, relation_type)`, `unlink_files(source_id, target_id)`; `has_raw` kept in sync.
- **Template ↔ completion:** `link_to_template(completed_id, template_id, inherit_metadata=True)`, `unlink_template(completed_id)`, `get_template(file_id)`, `get_completions(template_id)`; validation (both main, template `is_template=True`, completed `is_template=False`, not already linked).
- **File groups:** `create_file_group`, `add_to_file_group` (main only), `remove_from_file_group`, `set_file_group_anchor`, `update_file_group_notes`, `get_file_group`, `list_file_groups`, `get_file_group_membership`, `delete_file_group`; `open_file_group(group_id)` opens anchor (raises `ConfigError` if no anchor).
- **Suggest groups:** `suggest_groups()` — main files with `doc_type='exam'`, `is_template=False`, and `metadata.exam_date`; group by (student_id, subject, exam_date); return `list[SuggestedGroup]` for groups of size ≥ 2.

### Phase 5 — Audit & CLI

- **Operation log query:** `get_operation_log(file_id=None, group_id=None, operation=None, since=None, log_id=None)` — optional filters; if `log_id` set return at most one entry (empty if not found); otherwise order by `performed_at ASC`; return `list[OperationRecord]` with parsed before_state/after_state.
- **CLI:** Entry point in `pdf_file_manager.py` (`if __name__ == "__main__"`). Global `--db`; subcommand `log` with `--file`, `--group`, `--operation`, `--since`, `--id`; `--help` on main and subcommands.

### Testing

- **Phase 1:** 6 tests (schema, custom/default DB path, operation log write).
- **Phase 2:** 14 tests (students, roots, register_file, compress_and_register, scan dry_run and full); uses DaydreamEdu fixture (copy to temp dir); real `compress_pdf`.
- **Phase 3:** 22 tests (get_file, find_files filters, update_metadata merge/validation, rename/move, delete with/without cascade, open_file); open_file subprocess mocked in test to avoid blocking dialog.
- **Phase 4:** 17 tests (get_related_files, link/unlink files, link_to_template/get_template/get_completions/unlink, validation, file group CRUD, suggest_groups, open_file_group).
- **Phase 5:** 8 tests (get_operation_log no filters + ordering, filters by file_id/operation/group_id/log_id/since; CLI --help and --db log --help).

All tests use a temporary DB and (where needed) temp dirs and the shared fixture; no real drive or production registry.
