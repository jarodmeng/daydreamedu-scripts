# Proposal 16: Goodnotes document timestamps for registered `g_root` mains

**Status:** Implemented (2026-05-25) — core API, tests, and docs shipped in `pdf_file_manager` v0.3.21; optional Phase 2 batch helper remains future work  
**Audience:** `pdf_file_manager` maintainers, AI Study Buddy agents, GoodNotes registration/linking workflows, inventory/browser consumers  
**Related:** [L4_FILE_FRAMEWORK.md](../../../docs/L4_FILE_FRAMEWORK.md#goodnotes-files), [TODO.md P1-3](../../../TODO.md), [`files` root helpers](../../../files/SPEC.md)

---

## Motivation

Registered `g_root` files are PDFs produced by Goodnotes Auto Backup and stored under `GOODNOTES_ROOT`. They are useful as normal on-disk PDFs, but they currently lose an important piece of provenance: when the source Goodnotes notebook was created/imported, last updated in Goodnotes, and last modified according to Goodnotes search metadata.

Local Goodnotes metadata can answer this for active notebooks:

| Field | Source | Meaning |
|-------|--------|---------|
| `created_at` | `projection.sqlite.documents.created_at` | Best candidate for notebook creation/import date |
| `updated_at` | `projection.sqlite.documents.updated_at` | Goodnotes app-level update timestamp; matches Goodnotes list date |
| `last_modified` | `fts.sqlite.document_meta.last_modified` | Search/index metadata timestamp |

For AI Study Buddy, these timestamps are useful for:

- ordering student completion attempts that originated in Goodnotes,
- auditing whether an Auto Backup PDF is stale relative to Goodnotes,
- correlating registry rows with Goodnotes notebook lifecycle,
- giving agents a supported API instead of ad hoc `sqlite3` reads from the Goodnotes app container.

## Problem statement

Today, code can query `PdfFileManager` for registered `g_root` files, but it cannot ask:

> "What are the Goodnotes `created_at`, `updated_at`, and `last_modified` timestamps for this registered main PDF?"

Agents can work around this manually by:

1. deriving a backup stem from the registered PDF path,
2. accounting for Goodnotes Auto Backup stripping one leading underscore,
3. querying Goodnotes local SQLite databases,
4. joining `documents` to `fts.document_meta`,
5. handling no-match and ambiguous-match cases.

That repeated logic is brittle. It also risks silently guessing wrong when a registered file is a compressed `_c_` main derived from a Goodnotes notebook with a different name.

## Goals

1. Add a supported `PdfFileManager` API for Goodnotes document timestamp lookup for registered `g_root` **main** files.
2. Keep the lookup read-only against Goodnotes local databases.
3. Return structured match status, not just timestamps, so callers can see exact / underscore-restored / raw-source / no-match / ambiguous outcomes.
4. Preserve current `PdfFile` shape and registry schema.
5. Return the matched Goodnotes document's full app-folder path.
6. Document the Goodnotes-specific filename matching rule and limitations.

## Non-goals

- Do not mutate Goodnotes databases.
- Do not require Goodnotes to be running.
- Do not add Goodnotes timestamps to the registry schema in this proposal.
- Do not rename or repair registered files.
- Do not infer timestamps for non-GoodNotes roots.
- Do not fuzzy-match mismatched names. Deterministic raw-source fallback is in scope; approximate string matching is not.
- Do not solve [TODO.md P1-3](../../../TODO.md) filename policy migration; this proposal may inform it, but does not complete it.

## Current findings

Local Goodnotes metadata on macOS was observed at:

- `~/Library/Containers/com.goodnotesapp.x/Data/Library/Databases/projection.sqlite`
- `~/Library/Containers/com.goodnotesapp.x/Data/Library/Databases/fts.sqlite`

Relevant tables:

| Table | Fields |
|-------|--------|
| `projection.sqlite.documents` | `id`, `name`, `created_at`, `updated_at`, `deleted` |
| `fts.sqlite.document_meta` | `document_id`, `name`, `last_modified`, `is_deleted` |
| `projection.sqlite.folder_to_folder_items` | folder path and denormalized document timestamps |
| `projection.sqlite.attachments` | imported PDF asset key, not original Finder path |

Observed matching behavior:

- Goodnotes Auto Backup can strip one leading underscore from filenames.
- Therefore, a Goodnotes document named `_c_foo` may back up as `c_foo.pdf`.
- A registered `g_root` PDF stem should first be matched against:
  - the exact Goodnotes document name,
  - the same stem with one leading `_` added.
- If the registered row is a compressed completion main (`_c_...` / `c_...`) and that first pass does not match, v1 should also try a deterministic **raw-source fallback**:
  - prefer the linked raw file's basename stem when the registry has a raw/main relation,
  - otherwise derive a raw-source candidate by removing one technical completion prefix (`_c_` or `c_`) from the main stem,
  - apply the same exact / leading-underscore-restored candidate rule to that raw-source stem.
- In the current local data, most registered `g_root` rows match by one of those rules. Known exceptions exist where a registered `_c_` main appears to be derived from a Goodnotes document that does not itself have `_c_`.

## Proposed design

### New data objects

Add a small module, for example:

`ai_study_buddy/pdf_file_manager/goodnotes_metadata.py`

With dataclasses:

```python
@dataclass(frozen=True)
class GoodnotesDocumentTimestamps:
    created_at: str | None
    updated_at: str | None
    last_modified: str | None
    created_at_raw: float | None
    updated_at_raw: float | None
    last_modified_raw: str | None

@dataclass(frozen=True)
class GoodnotesDocumentMatch:
    status: Literal[
        "matched_exact",
        "matched_leading_underscore_restored",
        "matched_raw_source",
        "matched_raw_source_leading_underscore_restored",
        "not_goodnotes_root",
        "not_main_file",
        "metadata_unavailable",
        "not_found",
        "ambiguous",
    ]
    file_id: str
    registered_path: str
    backup_stem: str
    candidate_names: tuple[str, ...]
    matched_candidate_name: str | None
    goodnotes_document_id: str | None
    goodnotes_document_name: str | None
    goodnotes_folder_path: str | None
    goodnotes_folder_ids: tuple[str, ...]
    timestamps: GoodnotesDocumentTimestamps | None
    message: str | None = None
```

Notes:

- `created_at`, `updated_at`, and `last_modified` should be returned as UTC ISO-8601 strings where possible.
- Raw values should be retained because Goodnotes stores `documents.created_at` / `updated_at` as Unix milliseconds, while `document_meta.last_modified` is already a datetime string.
- `status` is part of the API contract. Callers must not infer success from nullable timestamp fields alone.
- `goodnotes_folder_path` should be a slash-separated app folder path reconstructed from `folder_to_folder_items` / `folders`, not a filesystem path.

### New `PdfFileManager` API

Add methods:

```python
def get_goodnotes_document_timestamps_for_file(
    self,
    file_id: str,
    *,
    include_deleted: bool = False,
) -> GoodnotesDocumentMatch:
    ...

def get_goodnotes_document_timestamps_for_path(
    self,
    path: str | Path,
    *,
    include_deleted: bool = False,
) -> GoodnotesDocumentMatch:
    ...
```

Contract:

1. Resolve the registry row by `file_id` or exact path.
2. Return `not_goodnotes_root` if the row is not under `GOODNOTES_ROOT`.
3. Return `not_main_file` if `file_type != "main"`.
4. Derive `backup_stem = Path(pdf_file.path).stem`.
5. Primary candidate names, in order:
   - `backup_stem`
   - `"_" + backup_stem` when that differs from `backup_stem`
6. If primary candidates do not match, derive raw-source candidate names for registered completion mains:
   - prefer linked raw file stem from the registry raw/main relation,
   - else, if `backup_stem` starts with `_c_`, try `backup_stem.removeprefix("_c_")`,
   - else, if `backup_stem` starts with `c_`, try `backup_stem.removeprefix("c_")`,
   - for the raw-source stem, try both exact and one-leading-underscore-restored names.
7. Query active Goodnotes documents by candidate name:
   - `documents.deleted = 0`
   - `document_meta.is_deleted = 0`
   - unless `include_deleted=True`
8. If exactly one document matches, return timestamps, folder path, and status:
   - `matched_exact` if `documents.name == backup_stem`
   - `matched_leading_underscore_restored` if `documents.name == "_" + backup_stem`
   - `matched_raw_source` if it matched a raw-source candidate exactly
   - `matched_raw_source_leading_underscore_restored` if it matched a raw-source candidate with one leading `_` restored
9. If zero documents match, return `not_found` with all candidate names attempted.
10. If multiple documents match, return `ambiguous` and no timestamps unless a future version adds explicit disambiguation.

### Goodnotes folder path traversal

The v1 feature should return the whole Goodnotes app folder path for a matched document.

Traversal algorithm:

1. Find the active `folder_to_folder_items` row where `item_id = documents.id`.
2. Add `item_name` as the leaf document name.
3. Follow `parent_folder_id` upward by finding rows where `item_id = previous.parent_folder_id`.
4. Resolve folder names through `folders.name`.
5. Stop when there is no parent row or when a cycle guard is reached.
6. Return folder names from root to immediate parent as `goodnotes_folder_path`; return folder ids in the same order as `goodnotes_folder_ids`.

Example:

```text
Singapore Primary Science / winston.ry.meng@gmail.com / P6 / Exam
```

The document name itself should remain in `goodnotes_document_name`; callers can append it if they need a full display path including the leaf.

### Goodnotes database resolution

Default paths:

```text
~/Library/Containers/com.goodnotesapp.x/Data/Library/Databases/projection.sqlite
~/Library/Containers/com.goodnotesapp.x/Data/Library/Databases/fts.sqlite
```

Add optional environment overrides for tests and non-standard installs:

| Env var | Meaning |
|---------|---------|
| `GOODNOTES_PROJECTION_DB` | Absolute path to `projection.sqlite` |
| `GOODNOTES_FTS_DB` | Absolute path to `fts.sqlite` |

If either DB is missing, return `metadata_unavailable`.

### SQL shape

The lookup should use a read-only SQLite connection when possible:

```sql
ATTACH ? AS fts;

SELECT
  d.id,
  d.name,
  d.created_at,
  d.updated_at,
  m.last_modified
FROM documents d
LEFT JOIN fts.document_meta m ON m.document_id = d.id
WHERE d.name IN (?, ?)
  AND d.deleted = 0
  AND COALESCE(m.is_deleted, 0) = 0;
```

The `IN` placeholder count should be generated from the candidate list; two placeholders are illustrative only.

Implementation should avoid direct registry SQLite reads. Use existing `PdfFileManager` APIs to load the registered file row; direct SQLite access is only for Goodnotes' external local metadata DB.

### Optional helper for batch use

If the first API proves useful, add a batch helper:

```python
def list_goodnotes_document_timestamp_matches(
    self,
    *,
    only_registered_mains: bool = True,
) -> list[GoodnotesDocumentMatch]:
    ...
```

This should be a Phase 2 or later addition, not required for the first implementation.

## Edge cases and expected behavior

| Case | Behavior |
|------|----------|
| Registered file under `DAYDREAMEDU_ROOT` | `not_goodnotes_root` |
| Registered GoodNotes raw file | `not_main_file` |
| Goodnotes DB missing, moved, or inaccessible | `metadata_unavailable` |
| Backup stem matches active Goodnotes document exactly | `matched_exact` |
| Backup stem `c_foo` matches Goodnotes `_c_foo` | `matched_leading_underscore_restored` |
| Registered `_c_foo` and linked raw / derived raw-source stem is `foo` | `matched_raw_source` when the Goodnotes document is `foo` |
| Registered `_c_foo` but no raw-source candidate matches | `not_found`; do not fuzzy-match |
| Multiple active Goodnotes docs with same candidate name | `ambiguous` |
| `last_modified` missing but document row found | Matched status with `timestamps.last_modified = None` |
| Matched document is in a Goodnotes folder tree | Return `goodnotes_folder_path` and `goodnotes_folder_ids` |

## Open Questions and decisions

1. **Timestamp timezone:** resolved — return UTC ISO-8601 strings for API fields.
2. **Timestamp scope:** resolved — keep v1 to `created_at`, `updated_at`, and `last_modified`; page-level summaries stay future work.
3. **Folder traversal:** resolved — include Goodnotes app-folder path in v1.
4. **Known compressed-main exceptions:** resolved — include deterministic raw-source fallback in v1, but do not use fuzzy matching.
5. **Caching:** resolved — no cache in v1.

## Implementation plan

### Phase 1 — Core lookup API

**Goal:** Add a read-only Goodnotes timestamp lookup for one registered file.

**Todo checklist**

- [x] Add `goodnotes_metadata.py` dataclasses and helper functions.
- [x] Add Goodnotes DB path resolution with env overrides.
- [x] Add candidate-name generation: exact stem, one leading `_` restored, linked raw-source stem, and raw-source stem with one leading `_` restored.
- [x] Add read-only query joining `projection.sqlite.documents` to `fts.sqlite.document_meta`.
- [x] Add Goodnotes folder path traversal using `folder_to_folder_items` and `folders`.
- [x] Add `PdfFileManager.get_goodnotes_document_timestamps_for_file(...)`.
- [x] Add `PdfFileManager.get_goodnotes_document_timestamps_for_path(...)`.
- [x] Ensure unsupported cases return structured statuses instead of raising for normal no-match conditions.

**Test checklist**

- [x] Unit test exact match.
- [x] Unit test leading-underscore restored match (`c_foo.pdf` -> `_c_foo`).
- [x] Unit test raw-source fallback for a registered `_c_foo.pdf` main matching Goodnotes `foo`.
- [x] Unit test Goodnotes folder path traversal.
- [x] Unit test `not_goodnotes_root`.
- [x] Unit test `not_main_file`.
- [x] Unit test `metadata_unavailable`.
- [x] Unit test `not_found`.
- [x] Unit test `ambiguous`.
- [x] Unit test missing `last_modified` while `documents` row exists.

**Success / handoff criteria**

- [x] A caller can pass a registered `g_root` main `file_id` and receive `created_at`, `updated_at`, and `last_modified` when the Goodnotes document is matchable.
- [x] No implementation code writes to Goodnotes databases.
- [x] No implementation code uses direct SQLite access to the pdf registry.

### Phase 2 — Batch audit helper and diagnostics

**Goal:** Make it easy to verify coverage across all registered `g_root` mains.

**Todo checklist**

- [ ] Add `list_goodnotes_document_timestamp_matches(...)` or a small script using the Phase 1 API.
- [ ] Report counts by status.
- [ ] Include candidate names and registered paths for `not_found` / `ambiguous`.
- [ ] Keep fuzzy suggestions out of the API; optionally include them only in a diagnostic script output.

**Test checklist**

- [ ] Unit test batch status aggregation with temp fixture DBs.
- [ ] Unit test that raw files are counted separately or excluded according to option.

**Success / handoff criteria**

- [x] Operators can reproduce a summary like "registered `g_root` mains matched by exact / underscore / raw-source / missing" without ad hoc SQL.
- [x] Known compressed-main exceptions match only through deterministic raw-source fallback, not fuzzy guessing.

### Phase 3 — Documentation updates

**Goal:** Make the behavior discoverable and consistent with project docs.

**Todo checklist**

- [x] Update `pdf_file_manager/README.md` with the new API and caveats.
- [x] Update `pdf_file_manager/SPEC.md` with the match contract and status enum.
- [x] Update `pdf-file-manager` skill docs if agents should use this API in routine GoodNotes audits.
- [x] Cross-link [L4_FILE_FRAMEWORK.md](../../../docs/L4_FILE_FRAMEWORK.md#goodnotes-files) to the shipped API.
- [x] Add CHANGELOG entry with version bump.

**Test checklist**

- [x] Documentation examples use `PdfFileManager` and attribute access, not direct registry SQL.
- [x] Example output includes at least one non-success status so callers know how to handle it.

**Success / handoff criteria**

- [x] A future agent can find the API from README/SPEC/L4 docs.
- [x] Docs clearly distinguish Goodnotes document timestamps from registry `added_at` / `updated_at` and filesystem mtimes.

### Phase 4 — Final sweep

**Goal:** Check completeness, accuracy, consistency, and readiness for implementation closure.

**Todo checklist**

- [x] Re-run all related tests.
- [x] Run a local audit against current `GOODNOTES_ROOT` and Goodnotes metadata DB.
- [x] Confirm no new direct registry-SQL usage was introduced.
- [x] Confirm statuses cover every local registered `g_root` main.
- [x] Check whether implementation affects any open TODO.md bullets; if so, update or complete those bullets in the same change.

**Test checklist**

- [x] `pytest` for `pdf_file_manager` tests passes.
- [x] Manual smoke: lookup by file id for one exact match and one leading-underscore match.
- [x] Manual smoke: lookup for a known compressed-main exception returns a raw-source match.

**Success / handoff criteria**

- [x] Proposal can be marked implemented with shipped API, tests, docs, and changelog aligned.
- [x] Remaining limitations are documented as future work rather than hidden behavior.

## Acceptance criteria

- `PdfFileManager` exposes a supported method to return Goodnotes timestamps for a registered `g_root` main file.
- The method returns a structured match object with status, candidate names, Goodnotes document id/name, Goodnotes folder path, and timestamps.
- Exact, leading-underscore-restored, and deterministic raw-source matches are supported.
- No-match and ambiguous cases are explicit and non-destructive.
- Unit tests cover success and failure statuses.
- README/SPEC/L4 docs mention the API and timestamp semantics.

## Risks

| Risk | Mitigation |
|------|------------|
| Goodnotes changes local DB schema | Return `metadata_unavailable` or a schema-specific error message; keep SQL isolated in one module. |
| Goodnotes DB is locked while app is running | Use read-only connections; if lock occurs, return a structured unavailable/error status or copy DB to temp if needed in a later version. |
| Filename matching guesses wrong | Restrict v1 to exact, leading-underscore, and deterministic raw-source candidates; no fuzzy matching. |
| Agents confuse registry timestamps with Goodnotes timestamps | Use explicit field names and docs. |
| API becomes macOS-specific | Document that v1 is macOS Goodnotes local metadata only. |

## Future work

- Add attachment file path lookup for matched Goodnotes documents.
- Add page-level timestamp summaries.
- Add optional audit command that proposes likely matches for `not_found` rows.
