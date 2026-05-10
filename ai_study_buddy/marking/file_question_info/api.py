from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Sequence, TypedDict

from jsonschema import Draft202012Validator

from ai_study_buddy.learning_db.core.config import learning_db_read_fallback_filesystem, learning_db_reads_enabled
from ai_study_buddy.learning_db.core.connection import default_db_path, get_connection
from ai_study_buddy.marking.core.subject_scope import subject_context_from_pdf_subject
from ai_study_buddy.pdf_file_manager.pdf_file_manager import normalize_pdf_display_name
from ai_study_buddy.marking.file_question_info.errors import (
    FileQuestionInfoError,
    InvalidGradeOrScopeError,
    MissingGradeOrScopeError,
    QuestionSectionsConsumerError,
    QuestionSectionsDuplicateQuestionIdError,
    QuestionSectionsLookupError,
    QuestionSectionsNotFoundError,
    QuestionSectionsSchemaLoadError,
    QuestionSectionsValidationError,
    UnknownQuestionSectionsSchemaVersionError,
    UnsupportedPdfSubjectError,
)

_ALLOWED_GRADES = ("P1", "P2", "P3", "P4", "P5", "P6", "PSLE")
_SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
_SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"
_SCHEMA_PATHS_BY_VERSION: dict[str, Path] = {
    "chinese-v1.4": _SCHEMAS_DIR / "chinese_paper2_questions_section.v1.4.schema.json",
    "high-chinese-v1.2": _SCHEMAS_DIR / "higher_chinese_paper2_questions_section.v1.2.schema.json",
    "english-v1.3": _SCHEMAS_DIR / "english_paper2_questions_section.v1.3.schema.json",
    "math-v1.0": _SCHEMAS_DIR / "math_questions_section.v1.0.schema.json",
    "math-v1.2": _SCHEMAS_DIR / "math_questions_section.v1.2.schema.json",
    "science-v1.0": _SCHEMAS_DIR / "science_questions_section.v1.0.schema.json",
    "science-v1.2": _SCHEMAS_DIR / "science_questions_section.v1.2.schema.json",
}


class SectionRow(TypedDict):
    section_index: int
    question_type: str
    printed_section_title: str | None
    questions_page_range: dict[str, int]
    stem_page_range: dict[str, int] | None
    answers_page_range: dict[str, int] | None
    answers_in_separate_booklet: bool | None
    raw_section: Mapping[str, object]


class QuestionRow(TypedDict):
    section_index: int
    question_type: str
    question_index: str
    question_mark: float | int | None
    start_page: int | None
    question_ordinal: int
    raw_question: Mapping[str, object]


class QuestionSectionsSource(TypedDict):
    payload: dict[str, object]
    schema_version: str
    source_kind: str
    source_locator: str
    template_file_id: str
    validated_at_runtime: bool


def _default_context_root() -> Path:
    return Path(__file__).resolve().parents[2] / "context"


def _normalize_image_format(image_format: str) -> str:
    ext = image_format.strip().casefold()
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        raise ValueError("image_format must be one of: png|jpg|jpeg|webp")
    return ext


def _import_fitz():
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover - environment guard
        raise RuntimeError("PyMuPDF dependency missing: install with `pip3 install pymupdf`") from exc
    return fitz


def _resolve_page_numbers(*, page_count: int, pages_1_based: Sequence[int] | None) -> list[int]:
    if page_count <= 0:
        return []
    if pages_1_based is None:
        return list(range(1, page_count + 1))
    if len(pages_1_based) == 0:
        raise ValueError("pages_1_based must be non-empty when provided")

    resolved: list[int] = []
    for value in pages_1_based:
        if not isinstance(value, int):
            raise ValueError("pages_1_based must contain only integers")
        if value < 1 or value > page_count:
            raise ValueError(f"pages_1_based entry out of range: {value} (valid range: 1-{page_count})")
        resolved.append(value)
    return resolved


def _clean_existing_images(target_dir: Path) -> None:
    if not target_dir.is_dir():
        return
    for candidate in target_dir.iterdir():
        if candidate.is_file() and candidate.suffix.casefold() in _SUPPORTED_IMAGE_EXTENSIONS:
            candidate.unlink()


def _normalize_for_json_schema(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalize_for_json_schema(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_normalize_for_json_schema(v) for v in value]
    if isinstance(value, list):
        return [_normalize_for_json_schema(v) for v in value]
    return value


def _deep_equal(a: Any, b: Any) -> bool:
    return _normalize_for_json_schema(a) == _normalize_for_json_schema(b)


def _range_dict_or_none(value: Any, *, field_name: str) -> dict[str, int] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise QuestionSectionsConsumerError(f"{field_name} must be object when present")
    start = value.get("start_page")
    end = value.get("end_page")
    if not isinstance(start, int) or not isinstance(end, int):
        raise QuestionSectionsConsumerError(f"{field_name} must include integer start_page/end_page")
    return {"start_page": start, "end_page": end}


def _section_answers_range(section: Mapping[str, object]) -> dict[str, int] | None:
    return _range_dict_or_none(section.get("answers_page_range"), field_name="answers_page_range")


def _question_sections_list(payload: Mapping[str, object]) -> list[Mapping[str, object]]:
    sections = payload.get("sections")
    if not isinstance(sections, list):
        raise QuestionSectionsConsumerError("payload.sections must be a list")
    rows: list[Mapping[str, object]] = []
    for section in sections:
        if not isinstance(section, dict):
            raise QuestionSectionsConsumerError("each section must be an object")
        rows.append(section)
    return rows


def _schema_path_for_version(schema_version: str | None) -> Path:
    if not schema_version:
        raise UnknownQuestionSectionsSchemaVersionError(
            f"missing schema_version. Supported versions: {sorted(_SCHEMA_PATHS_BY_VERSION.keys())}"
        )
    path = _SCHEMA_PATHS_BY_VERSION.get(schema_version)
    if path is None:
        raise UnknownQuestionSectionsSchemaVersionError(
            f"unknown schema_version: {schema_version}. Supported versions: {sorted(_SCHEMA_PATHS_BY_VERSION.keys())}"
        )
    return path


def _load_schema(schema_path: Path) -> dict[str, Any]:
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise QuestionSectionsSchemaLoadError(f"failed loading schema: {schema_path}") from exc


def _subject_scope_from_pdf_file(pdf_file) -> str:
    try:
        return subject_context_from_pdf_subject(pdf_file.subject)
    except ValueError as exc:
        raise UnsupportedPdfSubjectError(f"unsupported pdf subject for file_id={pdf_file.id}: {pdf_file.subject!r}") from exc


def _grade_segment_from_pdf_file(pdf_file) -> str:
    metadata = pdf_file.metadata or {}
    value = metadata.get("grade_or_scope")
    if value is None or not str(value).strip():
        raise MissingGradeOrScopeError(
            f"missing metadata.grade_or_scope for file_id={pdf_file.id}, path={pdf_file.path}"
        )
    normalized = str(value).strip().upper()
    if normalized not in _ALLOWED_GRADES:
        raise InvalidGradeOrScopeError(
            f"invalid metadata.grade_or_scope for file_id={pdf_file.id}: {value!r}. "
            f"Allowed values: {list(_ALLOWED_GRADES)}"
        )
    return normalized


def _slug_from_pdf_file(pdf_file) -> str:
    return normalize_pdf_display_name(Path(pdf_file.path).resolve())


def _file_question_info_run_dir(
    *,
    subject_scope: str,
    grade: str,
    slug: str,
    context_root: Path | None = None,
) -> Path:
    root = (context_root or _default_context_root()).resolve()
    return root / "file_question_info" / subject_scope / grade / slug


def file_question_info_run_dir_for_pdf(pdf_file, *, context_root: Path | None = None) -> Path:
    return _file_question_info_run_dir(
        subject_scope=_subject_scope_from_pdf_file(pdf_file),
        grade=_grade_segment_from_pdf_file(pdf_file),
        slug=_slug_from_pdf_file(pdf_file),
        context_root=context_root,
    )


def render_file_question_info_pages_for_pdf(
    pdf_file,
    *,
    context_root: Path | None = None,
    dpi_scale: float = 2.0,
    image_format: str = "png",
    clean_existing: bool = True,
    pages_1_based: Sequence[int] | None = None,
) -> list[Path]:
    if dpi_scale <= 0:
        raise ValueError("dpi_scale must be > 0")

    ext = _normalize_image_format(image_format)
    source_pdf = Path(pdf_file.path).resolve()
    if not source_pdf.is_file():
        raise FileNotFoundError(f"PDF does not exist: {source_pdf}")

    run_folder = file_question_info_run_dir_for_pdf(pdf_file, context_root=context_root)
    target_dir = run_folder / "rendered_pages"
    target_dir.mkdir(parents=True, exist_ok=True)
    if clean_existing:
        _clean_existing_images(target_dir)

    fitz = _import_fitz()
    doc = fitz.open(str(source_pdf))
    try:
        page_numbers = _resolve_page_numbers(page_count=doc.page_count, pages_1_based=pages_1_based)
        matrix = fitz.Matrix(dpi_scale, dpi_scale)
        written: list[Path] = []
        for render_index, page_1_based in enumerate(page_numbers, start=1):
            page = doc[page_1_based - 1]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            out_path = target_dir / f"page_{render_index:03d}.{ext}"
            pix.save(str(out_path))
            written.append(out_path)
        return written
    finally:
        doc.close()


def load_question_sections_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise QuestionSectionsValidationError(f"question_sections payload must be an object: {path}")
    return loaded


def validate_question_sections_dict(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise QuestionSectionsValidationError("question_sections payload must be an object")

    schema_version = payload.get("schema_version")
    schema_path = _schema_path_for_version(schema_version if isinstance(schema_version, str) else None)
    schema = _load_schema(schema_path)

    normalized_payload = _normalize_for_json_schema(payload)
    errors = sorted(Draft202012Validator(schema).iter_errors(normalized_payload), key=lambda e: list(e.path))
    if errors:
        lines: list[str] = []
        for error in errors:
            path = ".".join(str(part) for part in error.absolute_path)
            lines.append(f"{path}: {error.message}" if path else error.message)
        raise QuestionSectionsValidationError(
            f"question_sections schema validation failed for schema_version={schema_version}: " + " | ".join(lines)
        ) from errors[0]

    try:
        files = payload["input_context"]["files"]
    except Exception as exc:
        raise QuestionSectionsValidationError("input_context.files must exist and contain exactly one entry") from exc
    if not isinstance(files, list) or len(files) != 1:
        raise QuestionSectionsValidationError(
            f"input_context.files must contain exactly one entry; got {len(files) if isinstance(files, list) else type(files).__name__}"
        )

    # Additional runtime invariants that aren't captured cleanly by JSON Schema.
    #
    # For sections with a separable reading stem, we expect question_info.start_page
    # values to refer to the numbered questions pages, while stem_page_range covers
    # stem-only pages. In that common layout, questions_page_range.start_page should
    # match the earliest question_info.start_page.
    sections = payload.get("sections")
    if isinstance(sections, list):
        for section_index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            if "stem_page_range" not in section:
                continue
            qpr = section.get("questions_page_range")
            qinfo = section.get("question_info")
            if not isinstance(qpr, dict) or not isinstance(qinfo, list) or not qinfo:
                continue

            starts: list[int] = []
            for item in qinfo:
                if isinstance(item, dict) and isinstance(item.get("start_page"), int):
                    starts.append(item["start_page"])
            if not starts:
                continue

            expected = min(starts)
            actual = qpr.get("start_page")
            if actual != expected:
                qtype = section.get("question_type")
                raise QuestionSectionsValidationError(
                    "questions_page_range.start_page must equal min(question_info.start_page) for sections with "
                    f"stem_page_range; got {actual!r}, expected {expected} "
                    f"(section_index={section_index}, question_type={qtype!r})"
                )


def iter_sections_ordered(payload: Mapping[str, object]) -> tuple[SectionRow, ...]:
    rows: list[SectionRow] = []
    for section_index, section in enumerate(_question_sections_list(payload)):
        question_type = section.get("question_type")
        if not isinstance(question_type, str) or not question_type.strip():
            raise QuestionSectionsConsumerError(f"section[{section_index}].question_type must be non-empty string")
        qpr = _range_dict_or_none(section.get("questions_page_range"), field_name="questions_page_range")
        if qpr is None:
            raise QuestionSectionsConsumerError(f"section[{section_index}].questions_page_range is required")
        rows.append(
            {
                "section_index": section_index,
                "question_type": question_type,
                "printed_section_title": section.get("printed_section_title")
                if isinstance(section.get("printed_section_title"), str)
                else None,
                "questions_page_range": qpr,
                "stem_page_range": _range_dict_or_none(section.get("stem_page_range"), field_name="stem_page_range"),
                "answers_page_range": _section_answers_range(section),
                "answers_in_separate_booklet": section.get("answers_in_separate_booklet")
                if isinstance(section.get("answers_in_separate_booklet"), bool)
                else None,
                "raw_section": section,
            }
        )
    return tuple(rows)


def iter_questions_ordered(payload: Mapping[str, object]) -> tuple[QuestionRow, ...]:
    rows: list[QuestionRow] = []
    for section_row in iter_sections_ordered(payload):
        raw_section = section_row["raw_section"]
        qinfo = raw_section.get("question_info")
        if qinfo is None:
            continue
        if not isinstance(qinfo, list):
            raise QuestionSectionsConsumerError(
                f"section[{section_row['section_index']}].question_info must be list when present"
            )
        for question_ordinal, q in enumerate(qinfo):
            if not isinstance(q, dict):
                raise QuestionSectionsConsumerError(
                    f"section[{section_row['section_index']}].question_info[{question_ordinal}] must be object"
                )
            qid = q.get("question_index")
            if not isinstance(qid, str) or not qid.strip():
                raise QuestionSectionsConsumerError(
                    f"section[{section_row['section_index']}].question_info[{question_ordinal}].question_index must be non-empty string"
                )
            sp = q.get("start_page")
            if sp is not None and not isinstance(sp, int):
                raise QuestionSectionsConsumerError(
                    f"section[{section_row['section_index']}].question_info[{question_ordinal}].start_page must be int when present"
                )
            rows.append(
                {
                    "section_index": section_row["section_index"],
                    "question_type": section_row["question_type"],
                    "question_index": qid,
                    "question_mark": q.get("question_mark")
                    if isinstance(q.get("question_mark"), (int, float))
                    else None,
                    "start_page": sp if isinstance(sp, int) else None,
                    "question_ordinal": question_ordinal,
                    "raw_question": q,
                }
            )
    return tuple(rows)


def build_detector_question_id_list(payload: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(row["question_index"] for row in iter_questions_ordered(payload))


def assert_unique_detector_question_ids(payload: Mapping[str, object]) -> None:
    seen: set[str] = set()
    dupes: list[str] = []
    for qid in build_detector_question_id_list(payload):
        if qid in seen and qid not in dupes:
            dupes.append(qid)
        seen.add(qid)
    if dupes:
        raise QuestionSectionsDuplicateQuestionIdError(
            "duplicate question_index values detected: " + ", ".join(sorted(dupes))
        )


def _compute_attempt_span(
    *,
    section_row: SectionRow,
    question_row: QuestionRow,
    next_question_row: QuestionRow | None,
) -> tuple[int, int]:
    start = question_row.get("start_page")
    if not isinstance(start, int):
        raise QuestionSectionsConsumerError(
            f"missing start_page for question_index={question_row['question_index']} required for question_page_map"
        )
    if next_question_row is not None and isinstance(next_question_row.get("start_page"), int):
        end = int(next_question_row["start_page"]) - 1
    else:
        end = int(section_row["questions_page_range"]["end_page"])
    if end < start:
        end = start
    return start, end


def question_page_map_from_question_sections(
    payload: Mapping[str, object],
    *,
    source: str = "script_inferred",
    confidence: str = "high",
    note: str | None = None,
) -> dict[str, dict[str, object]]:
    assert_unique_detector_question_ids(payload)
    by_section: dict[int, list[QuestionRow]] = {}
    for row in iter_questions_ordered(payload):
        by_section.setdefault(row["section_index"], []).append(row)
    section_rows = {row["section_index"]: row for row in iter_sections_ordered(payload)}
    out: dict[str, dict[str, object]] = {}
    for section_index, questions in by_section.items():
        section_row = section_rows[section_index]
        for idx, qrow in enumerate(questions):
            next_row = questions[idx + 1] if idx + 1 < len(questions) else None
            start, end = _compute_attempt_span(section_row=section_row, question_row=qrow, next_question_row=next_row)
            _ = end  # computed for deterministic internal span logic, not stored in current page-map schema
            out[qrow["question_index"]] = {
                "result_id": qrow["question_index"],
                "attempt_page_start": start,
                "confidence": confidence,
                "source": source,
                "note": note,
            }
    return out


def section_hint_strings_for_context(payload: Mapping[str, object]) -> tuple[str, ...]:
    out: list[str] = []
    for row in iter_sections_ordered(payload):
        qtype = " ".join(row["question_type"].split())
        title = " ".join(row["printed_section_title"].split()) if row["printed_section_title"] else ""
        base = f"S{row['section_index'] + 1}: {qtype}"
        out.append(f"{base}: {title}" if title else base)
    return tuple(out)


def _try_fetch_db_source(
    file_id: str,
    *,
    conn: sqlite3.Connection | None,
) -> tuple[dict[str, object], str] | None:
    close_conn = False
    active = conn
    if active is None:
        active = get_connection(default_db_path())
        close_conn = True
    try:
        row = active.execute(
            """
            SELECT run_id, raw_json
            FROM file_question_info_runs
            WHERE primary_file_id = ? AND is_deleted = 0
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (file_id,),
        ).fetchone()
        if not row:
            return None
        payload = json.loads(str(row["raw_json"]))
        if not isinstance(payload, dict):
            raise QuestionSectionsLookupError("file_question_info_runs.raw_json is not an object")
        return payload, f"run_id:{row['run_id']}"
    except sqlite3.Error as exc:
        raise QuestionSectionsLookupError(f"failed DB lookup for file_id={file_id}: {exc}") from exc
    finally:
        if close_conn and active is not None:
            active.close()


def _find_filesystem_candidates_by_file_id(*, file_id: str, context_root: Path) -> list[tuple[Path, dict[str, object]]]:
    root = context_root / "file_question_info"
    if not root.exists():
        return []
    matches: list[tuple[Path, dict[str, object]]] = []
    for path in sorted(root.rglob("question_sections.json")):
        try:
            payload = load_question_sections_json(path)
        except Exception:
            continue
        files = ((payload.get("input_context") or {}).get("files") if isinstance(payload, dict) else None)
        if not isinstance(files, list) or not files:
            continue
        file0 = files[0] if isinstance(files[0], dict) else None
        if file0 and str(file0.get("file_id") or "") == file_id:
            matches.append((path, payload))
    return matches


def _assert_no_divergence(
    *,
    db_payload: dict[str, object] | None,
    fs_payload: dict[str, object] | None,
    file_id: str,
) -> None:
    if db_payload is None or fs_payload is None:
        return
    if not _deep_equal(db_payload, fs_payload):
        raise QuestionSectionsLookupError(
            f"divergence detected for file_id={file_id}: DB payload differs from filesystem question_sections.json"
        )


def _validate_if_required(payload: dict[str, object], *, require_valid: bool) -> bool:
    if not require_valid:
        return False
    validate_question_sections_dict(payload)
    return True


def get_latest_question_sections_for_file_id(
    file_id: str,
    *,
    conn: sqlite3.Connection | None = None,
    context_root: Path | None = None,
    require_valid: bool = True,
    detect_divergence: bool = True,
) -> QuestionSectionsSource:
    if not str(file_id).strip():
        raise QuestionSectionsLookupError("file_id must be non-empty")
    use_db = learning_db_reads_enabled()
    allow_fs_fallback = learning_db_read_fallback_filesystem()
    ctx = (context_root or _default_context_root()).resolve()

    db_payload: dict[str, object] | None = None
    db_locator: str | None = None
    if use_db:
        found = _try_fetch_db_source(str(file_id), conn=conn)
        if found is not None:
            db_payload, db_locator = found

    fs_candidates: list[tuple[Path, dict[str, object]]] = []
    if (not use_db) or allow_fs_fallback or detect_divergence:
        fs_candidates = _find_filesystem_candidates_by_file_id(file_id=str(file_id), context_root=ctx)

    fs_payload: dict[str, object] | None = fs_candidates[0][1] if fs_candidates else None
    fs_locator: str | None = str(fs_candidates[0][0].resolve()) if fs_candidates else None

    if detect_divergence:
        _assert_no_divergence(db_payload=db_payload, fs_payload=fs_payload, file_id=str(file_id))

    if db_payload is not None:
        validated = _validate_if_required(db_payload, require_valid=require_valid)
        schema_version = db_payload.get("schema_version")
        if not isinstance(schema_version, str):
            raise QuestionSectionsLookupError("db payload missing schema_version string")
        return {
            "payload": db_payload,
            "schema_version": schema_version,
            "source_kind": "db",
            "source_locator": db_locator or "db",
            "template_file_id": str(file_id),
            "validated_at_runtime": validated,
        }

    if (not use_db) or allow_fs_fallback:
        if fs_payload is None or fs_locator is None:
            raise QuestionSectionsNotFoundError(f"no question_sections found for file_id={file_id}")
        validated = _validate_if_required(fs_payload, require_valid=require_valid)
        schema_version = fs_payload.get("schema_version")
        if not isinstance(schema_version, str):
            raise QuestionSectionsLookupError("filesystem payload missing schema_version string")
        return {
            "payload": fs_payload,
            "schema_version": schema_version,
            "source_kind": "filesystem",
            "source_locator": fs_locator,
            "template_file_id": str(file_id),
            "validated_at_runtime": validated,
        }

    raise QuestionSectionsNotFoundError(
        f"no DB-backed question_sections found for file_id={file_id} and filesystem fallback disabled"
    )


def get_latest_question_sections_for_pdf_file(
    pdf_file,
    *,
    conn: sqlite3.Connection | None = None,
    context_root: Path | None = None,
    require_valid: bool = True,
    detect_divergence: bool = True,
) -> QuestionSectionsSource:
    return get_latest_question_sections_for_file_id(
        str(pdf_file.id),
        conn=conn,
        context_root=context_root,
        require_valid=require_valid,
        detect_divergence=detect_divergence,
    )


def resolve_question_sections_for_template_file(
    *,
    template_file,
    detect_divergence: bool = True,
) -> QuestionSectionsSource:
    return get_latest_question_sections_for_pdf_file(
        template_file,
        require_valid=True,
        detect_divergence=detect_divergence,
    )


__all__ = [
    "SectionRow",
    "QuestionRow",
    "QuestionSectionsSource",
    "iter_sections_ordered",
    "iter_questions_ordered",
    "build_detector_question_id_list",
    "assert_unique_detector_question_ids",
    "question_page_map_from_question_sections",
    "section_hint_strings_for_context",
    "get_latest_question_sections_for_file_id",
    "get_latest_question_sections_for_pdf_file",
    "resolve_question_sections_for_template_file",
    "file_question_info_run_dir_for_pdf",
    "render_file_question_info_pages_for_pdf",
    "load_question_sections_json",
    "validate_question_sections_dict",
]
