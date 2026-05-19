"""Path layout → filter facets (registry-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_study_buddy.pdf_file_manager.pdf_file_manager import InvalidDocTypeError, PdfFileManager

_GRADE_SCOPE_SEGMENTS = frozenset({"P1", "P2", "P3", "P4", "P5", "P6", "PSLE"})


@dataclass(frozen=True)
class PathFacets:
    root_id: str
    scope: str
    subject: str
    grade_or_scope: str
    doc_type: str
    book_group_name: str | None
    student_email: str | None
    parse_status: str


def _student_email_from_parts(parts: tuple[str, ...]) -> str | None:
    for i, segment in enumerate(parts):
        if "@" in segment and i + 1 < len(parts) and parts[i + 1] in _GRADE_SCOPE_SEGMENTS:
            return segment
    return None


def _book_group_name_from_parts(parts: tuple[str, ...]) -> str | None:
    for i, segment in enumerate(parts):
        if segment == "Book" and i + 1 < len(parts):
            return parts[i + 1]
    return None


def infer_path_facets(path: Path | str, *, root_id: str) -> PathFacets:
    """Derive filter facets from on-disk path segments (Phase A: delegates to PdfFileManager inference)."""
    resolved = Path(path).expanduser().resolve()
    parts = resolved.parts

    try:
        inferred = PdfFileManager._infer_from_path(resolved)
    except InvalidDocTypeError:
        return PathFacets(
            root_id=root_id,
            scope="unknown",
            subject="unknown",
            grade_or_scope="unknown",
            doc_type="unknown",
            book_group_name=None,
            student_email=_student_email_from_parts(parts),
            parse_status="invalid",
        )

    is_template = inferred.get("is_template")
    if is_template is True:
        scope = "template"
    elif is_template is False:
        scope = "completion"
    else:
        scope = "unknown"

    meta = inferred.get("metadata") if isinstance(inferred.get("metadata"), dict) else {}
    subject = inferred.get("subject") or "unknown"
    doc_type = inferred.get("doc_type") or "unknown"
    grade = meta.get("grade_or_scope") or "unknown"

    student_email = _student_email_from_parts(parts)
    if scope == "template":
        student_email = None

    book_group = _book_group_name_from_parts(parts) if doc_type == "book" else None

    parse_status = "ok"
    if subject == "unknown" and doc_type == "unknown" and scope == "unknown":
        parse_status = "invalid"

    return PathFacets(
        root_id=root_id,
        scope=scope,
        subject=subject,
        grade_or_scope=grade,
        doc_type=doc_type,
        book_group_name=book_group,
        student_email=student_email,
        parse_status=parse_status,
    )
