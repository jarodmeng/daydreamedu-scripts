# Proposal 11: Harden agent-facing API and skill to prevent `PdfFile` shape misuse

**Happy path item:** [Agent reliability] — Common workflows (scan, resolve mains, enforce template flags, link completion to template, verify) should be hard to misuse even when executed by autonomous agents.

---

## Implementation status

| Area | Status |
| --- | --- |
| Recurring failure observed (`PdfFile` object treated as dict with `.get` / `[...]`) | **Observed** |
| Skill docs explicitly state return shape and accessor style | **Proposed** |
| Library helper for stable field access across object/dict transitions | **Proposed** |
| Single high-level helper for completion-template reconciliation + linking | **Proposed** |
| Return-type consistency audit across `get_*` methods | **Proposed** |
| Regression tests for agent-style link/verify flow | **Proposed** |

---

## Motivation

In repeated WA/exam reprocessing runs, agents commonly execute nearly identical code paths:

1. `get_file_by_path(...)` for student/general mains,
2. enforce `is_template` on general side and non-template on student side,
3. call `link_to_template(...)`,
4. verify linked template id and flags.

A recurring failure mode appears when agent code assumes dict-like return values and uses `.get(...)` or `['id']`, but runtime values are `PdfFile` objects (or vice versa in older assumptions). The result is avoidable runtime errors in the final verification stage, even when all disk/registry actions already succeeded.

This is an API ergonomics issue: callers should not need to guess representation while running high-stakes file operations.

---

## Problem statement

Today, agent code can become fragile because:

- call sites may assume mixed shapes (`PdfFile` dataclass vs dict-like payload),
- the skill currently does not provide a canonical accessor pattern,
- the linking flow is spread across repeated boilerplate that is easy to get subtly wrong.

The practical impact is wasted retries, noisy logs, and higher risk of accidental partial runs when scripts fail late in verification.

---

## Goals

1. Make normal `PdfFileManager` usage representation-safe by default.
2. Provide one canonical, low-boilerplate path for completion-template linking flows.
3. Update skill guidance so agents copy a known-good pattern.
4. Preserve backward compatibility where feasible during migration.

Non-goals:

- redesigning the registry schema,
- changing domain semantics for `is_template`, raw/main, or linking rules.

---

## Design options

### Option A — Documentation-only fix

- Update skill/docs to always use attribute access (`f.id`, `f.is_template`).
- Add examples showing verification and linking.

**Pros:** Fastest, low risk.  
**Cons:** Still brittle if some call sites receive dicts or if future refactors change representation.

### Option B — Stable accessor helpers + docs

- Add helper(s) in `pdf_file_manager.py`, for example:
  - `file_id(file_or_dict) -> str`
  - `file_path(file_or_dict) -> str`
  - `file_is_template(file_or_dict) -> bool`
  - `to_dict(pdf_file) -> dict`
- Update skill to require helper usage in scripts.

**Pros:** Strong compatibility bridge; easy migration.  
**Cons:** Adds utility surface area that must be documented and tested.

### Option C — High-level reconciliation/link helper + Option B

- Implement an operation-level helper, for example:
  - `ensure_completion_template_link_by_paths(completed_path, template_path, inherit_metadata=True, enforce_template_flags=True) -> LinkResult`
- Helper performs resolution, optional template-flag normalization, linking, and postcondition verification in one call.
- Keep low-level APIs for advanced workflows.

**Pros:** Removes repeated fragile boilerplate; best for agent reliability.  
**Cons:** Requires careful design to avoid hiding too much behavior.

---

## Recommendation

Adopt **Option C** (with Option B baseline):

1. Add stable field-access helpers for representation safety.
2. Add one high-level path-based link/reconcile helper for common workflows.
3. Update the skill and docs to make this the default agent path.

This combines immediate reliability wins with a clean long-term call pattern.

---

## Proposed API additions

### 1) Representation-safe helpers

Add lightweight helpers in `PdfFileManager` module scope (or as `@staticmethod`s):

- `file_id(file_like) -> str`
- `file_path(file_like) -> str`
- `file_is_template(file_like) -> bool`
- `file_name(file_like) -> str`
- `pdf_file_to_dict(file_like) -> dict`

Behavior:

- accept `PdfFile` (current object form) and optionally dict-like inputs,
- raise explicit `TypeError` for unsupported shapes,
- centralize field extraction so callers do not branch ad hoc.

### 2) High-level linking helper

Add:

`ensure_completion_template_link_by_paths(completed_main_path: str, template_main_path: str, inherit_metadata: bool = True, enforce_template_flags: bool = True) -> LinkResult`

Where `LinkResult` includes:

- `completed_id`, `template_id`,
- `completed_path`, `template_path`,
- `completed_is_template`, `template_is_template`,
- `already_linked` (bool),
- `linked_now` (bool),
- `postcondition_ok` (bool).

Contract:

- resolves both paths (error if missing/unregistered),
- optionally enforces `is_template=False` for completion and `True` for template,
- links if needed,
- verifies final template relation and returns structured result.

---

## Skill/documentation changes

Update:

- `.cursor/skills/pdf-file-manager/SKILL.md`
- `ai_study_buddy/pdf_file_manager/README.md`
- `ai_study_buddy/pdf_file_manager/SPEC.md` (API contract section)

Add an explicit section:

- **Return shape and access discipline**
  - `get_*` returns `PdfFile` objects (or documented transitional contract),
  - use helpers for cross-version safety,
  - avoid direct `.get(...)` / `['id']` in workflow scripts unless working with explicit dict payloads.

Add a canonical snippet for Phase-B-style link/verify using new helper.

---

## Backward compatibility and migration

1. Keep existing low-level methods unchanged.
2. Introduce helpers and high-level API as additive changes.
3. Migrate internal scripts/skills first.
4. Optionally emit deprecation warnings in internal utilities when dict-like fallback path is used (if mixed shape remains possible).

---

## Test plan

1. **Unit tests — helper accessors**
   - `PdfFile` input returns expected values.
   - dict-like input (if supported) returns expected values.
   - invalid input raises clear `TypeError`.
2. **Unit tests — high-level link helper**
   - already linked case returns `already_linked=True`, `postcondition_ok=True`.
   - unlinked case performs link and returns `linked_now=True`.
   - wrong `is_template` flags are corrected when `enforce_template_flags=True`.
3. **Workflow regression test**
   - simulate Phase B subset: scan, resolve mains, helper link, verify all postconditions.
   - assert no representation-shape branching is required in test script.

---

## Risks and open questions

- If some external consumers rely on dict-return behavior, strict object-only contracts may break those scripts; helpers should bridge this.
- High-level helpers must not hide side effects; docs should clearly state when metadata/flags are mutated.
- Naming: decide whether helper belongs on `PdfFileManager` instance or module-level utility namespace.

---

## References

- `PdfFileManager` source: [`pdf_file_manager.py`](../../pdf_file_manager.py)
- Skill currently used in these workflows: [`.cursor/skills/pdf-file-manager/SKILL.md`](../../../../.cursor/skills/pdf-file-manager/SKILL.md)
- Related linking helper proposal: [`04-template-linking-helper.md`](./04-template-linking-helper.md)
