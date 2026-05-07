# Proposal 14: Split `DAYDREAMEDU_ROOT` into top-level `template/` and `completion/`

**Happy path item:** [Navigation clarity] — Users should not need to mentally branch on mixed `<grade>` vs `<student>` second-level folders under subject. The path itself should reveal template vs completion from the first segment.

**Proposal status:** **Complete** — migration, registry, integrity, docs, and on-disk cleanup are done. **Strict D_ROOT path enforcement inside `PdfFileManager` write APIs** is **deferred** (optional follow-up only if operational need arises).

---

## Implementation status

| Area | Status |
| --- | --- |
| **Overall** | **Complete** (see proposal status above) |
| Problem and scope definition (D_ROOT only) | **Done** |
| Path schema redesign (`template/` vs `completion/`) | **Done** (on disk + registry) |
| Migration strategy (on-disk + registry) | **Done** — see [Completed work](#completed-work) |
| Integrity post-check and remediation | **Done** — `validate_pdf_registry_integrity` clean exit **`0`** |
| Strict write-path invariant in `PdfFileManager` APIs | **Deferred** — revisit only if needed; not required to treat this proposal as closed |
| Reporting/leaf docs updated for `template/` / `completion/` paths | **Done** — see below |
| Prune empty legacy folders under `DAYDREAMEDU_ROOT` | **Done** — [`scripts/_prune_empty_dirs_d_root.py`](../../scripts/_prune_empty_dirs_d_root.py) |

### Completed work

Migration was executed using `PdfFileManager` (`move_file`, `remove_scan_root` + `ensure_scan_root` for scan roots) via the one-off script:

- [`scripts/_migrate_d_root_top_level_branches.py`](../../scripts/_migrate_d_root_top_level_branches.py) — dry-run and batched `--execute` with optional `--subject` / `--branch`.

Concrete outcomes:

| Item | Result |
| --- | --- |
| Files moved (D_ROOT + registry) | **5247** (`4489` template, `758` completion) |
| Scan roots updated | **138** (`76` template-scope, `62` completion-scope) |
| Batching | By subject: English → Math → Chinese → Science; `template` then `completion` per subject |
| Full dry-run ledger | `scripts/d_root_migration_dry_run_full.json` |
| Post-migration dry-run (zero remaining work) | `scripts/d_root_migration_postcheck_dry_run.json` |
| Per-batch execute logs | `scripts/d_root_migration_execute_*_template.json`, `*_completion.json` |

Post-migration integrity remediation:

| Item | Result |
| --- | --- |
| `repair_main_raw_metadata_drift()` | **1** raw/main pair aligned (doc_type + `metadata.content_folder`) |
| Dangling raw/main relation edges removed | **130** rows deleted from `file_relations` (endpoints missing from `pdf_files`) |
| Helper script | `scripts/_repair_raw_main_relation_dangling_edges.py` |
| Final audit | `python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity` → exit **`0`**, all summary counts **`0`** |

Artifacts for audit trail:

- `scripts/post_migration_integrity_before_repair.json`
- `scripts/post_migration_integrity_after_repair.json`

**Docs (template/completion reporting):**

- [`.cursor/commands/daydreamedu-leaf-registry-report.md`](../../../../.cursor/commands/daydreamedu-leaf-registry-report.md) — “Path layout” section (branch-first paths), obsolete legacy layout note, and **empty-folder cleanup** guidance including **`.DS_Store` / `.localized`** and the `--evict-macos-metadata` flag on the prune script.
- [`docs/L4_FILE_FRAMEWORK.md`](../../../docs/L4_FILE_FRAMEWORK.md) — D_ROOT mermaid nodes and notes updated for `template/` and `completion/` prefixes; DaydreamEdu leaf bullet updated.

**Empty-folder prune (filesystem only):**

- Script: [`scripts/_prune_empty_dirs_d_root.py`](../../scripts/_prune_empty_dirs_d_root.py) — default dry-run; `--execute` removes empty dirs bottom-up; **`--evict-macos-metadata`** (with `--execute`) removes `.DS_Store` and `.localized` when they are the only files in a directory, then removes that directory. Never deletes top-level `template/` or `completion/` branch roots.

| Pass | What ran | Result |
| --- | --- | --- |
| 1 | Empty dirs only (no metadata eviction) | **123** directories removed; JSON: `d_root_prune_empty_dirs_execute.json`, postcheck `d_root_prune_empty_dirs_postcheck.json` |
| 2 | `--evict-macos-metadata --execute` | **108** `.DS_Store` (and/or `.localized`) files removed, **108** additional directories removed; legacy **`Singapore Primary …`** subject roots at D_ROOT **removed**; second pass **0** dirs (`d_root_prune_evict_execute_2.json`). First-pass evict dry-run/execute: `d_root_prune_evict_execute_1.json` |

**Expected D_ROOT top-level after cleanup:** `template/`, `completion/`, and any other fixed folders you keep (e.g. `db/`), plus optional root `.DS_Store` from Finder — not legacy subject folders.

---

## Motivation

Current `DAYDREAMEDU_ROOT` organization places both template and completion files under the same top-level `<subject>` branch. This creates a mixed second-level namespace:

- template branch second segment is `<grade>`,
- completion branch second segment is `<student>`.

In day-to-day navigation, users must repeatedly decide whether a second-level folder token is a grade or a student, which adds avoidable cognitive overhead.

This proposal aligns on-disk layout with the registered-file conceptual model in `L4_FILE_FRAMEWORK.md`, where template vs completion is already the top-level attribute.

---

## Problem statement

> **Note:** The layout below is the **legacy** shape. After migration, D_ROOT files live under `template/...` or `completion/...` only.

Under legacy `D_ROOT`, both of these coexisted under the same subject:

- `<subject>/<grade>/<type>/.../file.pdf` (template-like)
- `<subject>/<student>/<grade>/<type>/.../file.pdf` (completion-like)

This makes visual scanning and file retrieval error-prone, especially in large subject trees with many students.

---

## Goals

1. Make template/completion explicit at the first path segment under `DAYDREAMEDU_ROOT`.
2. Preserve current semantic hierarchy for each branch after the new root segment.
3. Provide a deterministic, reversible migration for both on-disk paths and registry entries.
4. Keep rollout operationally safe with dry-run, idempotency, and post-migration validation.

Non-goals:

- changing `GOODNOTES_ROOT` path conventions in this proposal,
- changing file naming prefixes (`_c_`, `_raw_`, etc.),
- redefining `subject`, `grade`, `type`, `book` semantics.

---

## Scope

Included:

- `DAYDREAMEDU_ROOT` on-disk path migration,
- corresponding registry path updates for files stored in `DAYDREAMEDU_ROOT`,
- updates to D_ROOT-facing audit/reporting assumptions.

Excluded (explicitly):

- `GOODNOTES_ROOT` structural migration,
- GoodNotes-specific path policies beyond compatibility checks.

---

## Proposed design

### Target path schemas

1. Template:
   - `template/<subject>/<grade>/<type>/<optional book name>/file.pdf`
2. Completion:
   - `completion/<subject>/<student>/<grade>/<type>/<optional book name>/file.pdf`

`<optional book name>` appears only when `type == book`.

### Before vs after examples

- Before (template): `chinese/P4/exam/SA2/_c_P4 Chinese SA2 2024.pdf`
- After  (template): `template/chinese/P4/exam/SA2/_c_P4 Chinese SA2 2024.pdf`

- Before (completion): `chinese/emma.rs.meng@gmail.com/P4/exam/SA2/_c_P4 Chinese SA2 2024.pdf`
- After  (completion): `completion/chinese/emma.rs.meng@gmail.com/P4/exam/SA2/_c_P4 Chinese SA2 2024.pdf`

### Why this shape

- first segment directly encodes the highest-order semantic (`template|completion`),
- branch internals remain familiar to existing operators,
- physical layout now matches the “Registered file structure” hierarchy in `L4_FILE_FRAMEWORK.md`.

---

## Path mapping rules (authoritative migration spec)

For each registered file rooted at `DAYDREAMEDU_ROOT`, compute a new relative path:

1. Determine branch:
   - `template` if file is general-scoped/template-classified,
   - `completion` if file is student-scoped/completion-classified.
2. Preserve existing downstream segments exactly:
   - template old: `<subject>/<grade>/<type>/...`
   - completion old: `<subject>/<student>/<grade>/<type>/...`
3. Prepend selected branch segment.

Formal mapping:

- Template:
  - old: `R = <subject>/<grade>/<type>/<tail>`
  - new: `R' = template/<subject>/<grade>/<type>/<tail>`
- Completion:
  - old: `R = <subject>/<student>/<grade>/<type>/<tail>`
  - new: `R' = completion/<subject>/<student>/<grade>/<type>/<tail>`

Where `<tail>` is either:

- `file.pdf`, or
- `<book_name>/file.pdf` when `type=book`.

### Edge-case policy

- **Already-migrated paths:** if path already starts with `template/` or `completion/`, skip (idempotent).
- **Ambiguous/malformed depth:** if relative path shape does not match expected legacy branch depth, quarantine into a manual-review report and do not auto-move.
- **Collision at target path:** abort that item, record conflict, continue dry-run report; execute phase must fail-fast unless conflict policy is explicitly approved.
- **Registry-only missing on disk:** flagged and excluded from move phase; handle via integrity remediation first.

---

## Detailed implementation plan (TODO checklists)

### Phase A — preflight inventory and dry-run mapping

- [x] Enumerate all registered files where `root == DAYDREAMEDU_ROOT`.
- [x] Classify each file as template/completion using authoritative metadata.
- [x] Compute `old_rel_path -> new_rel_path` with rules above.
- [x] Validate shape assumptions (template depth vs completion depth).
- [x] Detect target collisions and path anomalies.
- [x] Emit dry-run artifact:
  - [x] move candidates,
  - [x] skipped already-migrated items,
  - [ ] anomalies requiring manual action (none encountered),
  - [ ] collisions (none in dry-run).
- [x] Review dry-run output and obtain explicit go/no-go approval.

### Phase B — execution (on-disk + registry, single source of truth)

- [x] Freeze concurrent file-moving workflows during migration window (implicit single-operator batch).
- [x] Create missing parent directories for target paths (`move_file` + mkdir).
- [x] Move files on disk from old to new paths.
- [x] Update registry `path` values to the new resolved locations.
- [x] Ensure each record update corresponds to exactly one successful move.
- [x] Track operation log entries for each successful path change.
- [x] Fail-fast on first unexpected mismatch between disk result and registry mutation (no collisions hit).

### Phase C — post-migration validation

- [x] Re-run path-shape audit for all D_ROOT registered files (postcheck dry-run: all already prefixed).
- [x] Confirm no legacy top-level `<subject>/...` D_ROOT mains remain.
- [x] Confirm all migrated files now begin with `template/` or `completion/`.
- [x] Run registry integrity audit script and capture output snapshot.
- [ ] Run D_ROOT leaf registry report against new branch layout (optional; not required for cutover).
- [x] Produce migration summary counts (per-batch JSON + postcheck).

### Phase D — rollback preparedness and recovery

- [x] Persist reversible mapping ledger (`new_path -> old_path`) — full dry-run + per-batch JSON outputs.
- [ ] Document rollback command strategy (reverse moves + registry rewind) — **not written**; ledger exists if needed.
- [ ] Validate rollback on a sampled subset in a non-production environment — **not done**.
- [ ] Define hard stop criteria that trigger rollback recommendation — **not formalized**.

### Phase E — prune empty legacy folders (D_ROOT filesystem only)

- [x] Enumerate empty directories under `DAYDREAMEDU_ROOT` left after moves (e.g. walk bottom-up or list candidates).
- [x] Dry-run: print or log every directory that would be removed; verify none contain hidden non-PDF content you care about.
- [x] Remove only empty directories bottom-up (do not delete `template/` or `completion/` roots or any folder that still has files).
- [x] Optional: exclude paths that remain configured elsewhere (sync stubs); confirm Google Drive behavior if applicable — no exclusions needed.
- [x] Re-list D_ROOT top level — `template/`, `completion/`, no `Singapore Primary …` legacy roots; optional **`db/`** retained by operator; root **`.DS_Store`** may still appear (Finder); post-evict second pass **0** dirs to remove.

---

## Migration plan (operational sequence)

1. **Prepare**
   - generate dry-run ledger and anomaly report,
   - clear unresolved anomalies/collisions.
2. **Migrate**
   - run deterministic batch moves with transaction-like pairing between disk and registry updates.
3. **Verify**
   - run integrity/report scripts and compare counts with dry-run expectations.
4. **Close**
   - publish final migration report and freeze legacy path assumptions in docs.
5. **Prune empty folders**
   - remove empty legacy directory shells under `DAYDREAMEDU_ROOT` after migration (filesystem only; not registry) — see Phase E.
   - if **`Singapore Primary …`** folders remain with no PDFs but still containing **`.DS_Store`**, run the same script with **`--evict-macos-metadata --execute`** (and repeat until dry-run shows **0** dirs).

Recommended batching:

- by subject, then by branch (`template` first, `completion` second),
- stop between batches for quick reconciliation.

---

## Migration execution tooling (explicit)

This migration must be executed through the `PdfFileManager` Python API as the system of record for registry-backed file operations.

Required execution approach:

- Build migration inventory and dry-run mapping with `PdfFileManager` reads (for example `find_files`, `list_scan_roots`).
- Execute per-file path migration via `PdfFileManager` mutation methods (for example `move_file`) so on-disk and registry state remain coupled.
- Update scan-root paths using `PdfFileManager` APIs (or a dedicated helper added in `pdf_file_manager.py` that still uses manager-level operations/logging semantics).
- Run post-migration validation with:
  - `python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity`
  - DaydreamEdu leaf coverage/report workflow.

Explicitly disallowed execution patterns:

- direct SQLite mutation of registry tables for normal migration work,
- ad hoc shell `mv` + manual DB synchronization,
- any migration flow that bypasses `PdfFileManager` operation semantics/logging.

Rationale:

- ensures path updates are applied with the same invariants as normal product workflows,
- reduces risk of disk/registry drift during a high-volume move,
- keeps migration auditable via manager-driven operation history.

---

## Test checklist

### Functional mapping tests

- [x] Template sample maps to `template/<subject>/<grade>/<type>/...`.
- [x] Completion sample maps to `completion/<subject>/<student>/<grade>/<type>/...`.
- [x] `book`-type samples preserve `<book_name>` segment.
- [x] Already-migrated sample is skipped without mutation (postcheck dry-run).

### Safety and idempotency tests

- [x] Dry-run rerun yields stable mapping output.
- [x] Execution rerun after successful migration performs zero additional moves (postcheck).
- [x] Collision detection prevents unsafe overwrite (full dry-run: no collisions).
- [ ] Malformed path sample is reported and excluded from automatic move (not exercised; no malformed paths in scope).

### Regression/compatibility checks

- [x] `validate_pdf_registry_integrity.py` passes with no migration-induced failures (exit `0` after remediation).
- [ ] D_ROOT leaf registry report still computes expected coverage categories with new roots (optional follow-up).
- [ ] Existing workflows that query by registry metadata (not hardcoded path depth) continue functioning (spot-check as needed).

### Manual verification

- [ ] Spot-check at least one subject tree in filesystem explorer for clearer first-level branching.
- [ ] Spot-check at least one template and one completion record end-to-end (disk path and registry path).

---

## Compatibility impacts and mitigations

Potentially impacted areas:

- DaydreamEdu leaf-folder reporting command assumptions about top-level path shape.
- Any scripts that infer template/completion from second-level token semantics.
- Documentation snippets that still show legacy D_ROOT examples.

Mitigations:

- update report command docs/examples to include `template/` and `completion/` (**done** for DaydreamEdu leaf report + L4 framework notes),
- keep mapping ledger for traceability from legacy paths to new paths,
- run a short-term compatibility scan for hardcoded legacy regex/path-depth logic before cutover,
- after migration, prune legacy empty trees on disk; if **`Singapore Primary …`** folders remain with **no PDFs**, evict **`.DS_Store` / `.localized`** via `scripts/_prune_empty_dirs_d_root.py --evict-macos-metadata` so directories become removable (**done** — two-pass prune; see Completed work).

---

## Migration surface area (pre-migration baseline)

**Status:** Migration **completed** — all D_ROOT paths now use the `template/` or `completion/` prefix; postcheck dry-run reported **5247** files and **138** scan roots already prefixed.

The following numbers summarize scope **before** cutover (combined on-disk scan under `DAYDREAMEDU_ROOT` and registry query via `PdfFileManager`).

### Global counts

- Total on-disk PDFs under `DAYDREAMEDU_ROOT`: `5247`
- Exact-path registered files under `DAYDREAMEDU_ROOT`: `5247`
- Unregistered on-disk PDFs (exact resolved-path comparison): `0`
- Already under new top-level prefixes (`template/` or `completion/`): `0`
- Legacy top-level subject paths requiring migration: `5247`

### Branch sizing (registry truth)

- Template (`is_template=True`): `4489`
- Completion (`is_template=False`): `758`
- Null template flag: `0`
- Prefix/flag mismatch among already-prefixed paths: none observed

### Subject-level breakdown

- `Singapore Primary English`: `2174` total (`1910` template, `264` completion)
- `Singapore Primary Math`: `1336` total (`1166` template, `170` completion)
- `Singapore Primary Chinese`: `896` total (`752` template, `144` completion)
- `Singapore Primary Science`: `841` total (`661` template, `180` completion)

### Doc-type distribution (all D_ROOT registered files)

- `book`: `3440`
- `exam`: `829`
- `exercise`: `628`
- `activity`: `262`
- `note`: `88`

### Completion-path footprint

- Distinct completion student-folder segments currently on disk: `3`
  - `winston.ry.meng@gmail.com`: `658`
  - `emma.rs.meng@gmail.com`: `94`
  - `abigail.rg.meng@gmail.com`: `6`
- Unexpected completion path depth in sampled registry paths: `0`

### Scan-root migration impact

- D_ROOT scan roots to update: `138`
- Already under new prefixes: `0`
- Legacy-prefix scan roots: `138`
  - Template-scope candidates (`student_id is None`): `76`
  - Completion-scope candidates (`student_id is set`): `62`

### Implications (historical)

- This was a full-shape migration (no partial prior rollout to reconcile).
- Pre-cutover, registry and disk were path-aligned (no unregistered delta), which lowered migration ambiguity.
- Operational workload matched both file-path migration (`5247` files) and scan-root remapping (`138` roots).

---

## Risks and open questions

1. **Risk:** metadata/classification errors can route files to wrong branch.
   - Mitigation: preflight classification audit + anomaly gate before execution.
2. **Risk:** hidden hardcoded path assumptions in one-off scripts.
   - Mitigation: path-pattern grep sweep plus staged rollout.
3. **Risk:** partial migration if process fails mid-run.
   - Mitigation: strict move/update pairing and rollback ledger.

Open questions:

None.

Recommended defaults:

- **`template|completion` strict enforcement in `PdfFileManager`:** deferred with proposal closure; re-open only if regressions or repeated misuse justify API-level rejects.
- no temporary compatibility resolver for legacy D_ROOT input paths; callers must provide migrated paths (still the intended convention; not wired as automatic rewrite).

---

## Success criteria

- [x] 100% of migrated `DAYDREAMEDU_ROOT` registered files start with either `template/` or `completion/`.
- [x] 0 unintended path overwrites/collisions in execution logs.
- [x] 0 unresolved disk/registry path mismatches introduced by migration (`missing_on_disk_files: 0` post-migration).
- [x] Integrity audit reports no migration-induced failures (clean after drift repair + dangling-edge cleanup).
- [ ] Operators confirm faster manual navigation in D_ROOT subject trees (qualitative acceptance).
- [x] Legacy mixed `<subject>/<grade|student>/...` branch is retired for migrated scope (all under `template/` or `completion/`).
- [x] Legacy **`Singapore Primary …`** folder trees removed from D_ROOT top level after empty-dir prune + macOS metadata eviction (PDFs live only under `template/` and `completion/`).

---

## Decision summary

- **Decision:** Split D_ROOT into explicit top-level `template/` and `completion/` branches.
- **Scope decision:** D_ROOT only in this proposal; GoodNotes unchanged.
- **Rollout decision:** staged migration with mandatory dry-run, anomaly gate, and rollback ledger.
- **Post-migration enforcement decision (original intent):** strict write-path invariant in `PdfFileManager` for D_ROOT — **deferred**; proposal closed without library changes; optional future work if needed.
- **Compatibility decision:** do not add a temporary legacy-path resolver; legacy path inputs should fail fast after cutover.
