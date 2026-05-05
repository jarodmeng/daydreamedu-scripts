from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from jsonschema import Draft202012Validator

from ai_study_buddy.marking.core.artifact_paths import normalize_attempt_stem
from ai_study_buddy.marking.file_question_info.errors import (
    FileQuestionInfoError,
    InvalidGradeOrScopeError,
    MissingGradeOrScopeError,
    QuestionSectionsSchemaLoadError,
    QuestionSectionsValidationError,
    UnknownQuestionSectionsSchemaVersionError,
    UnsupportedPdfSubjectError,
)

_ALLOWED_GRADES = ("P1", "P2", "P3", "P4", "P5", "P6", "PSLE")
_SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
_SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"
_SCHEMA_PATHS_BY_VERSION: dict[str, Path] = {
    "chinese-v1.3": _SCHEMAS_DIR / "chinese_paper2_questions_section.v1.3.schema.json",
    "high-chinese-v1.1": _SCHEMAS_DIR / "higher_chinese_paper2_questions_section.v1.1.schema.json",
    "english-v1.2": _SCHEMAS_DIR / "english_paper2_questions_section.v1.2.schema.json",
    "math-v1.0": _SCHEMAS_DIR / "math_questions_section.v1.0.schema.json",
    "math-v1.1": _SCHEMAS_DIR / "math_questions_section.v1.1.schema.json",
    "science-v1.0": _SCHEMAS_DIR / "science_questions_section.v1.0.schema.json",
    "science-v1.1": _SCHEMAS_DIR / "science_questions_section.v1.1.schema.json",
}


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
    subject = (pdf_file.subject or "").strip().casefold()
    if subject == "english":
        return "singapore_primary_english"
    if subject == "math":
        return "singapore_primary_math"
    if subject == "science":
        return "singapore_primary_science"
    if subject == "chinese":
        return "singapore_primary_chinese"
    raise UnsupportedPdfSubjectError(f"unsupported pdf subject for file_id={pdf_file.id}: {pdf_file.subject!r}")


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
    return normalize_attempt_stem(Path(pdf_file.path).resolve())


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


__all__ = [
    "file_question_info_run_dir_for_pdf",
    "render_file_question_info_pages_for_pdf",
    "load_question_sections_json",
    "validate_question_sections_dict",
]
