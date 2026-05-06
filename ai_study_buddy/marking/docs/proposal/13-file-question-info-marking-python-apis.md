# Proposal 13: `file_question_info` Python helpers in `marking/`

## What this proposal is

Ship **`marking.file_question_info`** (name TBD) so that—for every **`PdfFile`** backed by **`PdfFileManager`**—the repo has **deterministic** answers to:

1. **Where** detector output lives (**`run_folder`** under **`context/file_question_info/…`**).  
2. **How** `rendered_pages/` is produced (**consistent PNG naming** for detector vision runs).  
3. **Whether** on-disk **`question_sections.json`** is structurally trustworthy: one **`schema_version`**-dispatched **`jsonschema`** gate.

It also aligns **`*-question-section-detector`** agent Markdown (**`.cursor/agents/`**) with those helpers so detector runs stop hand-rolled paths, ad hoc renders, and “successful” payloads that fail conformance.

**Related:** Proposals **14** (**SQLite mirror**) and **15** (**consumers + SKILL orchestration**) ship on their **own** cadence. Proposal **13** still supplies **`load_question_sections_json` + `validate_question_sections_dict`**—conformance APIs any ingestion path (**`learning_db`**, notebooks, SKILL, future accessors) can reuse without blocking this merge.

---

## Context

`ai_study_buddy/context/file_question_info/` holds **structured, subject-shaped** metadata for exam / WA / practice PDFs: each run is a folder

`file_question_info/<subject_scope>/<grade>/<slug>/`

containing `question_sections.json` (detector output) and `rendered_pages/` (page PNGs). Slug and layout rules are already tied to **`normalize_attempt_stem`** in `ai_study_buddy.marking.core.artifact_paths`, and detectors record **`file_id`** from `PdfFileManager` in **`input_context.files`** (see **single input PDF** below).

**Single input PDF:** Each **`question_sections.json`** describes **one** registered source PDF: **`input_context.files`** is treated as **exactly one** entry (merged booklets, OAS bundled in the same file, etc., are one file). Helpers and validation do **not** need role disambiguation across multiple files or a **`primary_pdf_path_from_input_context`**-style selector—use **`input_context.files[0]`** (after asserting length 1) or resolve **`PdfFile`** from that row’s **`file_id`**.

**Authoritative production rule:** A valid **`question_sections.json`** (and its **`rendered_pages/`** companion) is **only** produced when that PDF was **registered** in **`PdfFileManager`** first—see **Registry prerequisite** and **Input policy** in **`.cursor/agents/*-question-section-detector*.md`**. If registration cannot complete, the detector **fails fast** and emits **no** JSON. Therefore:

- The sole **`input_context.files[0].file_id`** in stored artifacts should always be a real registry UUID (and **`path`** should match **`PdfFile.path`**), not ad-hoc placeholders.
- `marking/` helpers and validators can treat **registry-backed `file_id`** as an **invariant** for runs created under the current agent contract (contrast: hand-edited or foreign JSON may violate this—**`validate_question_sections_dict`** rejects them; **`learning_db`** quarantine semantics live in Proposal **14**).

Today, tooling around `context/file_question_info/` often mixes ad hoc path logic with uneven structural checks, even though detectors already emit **`question_sections.json`**. This proposal ties **`run_folder`** and **`rendered_pages/`** to **`PdfFile`** deterministically and supplies **`load_question_sections_json`** plus **`validate_question_sections_dict`** as the **canonical** structural gate on disk.

**Separate topic:** Proposal **15** (*file question info consumers + marking orchestration*) adds iterators, a **`question_page_map`** bridge, and SKILL / **`marking-phase*`** rewires on **validated** payloads. That is complementary work, not a continuation of this document; see [15-file-question-info-consumer-layer-and-marking-orchestration.md](./15-file-question-info-consumer-layer-and-marking-orchestration.md).


### Current corpus (latest `schema_version` only)

Every existing `question_sections.json` under `file_question_info/` already uses the **current** detector contract for its subject:

| Subject line | `schema_version` |
|--------------|------------------|
| Standard Chinese Paper 2 | `chinese-v1.3` |
| Higher Chinese Paper 2 | `high-chinese-v1.1` |
| English Paper 2 | `english-v1.2` |
| Mathematics | `math-v1.0` |
| Science | `science-v1.0` |

**Implementation scope:** this proposal’s tooling in **`marking/`** need only target these five **`schema_version`** strings unless a deliberate schema bump expands the registry (**`learning_db`** import scope follows Proposal **14**). **Supported production path:** artifacts are always tied to **registered** PDFs (see authoritative production rule above). **Policy decision:** enforce **`input_context.files` length exactly 1** in **both** JSON Schema (`minItems=1`, `maxItems=1`) and **`validate_question_sections_dict`** as a defensive runtime check. Older structural JSON Schema files (`*.v1.0.schema.json`, etc.) remain in `ai_study_buddy/schemas/` as history only; **no dual-read paths or downgrade compatibility** are required for new code.

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

**Registered files (`PdfFileManager`):** Production **`question_sections.json`** always implies the detector started from **registry-backed** PDFs. In `marking/` helpers, **do not re-derive grade** from raw path parsing when **`metadata["grade_or_scope"]`** is present (see **`ARCHITECTURE.md`** / **`metadata.grade_or_scope`**). Normalize for the folder segment (e.g. `P6` / `PSLE` casing). If it is missing, treat as a **data gap** (fail closed or require an explicit override)—repair registry metadata instead. **Detector agents** require **Registry prerequisite** in each **`.cursor/agents/*-question-section-detector*.md`**; downstream **`marking`** validation (**§2**) must not be bypassed for production consumers (alongside **Proposal 14** ingestion where applicable).

These contracts are **not identical JSON shapes** across subjects; any shared Python layer must **dispatch by `schema_version`** (and thus subject), not one rigid dataclass for all payloads.

## What `marking/` already provides (relevant)

- **Paths:** `normalize_attempt_stem`, `build_marking_run_paths`, bundle paths under `marking_assets/…`.
- **Context:** `resolve_marking_context` → file ids, answer page range, `QuestionSelection` (including `section_hint`).
- **Artifacts:** `write_marking_artifact`, `context.question_page_map`, schema in `ai_study_buddy/schemas/marking/`.
- **Assets:** `render_attempt_pdf_to_bundle`, validation, manifest writers.

**Gap this proposal fills:** `marking` still lacks authoritative, **`schema_version`**-keyed **`jsonschema`** validation over on-disk **`question_sections.json`** and deterministic **`PdfFile → run_folder` / `rendered_pages/`** rasterization. Iterators, **`question_page_map`** accessors, and SKILL / agent rewires are **out of scope here**—see Proposal **15**.

## Proposed Python helpers (new surface under `marking/`)

Introduce **`ai_study_buddy.marking.file_question_info`** (package name TBD): small **pure**, **testable** APIs. **`§1`** covers **`file_question_info_run_dir_for_pdf`** and **`render_file_question_info_pages_for_pdf`**; **`§2`** covers **`load_question_sections_json`** and **`validate_question_sections_dict`**. This proposal’s rollout should **`__all__`-export** those four symbols from **`api.py`**. Extra consumer exports (Proposal **15**) should ship as separate semver/changelog steps so unrelated surfaces are not bundled. Keep **`_*`** helpers and the internal **`schema_version → schema Path`** map **private** (not in **`__all__`**).


### 1. Layout, **`rendered_pages/`**, discovery (deterministic, agent-aligned)

**Desired call sites:** given a **`PdfFile`** from **`PdfFileManager`**, (a) compute **`file_question_info/…/run_folder`**, (b) **rasterize every source PDF page** into **`run_folder/rendered_pages/`** under a **fixed filename convention**, without each detector run re-inventing PyMuPDF invocations or subfolder layouts. Detector agents remain free to orchestrate prompts and write **`question_sections.json`**, but they **should call** **`render_file_question_info_pages_for_pdf`** once the input PDF path is settled so renders match **§2 tooling** expectations and **`.cursor/agents/*-question-section-detector*.md`** layout rules.

**Public**

- **`file_question_info_run_dir_for_pdf(pdf_file: PdfFile, *, context_root: Path | None = None) -> Path`**  
  Implemented as **`_file_question_info_run_dir`** with  
  **`subject_scope=_subject_scope_from_pdf_file(pdf_file)`**,  
  **`grade=_grade_segment_from_pdf_file(pdf_file)`**,  
  **`slug=_slug_from_pdf_file(pdf_file)`**,  
  **`context_root=context_root`**. Resolve the canonical **`run_folder`** for this registry-backed PDF.  
  When **`context_root`** is `None`, resolve a default to repo **`ai_study_buddy/context`** via a project-root resolver helper (do not hardcode a string literal path in call sites).

- **`render_file_question_info_pages_for_pdf(pdf_file: PdfFile, *, context_root: Path | None = None, dpi_scale: float = 2.0, image_format: str = "png", clean_existing: bool = True, pages_1_based: Sequence[int] | None = None) -> list[Path]`** (exact kwargs TBD—mirror **`render_attempt_pdf_to_bundle`** ergonomics where sensible)  
  Deterministic **full-document** rasterization: **`pdf_path = Path(pdf_file.path).resolve()`**, **`run_folder = file_question_info_run_dir_for_pdf(pdf_file, context_root=context_root)`**, **`target = run_folder / "rendered_pages"`**, **`mkdir -p`** semantics, when **`clean_existing`**, scrub all existing images in **`rendered_pages/`** before writing fresh outputs so re-runs are idempotent.  
  **Naming:** **`page_%03d.png`** ( **`page_001.png`**, …) in dense output order **`1 … N`** (align **Chinese / English / Higher Chinese / math** agent wording; unify any ad-hoc **`page-NN`** experiments in one place). Delegate to **PyMuPDF** via **`ai_study_buddy.marking.assets.render`**—either parametrized extension of **`_render_pdf_pages_to_bundle_subdir`** (subdir + basename pattern) or a thin sibling helper so **`marking_assets`** **`attempt/page-%02d.png`** convention stays unchanged while **`file_question_info`** keeps its **`page_%03d`** contract. Detectors consume these images **only as pixels**—no structural inference belongs in this function.

**Module-private (leading underscore)**

- **`_file_question_info_run_dir(*, subject_scope: str, grade: str, slug: str, context_root: Path | None = None) -> Path`**  
  Return `…/context/file_question_info/<subject_scope>/<grade>/<slug>/`—pure path join with no **`PdfFile`**. Used by **`file_question_info_run_dir_for_pdf`** and by **same-subpackage** tests or glue that already holds **`subject_scope` / `grade` / `slug`** (e.g. asserting paths from literals or DB-unpacked columns). External callers should resolve a **`PdfFile`** and use **`file_question_info_run_dir_for_pdf`** instead of importing this.

- **`_grade_segment_from_pdf_file(pdf_file: PdfFile) -> str`**  
  The **`<grade>`** path tier: read **`(pdf_file.metadata or {}).get("grade_or_scope")`**, raise a dedicated error (e.g. **`MissingGradeOrScopeError`**) when the value is missing/blank before building a path, and normalize/validate against an allowlist of **exactly** **`P1`**, **`P2`**, **`P3`**, **`P4`**, **`P5`**, **`P6`**, **`PSLE`**. Any value outside this set raises a dedicated exception and requires human correction of registry metadata. **Not** a path parser—empty metadata ⇒ fix registry / re-scan, not inference from **`pdf_file.path`** by default.  
  **Optional later:** if **`pdf_file_manager`** adds **`normalize_grade_or_scope(...)`**, delegate normalization there while **`marking/`** keeps this hook and error type for **`file_question_info`** layout.

- **`_subject_scope_from_pdf_file(pdf_file: PdfFile) -> str`**  
  The **`<subject_scope>`** path tier: map subjects as **`math -> singapore_primary_math`**, **`science -> singapore_primary_science`**, **`english -> singapore_primary_english`**, **`chinese -> singapore_primary_chinese`**, and **`higher_chinese -> singapore_primary_chinese`** (with variant retained in payload semantics, not path scope).

- **`_slug_from_pdf_file(pdf_file: PdfFile) -> str`**  
  The **`<slug>`** path tier, detector-aligned: **`normalize_attempt_stem(Path(pdf_file.path).resolve())`** (same semantics as **`input_context.files[0].path`** after **`PdfFile`** resolution—see **`ai_study_buddy.marking.core.artifact_paths`**).

### 2. Load and validate (**canonical gate on detector-written JSON**)

**Division of labour:** Detector agents **produce** `question_sections.json`. Populate **`rendered_pages/`** via **`render_file_question_info_pages_for_pdf`** (**§1**) rather than bespoke PyMuPDF invocations.

Structural conformance is **`load_question_sections_json`** + **`validate_question_sections_dict`**; on-disk indentation/pretty-print is **explicitly unspecified**.

Persisted flow: §1 **`render`** → persist **`question_sections.json`** → **`payload = load_question_sections_json(path)`** → **`validate_question_sections_dict(payload)`**. Trusted consumers (Proposal **14**, scripts, SKILL, Proposal **15**) should reuse that sequence.



**Public**

- **`load_question_sections_json(path: Path) -> dict[str, Any]`**  
  UTF-8 read + **`json.load`**—only **syntax** (truncated files, invalid JSON). Leaves contract checks to **`validate_question_sections_dict`**.

- **`validate_question_sections_dict(payload: dict[str, Any]) -> None`**  
  **Yes: this is the canonical validator for what detector agents (or scripts) persist.** Inspect **`payload["schema_version"]`**, dispatch to the matching **`ai_study_buddy/schemas/*.schema.json`** (see **`_*`** registry below—one file each for **`chinese-v1.3`**, **`high-chinese-v1.1`**, **`english-v1.2`**, **`math-v1.0`**, **`science-v1.0`**, extended when new versions ship), run **`jsonschema`** validation (match project conventions). Raises **distinct errors** for: **`schema_version` missing/unknown**, schema file unreadable, **`ValidationError`** (with useful paths). Optionally apply **extras** (`input_context.files` length **exactly 1**) here if schemas don’t nail it yet.  
  **`learning_db`** importers (Proposal **14**) and other trusted pipelines should **not** treat payloads as production-truth until **`validate_question_sections_dict`** succeeds (or quarantine per Proposal **14**).

### Error contract recommendations

Define a small public hierarchy in **`marking.file_question_info.errors`**:

- **`FileQuestionInfoError`** (base)
- **`MissingGradeOrScopeError`**
- **`UnknownQuestionSectionsSchemaVersionError`**
- **`QuestionSectionsSchemaLoadError`**
- **`QuestionSectionsValidationError`**

Contract guidance:

- Keep **exception types** stable for caller `except` handling.
- Keep message **content fields** stable (exact phrasing may vary):
  - unknown schema version → include bad version + allowed versions
  - schema load failure → include schema file path
  - validation failure → include `schema_version` + instance path + validator message
  - missing grade/scope → include `file_id` + `pdf_file.path`
  - invalid grade/scope value → include `file_id` + provided value + allowed values
- Preserve underlying causes with `raise ... from exc`.

**Module-private**

- **`schema_version` → schema `Path` map** (implementation detail)—enumerates **`ai_study_buddy/schemas/`** structural schemas (e.g. `chinese_paper2_questions_section.v1.3.schema.json`, `english_paper2_questions_section.v1.2.schema.json`, `higher_chinese_paper2_questions_section.v1.1.schema.json`, `math_questions_section.v1.0.schema.json`, `science_questions_section.v1.0.schema.json`). **`validate_question_sections_dict`** consumes this internally; callers need not import it.

### Explicit non-goals (**`file_question_info`** foundation scope)

- **No** mandated **`marking`**-owned **`question_sections.json` writer:** detector agents persist files; **`validate_question_sections_dict`** is where **`marking`** standardizes conformance (serialization prettiness/key order is intentionally **not** required by this submodule).
- **No** **layout inference, OCR, or question detection** inside **`file_question_info`**—only **deterministic** PDF→raster for **`rendered_pages/`** (§1) and structural checks on **already-emitted** JSON (§2). Vision models and heuristics stay in detector agents.
- **No** emitting **`question_sections.json`** “from scratch” **inside this submodule**—orchestration that fabricates payloads without detectors still belongs outside **`file_question_info`**, parity with detector **Input policy** / registry contract.
- **No** automatic overwrite of Phase 3 `max_marks` from detector data without human policy (Phase 2 remains authoritative per SKILL).

## Deferred: `study_buddy.db` persistence

Migrations (**`file_question_info_runs`** / **`_sections`** / **`_items`**), **`learning_db`** upserts, **`import_context_json`**, dual-write hooks, **`get_latest_question_sections_for_file_id`**, resolver **`prefer_file_question_info`**—all live in **`14-persist-file-question-info-in-study-buddy-db.md`**.

### Relationship to detector agents

**Detectors are the normative writers** of **`question_sections.json`** and **`rendered_pages/`** under the registry prerequisite (**LLM tooling stays agent-side**). They **should** call **`render_file_question_info_pages_for_pdf`** (**§1**) so **`rendered_pages/`** naming stays uniform. **`validate_question_sections_dict`** (**§2**) gates downstream consumers **including** Proposal **15** accessors (**`iter_sections_ordered`** / **`iter_questions_ordered`**, **`question_page_map_from_question_sections`**, …). Mirrors into **`study_buddy.db`** are Proposal **14**: importers **`load`** from disk and run **`validate_question_sections_dict`** before **`upsert`**.

## Implementation plan

Implementation status snapshot (2026-05-05):

- Phase A: implemented
- Phase B: implemented
- Phase C: implemented
- Phase D: pending (agent spec updates)
- Phase E: pending (package docs/changelog/versioning)

The milestones below (**Phases A–E**) are **this proposal’s own** rollout; the letters are **not** meant to splice into another doc’s numbering (Proposal **15** uses **E–H** only inside [that doc](./15-file-question-info-consumer-layer-and-marking-orchestration.md)). Work lands in **`ai_study_buddy.marking.file_question_info`** (name TBD) with **`api.py`** re-exports. Scope: **`run_folder`**, **`rendered_pages/`**, **`load`**, **`validate`**, detector agent prose (**Phase D**), and **`marking/`** package documentation + semver (**Phase E**). **Iterators**, **`question_page_map`** bridge, SKILL + **`marking-phase*.md`** upgrades, cross-consumer **`README`/`python -c`** lockstep beyond this package are **not** bundled here—see Proposal **15**.

### Phase A — Scaffold + run-folder resolution (**§1** paths)

**Objective:** From a registry **`PdfFile`**, resolve **`run_folder`** to **`context/file_question_info/<subject_scope>/<grade>/<slug>/`** per **§1** (metadata-derived tiers **`+`** **`normalize_attempt_stem`** on **`PdfFile.path`**).

**Implementation checklist**

- [x] Add package layout (e.g. **`marking/file_question_info/`** with **`__init__.py`**, **`api.py`**).
- [x] Implement **`_subject_scope_from_pdf_file`**, **`_grade_segment_from_pdf_file`** (with **`MissingGradeOrScopeError`** or equivalent), **`_slug_from_pdf_file`**.
- [x] Implement **`_file_question_info_run_dir`** (path join only) + **`file_question_info_run_dir_for_pdf`** (**`context_root`** default resolves repo **`ai_study_buddy/context`** via resolver helper, or explicit **`Path`** override).
- [x] Re-export **`file_question_info_run_dir_for_pdf`** from **`marking`** **`api`** / package **`__init__`** per existing **`marking`** export conventions.

**Testing checklist**

- [x] **`pytest`**: **`_slug_from_pdf_file`** matches **`normalize_attempt_stem`** on **`PdfFile.path`** for stems with **`_raw_`**, **`_c_`**, **`raw_`**, **`c_`** prefixes (same cases as **`marking.tests.test_artifact_core`** for **`normalize_attempt_stem`**).
- [x] **`pytest`**: **`_grade_segment_from_pdf_file`** raises documented error when **`metadata["grade_or_scope"]`** missing/blank; happy path returns normalized segment (e.g. **`P6`**, **`PSLE`** casing).
- [x] **`pytest`**: **`_subject_scope_from_pdf_file`** — small matrix mapping **`PdfFile.subject`** (+ optional **`metadata.chinese_variant`**) to expected layout string (at least **English**, **Standard Chinese**, **Higher Chinese** if table has three rows).
- [x] **`pytest`**: **`file_question_info_run_dir_for_pdf`** end-to-end with **`tmp_path`** / mocked **`PdfFile`** — final **`Path`** equals **`context_root / "file_question_info" / subject_scope / grade / slug`** with no duplicate separators; **`_file_question_info_run_dir`** covered by the same test or a dedicated join test.
- [x] Optional contract test deemed unnecessary: on-disk `context/file_question_info/...` samples embed machine-specific absolute paths and depend on local `PdfFileManager` registry state, making a CI contract test brittle. The deterministic join logic is already covered by `file_question_info_run_dir_for_pdf` unit tests.

**Success criteria**

- **All Phase A tests green in CI** for **`marking`** (or dedicated **`file_question_info`** test module).
- For a **`PdfFile`** fixture (or mocked row) with known **`subject`**, **`metadata.grade_or_scope`**, and path stem, **`file_question_info_run_dir_for_pdf`** equals the expected **`Path`** segments (no accidental double slashes / case drift beyond documented normalization).
- Tests fail fast when **`grade_or_scope`** missing and policy says path is required (**§1**).
- **`_file_question_info_run_dir`** stays **non-exported** (assert via **`importlib`** / no entry in **`__all__`** test if useful).

---

### Phase B — **`rendered_pages/`** rasterization (**§1** renders)

**Objective:** Deterministic **full-PDF → PNG** into **`{run_folder}/rendered_pages/page_%03d.png`** (e.g. **`page_001.png`**).

**Implementation checklist**

- [x] Extend or wrap **`marking.assets.render`** so **`file_question_info`** can request **`subdir="rendered_pages"`** + basename pattern **`page_{i:03d}.png`** without breaking **`render_attempt_pdf_to_bundle`** (**`attempt/page-%02d.png`** contract untouched).
- [x] Implement **`render_file_question_info_pages_for_pdf`** (kwargs aligned with Proposal **§1**, including **`dpi_scale`**, **`clean_existing`**, optional **`pages_1_based`**).
- [x] Document PyMuPDF install expectation (same **`RuntimeError`** pattern as **`render.py`**).

**Testing checklist**

- [x] **`pytest`**: **`render_attempt_pdf_to_bundle`** (existing) still passes unchanged — regression guard whenever **`render.py`** internals move.
- [x] **`pytest`**: **`render_file_question_info_pages_for_pdf`** on a minimal **fixtures** PDF (small page count)—written files **`==`** **`doc.page_count`**, basenames **`page_001.png` … `page_0NN.png`**, deterministic sizes / non‑empty payloads.
- [x] **`pytest`**: **`clean_existing=True`** deletes all prior images in **`rendered_pages/`** before rewrite; **`clean_existing=False`** leaves existing files untouched (optional negative case).
- [x] **`pytest`**: **`pages_1_based`** subset — rendered count equals requested list length and outputs remain dense as **`page_001`**, **`page_002`**, … in the requested order.
- [x] PyMuPDF-missing test intentionally omitted: the environment pins PyMuPDF for detector workflows and the render path is already exercised via a fake `fitz` module in unit tests.

**Success criteria**

- **All Phase B tests green in CI**, including **`test_marking_asset_render`** regressions upstream.
- Golden test: **`page_count`** raster outputs; **`clean_existing`** removes stale **`page_*.png`** then rewrites.
- No structural / OCR logic in module—imports stay limited to **`fitz`** path + **`Path`** (**Explicit non-goals** above).

---

### Phase C — **`load_question_sections_json`** + **`validate_question_sections_dict`** (**§2**)

**Objective:** one **canonical JSON Schema gate** for all five **`schema_version`** strings in the corpus table.

**Implementation checklist**

- [x] **`load_question_sections_json`**: UTF‑8 **`json.load`**, clear **`JSONDecodeError`** wrapping.
- [x] Internal map **`schema_version` → Path** for **`ai_study_buddy/schemas/`** artifacts (five current versions; raise **`UnknownQuestionSectionsSchemaVersionError`** on unknown/missing version). Load schema files fresh per validation call (no process-level cache for now).
- [x] **`validate_question_sections_dict`**: **`jsonschema`** validate instance; raise **`QuestionSectionsValidationError`** (with instance path + message) and chain underlying validator exceptions.
- [x] Optional assertion: **`input_context.files`** length **`==`** **1** (if not enforced by schemas yet)—document bypass for tests via fixture toggles only if unavoidable.
- [x] Export **`load_question_sections_json`** and **`validate_question_sections_dict`** from **`api.py`**.

**Testing checklist**

- [x] **`pytest`**: **`load_question_sections_json`** on invalid UTF‑8 / truncated file — fails with predictable exception type (**`UnicodeDecodeError`** / **`JSONDecodeError`**).
- [x] **`pytest`**: **`validate_question_sections_dict`** — payload with missing / unknown **`schema_version`** raises **`UnknownQuestionSectionsSchemaVersionError`**; message lists allowed versions.
- [x] **`pytest`**: **`validate_question_sections_dict`** — parametrize **five** **`schema_version`** strings × **minimal valid-ish** inlined dicts (**or trimmed copies** checked into **`marking/tests/fixtures/file_question_info/<schema_version>/minimal.json`**); each **pass** validate after optional **`load`**.
- [x] **`pytest`**: **`validate_question_sections_dict`** — structured invalid payloads (bad **`question_type`**, **`sections=[]`**, malformed **`questions_page_range`**) assert failure surfaces as **`QuestionSectionsValidationError`** with a usable instance path / message for debugging and preserved `__cause__`.
- [x] **`pytest`**: **`input_context.files` length≠1** assertion (when implemented)—raises dedicated error vs schema noise.
- [x] **`pytest`**: **`load + validate`** on each real `context/file_question_info/.../question_sections.json` corpus file (small corpus; enforced in default test suite).

**Success criteria**

- **All Phase C tests green in CI**.
- Intentionally bad payloads (wrong **`question_type`**, missing **`sections`**) fail **`validate_question_sections_dict`** with actionable errors—no silent pass into iterators.
- All five **`schema_version`** enums have **exactly one** schema path wired (asserted by a parametrized test that **`SCHEMA_REGISTRY.keys()`** equals the corpus table—or explicit denylist test for drift).

---

### Phase D — Upgrade detector agents (`.cursor/agents/` specs)

**Objective:** Align all **`*-question-section-detector`** agent Markdown with **`marking.file_question_info`** so production runs stop ad hoc renders, path drift, and inconsistent “done” semantics—**mandatory **`load_question_sections_json`** + **`validate_question_sections_dict`** terminal gate first.**

**Depends on**

- **`validate`** path: **Phase C** must be merged (and the validator CLI/module entrypoint import path stabilized).
- **Run folder + renders:** Prefer **Phases A + B merged** **before** or **in the same release** as this phase so agents cite **`file_question_info_run_dir_for_pdf`** / **`render_file_question_info_pages_for_pdf`** verbatim. If rollout is split, Phase **D** wording can mandate **validation-only** until **A+B** land, plus an explicit **`TODO`/deprecation banner** for hand-rolled **`rendered_pages`** instructions pending **B**.

**Implementation checklist**

- [x] Update **Standard Chinese Paper 2** detector spec (**`.cursor/agents/chinese-paper-2-question-section-detector.md`**) to use the canonical helpers + mandatory validation gate (and bump spec version). Also aligned `questions_page_range` semantics for stem-bearing sections with English/Higher Chinese (stem pages live in `stem_page_range`; `questions_page_range` begins on the first numbered-question page).
- [x] Science detector spec (**`.cursor/agents/science-question-section-detector.md`**) already uses the canonical helpers + mandatory validation gate; smoke-tested successfully post-implementation (see Validation notes below).
- [x] English Paper 2 detector spec (**`.cursor/agents/english-paper-2-question-section-detector.md`**) already uses the canonical helpers + mandatory validation gate.
- [x] Higher Chinese Paper 2 detector spec (**`.cursor/agents/higher-chinese-paper-2-question-section-detector.md`**) already uses the canonical helpers + mandatory validation gate.
- [x] Math detector spec (**`.cursor/agents/math-question-section-detector.md`**) already uses the canonical helpers + mandatory validation gate.
- [x] Bump agent **`version:`** when Phase D changes are material. (In practice: Standard Chinese spec was changed and bumped `v1.4 -> v1.5`; other specs were already compliant so no bump was required.)
- [x] **[Mandatory]** Terminal step in each updated agent: run the canonical validator command entrypoint (preferred: **`python -m ai_study_buddy.marking.file_question_info.validate <path/question_sections.json>`**; use **`python3 -m ...`** in environments without a `python` shim) and require zero-exception success; if load or validate fails, the detector run must fail.
- [x] **[When A+B landed]** Agent specs declare `run_folder` per `file_question_info_run_dir_for_pdf(...)` (no ad hoc path reconstruction).
- [x] **[When B landed]** Agent specs declare `render_file_question_info_pages_for_pdf(...)` before analysis so `rendered_pages/page_%03d.png` naming is authoritative.
- [x] Remove contradictory instructions (loose PNGs, nonstandard basenames, bespoke PyMuPDF) from question-section-detector specs.

**QA / rollout checklist**

- [x] **`rg`/review diff:** no question-section-detector spec uses “optional/recommended validate” wording; validation is blocking.
- [x] Paste-trap check — helper names and validator command are consistent across all `*question-section-detector*.md` specs.
- [x] Smoke: invoked **Science** + **Standard Chinese Paper 2** detectors on registered PDFs and confirmed emitted `question_sections.json` passes `validate_question_sections_dict` via the module CLI entrypoint.

**Validation notes (observed in practice)**

- Science + Standard Chinese Paper 2 detector runs completed successfully and produced structurally valid outputs (some small wrinkles noted during runs, but no major issues). This serves as an end-to-end confirmation that Phase D wiring (helpers + validator gate) is workable in real detector usage.

**Success criteria**

- **All five** **`question-section-detector`** specs reference the **exact same** validator command entrypoint (preferred **`python -m ai_study_buddy.marking.file_question_info.validate ...`**) and that command is echoed in **`marking`** package **`README`** in **Phase E**.
- **`validate`** step is **blocking** wording (run must not advertise success otherwise).
- **When A+B are on `main`** for this repo revision: helpers for **`run_dir`** **`+`** **`render`** are **required**, not supplementary, in detector docs—or an explicit phased exception note with removal date (**no indefinite dual instructions**).
- **Zero** regressions vs **Registry prerequisite**: agents still **`fail fast`** when **`PdfFile`** missing for **`input_context.files[0]`**—Python helpers augment, not replace registry policy.

---

### Phase E — **`marking/`** documentation + package version bump

**Objective:** Ship **user-facing docs** for the new **`marking.file_question_info`** surface and record a **semver** bump for **`ai_study_buddy.marking`** consistent with **`ai_study_buddy/marking/CHANGELOG.md`** ( **`README.md`** **Current version** must stay in sync; **`CHANGELOG.md`** header spells **patch** vs **minor** rules).

**Timing:** Prefer **after** Phases **A–C** (helpers available); **overlap or follow** Phase **D** as convenient (agent footers stable enough to reference the canonical validator CLI command).

**Implementation checklist**

- [x] **`CHANGELOG.md`**: entry summarizing **`file_question_info`** public helpers (**§1**/§**2**) and validation invariants; bump **Current version** in `README.md`.
- [x] **`README.md`**: **Current version** bump; dedicated subsection for **`question_sections.json`** layout and the canonical validator CLI command.
- [x] **`SPEC.md`** / **`TESTING.md`** (and **`ARCHITECTURE.md`** if needed): minimal alignment so newcomers do not contradict Proposal **§1**/§**2**.
- [x] Bump level: **`minor`** semver for the `file_question_info` public API rollout.

**Success criteria**

- **Current version** in **`README.md`** matches **`CHANGELOG.md`** headline.
- A maintainer following **`README`** alone can run the canonical validator CLI command and find **`rendered_pages/`** naming without reading agent Markdown.

---

### Outbound — **`study_buddy.db`** mirror (**Proposal 14**)

**Todo checklist** — execute per **`marking/docs/proposal/14-persist-file-question-info-in-study-buddy-db.md`** (migration, **`upsert`**, **`import_context_json`** / dual-write, **`get_latest_question_sections_*`**).

**Success criteria**

- Rows ingested **only after** **`validate_question_sections_dict`** succeeds; importer tests fail when payload invalid.


## Open Questions

Resolved decisions:

1. `input_context.files` cardinality is enforced in both schema and Python validator.
2. Subject scope mapping is fixed as `math/chinese/science/english -> singapore_primary_<subject>` and `higher_chinese -> singapore_primary_chinese`.
3. `clean_existing=True` deletes all images under `rendered_pages/`.
4. Subset renders still use dense output naming (`page_001`, `page_002`, ...), not source page-number naming.
5. Schema files are loaded fresh on each validation call (no cache for now).
6. If `load` or `validate` fails, detector run fails.
7. Canonical validation command is a dedicated module entrypoint (preferred: `python -m ai_study_buddy.marking.file_question_info.validate <path>`), not duplicated `python -c` snippets.
8. `_grade_segment_from_pdf_file` must allow only `P1`, `P2`, `P3`, `P4`, `P5`, `P6`, `PSLE`; anything else raises and requires human attention.
9. Invalid grade values use a dedicated exception type (for example `InvalidGradeOrScopeError`) distinct from missing/blank grade errors.
10. **Stem vs questions range invariant:** For any section that includes `stem_page_range`, `questions_page_range.start_page` must equal `min(question_info[*].start_page)` (i.e. `questions_page_range` begins on the first page that contains the numbered questions, not the stem-only pages). **Implemented** in `validate_question_sections_dict` (`ai_study_buddy/marking/file_question_info/api.py`).

No remaining open questions.

## References

- `.cursor/agents/*-question-section-detector*.md` — layout, `schema_version`, field semantics, **Registry prerequisite** / **Input policy** (registered PDFs only; fail fast).
- `ai_study_buddy/marking/core/artifact_paths.py` — `normalize_attempt_stem`.
- `ai_study_buddy/marking/assets/render.py` — PyMuPDF bundle renders (**`render_attempt_pdf_to_bundle`**); §1 **`render_file_question_info_pages_for_pdf`** should share internals with a **`rendered_pages/`** + **`page_%03d`** profile.
- `ai_study_buddy/marking/README.md`, `CHANGELOG.md` — marking package contracts.
- **`marking/docs/proposal/14-persist-file-question-info-in-study-buddy-db.md`** — SQLite / **`learning_db`** mirror (**`dual_write.py`**, **`import_context_json`**, migrations).
- `marking/docs/proposal/4-question-page-mapping-v1_4.md`, **`8-multi-agent-marking-architecture.md`** — **`question_page_map`** contract and orchestration layering (marking SKILL/**`marking-phase*.md`** upgrades: Proposal **15**).
- **`marking/docs/proposal/15-file-question-info-consumer-layer-and-marking-orchestration.md`** — §**3**/§**4** accessors, **`question_page_map`** bridge, **`mark-student-work-multi-agent-v2`** SKILL, **`marking-phase*.md`**, cross-doc **`README`** / **`python -c`** stabilization (standalone rollout plan in that file).
