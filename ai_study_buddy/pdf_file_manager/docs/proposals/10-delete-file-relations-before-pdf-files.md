# Proposal 10: Delete `file_relations` (or enforce FK cascades) before removing `pdf_files`

**Happy path item:** [Registry integrity] — When `PdfFileManager.delete_file` removes a `pdf_files` row, every `file_relations` row involving that file must disappear in the same transaction, without relying solely on implicit SQLite behavior.

---

## Implementation status

| Area | Status |
| --- | --- |
| Problem observed (orphan `file_relations` after `delete_file`) | **Observed** (e.g. `raw_source`, `main_version`, `template_for`, `completed_from` left pointing at deleted UUIDs) |
| Code change — explicit `DELETE FROM file_relations` in `delete_file` | **Implemented** (`v0.3.8`) |
| Docs — `SPEC.md` + `CHANGELOG.md` update for explicit relation delete | **Implemented** (`v0.3.8`) |
| Regression test — no orphan relations for deleted main/raw ids | **Implemented** (`tests/test_file_ops.py::test_delete_file_keep_related_false_cascades_to_raw`) |
| Regression test — template/completion edge cleanup on delete | **Proposed / Not yet implemented** |
| Code change — connection `PRAGMA foreign_keys=ON` in `_get_connection` | **Implemented** (`v0.3.8`) |
| Integrity validator check for dangling `file_relations` ids | **Proposed** |

---

## Motivation

The schema declares referential integrity with `ON DELETE CASCADE` on `file_relations` for both `source_id` and `target_id` ([`schema.sql`](../../schema.sql)). Callers reasonably expect that deleting a file clears template links, raw/main pairs, and any other edges in `file_relations`.

In practice, **SQLite only enforces foreign keys when `PRAGMA foreign_keys=ON` is set for the connection** ([SQLite foreign key docs](https://www.sqlite.org/foreignkeys.html)). Historically, `PdfFileManager._get_connection` opened a normal `sqlite3.connect` without enabling this pragma (aside from brief toggles inside legacy table rebuild helpers), so `DELETE FROM pdf_files WHERE id = ?` could succeed **without** cascading and leave orphan `file_relations` rows.

As of `v0.3.8`, manager-owned connections now enable `PRAGMA foreign_keys=ON` at connect time.

Historical impact (before `v0.3.8`):

- `get_template` / completion discovery can see stale edges or inconsistent graphs.
- Integrity scripts and ad hoc SQL may count “relations still present” for deleted IDs.
- The **Python cascade** in `delete_file` (delete main → recurse into linked raw) removed **both** `pdf_files` rows, but **did not** remove `file_relations` unless something else deleted them.

---

## Problem (historical, pre-`v0.3.8`)

Before `v0.3.8`, `delete_file` roughly:

1. Logs `operation_log` with a snapshot including existing `relations` / `group_members`.
2. Clears `file_groups.anchor_id` and deletes `file_group_members` for the file.
3. Attempts `os.remove(path)` (optional if file already moved).
4. `DELETE FROM pdf_files WHERE id = ?`.

There was **no** `DELETE FROM file_relations ...` and no guaranteed FK cascade, so relations involving the deleted `id` could remain indefinitely.

As of `v0.3.8`, `delete_file` now executes:

```sql
DELETE FROM file_relations WHERE source_id = ? OR target_id = ?
```

before deleting from `pdf_files`.

---

## Goals

1. After `delete_file` returns, **no** `file_relations` row may reference the deleted `pdf_files.id` (whether as `source_id` or `target_id`).
2. Behavior should **not** depend on connection-local `PRAGMA foreign_keys` unless we deliberately adopt that as a **global** contract for every registry accessor.
3. Preserve existing semantics: raw cascade from main, `has_raw` clearing, group membership cleanup, operation log shape (possibly extended with explicit relation deletes in `before_state` / notes if useful).
4. Add regression tests proving template links and raw/main links do not survive file deletion.

---

## Design options

### Option A — Enable `PRAGMA foreign_keys=ON` on the manager connection (global)

- Immediately after creating the connection in `_get_connection`, run `PRAGMA foreign_keys=ON` once per process lifetime (same connection is reused).
- **Pros:** All `ON DELETE CASCADE` clauses in `schema.sql` behave as authored (`file_relations`, `book_answer_mappings`, etc.); fewer bespoke `DELETE` paths.
- **Cons:** Must audit **all** registry write paths (migrations, one-off scripts, tests) for assumptions that FKs are off; some bulk rebuild paths explicitly set `OFF` and must continue to do so safely; any **external** tool opening the same DB file without the pragma can still orphan rows.

### Option B — Explicit `DELETE FROM file_relations` inside `delete_file` (local)

- Before `DELETE FROM pdf_files WHERE id = ?`, run:

  ```sql
  DELETE FROM file_relations WHERE source_id = ? OR target_id = ?
  ```

  for the file being deleted (same transaction as today’s sequence, or wrapped in `BEGIN`/`COMMIT` if we consolidate).

- **Pros:** Deterministic for **`delete_file`** regardless of pragma; self-documenting; fixes the observed bug even if other code opens the DB without FKs.
- **Cons:** Duplicates declarative CASCADE logic in imperative code; must stay in sync if new tables reference `pdf_files` without CASCADE (today other FKs largely use CASCADE—verify on change).

### Option C — A + B (belt and suspenders)

- Turn on `foreign_keys` for normal operations **and** delete relations explicitly in `delete_file`.
- **Pros:** Defense in depth.
- **Cons:** Redundant if FKs are always on and tests cover cascades; slightly more maintenance.

---

## Recommendation

Adopt **Option C (A + B)**:

1. Keep explicit relation deletion inside `delete_file` (shipped in `v0.3.8`).
2. Enable `PRAGMA foreign_keys=ON` in `_get_connection` (shipped in `v0.3.8`).

Result: manager-managed connections enforce declared FK behavior globally, while `delete_file` still performs explicit cleanup as defense in depth and for clarity in audit reasoning.

---

## Implementation plan

1. **`delete_file`** (completed in `v0.3.8`)
   - After building `before_state` (which already snapshots relations), execute `DELETE FROM file_relations WHERE source_id = ? OR target_id = ?` with `file_id` **before** `DELETE FROM pdf_files WHERE id = ?`.
   - Keep existing main→raw Python cascade: when deleting the main, still recurse into the raw child; each invocation clears relations for **that** id, so order remains correct (no need to delete edges twice if the second delete is idempotent).
2. **Transactions (optional hardening, not yet implemented)**
   - Wrap the delete sequence in a single transaction so log insert, relation deletes, group updates, file delete, and `has_raw` patch commit atomically.
3. **Documentation** (completed in `v0.3.8`)
   - [SPEC.md](../../SPEC.md): document that `delete_file` removes all `file_relations` incident on the file and that callers should not expect orphan edges.
   - [CHANGELOG.md](../../CHANGELOG.md): note registry integrity fix under an appropriate version.
4. **Foreign keys in manager connection** (completed in `v0.3.8`)
   - `PRAGMA foreign_keys=ON` now runs in `_get_connection`; schema coverage includes an assertion that manager connections report `PRAGMA foreign_keys=1`.
5. **Coverage follow-up (recommended)**
   - Add a targeted regression test for template/completion relations during delete:
     - setup template `T`, completed main `C`, raw `R` (linked to `C`), and `link_to_template(C, T)`;
     - call `delete_file(C)`;
     - assert `T` remains, `C` and `R` are deleted, and no `template_for` / `completed_from` / raw-main rows reference deleted ids.
6. **Integrity validator follow-up (optional)**
   - Extend [`validate_pdf_registry_integrity.py`](../../scripts/validate_pdf_registry_integrity.py) with an explicit dangling-relation check (for rows in `file_relations` whose `source_id` or `target_id` has no matching `pdf_files.id`), so external writers that bypass manager safeguards are detectable.

---

## Test plan

1. **Unit test — template + raw/main**
   - Register or fixture three files: template `T`, completed main `C`, raw `R` linked to `C`, with `link_to_template(C, T)` and raw/main links as produced by `compress_and_register` or `link_files`.
   - Call `delete_file(C)`.
   - Assert: no `pdf_files` rows for `C` or `R`; **no** `file_relations` rows where `source_id` or `target_id` equals former `C` or `R` ids; template `T` still exists; no `template_for` / `completed_from` edges involving deleted ids.
2. **Unit test — delete raw first**
   - Same fixture; call `delete_file(R)` (if API allows); assert main’s `has_raw` cleared and no orphan relations (already partially covered today—extend to assert `file_relations` counts).
3. **Regression — operation log**
   - Assert `before_state` still captures prior relations for audit; optional assert post-delete `SELECT COUNT(*) FROM file_relations WHERE …` is zero for those ids.

### Current coverage snapshot

- Implemented:
  - delete cascade to raw + no orphan `file_relations` for deleted main/raw ids.
- Missing:
  - explicit template/completion deletion regression (`template_for` / `completed_from` cleanup assertions).

---

## Risks and open questions

- **Performance:** `DELETE FROM file_relations WHERE source_id = ? OR target_id = ?` uses indexes on `(source_id, …)` / `(target_id, …)` only if present; today schema may rely on table scans. If large registries show up, add indexes (e.g. on `target_id`)—measure first.
- **Other tables:** If any future table references `pdf_files` without `ON DELETE CASCADE`, `delete_file` could still leave orphans; periodic integrity validation ([`validate_pdf_registry_integrity.py`](../../scripts/validate_pdf_registry_integrity.py)) should optionally flag dangling `file_relations`.
- **Concurrent writers:** Multiple processes opening the same SQLite file are already a risk; this proposal does not change locking semantics.

---

## References

- `PdfFileManager.delete_file` — [`pdf_file_manager.py`](../../pdf_file_manager.py)
- `schema.sql` — `file_relations` and `ON DELETE CASCADE`
- SQLite: [Foreign Key Support](https://www.sqlite.org/foreignkeys.html)
