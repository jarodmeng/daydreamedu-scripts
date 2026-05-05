# Proposal 13: Standardize `file_question_info` helpers in `marking/` and mirror runs into `study_buddy.db`

## Context

`ai_study_buddy/context/file_question_info/` holds **structured, subject-shaped** metadata for exam / WA / practice PDFs: each run is a folder

`file_question_info/<subject_scope>/<grade>/<slug>/`

containing `question_sections.json` (detector output) and `rendered_pages/` (page PNGs). Slug and layout rules are already tied to **`normalize_attempt_stem`** in `ai_study_buddy.marking.core.artifact_paths`, and detectors record **`file_id`** from `PdfFileManager` in **`input_context.files`** (see **single input PDF** below).

**Single input PDF:** Each **`question_sections.json`** describes **one** registered source PDF: **`input_context.files`** is treated as **exactly one** entry (merged booklets, OAS bundled in the same file, etc., are one file). Helpers and validation do **not** need role disambiguation across multiple files or a **`primary_pdf_path_from_input_context`**-style selector—use **`input_context.files[0]`** (after asserting length 1) or resolve **`PdfFile`** from that row’s **`file_id`**.

**Authoritative production rule:** A valid **`question_sections.json`** (and its **`rendered_pages/`** companion) is **only** produced when that PDF was **registered** in **`PdfFileManager`** first—see **Registry prerequisite** and **Input policy** in **`.cursor/agents/*-question-section-detector*.md`**. If registration cannot complete, the detector **fails fast** and emits **no** JSON. Therefore:

- The sole **`input_context.files[0].file_id`** in stored artifacts should always be a real registry UUID (and **`path`** should match **`PdfFile.path`**), not ad-hoc placeholders.
- `marking/` helpers, validators, and DB import can treat **registry-backed `file_id`** as an **invariant** for runs created under the current agent contract (contrast: hand-edited or foreign JSON may violate this and should fail validation or quarantine).

The multi-agent marking skill (`.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md`) today drives structure **only from images + Phase 1 mapper JSON** (`question_id` → `attempt_pages`), with QC gates (duplicate IDs, section collisions). **`file_question_info` is not yet a first-class input** to that pipeline, but it is the natural place to:

- seed or cross-check **question ordering** and **section boundaries**;
- supply **per-item marks** (math/science) and **separate-booklet answer page spans** (Chinese / Higher Chinese) for render and key alignment;
- route Phase 2 batching by **detector `question_type`** (e.g. MCQ vs open-ended).

Separately, marking and review payloads are **JSON-first** with **SQLite projection** into `study_buddy.db` via `ai_study_buddy.learning_db` (migrations, `import_context_json`, dual-write from canonical writers). Question-section artifacts should follow the same pattern: **one canonical on-disk JSON (or explicit export)** plus **queryable DB rows** for lookup by `file_id` and orchestration.

### Current corpus (latest `schema_version` only)

Every existing `question_sections.json` under `file_question_info/` already uses the **current** detector contract for its subject:

| Subject line | `schema_version` |
|--------------|------------------|
| Standard Chinese Paper 2 | `chinese-v1.3` |
| Higher Chinese Paper 2 | `high-chinese-v1.1` |
| English Paper 2 | `english-v1.2` |
| Mathematics | `math-v1.0` |
| Science | `science-v1.0` |

**Implementation scope:** tooling in `marking/` and DB import need only target these five payload strings unless a deliberate schema bump expands the registry. **Supported production path:** artifacts are always tied to **registered** PDFs (see authoritative production rule above). **Optional hardening:** enforce **`input_context.files` length exactly 1** in **`validate_question_sections_dict`** or a future JSON Schema `minItems`/`maxItems` on **`files`**. Older structural JSON Schema files (`*.v1.0.schema.json`, etc.) remain in `ai_study_buddy/schemas/` as history only; **no dual-read paths or downgrade compatibility** are required for new code.

## Subject detectors (summary)

The five agent specs under `.cursor/agents/` agree on layout and ontology; payloads differ by subject:

| Agent | `schema_version` (current) | Notes |
|--------|-----------------------------|--------|
| Chinese Paper 2 | `chinese-v1.3` | `answers_in_separate_booklet`, optional `answers_page_range`, `stem_page_range`, `question_info` |
| Higher Chinese Paper 2 | `high-chinese-v1.1` | Same family of fields; HC uses `singapore_primary_chinese` as `<subject_scope>` per layout table |
| English Paper 2 | `english-v1.2` | Optional `stem_page_range`, `answer_page_range` (OAS); `question_info` |
| Math | `math-v1.0` | Per-section `question_info`; no separate booklet |
| Science | `science-v1.0` | `question_info`; uniform MCQ marks |

**Folder layout on disk:** **`<slug>`** = `normalize_attempt_stem` on **`input_context.files[0].path`** (after resolving the registered **`PdfFile`**). **`<grade>`** is the folder segment under `file_question_info/.../<grade>/...`: prefer **`PdfFile.metadata["grade_or_scope"]`** for that sole file; path-walk fallbacks in agent docs apply only when metadata is still missing **after** registration (rare—usually a registry repair task).

**Registered files (`PdfFileManager`):** Production **`question_sections.json`** always implies the detector started from **registry-backed** PDFs. In `marking/` helpers, **do not re-derive grade** from raw path parsing when **`metadata["grade_or_scope"]`** is present (see **`ARCHITECTURE.md`** / **`metadata.grade_or_scope`**). Normalize for the folder segment (e.g. `P6` / `PSLE` / `Archive` casing). If it is missing, treat as a **data gap** (fail closed or require an explicit override)—repair registry metadata instead. **Detector agents** require **Registry prerequisite** in each **`.cursor/agents/*-question-section-detector*.md`**; orchestrators **`write_question_sections_bundle`**-style tooling should not bypass that contract.

These contracts are **not identical JSON shapes** across subjects; any shared Python layer must **dispatch by `schema_version`** (and thus subject), not one rigid dataclass for all payloads.

## What `marking/` already provides (relevant)

- **Paths:** `normalize_attempt_stem`, `build_marking_run_paths`, bundle paths under `marking_assets/…`.
- **Context:** `resolve_marking_context` → file ids, answer page range, `QuestionSelection` (including `section_hint`).
- **Artifacts:** `write_marking_artifact`, `context.question_page_map`, schema in `ai_study_buddy/schemas/marking/`.
- **Assets:** `render_attempt_pdf_to_bundle`, validation, manifest writers.

**Gap:** no module loads `question_sections.json`, validates it, resolves `run_folder` from a registered `PdfFile`, or connects detector output to Phase 1 / `question_page_map` / partial-marking scope.

## Proposed Python helpers (new surface under `marking/`)

Introduce a small subpackage, e.g. **`ai_study_buddy.marking.file_question_info`** (name TBD), with **pure, testable** functions. Re-export only stable names from `api.py` once stabilized.

### 1. Layout and discovery (deterministic, agent-aligned)

**`<grade>` and `pdf_file_manager`:** There is **no** dedicated API in **`ai_study_buddy.pdf_file_manager`** today that returns a “folder segment for `file_question_info`.” Grade scope is persisted on the **`PdfFile`** row as **`metadata["grade_or_scope"]`** (set by path inference during scan/register/update—see **`pdf_file_manager`**, **`ARCHITECTURE.md`**). **`marking/` does not need a new helper** whose only job is wrapping that lookup: callers should use **`(pdf_file.metadata or {}).get("grade_or_scope")`**, validate non-empty when composing **`run_folder`**, and optionally apply trivial normalization inline (trim, canonical **`P6`** / **`PSLE`** casing) if mismatches appear in the wild.

If the repo later wants **one canonical normalization** shared by detectors, import scripts, and UIs—rather than inlined checks—add a **small function under `pdf_file_manager`** (e.g. **`normalize_grade_or_scope_folder_segment(value: str | None) -> str`** or **`require_grade_folder_segment(pdf_file: PdfFile) -> str`** that reads metadata and raises **`MissingGradeMetadataError`**). Prefer that location over **`marking/`** so the registry module owns semantics for stored metadata shapes.

- **`file_question_info_run_dir(*, subject_scope: str, grade: str, slug: str, context_root: Path | None = None) -> Path`**  
  Return `…/context/file_question_info/<subject_scope>/<grade>/<slug>/`. Typical call: **`grade`** from **`(pdf_file.metadata or {}).get("grade_or_scope")`** (or the future **`pdf_file_manager`** normalizer above) when resolving from the registry.

- **`expected_slug_for_pdf(pdf_path: Path | str) -> str`**  
  Wrapper: `normalize_attempt_stem(Path(pdf_path).resolve())`.

**`subject_scope`** for the run path (`singapore_primary_english`, etc.) should likewise come from registry semantics when the file is registered (e.g. map **`PdfFile.subject`** + optional **`metadata.chinese_variant`** to the detector `subject_scope` table), rather than re-parsing the subject from the path—if a mapper is duplicated, **`pdf_file_manager`** is the better home than **`marking/`** unless it is only consumed by marking.

### 2. Load, validate, and dispatch by `schema_version`

- **`load_question_sections_json(path: Path) -> dict[str, Any]`**  
  UTF-8 read + `json.load`; clear errors on malformed files.

- **Schema registry**  
  Reuse existing files under **`ai_study_buddy/schemas/`** (e.g. `chinese_paper2_questions_section.v1.3.schema.json`, `english_paper2_questions_section.v1.2.schema.json`, `higher_chinese_paper2_questions_section.v1.1.schema.json`, `math_questions_section.v1.0.schema.json`, `science_questions_section.v1.0.schema.json`): a small **`schema_version` → pathlib.Path** map suffices. Implement **`validate_question_sections_dict(payload) -> None`** raising a dedicated error type (unknown version vs JSON Schema validation failures).

  Rationale: agents already commit to enumerated `question_type` values per subject; failing fast avoids silent drift in downstream mapping.

### 3. Normalized “consumer views” for marking (subject-agnostic accessors)

Higher-level helpers that return **immutable dataclasses** or **typed dicts** for orchestration (without forcing one JSON shape):

- **`iter_sections_ordered(payload)`** → sequence of section records with at minimum:  
  `question_type`, optional `printed_section_title`, `questions_page_range`, optional `stem_page_range`, optional `answers_page_range` / `answer_page_range`, `answers_in_separate_booklet` (when present).

- **`iter_questions_ordered(payload)`** → sequence of rows with:  
  stable **`question_index`** string (e.g. `Q1`, `Q11(a)` — as emitted), optional **`question_mark`**, optional **`start_page`**, **`section_index`** (ordinal), **`question_type`** (section-level canonical label).

  Implementation detail: walk each section’s **`question_info`** in document order (Chinese, English, Higher Chinese, Math, and Science share this pattern under the latest contracts).

These iterators are what **Phase 1 QC** and **skill documentation** can refer to (“expected ID set vs mapper output”), without the orchestrator parsing raw JSON shapes.

### 4. Bridge to marking artifacts (optional seeds, never authoritative alone)

- **`build_detector_question_id_list(payload) -> tuple[str, ...]`**  
  Ordered list of `question_index` values for duplicate-ID checks comparable to SKILL Phase 1 gate.

- **`suggest_question_page_map_seed(*, detector_payload: dict, bundle_attempt_page_offset: int = 1) -> list[dict]`**  
  Map each question’s hinted `start_page` (when present) to `attempt_page_start` for `context.question_page_map`, with **`confidence="low"`** and **`source="script_inferred"`** (or a new enum value **`detector_layout`** if you extend the schema), plus a **`note`** citing `schema_version` and detector confidence.

  **Policy:** Treat as **hint only** unless a future schema explicitly certifies detector alignment with the scanned attempt PDF (template vs completion, inserted pages). The SKILL should keep Phase 1 mapper as the default producer of high-confidence anchors.

- **`section_hint_strings_for_context(detector_payload) -> tuple[str, ...]`**  
  Concatenate useful labels (`question_type`, optional `printed_section_title`) for `QuestionSelection.section_hint` or prompts.

### 5. Workflow utilities

- **`write_question_sections_bundle(...)`** (optional thin wrapper)  
  Ensure directory exists, write canonical `question_sections.json` with deterministic key order / trailing newline convention matching `learning_db` import expectations, and optionally trigger DB upsert (see below). Callers must only invoke this **after** the same registry contract as detectors (the **single** **`input_context.files[0]`** resolves in **`PdfFileManager`**—or omit this API and treat **detector agents** as the sole writers of new runs).

- **CLI or script entrypoint** (e.g. `python -m ai_study_buddy.marking.workflows.validate_question_sections <path>`) for CI and manual QA.

### 6. Explicit non-goals (for this package)

- **No** OCR or PDF rendering inside this module (detectors remain responsible for renders in `rendered_pages/`).
- **No** emitting **`question_sections.json`** “from scratch” without **registered** input PDFs and valid **`PdfFile`** resolution—parity with detector **Input policy** / **fail fast** semantics.
- **No** automatic overwrite of Phase 3 `max_marks` from detector data without human policy (Phase 2 remains authoritative per SKILL).

## Persisting `file_question_info` in `study_buddy.db`

Follow the pattern used for marking artifacts:

1. **Canonical blob:** keep `question_sections.json` as the portable source (or eventual **canonical string**_snapshot for import, same hash semantics as dual-write).

2. **SQLite projection:** normalized tables for query and FK-friendly joins to registry ids.

### Suggested tables (migration `00N_file_question_info.sql`)

**`file_question_info_runs`**

| Column | Purpose |
|--------|--------|
| `run_id` (PK, UUID/text) | Stable id per import row |
| `schema_version` | e.g. `english-v1.2`, `math-v1.0` |
| `subject_scope`, `grade`, `slug` | Mirror folder semantics; when `primary_file_id` resolves to a **`PdfFile`**, prefer **`subject` + variant metadata** and **`metadata["grade_or_scope"]`** for scope/grade rather than inferring either from filesystem paths |
| `primary_file_id` | Registry id **`input_context.files[0].file_id`** (sole source PDF); **required** for production-shaped rows — store non-null UUID and enforce **application-side** lookup in **`PdfFileManager`** at import time; empty IDs violate the registry-only production rule |
| `primary_file_path` | Resolved path string (privacy policy TBD — may mirror marking path handling) |
| `source_rel_path` | Path relative to context root (`context/file_question_info/…`) |
| `source_content_hash` | SHA-256 of canonical JSON text |
| `raw_json` | Full payload for lossless reload |
| `detector_model`, `detector_confidence`, `detector_notes` | From top-level `debug` |
| `created_at`, `updated_at`, `row_version`, `is_deleted` | Align with existing marking row conventions |

Indexes: `(primary_file_id, updated_at DESC)`, `(subject_scope, grade, slug)`.

**`file_question_info_sections`**

- `run_id`, `ordinal` (PK), `question_type`, `printed_section_title`, optional `section_total_marks`,
- JSON or scalar columns for `questions_page_range`, optional `stem_page_range`, optional answer-range fields,
- optional `answers_in_separate_booklet`,
- `raw_json` subsection slice optional.

**`file_question_info_items`**

- `run_id`, `section_ordinal`, `question_index` (PK composite),
- optional `question_mark`, `start_page`, `topic`/`notes`/`subpart` columns as nullable or `extra_json`.

### Write path

- **`learning_db`** module: implement **`upsert_file_question_info_run(conn, payload, rel_path, source_hash)`** analogous to `upsert_marking_result`, validating JSON schema first and optionally asserting **`input_context.files[0].file_id`** resolves in **`PdfFileManager`** (fail closed for production imports).

- **Dual-write hook:** after a detector (or registry-compliant tooling) writes `question_sections.json` to disk, call **`maybe_dual_write_snapshot`** (or a sibling `maybe_dual_write_question_sections`) mirroring **`learning_db/dual_write.py`** semantics so dev/prod parity matches marking.

- **`import_context_json`:** extend scanner to ingest `**/file_question_info/**/question_sections.json` in bulk imports (idempotent by `primary_file_id` + `source_content_hash` or by `run_id` derived deterministically).

### Read path for orchestrators

1. **`get_latest_question_sections_for_file_id(conn, file_id)`** → payload or row handles for the newest non-deleted run.

2. **Join to marking:** when `attempt_file_id` or `template_file_id` matches `primary_file_id` (or a linked template completion pair resolved via `PdfFileManager`), optionally attach **`detector_hints`** block into non-persisted orchestration JSON (never violate `marking_result` closed schema unless a future RFC extends it).

3. **`marking/context_resolver` integration (later):** optional parameter `prefer_file_question_info: bool` to populate `QuestionSelection`/internal hints when a DB row exists (default **off** so existing resolver behaviour is unchanged).

### Importing existing on-disk runs

- One-off **`workflows/import_file_question_info_to_db.py`**: walk `context/file_question_info/`, validate each payload against its **current** schema, compute hash, upsert rows, write operation-log events (`entity_type=file_question_info_run`).

- Optionally **verify** **`input_context.files[0].file_id`** exists in **`PdfFileManager`**; treat missing or empty ID as **quarantine** (legacy hand-edits or broken runs) under the registry-only production rule.

- Rows that fail validation (unknown `schema_version`, corrupt JSON, or drift after a future detector/schema bump): quarantine or skip via the same **`repository.upsert_quarantine`** patterns as `import_context_json`. Fix-forward: re-run the detector from **registered** PDFs at the supported `schema_version`.

### Relationship to detector agents

**Detectors are the normative writers** of new **`question_sections.json`** under the registry prerequisite. When agents persist runs, documenting **optional** “after write, run import” keeps agent specs simple; alternatively a shared Python **`persist_detector_run(path)`** (post-registration, post-detector) avoids duplicate logic.

## Phased rollout

1. **Phase A:** Add iterators + path helpers + **`schema_version` → schema path** wiring + unit tests against small **fixtures** (current-shape samples under `marking/tests/fixtures/`, optionally trimmed from real runs).

2. **Phase B:** SQLite migration + `upsert_*` + import script + optional dual-write stub (env-flagged).

3. **Phase C:** SKILL updates: optionally pass detector payload into Phase 1 prompt as **reference numbering** and run **duplicate-ID** check against **`build_detector_question_id_list`**.

4. **Phase D (optional):** `resolve_marking_context` enrichment + review UI surfaces for “paper structure preview.”

## References

- `.cursor/agents/*-question-section-detector*.md` — layout, `schema_version`, field semantics, **Registry prerequisite** / **Input policy** (registered PDFs only; fail fast).
- `ai_study_buddy/marking/core/artifact_paths.py` — `normalize_attempt_stem`.
- `ai_study_buddy/marking/README.md`, `CHANGELOG.md` — marking package contracts.
- `ai_study_buddy/learning_db/migrations/001_initial_schema.sql`, `dual_write.py`, `import_context_json.py` — DB projection patterns.
- `marking/docs/proposal/4-question-page-mapping-v1_4.md`, `8-multi-agent-marking-architecture.md` — alignment with `question_page_map` and orchestration layers.
