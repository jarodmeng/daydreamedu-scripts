# Marking Asset Bundle: First-Class Contract and Package Support

Status: Implemented (Phases A-E complete)

Audience: Maintainers of `ai_study_buddy/marking`, `ai_study_buddy/review_workspace`, `ai_study_buddy/context/marking_assets`, `.cursor/skills/mark-goodnote-completion/SKILL.md`, `.cursor/skills/diagnose-student-school-work/SKILL.md`, and any future consumers of per-run page renders or crops (sync jobs, parent portals, analytics).

Implementation snapshot (as of 2026-04-23):

- Completed in package code: shared MAB path builders, writer-aligned bundle bootstrapping (`attempt/` + `crops/`), bundle validator/report types, validation CLI, manifest helpers, and test coverage for bundle checks.
- Completed in consumer docs/skills: MAB root/path guidance and full-page filename conventions for the two marking skills.
- Completed in package code (Phase C): default manifest write path after render finalization (`report_renderer` calls manifest writer when attempt images exist).
- Completed in Review Workspace (Phase D): backend startup/request preflight now validates the pilot bundle via strict MAB checks before serving attempt detail data.
- Completed in package code (Phase E): package-owned PDF rendering helpers now write standardized full-page outputs into MAB (`attempt/page-{nn}.{ext}` and mapped `answers/page-{nn}.{ext}`).
- Migration execution (Step 9) is complete through M4, including strict full-page filename normalization and manifest consistency checks (see §9.14).
- Verification status: `pytest -q ai_study_buddy/marking/tests` passed (**67 passed**) after subsequent package integrations (including run-artifact cleanup).

## 1) Executive summary

Previously, **per-run marking assets** (attempt page PNGs, optional answer renders, crops, helper scripts) were described partly in Cursor skills, partly in `SPEC.md` as “ephemeral,” and partly enforced by `write_marking_artifact` (auto `context.marking_asset` + directory creation). Downstream tools such as **Review Workspace** already assumed a **filesystem layout** under `context.marking_asset`, but there was **no single normative bundle contract** owned by the `marking` package.

This proposal elevates the **Marking Asset Bundle (MAB)** to a **standard, package-owned contract**: normative directory layout, **`bundle.json` manifest (written by default once Phase C lands)**, validation APIs, and path builders that **workflows import and skills follow** instead of re-deriving conventions. The canonical JSON artifact (`marking_result.v1.x`) remains the **scoring and reporting** source of truth; the bundle is the **auditable visual substrate** for human and AI review, question-page mapping evidence, and future outlets. A **detailed migration playbook** for existing on-disk trees is in **§9**.

## 2) Why this proposal exists

### 2.1 Problems

_Historical motivation for this proposal (many items are now addressed in Phase A-B implementation):_

1. **Split authority:** Skills document `marking_assets/<scratch_slug>/` with a suggested layout, while `artifact_writer._apply_marking_asset_path` pins `context.marking_asset` to `marking_assets/<student_slug>/<subject_context>/<artifact_stem>/`. Operators must mentally reconcile “scratch slug” vs **writer-derived** paths.
2. **Weak normative detail:** `SPEC.md` states where bundles live and that `marking_asset` is a relative path; it does not fully specify **required subfolders**, **filename conventions**, or **relationship to** `question_page_map[].evidence_image`.
3. **Consumer fragility:** Review Workspace sorts images by “trailing number in stem” (`review_workspace/SPEC.md`). Historically, mixed naming (`attempt-page-01.png` vs `page-01.png`) complicated ordering and duplicated script logic; the MAB contract fixes this with **one normative attempt filename pattern** (§4.4) and a **migration** that renames legacy files (§9.6).
4. **No package-level verification:** There is no shared `validate_marking_asset_bundle` used at write time, in tests, or before serving assets in production-like paths.
5. **Future sync:** If bundles are replicated to object storage or CDNs, a **small manifest** (page count, bundle schema version) avoids re-scanning PNG trees and clarifies what must be copied.

### 2.2 Goals

1. **Single normative spec** for what constitutes a valid MAB for a marking run, documented in `marking/SPEC.md` and summarized in `marking/README.md`.
2. **Package-owned implementation:** path resolution, directory creation, **`bundle.json` write (default on)**, and validation live under `ai_study_buddy/marking/` (new submodule or `core/` modules as appropriate).
3. **Stable downstream contract:** Review Workspace and other consumers depend only on **documented relative paths** under `context.marking_asset` and **documented manifest fields** where applicable—not on skill prose.
4. **Versioned bundle layout** independent of `marking_result` schema bumps where possible (e.g. `bundle_layout_version` in manifest only).
5. **Testability:** Small golden or synthetic bundles in `marking/tests/` exercise validators and path logic without relying on a full GoodNotes tree.
6. **Path safety:** bundle-relative references are normalized and cannot escape `context_root` / bundle root via absolute paths, `..`, or symlink tricks.

### 2.3 Non-goals

1. **Committing** real student PNGs to git (fixtures may use tiny placeholder images or empty-dir tests where sufficient).
2. **Replacing** canonical JSON with the bundle as the source of truth for scores or diagnosis text.
3. **Mandatory** answer-key renders for workflows that legitimately have **no** answer PDF (`diagnose-student-school-work`); `answers/` stays optional.
4. **Pixel-level** question bounding boxes or automatic crop generation for all subjects (may compose with later proposals).
5. **Registry or SQLite** integration for bundle storage URIs (out of scope; bundles remain under `context_root` unless a separate sync proposal adds remote handles).

## 3) Current implementation snapshot

### 3.1 Canonical JSON linkage

- `write_marking_artifact` (`marking/core/artifact_writer.py`):
  - Resolves the JSON path under `marking_results/<student>/<subject>/`.
  - Sets `context.marking_asset` using shared path logic (`marking_asset_rel_path_from_artifact_path`) to:
    - `marking_assets/<student_slug>/<subject_context>/<artifact_stem>`
    - where `<artifact_stem>` equals the JSON filename stem (includes `__YYYYMMDD_HHMMSS` suffix).
  - Calls `_ensure_marking_asset_dir` to create the bundle root and required subfolders `attempt/` and `crops/` under `context_root`.
- If the JSON path is not under `context_root` / `marking_results/...`, `marking_asset` defaults to `null` (edge case for custom `output_path`).

### 3.2 Schema

- `marking_result.v1.2+`: `context.marking_asset` is `null` or non-empty string; validator requires it to be a plausible relative path (see `artifact_schema.py`).
- `marking_result.v1.4`: `context.question_page_map[]` may reference `evidence_image` relative to the bundle root (proposal `4-question-page-mapping-v1_4.md`).

### 3.3 Downstream: Review Workspace

- `review_workspace/SPEC.md` expects:
  - `context.marking_asset` present for attempt detail route (500 if missing).
  - Static files under `ai_study_buddy/context/**`; images from `<marking_asset>/attempt/*` and optionally `<marking_asset>/answers/*`.
  - Filename sort: trailing number in stem, then lexical.

### 3.4 Repository hygiene

- `.gitignore` ignores `ai_study_buddy/context/marking_assets/`, `marking_results/`, `learning_reports/` so local runs do not dirty the repo; **CI tests** should use temporary directories.

### 3.5 Package APIs and workflow entrypoints (implemented)

- New package module: `ai_study_buddy/marking/assets/`:
  - `layout.py`: directory constants and full-page filename pattern helpers.
  - `paths.py`: `marking_asset_rel_path_from_artifact_path`, `bundle_root_from_context`.
  - `render.py`: `render_attempt_pdf_to_bundle`, `render_answers_pdf_pages_to_bundle`.
  - `validate.py`: `ValidationIssue`, `ValidationReport`, `validate_marking_asset_bundle`, `assert_marking_asset_bundle_ready_for_review`.
- Public API exports in `marking/api.py` include path helpers, validators, and render helpers.
- Validation CLI: `python3 -m ai_study_buddy.marking.workflows.validate_bundle <artifact.json> [--strict]`.

## 4) Design: Marking Asset Bundle (MAB)

### 4.1 Definitions

| Term | Meaning |
| --- | --- |
| **Context root** | Directory containing `marking_results/`, `learning_reports/`, `marking_assets/` (default: `ai_study_buddy/context`). |
| **Bundle root** | Absolute path: `context_root / context.marking_asset` when `marking_asset` is set. |
| **MAB** | The filesystem tree at bundle root that conforms to this proposal’s layout and manifest rules (**`bundle.json`** required for new/post–Phase-C bundles; see §4.5). |

### 4.2 Normative relative path for `context.marking_asset`

**Canonical (writer-aligned):**

```text
marking_assets/<student_slug>/<subject_context>/<artifact_stem>
```

- **No** trailing slash in JSON.
- `<artifact_stem>` **must** match the marking result JSON basename (without `.json`) for that run, so JSON and bundle are **joinable by stem** without scanning.
- `context.marking_asset` **must** be a normalized relative POSIX path under `marking_assets/`: no leading slash, no `..` segments, no empty path parts, and no symlink-resolved escape outside `context_root / marking_assets`.

**Rationale:** Ties bundle identity to the canonical artifact row; avoids orphan folders with different names than the JSON; matches existing writer behavior so migration is mostly **documentation + validation**, not a path breaking change.

**Skills:** `.cursor/skills/mark-goodnote-completion/SKILL.md` and `diagnose-student-school-work/SKILL.md` should be updated to describe “bundle root = writer path above” and deprecate informal-only `<scratch_slug>` wording except as a pre-json alias for the same folder.

### 4.3 Directory layout (normative)

All paths are relative to **bundle root**.

| Path | Required | Contents |
| --- | --- | --- |
| `attempt/` | **Yes** | Rendered pages of the **student attempt** (completion PDF). At least one image after a full visual marking workflow, unless explicitly documented as a partial “JSON-only” run (see §4.8). |
| `answers/` | No | Rendered pages of the **answer key** PDF (mapped or embedded range). Omit entire directory when no answer PDF exists (school-work workflow). |
| `crops/` | No | Isolated crops (e.g. answer-key block verification, tight evidence for a question). |
| `scripts/` | No | Per-run one-off Python helpers (`_*.py`). Not consumed by production viewers. |

**Forbidden:** placing bundle PNGs inside `marking_results/` or `learning_reports/` (existing rule; restated for sync pipelines).

**External sync profile (decision):** pipelines that replicate a bundle to object storage, CDNs, or parent-facing hosts should copy **`attempt/`**, **`answers/`** (if present), **`crops/`** (if present), and **`bundle.json`** when present (after Phase C it should almost always exist). They should **exclude `scripts/` by default** (operator-only code; not required for review UIs). A separate “full archive” profile may include `scripts/` for forensics or rerun.

### 4.4 Attempt image naming (normative — single convention)

There is **only** the normative pattern below for new work and for any bundle considered **MAB-compliant** after migration. Validators and package renderers **do not** treat alternate spellings (e.g. `attempt-page-NN.png`) as valid long-term; legacy names are **renamed on disk** during migration (§9.6) and JSON references updated.

- **Attempt pages (full-page renders):** `attempt/page-{n:02d}.png` for 1-based PDF page index `n` (e.g. `page-01.png`, `page-02.png`, …).

**`crops/` exception:** Files under **`crops/`** are **not** required to use `page-NN` stems (e.g. `crops/q5-key-block.png` is fine). The strict **`page-{nn}.{ext}`** contract applies only to **full-page** PNGs/JPEGs/WebP under **`attempt/`** and **`answers/`**.

**Sorting rule for consumers (attempt/answers):** sort by parsed 1-based page index when the filename matches `^page-(\d+)\.(png|jpg|jpeg|webp)$` (case-insensitive). Any other basename under `attempt/` or `answers/` is a **validation error** in strict mode (or a migration-tool **warning** only while §9.6 is in progress).

**Answers folder:** use the same numeric stem under `answers/`, e.g. `answers/page-{n:02d}.png` for the *n*th rendered answer page in **mapping order** (first rendered page = `page-01.png`, not necessarily the global PDF page number). If a second naming prefix is ever required for clarity, document it in `bundle_layout_version` > 1; v1 uses `page-NN` under both `attempt/` and `answers/`.

### 4.4.1 Filename contract vs `bundle_layout_version`

Do not conflate **PNG basename rules** with **`bundle_layout_version`** in `bundle.json`:

- **Filenames** — Under v1, only `page-{nn}.{ext}` as in §4.4. Legacy names are removed from the repo/workspace via **§9.6**, not supported indefinitely in validators.
- **`bundle_layout_version`** — Versions the **bundle directory contract** (required subfolders, manifest fields, optional future additions such as `thumbnails/`). Bumping it is **not** the mechanism for alternate attempt spellings; filename rules stay in §4.4 unless a future proposal explicitly changes them with a new layout version and migration.

### 4.5 Manifest: `bundle.json`

Placed at **bundle root**.

#### Intended purpose and usage

The manifest is **not** a second source of truth for scores, marks, or per-question diagnosis — the canonical **`marking_result` JSON** remains authoritative for all gradable semantics. `bundle.json` exists so **machines can reason about the bundle folder** without parsing a large JSON file or scanning ambiguous directory trees.

**Primary purposes:**

1. **Sync and replication** — Jobs that push bundles to S3, GCS, or a CDN can read a small file to learn page counts and layout version instead of inferring from ad hoc filenames alone.
2. **Validation cross-checks** — Compare `attempt_page_count` (and optional `answers_page_count`) to actual files; detect incomplete copies or partial renders.
3. **Consumer handshake** — Review apps or future services can reject or downgrade unknown **`bundle_layout_version`** values with a clear error instead of mis-sorting pages.
4. **Operational metadata** — Optional `created_at` / `notes` for humans and logs without touching canonical JSON.

**Who writes it:** the marking pipeline **after render finalization**, or a dedicated `write_bundle_manifest` step that runs only once bundle contents are finalized enough for counts and layout checks to be trustworthy.

**Who reads it:** validators, sync CLIs, optional Review Workspace enhancements — minimal image serving can still glob `attempt/page-*.png`; the manifest adds **cheap** structure checks and sync metadata.

**Default write policy (decision):** once **Phase C** (§10) lands, **`bundle.json` should be written by default only after render finalization** for a non-null `context.marking_asset` bundle, because the manifest is meant to describe the realized bundle on disk, not a provisional directory shell. **Historical bundles** predating Phase C may lack `bundle.json` until operators run a **backfill** pass (migration org phase **M3** / manifest write step); validators should emit a **warning** (not a hard failure) for missing manifest only for that transitional class, and **require** manifest for strict CI on new artifacts once Phase C is released.

**Proposed fields (initial schema, versioned):**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `bundle_layout_version` | `integer` | Yes | Starts at `1`; increment when layout rules change. |
| `marking_result_schema_version` | `string` | No | e.g. `marking_result.v1.4` for quick pairing checks. |
| `attempt_page_count` | `integer` | No | Number of attempt pages rendered. |
| `answers_page_count` | `integer` | No | Nullable when no answers. |
| `created_at` | `string` | No | ISO-8601 SGT (`+08:00`) mirroring artifact convention when written alongside JSON. |
| `notes` | `string` | No | Free text for operators (non-canonical). |

**Rules:**

- After Phase C ships, **new** marking runs should **always** write `bundle.json` after render finalization when `context.marking_asset` is set.
- Pre-Phase-C bundles: **warn** if manifest is missing until backfilled; **strict** CI for new code paths should require manifest + consistent counts.
- When present, `bundle_layout_version` must be understood by the package; unknown major versions → validation warning or error (policy TBD).

**Privacy:** manifest must **not** duplicate raw absolute filesystem paths if canonical JSON uses placeholder normalization; optional privacy-safe file ids only if already present on the artifact.

### 4.6 Relationship to `question_page_map` and `evidence_image`

- When `evidence_image` is set, it should be **relative to bundle root** (e.g. `attempt/page-03.png` or `crops/q5-block.png`).
- `evidence_image` **must** be a normalized relative POSIX path under the bundle root: no leading slash, no `..` segments, no empty path parts, and no symlink-resolved escape outside the bundle root.
- Validator option: `evidence_image` paths must resolve to an existing file under bundle root for `high` confidence rows (configurable strictness).

### 4.7 Workflow modes vs bundle contents

| Workflow | `answers/` | `attempt/` | Typical `crops/` |
| --- | --- | --- | --- |
| GoodNotes + mapped / embedded key | Expected when answer PDF was used | Required | Recommended for key verification |
| School work (no separate key) | Absent | Required | Optional per item |

### 4.8 Exceptional runs: JSON without images

Rare cases (regeneration, migration, headless tests) might produce JSON with `marking_asset` null or an empty `attempt/`. Policy choices:

1. **Strict mode** (CI / preflight): `attempt/` must contain ≥1 image when `marking_asset` is non-null.
2. **Lenient mode** (legacy migration): allow empty bundle with explicit `context.marking_asset` null and document that Review Workspace will not serve images.

Recommendation: **default strict for new artifacts**; lenient only for explicit migration flags.

## 5) Package API surface (implemented)

Names are indicative; final names follow existing `marking` naming style.

### 5.1 Path builders

- `marking_asset_rel_path_from_artifact_path(artifact_json_path, *, context_root) -> str | None`  
  Centralize logic currently in `_apply_marking_asset_path` for reuse and testing.
- `bundle_root_from_context(context: dict, *, context_root) -> Path | None`  
  Resolve absolute bundle path from loaded JSON `context`.

### 5.2 Lifecycle

- `ensure_marking_asset_bundle(bundle_root: Path, *, layout_version: int = 1) -> None`  
  **Status:** behavior implemented via `artifact_writer._ensure_marking_asset_dir` (creates bundle root + `attempt/` + `crops/`); dedicated public helper can still be extracted later if needed.
- `write_bundle_manifest(bundle_root: Path, payload: dict) -> None`  
  **Status:** implemented (Phase C). Default path writes after renders finalize; see §4.5.

### 5.3 Validation

- `validate_marking_asset_bundle(*, bundle_root: Path, artifact_dict: dict | None, strict: bool = False) -> ValidationReport`  
  - Checks directory layout, **§4.4** full-page naming under **`attempt/`** and **`answers/`** only (ignore arbitrary names under `crops/`), `bundle.json` presence/consistency (per strictness), optional cross-check with `question_page_map`.
- `assert_marking_asset_bundle_ready_for_review(bundle_root, artifact_dict) -> None`  
  Thin wrapper with Review Workspace minimum requirements.

### 5.4 Rendering helpers

Thin wrappers around PyMuPDF are now available in `marking/assets/render.py`:

- `render_attempt_pdf_to_bundle(pdf_path, bundle_root, *, dpi_scale=2.0, image_format=\"png\", clean_existing=True) -> list[Path]`  
  Renders all attempt pages to **`attempt/page-{n:02d}.{ext}`** (§4.4).
- `render_answers_pdf_pages_to_bundle(pdf_path, bundle_root, *, pages_1_based, dpi_scale=2.0, image_format=\"png\", clean_existing=True) -> list[Path]`  
  Renders selected answer pages in mapping order to **`answers/page-{n:02d}.{ext}`** (§4.4).

Keep **heavy** orchestration (registry resolution, cropping heuristics) in `workflows/`; keep **dumb IO + naming** in `core/` or `marking/assets/`.

### 5.5 Suggested module layout

```text
ai_study_buddy/marking/
  assets/                          # new package (or marking/bundle/)
    __init__.py                    # re-export stable public API
    paths.py                       # rel path builders, bundle_root resolution
    layout.py                      # constants: dir names, filename regexes
    render.py                      # PDF->bundle full-page render helpers
    manifest.py                    # read/write/validate bundle.json
    validate.py                    # ValidationReport, validate_marking_asset_bundle
```

Alternative: place `paths.py` logic next to `artifact_writer.py` and only add `assets/validate.py` to avoid churn; the proposal recommends a dedicated subpackage once multiple files are needed.

## 6) Integration points

### 6.1 `write_marking_artifact`

- After `_apply_marking_asset_path` and `_ensure_marking_asset_dir`:
  - **Implemented:** writer now applies shared path-builder logic and ensures bundle root + `attempt/` + `crops/` whenever `context.marking_asset` is non-null.
  - Do **not** write **`bundle.json`** at bare directory-creation time; manifest write remains tied to post-render finalization (**§4.5**).

### 6.2 `report_renderer`

- Include bundle root or `marking_asset` rel path in “Report Context” (already partially there). Rendering must **not** require reading `bundle.json`; markdown remains derived from canonical JSON alone.
- **Implemented (Phase C):** report rendering now triggers default `bundle.json` write for finalized bundles (attempt images present), keeping manifest generation after visual renders instead of at bare bundle creation time.

### 6.3 `retrack_marking_assets` workflow

- When inferring bundle location, prefer **normative** layout; continue to support legacy `.marking_scratch` / `.tmp_*` only as migration sources documented in `CHANGELOG.md`.
- **Operator playbook:** bulk filesystem + JSON migration steps, verification, and rollback are in **§9** (especially **§9.9** for current limitations when `context.marking_asset` is already a **nested** three-level path).
- **Implementation follow-up:** align this workflow with MAB path builders and nested-bundle preservation (or deprecate guessing in favor of deterministic paths derived from the JSON path).

### 6.4 Review Workspace

- Import `validate_marking_asset_bundle` in dev/preflight or startup (optional).
- Document in `review_workspace/SPEC.md` the **minimum bundle** required: non-null `marking_asset`, `attempt/` with at least one supported image extension.
- Longer term: use manifest for page count if sorting rules need a tie-break beyond filenames.

## 7) SPEC and documentation updates

| Document | Change |
| --- | --- |
| `marking/SPEC.md` | New section **“Marking Asset Bundle (MAB)”**: path rule, layout table, naming, manifest, relationship to `evidence_image`, strictness levels. |
| `marking/README.md` | Short pointer + example tree diagram. |
| `marking/CHANGELOG.md` | Entry per shipped phase. |
| `.cursor/skills/...` | Align Tier B paths with normative `marking_assets/<student>/<subject>/<stem>/`. |
| `review_workspace/SPEC.md` | Reference marking package bundle version; image discovery rules. |

## 8) Testing strategy

1. **Unit tests** under `marking/tests/`:
   - `test_marking_asset_bundle.py`: path builder behavior and validator coverage (good bundle, missing `attempt/`, bad `evidence_image`, manifest page_count mismatch).
   - `test_artifact_core.py`: writer integration with `tmp_path` including bundle subdir creation (`attempt/`, `crops/`).
2. **No large binaries:** use 1×1 PNG writes or empty-file tests where validation only checks existence.
3. **Golden bundle (optional):** tiny checked-in fixture under `marking/tests/fixtures/marking_asset_bundle_v1/` if repo policy allows tiny binary; otherwise generate in test setup.

## 9) Detailed migration plan

This section is the **operator playbook** for moving existing `marking_assets/` (and related legacy trees) to the **normative MAB** defined in §4, without breaking canonical JSON, Review Workspace, or future validators.

### 9.1 Preconditions (every migration)

1. **Backup:** Copy the entire `context_root` (or at minimum `marking_results/`, `learning_reports/`, `marking_assets/`) before bulk edits. Gitignored trees are easy to lose.
2. **Single source of truth:** After any move or rename, **canonical JSON** under `marking_results/` must remain valid (`validate_marking_artifact_dict` once implemented package checks exist; today use existing validator). **Markdown reports** must be re-rendered from JSON (`report_renderer`), not hand-edited, if JSON changed.
3. **Path semantics:** `context.marking_asset` is always **relative to `context_root`**, POSIX-style, **no** leading slash, **no** trailing slash (see `SPEC.md`).
4. **Atomicity per artifact:** For each marking run (one JSON file), complete **filesystem move + JSON update + optional report re-render** in one logical transaction before starting the next run, so no JSON points at a missing bundle mid-batch.

### 9.2 Inventory and classification

Run a **read-only** inventory (scripts may land under `marking/workflows/` as part of Phase B in §10):

| Class | Detection rule | Typical cause |
| --- | --- | --- |
| **A — Already normative** | `context.marking_asset == marking_assets/<student>/<subject>/<artifact_stem>` **and** that directory exists, **and** `<artifact_stem>` equals the sibling JSON basename stem under `marking_results/...` | Artifacts written by `write_marking_artifact` after v1.2 behavior landed |
| **B — Normative path, layout drift** | Bundle root matches Class A path but missing `attempt/` subfolder, or PNGs live at bundle root instead of under `attempt/` | Manual renders, older operator habits |
| **C — Flat legacy scratch** | Only **one** path segment under `marking_assets/` (e.g. `marking_assets/winston__unit_name/`) while JSON expects nested path **or** JSON still points at `.tmp_*` / `.marking_scratch` | Older skill wording, pre-writer conventions |
| **D — Orphan bundle** | Directory exists under `marking_assets/` but no matching JSON stem, or JSON has `marking_asset: null` | Deleted JSON, abandoned run |
| **E — Reference-only legacy strings** | JSON `answer_mapping_notes` / `generation.notes` contain textual paths to old roots but `context.marking_asset` is correct | Historical copy-paste |

**Output of inventory:** a manifest (CSV/JSON) listing: `json_path`, `current_marking_asset`, `bundle_exists`, `class`, `recommended_action`, `evidence_image_count` (if any).

### 9.3 Class A — Already normative (no path migration)

**Action:** None required for **path** alignment.

**Hygiene (normative before declaring bundle MAB-compliant):**

1. Ensure subfolders exist: create empty `attempt/` if all PNGs are wrongly at bundle root — **then move** PNGs into `attempt/` and update `question_page_map[].evidence_image` if paths referenced old locations.
2. Run **§9.6** on `attempt/` and `answers/` so **only** `page-{nn}.{ext}` names remain.
3. Write or refresh **`bundle.json`** (§4.5) once Phase C exists.

### 9.4 Class B — Normative path, layout drift

**Symptoms:** `marking_asset` already matches §4.2 but files violate §4.3–4.4 (e.g. PNGs directly under bundle root, or `Attempt/` casing mismatch on case-sensitive filesystems).

**Steps:**

1. Create normative dirs: `attempt/`, optionally `answers/`, `crops/`, `scripts/`.
2. **Move** (not copy-then-forget) image files into `attempt/` (or `answers/`).
3. Run **§9.6** so all page images use **`page-{nn}.{ext}`** only.
4. Grep inside the **single** artifact JSON for string literals matching old relative paths (`"evidence_image"`); update to new paths relative to bundle root.
5. `validate_marking_artifact_dict` → `render_learning_report_from_json`.
6. Smoke-test Review Workspace or static file list: image sort order matches attempt page order.

### 9.5 Class C — Flat legacy scratch or non-normative root

**Target state:** Bundle root = `marking_assets/<student_slug>/<subject_context>/<artifact_stem>/` where `<artifact_stem>` **equals** the marking JSON filename stem (same as today’s writer).

**Steps (per JSON row):**

1. Read `context.student_id` / `student_name` → `slugify_student` (must match `marking_results/` parent folder names already in use for that file).
2. Read `subject_context` from JSON `context` (must match JSON parent folder).
3. Derive `<artifact_stem>` from the **actual JSON path** on disk: `Path(json).stem` — this is authoritative for pairing folder ↔ JSON.
4. Create target directory: `context_root / "marking_assets" / student_slug / subject_context / artifact_stem`.
5. **Move** the entire contents of the legacy flat folder (e.g. `attempt/`, `crops/`, `scripts/`, loose PNGs) into the target bundle root, preserving inner structure where possible.
6. Set `context.marking_asset` to the **relative** path `marking_assets/<student_slug>/<subject_context>/<artifact_stem>`.
7. Run **§9.6** on the new bundle so attempt/answer pages use **only** `page-{nn}.{ext}`.
8. Replace any **absolute** or legacy path strings inside JSON notes that pointed at the old folder (optional but recommended for human grep); keep path-privacy rules from `SPEC.md`.
9. Validate + re-render report (§9.1).
10. Remove the **empty** legacy flat directory if nothing else references it.

**If one flat folder served multiple JSONs (collision):** split manually: duplicate PNGs is acceptable short-term; long-term each JSON gets its own bundle root. Do not point two JSONs at one bundle without an explicit operational reason.

### 9.6 Required: legacy PNG rename to normative `page-{nn}.{ext}`

**Policy:** There is **no** long-term dual support for **full-page** names like `attempt-page-NN.png` under `attempt/` or `answers/`. Every bundle that is kept in use must be migrated so those directories contain **only** §4.4 `page-{nn}.{ext}` files. **`crops/`** is out of scope for this rename rule (descriptive basenames remain valid). Package validators treat non-conforming names under `attempt/` / `answers/` as **errors** in strict mode once migration is declared complete for a workspace.

**Steps (per bundle):**

1. Enumerate image files in `attempt/` and `answers/`. Classify: already `page-{nn}.{ext}` → skip; legacy patterns (`attempt-page-*`, `page_*`, etc.) → plan rename to `page-{nn}.{ext}` using the **intended 1-based render order** (from PDF page order or manifest notes), resolving collisions before applying.
2. **Dry-run:** print rename map and any JSON string replacements; verify page order against source PDF if still available.
3. Rename on disk (copy + checksum verify + delete old, if safer than pure rename).
4. In the paired marking JSON, update every `question_page_map[].evidence_image` and any other field that embeds the old basename.
5. `validate_marking_artifact_dict` → `render_learning_report_from_json`.
6. If Phase C is available, write or refresh **`bundle.json`** with correct `attempt_page_count` / `answers_page_count`.

**Risk:** High if automated without per-bundle dry-run; **always** use `--dry-run` first and keep §9.1 backups.

### 9.7 Class D — Orphan bundles

**Policy (choose explicitly for your org):**

- **Archive:** Move to `marking_assets/_archive/<date>/...` outside any `context.marking_asset` pointer.
- **Delete:** Only after confirming no JSON references (grep `marking_results` for path fragments).

Do not delete until inventory shows **zero** JSON references.

### 9.8 Class E — Textual legacy path references (`.marking_scratch`, `.tmp_*`)

1. Prefer **filesystem reality** first: ensure assets live under `marking_assets/...` (§9.5).
2. Run or replicate the string substitution behavior of `retrack_marking_assets` for notes fields (`.marking_scratch` → `marking_assets`) **after** verifying the referenced folder exists at the new location.
3. Do not rely on notes alone for `marking_asset`; the **`context.marking_asset` field** must be correct for machines.

### 9.9 Tooling caveat: `retrack_marking_assets.py`

The workflow `ai_study_buddy.marking.workflows.retrack_marking_assets`:

- Builds **candidate** asset directories from **immediate children** of `marking_assets/` only (`iterdir` on the asset root).
- When an existing `context.marking_asset` points at a **nested** path under `marking_assets/`, the implementation resolves via the **first path segment** under `marking_assets/` in some branches (see source: `top_level = asset_root / rel_existing.parts[0]`).

**Implication:** For trees that already use the **full normative three-level** path (`marking_assets/<student>/<subject>/<stem>/`), **do not bulk-run** `retrack_marking_assets` expecting it to preserve deep paths until this workflow is reviewed/updated alongside MAB Phase A–B. Safer approaches for nested bundles:

- **Leave** `context.marking_asset` unchanged if it already resolves to an existing directory.
- Use a **dedicated migration script** (part of this proposal’s deliverables) that sets `marking_asset` to `marking_assets/<student>/<subject>/<stem>` **deterministically** from the JSON path without collapsing to top-level segments.

Document any fix to `retrack_marking_assets` in `CHANGELOG.md` when implemented.

### 9.10 Verification checklist (post-migration)

For each migrated artifact:

| Check | Pass criteria |
| --- | --- |
| JSON validity | `validate_marking_artifact_dict` passes |
| Bundle exists | `context_root / context.marking_asset` is a directory |
| Attempt images | `attempt/` contains ≥1 `.png`/`.jpg`/… **or** explicit documented exception for JSON-only runs (§4.8) |
| Map evidence | Every non-null `evidence_image` resolves under bundle root (when v1.4 map present) |
| Report | Learning report re-rendered; “Marking asset folder” line matches new rel path |
| Review UI | Pilot Review Workspace loads attempt images in correct page order |
| Filename contract | Every **full-page** image under `attempt/` and `answers/` matches §4.4 `page-{nn}.{ext}`; `crops/` exempt |
| Manifest | `bundle.json` present and consistent after Phase C / migration backfill |

Future: replace manual checklist rows with `validate_marking_asset_bundle` (§5.3).

### 9.11 Rollback

1. Restore from backup taken in §9.1.
2. If only JSON was wrong: revert `context.marking_asset` / `evidence_image` from backup JSON; re-render report.

### 9.12 Suggested migration phases (organizational, not package code)

These run **before or in parallel** with implementation Phase A in §10:

| Org phase | Scope | Exit criterion | Status (2026-04-23) |
| --- | --- | --- | --- |
| **M0** | Inventory only (§9.2) | Spreadsheet of all artifacts with class A–E | **Completed** |
| **M1** | Class A + B only | All targeted bundles have `attempt/` and valid JSON | **Completed** |
| **M2** | Class C for high-value students/subjects | No remaining flat `marking_assets/*` dirs referenced by JSON | **Completed** |
| **M3** | **Required** PNG rename + `bundle.json` backfill (§9.6, §4.5) | No legacy attempt/answer stems; manifests present for in-use bundles | **Completed** |
| **M4** | Orphan cleanup (§9.7) | No unreferenced multi-GB trees under `marking_assets/` | **Completed (archived)** |

### 9.13 Compatibility summary

1. **No breaking change** to the **string format** of `context.marking_asset` for artifacts that already use the writer-aligned three-level path.
2. **Legacy** flat dirs, `.tmp_*`, and `.marking_scratch` references require **explicit** filesystem + JSON work per §9.5–9.8.
3. **Filename contract:** after org phase **M3**, validators enforce **§4.4** only (no dual-pattern acceptance in strict mode).

### 9.14 Executed migration progress (as of 2026-04-23)

The following reflects actual execution results from the migration runs.

#### Inventory outcomes

- Canonical artifacts scanned: **145**
- Post-conflict-fix inventory before apply:
  - **A**: 5
  - **C**: 140 (all flat `marking_assets/<slug>` legacy paths)
  - **B/D/E**: 0 in this classifier pass
- Shared-bundle collisions at that point: **0**.

#### Class C migration apply

- Dry-run: **140 ready / 0 blocked**
- Apply:
  - JSON rows updated: **140**
  - whole directory moves: **136**
  - merge-into-existing-target cases: **4**
- Post-apply class shape:
  - **A**: 145
  - **C**: 0
  - shared-bundle collisions: **0**.

#### Legacy-vs-canonical asset reconciliation

A controlled reconciliation pass detected legacy folders with missing attempt/answer assets relative to canonical bundles and applied non-destructive merges:

- detected candidate pairs: **25**
- processed pairs: **25**
- copied attempt/answers image files into canonical bundles: **106**
- skipped-existing (same target path already present): **206**
- re-rendered affected reports from canonical JSON: **25**
- render errors: **0**
- processed legacy folders moved to:
  - `marking_assets/_archive/2026-04-23_mab_reconcile_legacy/`

#### Remaining orphan top-level cleanup

After reconciliation, remaining unreferenced top-level legacy dirs were archived:

- moved: **18**
- archive destination:
  - `marking_assets/_archive/2026-04-23_mab_archive_remaining_legacy/`
- remaining unreferenced top-level dirs under `marking_assets/`: **0**.

#### M3 completion follow-up

After the initial apply run, a targeted collision-resolution pass was executed for bundles that still contained legacy full-page names due to same-target filename conflicts. Final state:

- strict bundle validation sweep: **145 / 145 passed**
- strict failures remaining: **0**
- full-page naming under `attempt/` and `answers/`: normalized to §4.4 `page-{nn}.{ext}`.

#### Execution artifacts (logs/manifests)

The following run artifacts were generated during execution and can be used for audit/rollback support:

- `/tmp/marking_mab_inventory.csv`
- `/tmp/marking_mab_inventory_summary.json`
- `/tmp/marking_mab_class_c_dry_run.json`
- `/tmp/marking_mab_class_c_apply_summary.json`
- `/tmp/marking_mab_inventory_post_migration.csv`
- `/tmp/marking_mab_legacy_missing_assets_report.json`
- `/tmp/marking_mab_legacy_reconcile_apply_log.json`
- `/tmp/marking_mab_archive_remaining_legacy_manifest.json`

## 10) Phased implementation roadmap

| Phase | Deliverable | Risk | Status (2026-04-23) |
| --- | --- | --- | --- |
| **A** | SPEC + README MAB section; `layout.py` constants; extract path builder from `artifact_writer` into shared function; tests | Low | **Completed** |
| **B** | `validate.py` + `ValidationReport`; wire optional call from a workflow or CLI (`python -m ...validate_bundle`) | Low | **Completed** |
| **C** | `bundle.json` **write on by default after render finalization** + manifest validation; narrow escape hatch only for emergency rollout | Medium | **Completed** |
| **D** | Review Workspace uses validator in dev or documents minimum bundle; optional startup warning | Low–Medium | **Completed** |
| **E** | Optional `render_attempt_pdf_to_bundle` in package; skills point to module | Medium (dependency surface) | **Completed** |

Phases A-E are now in place.

## 11) Resolved decisions (maintenance of this proposal)

The following were **decided** during proposal review (see also §4.3, §4.4, §4.5, §5.2, §6.1):

| Topic | Decision |
| --- | --- |
| Empty **`attempt/`** and **`crops/`** | **Yes** — always create when `context.marking_asset` is set (cheap, reduces layout drift). |
| **`bundle.json` default** | **On by default** once Phase C ships, but written **only after render finalization** so counts and layout are trustworthy. **Warn-only** for pre–Phase-C trees until backfilled (**§4.5**). |
| **External sync of `scripts/`** | **Exclude by default** from the external sync profile; optional “full archive” may include `scripts/`. |
| **Full-page PNG names** | **Single convention** — only `page-{nn}.{ext}` under `attempt/` and `answers/` (**§4.4**). Legacy names there are **removed via migration** (**§9.6**). **`crops/`** may keep descriptive names. Validators do **not** keep dual-pattern support for `attempt/` / `answers/`. |

## 12) Open questions (remaining)

_None at present._ Further questions may be reopened for future non-breaking helper extensions.

## 13) Success criteria

1. A new engineer can read **only** `marking/SPEC.md` and implement a compatible asset exporter or consumer.
2. Review Workspace (or any third party) can validate a bundle with **one** package entry point.
3. Cursor skills do not introduce path or folder rules that contradict the package.
4. Adding a new optional subfolder (e.g. `thumbnails/`) in the future requires a **bundle_layout_version** bump and a short changelog entry, not ad hoc scattered updates.
5. **No legacy full-page basenames** remain under `attempt/` and `answers/` after migration org phase **M3**; only **`page-{nn}.{ext}`** there (§4.4); `crops/` may use descriptive names.
6. **New marking runs** emit **`bundle.json`** by default (Phase C), and external sync includes it in the default profile (§4.3).

---

## References (in-repo)

- `ai_study_buddy/marking/SPEC.md` — artifact paths, `marking_asset`, path privacy.
- `ai_study_buddy/marking/core/artifact_writer.py` — `_apply_marking_asset_path`, `_ensure_marking_asset_dir`.
- `ai_study_buddy/marking/docs/proposal/4-question-page-mapping-v1_4.md` — `evidence_image` and review UX.
- `ai_study_buddy/marking/workflows/retrack_marking_assets.py` — backfill / repair.
- `ai_study_buddy/review_workspace/SPEC.md` — static asset contract and `marking_asset` requirement.
- `.cursor/skills/mark-goodnote-completion/SKILL.md` — aligned to standardized MAB root and full-page naming.
- `.cursor/skills/diagnose-student-school-work/SKILL.md` — aligned to standardized MAB root and full-page naming.
