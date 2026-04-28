from pathlib import Path

from ai_study_buddy.marking.core.artifact_paths import derive_unit_label_from_attempt_name
from ai_study_buddy.marking.core.models import MarkingContext, QuestionSelection
from ai_study_buddy.pdf_file_manager.pdf_file_manager import (
    AlreadyRegisteredError,
    BookAnswerMapping,
    FileGroup,
    NotFoundError,
    PdfFile,
    PdfFileManager,
    Student,
)


class MarkingContextResolutionError(ValueError):
    """Raised when a user request cannot be resolved to one marking context."""


def _attempt_path_has_allowed_completion_root(path: Path) -> bool:
    """Student attempts may live under mirrored GoodNotes or under DaydreamEdu (e.g. student Book folder)."""
    parts = path.parts
    return "GoodNotes" in parts or "DaydreamEdu" in parts


def resolve_marking_context(
    *,
    student_name: str | None = None,
    student_id: str | None = None,
    attempt_file_id_or_path: str | Path | None = None,
    book_label: str | None = None,
    unit_query: str | None = None,
    question_request: str | None = None,
    question_refs: list[str] | tuple[str, ...] | None = None,
    section_hint: str | None = None,
    self_answer_pages: tuple[int, int] | None = None,
    manual_answer_pages: tuple[int, int] | None = None,
    marking_mode: str | None = None,
    auto_register_attempt: bool = False,
    auto_link_template: bool = False,
    manager: PdfFileManager | None = None,
) -> MarkingContext:
    """
    Resolve a user-facing marking request into the exact registered files and
    answer-page range needed by the marking pipeline.

    This function is intentionally deterministic: it orchestrates lookups
    against PdfFileManager but does not perform OCR, rendering, or grading.
    """
    question_selection = _build_question_selection(
        question_request=question_request,
        question_refs=question_refs,
        section_hint=section_hint,
    )
    mgr = manager or PdfFileManager()

    student = _resolve_student(mgr, student_id=student_id, student_name=student_name)
    attempt_file = _resolve_attempt_file(
        mgr,
        attempt_file_id_or_path=attempt_file_id_or_path,
        student=student,
        book_label=book_label,
        unit_query=unit_query,
        auto_register_attempt=auto_register_attempt,
    )
    template_file = _resolve_template_file(mgr, attempt_file, auto_link_template=auto_link_template)
    if self_answer_pages is not None and manual_answer_pages is not None:
        raise MarkingContextResolutionError(
            "Provide only one of self_answer_pages or manual_answer_pages, not both."
        )
    override_pages = manual_answer_pages if manual_answer_pages is not None else self_answer_pages
    self_answer_range = _normalize_self_answer_pages(override_pages)
    resolved_mode = _resolve_marking_mode(marking_mode=marking_mode, self_answer_pages=override_pages)

    if resolved_mode == "embedded_answer_override":
        assert self_answer_range is not None
        book_group = _resolve_book_group_if_present(mgr, template_file)
        answer_file_id = template_file.id
        answer_file_path = template_file.path
        answer_page_start, answer_page_end = self_answer_range
        starts_mid_page = False
        ends_mid_page = False
        source_label = "manual_answer_pages" if manual_answer_pages is not None else "self_answer_pages"
        answer_mapping_source = (
            f"{source_label} override: answers embedded in template/completion paper "
            f"(pages {answer_page_start}-{answer_page_end})"
        )
        answer_mapping_notes = None
    elif resolved_mode == "teacher_annotated":
        book_group = _resolve_book_group_if_present(mgr, template_file)
        answer_file_id = None
        answer_file_path = None
        answer_page_start = None
        answer_page_end = None
        starts_mid_page = False
        ends_mid_page = False
        answer_mapping_source = "teacher_annotated_completion"
        answer_mapping_notes = "No answer key mapping; grading grounded in teacher annotations on completion."
    else:
        book_group = _resolve_book_group(mgr, template_file)
        answer_mapping = _resolve_answer_mapping(mgr, template_file)
        answer_file_id = answer_mapping.answer_file_id
        answer_file_path = answer_mapping.answer_file.path
        answer_page_start = answer_mapping.answer_page_start
        answer_page_end = answer_mapping.answer_page_end
        starts_mid_page = answer_mapping.starts_mid_page
        ends_mid_page = answer_mapping.ends_mid_page
        answer_mapping_source = answer_mapping.source
        answer_mapping_notes = answer_mapping.notes

    return MarkingContext(
        student_id=student.id if student else attempt_file.student_id,
        student_name=student.name if student else None,
        attempt_file_id=attempt_file.id,
        attempt_file_path=attempt_file.path,
        template_file_id=template_file.id,
        template_file_path=template_file.path,
        book_group_id=book_group.id if book_group else None,
        book_label=book_group.label if book_group else None,
        unit_file_id=template_file.id,
        unit_file_path=template_file.path,
        unit_label=_infer_unit_label(template_file),
        answer_file_id=answer_file_id,
        answer_file_path=answer_file_path,
        answer_page_start=answer_page_start,
        answer_page_end=answer_page_end,
        starts_mid_page=starts_mid_page,
        ends_mid_page=ends_mid_page,
        answer_mapping_source=answer_mapping_source,
        answer_mapping_notes=answer_mapping_notes,
        question_selection=question_selection,
        marking_mode=resolved_mode,
    )


def _build_question_selection(
    *,
    question_request: str | None,
    question_refs: list[str] | tuple[str, ...] | None,
    section_hint: str | None,
) -> QuestionSelection:
    normalized_refs: list[str] = []
    if question_refs:
        for ref in question_refs:
            cleaned = ref.strip()
            if not cleaned:
                continue
            normalized_refs.append(cleaned)
    if len(set(normalized_refs)) != len(normalized_refs):
        raise MarkingContextResolutionError("question_refs must not contain duplicates")
    if question_request is not None and not question_request.strip():
        raise MarkingContextResolutionError("question_request must not be blank when provided")
    if section_hint is not None and not section_hint.strip():
        raise MarkingContextResolutionError("section_hint must not be blank when provided")
    return QuestionSelection(
        raw_text=question_request.strip() if question_request else None,
        canonical_refs=tuple(normalized_refs),
        section_hint=section_hint.strip() if section_hint else None,
    )


def _resolve_student(
    mgr: PdfFileManager,
    *,
    student_id: str | None,
    student_name: str | None,
) -> Student | None:
    if student_id is None and student_name is None:
        return None

    if student_id is not None:
        student = mgr.get_student(student_id)
        if student is None:
            raise NotFoundError(f"Student not found: {student_id}")
        if student_name is not None and student.name.casefold() != student_name.casefold():
            raise MarkingContextResolutionError(
                f"student_id={student_id!r} resolved to {student.name!r}, which does not match student_name={student_name!r}"
            )
        return student

    assert student_name is not None
    matches = [student for student in mgr.list_students() if student.name.casefold() == student_name.casefold()]
    if not matches:
        raise NotFoundError(f"Student not found by name: {student_name}")
    if len(matches) > 1:
        ids = ", ".join(sorted(student.id for student in matches))
        raise MarkingContextResolutionError(f"Multiple students matched name {student_name!r}: {ids}")
    return matches[0]


def _resolve_attempt_file(
    mgr: PdfFileManager,
    *,
    attempt_file_id_or_path: str | Path | None,
    student: Student | None,
    book_label: str | None,
    unit_query: str | None,
    auto_register_attempt: bool,
) -> PdfFile:
    if attempt_file_id_or_path is not None:
        return _resolve_attempt_file_by_id_or_path(
            mgr,
            attempt_file_id_or_path,
            student=student,
            auto_register_attempt=auto_register_attempt,
        )

    if unit_query is None:
        raise MarkingContextResolutionError(
            "Provide attempt_file_id_or_path, or provide enough lookup inputs such as student + unit_query"
        )

    candidates = mgr.find_files(
        query=unit_query,
        file_type="main",
        student_id=student.id if student else None,
        is_template=False,
    )
    candidates = [
        file for file in candidates if _attempt_path_has_allowed_completion_root(Path(file.path))
    ]
    if book_label is not None:
        candidates = [file for file in candidates if _path_mentions_book_label(file.path, book_label)]

    return _select_one_file(
        candidates,
        not_found_message=(
            f"No GoodNotes/DaydreamEdu attempt file matched unit_query={unit_query!r}"
            + (f" for student_id={student.id!r}" if student else "")
            + (f" in book {book_label!r}" if book_label else "")
        ),
        ambiguous_message=(
            "Multiple GoodNotes/DaydreamEdu attempt files matched the provided marking request"
        ),
    )


def _resolve_attempt_file_by_id_or_path(
    mgr: PdfFileManager,
    attempt_file_id_or_path: str | Path,
    *,
    student: Student | None,
    auto_register_attempt: bool,
) -> PdfFile:
    candidate = str(attempt_file_id_or_path)
    file = None
    is_path_like = "/" in candidate or "\\" in candidate or candidate.lower().endswith(".pdf")
    if is_path_like:
        file = mgr.get_file_by_path(candidate)
        if file is None and auto_register_attempt:
            normalized_path = Path(candidate).expanduser().resolve()
            if not _attempt_path_has_allowed_completion_root(normalized_path):
                raise MarkingContextResolutionError(
                    "auto_register_attempt requires attempt_file_id_or_path to be under a GoodNotes "
                    "or DaydreamEdu path"
                )
            if not normalized_path.exists():
                raise NotFoundError(f"Attempt file not found: {attempt_file_id_or_path}")
            try:
                mgr.register_file(normalized_path, file_type="main", is_template=False)
            except AlreadyRegisteredError:
                # A concurrent registration can still produce this result.
                pass
            except FileNotFoundError as exc:
                raise NotFoundError(f"Attempt file not found: {attempt_file_id_or_path}") from exc
            file = mgr.get_file_by_path(normalized_path)
    else:
        file = mgr.get_file(candidate)
    if file is None:
        raise NotFoundError(f"Attempt file not found: {attempt_file_id_or_path}")
    if file.file_type != "main":
        raise MarkingContextResolutionError("Attempt file must be a registered main file")
    if file.is_template:
        raise MarkingContextResolutionError("Attempt file must be a completed file, not a template")
    if not _attempt_path_has_allowed_completion_root(Path(file.path)):
        raise MarkingContextResolutionError(
            "Attempt file is expected to be under a GoodNotes or DaydreamEdu path"
        )
    if student is not None and file.student_id != student.id:
        raise MarkingContextResolutionError(
            f"Attempt file belongs to student_id={file.student_id!r}, expected {student.id!r}"
        )
    return file


def _resolve_template_file(
    mgr: PdfFileManager,
    attempt_file: PdfFile,
    *,
    auto_link_template: bool,
) -> PdfFile:
    template = mgr.get_template(attempt_file.id)
    if template is not None:
        return template
    if not auto_link_template:
        raise NotFoundError(
            f"No template is linked to attempt file {attempt_file.path}. "
            "Set auto_link_template=True to try resolving and linking it."
        )
    mgr.link_goodnotes_template_for_file(attempt_file.path)
    template = mgr.get_template(attempt_file.id)
    if template is None:
        raise NotFoundError(f"Template linking did not produce a template for {attempt_file.path}")
    return template


def _resolve_book_group(mgr: PdfFileManager, template_file: PdfFile) -> FileGroup:
    groups = [
        group
        for group in mgr.get_file_group_membership(template_file.id)
        if group.group_type == "book"
    ]
    if not groups:
        raise NotFoundError(f"No book group found for template file: {template_file.path}")
    if len(groups) > 1:
        labels = ", ".join(sorted(group.label for group in groups))
        raise MarkingContextResolutionError(f"Template file belongs to multiple book groups: {labels}")
    return groups[0]


def _resolve_book_group_if_present(mgr: PdfFileManager, template_file: PdfFile) -> FileGroup | None:
    try:
        return _resolve_book_group(mgr, template_file)
    except NotFoundError:
        return None


def _resolve_answer_mapping(mgr: PdfFileManager, template_file: PdfFile) -> BookAnswerMapping:
    mapping = mgr.get_book_answer_mapping(template_file.id)
    if mapping is None:
        raise NotFoundError(f"No book answer mapping found for template file: {template_file.path}")
    return mapping


def _select_one_file(
    candidates: list[PdfFile],
    *,
    not_found_message: str,
    ambiguous_message: str,
) -> PdfFile:
    if not candidates:
        raise NotFoundError(not_found_message)
    if len(candidates) > 1:
        matches = "\n".join(f"- {file.path}" for file in candidates[:10])
        raise MarkingContextResolutionError(f"{ambiguous_message}:\n{matches}")
    return candidates[0]


def _path_mentions_book_label(path: str | Path, book_label: str) -> bool:
    parts = Path(path).parts
    return book_label in parts


def _infer_unit_label(file: PdfFile) -> str | None:
    metadata = file.metadata or {}
    unit = metadata.get("unit")
    if isinstance(unit, str) and unit.strip():
        return unit.strip()

    return derive_unit_label_from_attempt_name(file.name)


def _resolve_marking_mode(*, marking_mode: str | None, self_answer_pages: tuple[int, int] | None) -> str:
    allowed = {"standard_mapped_answer", "embedded_answer_override", "teacher_annotated"}
    if marking_mode is not None and marking_mode not in allowed:
        raise MarkingContextResolutionError(
            f"Unsupported marking_mode: {marking_mode}. Expected one of {sorted(allowed)}."
        )
    if self_answer_pages is not None:
        if marking_mode is None:
            return "embedded_answer_override"
        if marking_mode != "embedded_answer_override":
            raise MarkingContextResolutionError(
                "self_answer_pages is only valid for marking_mode=embedded_answer_override"
            )
        return marking_mode
    return marking_mode or "standard_mapped_answer"


def _normalize_self_answer_pages(
    self_answer_pages: tuple[int, int] | None,
) -> tuple[int, int] | None:
    if self_answer_pages is None:
        return None
    if (
        not isinstance(self_answer_pages, tuple)
        or len(self_answer_pages) != 2
        or not isinstance(self_answer_pages[0], int)
        or not isinstance(self_answer_pages[1], int)
    ):
        raise MarkingContextResolutionError(
            "self_answer_pages must be a tuple of exactly two integers: (begin_page, end_page)"
        )
    begin_page, end_page = self_answer_pages
    if begin_page < 1 or end_page < 1:
        raise MarkingContextResolutionError("self_answer_pages must use 1-based inclusive pages")
    if begin_page > end_page:
        raise MarkingContextResolutionError("self_answer_pages begin_page must be <= end_page")
    return begin_page, end_page
