"""Orchestrate path facets, registry, and workflow flags for on-disk main PDFs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from ai_study_buddy.files.completion_enrichment import enrich_registered_completion
from ai_study_buddy.files.main_pdfs import OnDiskMainPdfRow
from ai_study_buddy.files.pdf_registry_paths import (
    RegistryPathIndex,
    has_template_link,
    is_pdf_registered,
    registry_file_for_path,
)
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile, PdfFileManager


@dataclass(frozen=True)
class FilterCriteria:
    scope: str = "completion"
    root_id: str = "all"
    student: str = ""
    subject: str = "all"
    grade: str = "all"
    doc_type: str = "all"
    book: str = ""
    is_registered: str | None = None
    has_template: str | None = None
    has_marking: str | None = None
    review_status: str | None = None
    sort: str = "recent"


_VALID_SORT_KEYS = frozenset({"name", "recent"})

_REVIEW_STATUS_ORDER = ("not_started", "in_progress", "completed")


def _bool_query_options(values: set[bool]) -> tuple[str, ...]:
    """``true`` / ``false`` strings present in a boolean dimension of the current slice."""
    out: list[str] = []
    if True in values:
        out.append("true")
    if False in values:
        out.append("false")
    return tuple(out)


def _count_all_and_values(
    cards: list[OnDiskMainPdfCard],
    values: tuple[str, ...],
    matches: Callable[[OnDiskMainPdfCard, str], bool],
    *,
    all_key: str = "all",
) -> dict[str, int]:
    """File counts for an ``All`` row (*all_key*) plus each *values* entry in *cards*."""
    counts: dict[str, int] = {all_key: len(cards)}
    for value in values:
        counts[value] = sum(1 for c in cards if matches(c, value))
    return counts


def _bool_option_counts(
    cards: list[OnDiskMainPdfCard],
    options: tuple[str, ...],
    flag: Callable[[OnDiskMainPdfCard], bool],
) -> dict[str, int]:
    """Counts for workflow bool filters (``""`` = All, ``true`` / ``false``)."""
    counts: dict[str, int] = {"": len(cards)}
    if "true" in options:
        counts["true"] = sum(1 for c in cards if flag(c) is True)
    if "false" in options:
        counts["false"] = sum(1 for c in cards if flag(c) is False)
    return counts


def resolve_card_student_id(
    card: OnDiskMainPdfCard,
    *,
    pfm: PdfFileManager,
    registry_row: object | None = None,
) -> str | None:
    """Registry ``students.id`` for a completion (e.g. ``winston``), not email."""
    if registry_row is not None:
        sid = getattr(registry_row, "student_id", None)
        if sid:
            return sid
    if card.registry_file_id:
        row = pfm.get_file(card.registry_file_id)
        if row and row.student_id:
            return row.student_id
    if card.student_email:
        needle = card.student_email.strip().lower()
        for student in pfm.list_students():
            if student.email and student.email.lower() == needle:
                return student.id
    return pfm._infer_student_id_from_path(card.absolute_path)


@dataclass(frozen=True)
class WorkflowFilterOptions:
    show_is_registered_filter: bool
    is_registered_options: tuple[str, ...]
    is_registered_counts: dict[str, int]
    show_has_template_filter: bool
    has_template_options: tuple[str, ...]
    has_template_counts: dict[str, int]
    show_has_marking_filter: bool
    has_marking_options: tuple[str, ...]
    has_marking_counts: dict[str, int]
    show_review_status_filter: bool
    review_status_options: tuple[str, ...]
    review_status_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "show_is_registered_filter": self.show_is_registered_filter,
            "is_registered_options": list(self.is_registered_options),
            "is_registered_counts": dict(self.is_registered_counts),
            "show_has_template_filter": self.show_has_template_filter,
            "has_template_options": list(self.has_template_options),
            "has_template_counts": dict(self.has_template_counts),
            "show_has_marking_filter": self.show_has_marking_filter,
            "has_marking_options": list(self.has_marking_options),
            "has_marking_counts": dict(self.has_marking_counts),
            "show_review_status_filter": self.show_review_status_filter,
            "review_status_options": list(self.review_status_options),
            "review_status_counts": dict(self.review_status_counts),
        }


@dataclass
class OnDiskMainPdfCard:
    absolute_path: str
    basename: str
    root_id: str
    scope: str
    subject: str
    grade_or_scope: str
    doc_type: str
    book_group_name: str | None
    student_email: str | None
    parse_status: str
    is_registered: bool
    student_id: str | None = None
    registry_file_id: str | None = None
    normal_name: str | None = None
    has_template: bool | None = None
    template_file_id: str | None = None
    completion_series_id: str | None = None
    attempt_sequence: int | None = None
    attempt_count: int | None = None
    has_marking: bool | None = None
    has_marking_amendment: bool | None = None
    review_status: str | None = None
    registry_added_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class InventoryMeta:
    total_in_index: int
    total_after_filter: int
    unregistered_in_index: int
    show_is_registered_filter: bool


def inventory_meta(
    cards: list[OnDiskMainPdfCard],
    *,
    filtered_count: int,
    show_is_registered_filter: bool | None = None,
) -> InventoryMeta:
    unreg = sum(1 for c in cards if not c.is_registered)
    return InventoryMeta(
        total_in_index=len(cards),
        total_after_filter=filtered_count,
        unregistered_in_index=unreg,
        show_is_registered_filter=unreg > 0 if show_is_registered_filter is None else show_is_registered_filter,
    )


def should_show_is_registered_filter(
    cards: list[OnDiskMainPdfCard],
    criteria: FilterCriteria,
    *,
    pfm: PdfFileManager | None = None,
) -> bool:
    """True when the contextual slice has both registered and unregistered mains."""
    return len(_registration_filter_options(cards, criteria, pfm=pfm)) > 1


def _registration_filter_options(
    cards: list[OnDiskMainPdfCard],
    criteria: FilterCriteria,
    *,
    pfm: PdfFileManager | None = None,
) -> tuple[str, ...]:
    sans_reg = replace(criteria, is_registered=None)
    subset = filter_main_pdf_cards(cards, sans_reg, pfm=pfm)
    return _bool_query_options({c.is_registered for c in subset})


def workflow_filter_options(
    cards: list[OnDiskMainPdfCard],
    criteria: FilterCriteria,
    *,
    pfm: PdfFileManager | None = None,
) -> WorkflowFilterOptions:
    """Contextual registration + completion workflow filter options for the current slice.

    Each control is shown only when its slice (with that field cleared) has **>1** distinct
    value. Dropdown values are exactly those present (no fixed Has/No lists).
    """
    sans_reg = replace(criteria, is_registered=None)
    reg_subset = filter_main_pdf_cards(cards, sans_reg, pfm=pfm)
    is_registered_options = _bool_query_options({c.is_registered for c in reg_subset})
    is_registered_counts = _bool_option_counts(reg_subset, is_registered_options, lambda c: c.is_registered)

    sans = replace(
        criteria,
        has_template=None,
        has_marking=None,
        review_status=None,
    )
    subset = filter_main_pdf_cards(cards, sans, pfm=pfm)
    registered = [c for c in subset if c.scope == "completion" and c.is_registered]

    template_vals = {c.has_template for c in registered}
    marking_vals = {c.has_marking for c in registered}
    review_vals = {c.review_status for c in registered if c.review_status}

    has_template_options = _bool_query_options(template_vals)
    has_marking_options = _bool_query_options(marking_vals)

    ordered_reviews = [s for s in _REVIEW_STATUS_ORDER if s in review_vals]
    for extra in sorted(review_vals - set(_REVIEW_STATUS_ORDER), key=str.casefold):
        ordered_reviews.append(extra)
    review_status_options = tuple(ordered_reviews)

    has_template_counts = _bool_option_counts(
        subset,
        has_template_options,
        lambda c: c.has_template is True,
    )
    has_marking_counts = _bool_option_counts(
        subset,
        has_marking_options,
        lambda c: c.has_marking is True,
    )
    review_status_counts: dict[str, int] = {"": len(subset)}
    for status in review_status_options:
        review_status_counts[status] = sum(
            1 for c in subset if (c.review_status or "") == status
        )

    return WorkflowFilterOptions(
        show_is_registered_filter=len(is_registered_options) > 1,
        is_registered_options=is_registered_options,
        is_registered_counts=is_registered_counts,
        show_has_template_filter=len(has_template_options) > 1,
        has_template_options=has_template_options,
        has_template_counts=has_template_counts,
        show_has_marking_filter=len(has_marking_options) > 1,
        has_marking_options=has_marking_options,
        has_marking_counts=has_marking_counts,
        show_review_status_filter=len(review_status_options) > 1,
        review_status_options=review_status_options,
        review_status_counts=review_status_counts,
    )


def distinct_book_group_names(
    cards: list[OnDiskMainPdfCard],
    criteria: FilterCriteria,
    *,
    pfm: PdfFileManager | None = None,
) -> list[str]:
    """Book group names in the index matching filters except ``book`` (requires ``doc_type=book``)."""
    if criteria.doc_type != "book":
        return []
    sans_book = replace(criteria, book="", is_registered=None)
    subset = filter_main_pdf_cards(cards, sans_book, pfm=pfm)
    names = {c.book_group_name for c in subset if c.book_group_name}
    return sorted(names, key=str.casefold)


@dataclass(frozen=True)
class FilterDropdownOptions:
    """Distinct facet values for filter dropdowns (each omits its own criterion)."""

    scopes: tuple[str, ...]
    scope_counts: dict[str, int]
    subjects: tuple[str, ...]
    subject_counts: dict[str, int]
    grades: tuple[str, ...]
    grade_counts: dict[str, int]
    doc_types: tuple[str, ...]
    doc_type_counts: dict[str, int]
    student_ids: tuple[str, ...]
    student_counts: dict[str, int]
    book_names: tuple[str, ...]
    book_counts: dict[str, int]
    root_ids: tuple[str, ...]
    root_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scopes": list(self.scopes),
            "scope_counts": dict(self.scope_counts),
            "subjects": list(self.subjects),
            "subject_counts": dict(self.subject_counts),
            "grades": list(self.grades),
            "grade_counts": dict(self.grade_counts),
            "doc_types": list(self.doc_types),
            "doc_type_counts": dict(self.doc_type_counts),
            "student_ids": list(self.student_ids),
            "student_counts": dict(self.student_counts),
            "book_names": list(self.book_names),
            "book_counts": dict(self.book_counts),
            "root_ids": list(self.root_ids),
            "root_counts": dict(self.root_counts),
        }


def _sorted_facet_values(values: set[str]) -> tuple[str, ...]:
    return tuple(sorted(values, key=str.casefold))


def filter_dropdown_options(
    cards: list[OnDiskMainPdfCard],
    criteria: FilterCriteria,
    *,
    pfm: PdfFileManager | None = None,
) -> FilterDropdownOptions:
    """Dropdown choices implied by the current filter slice (excluding each control's field)."""

    def subset(**overrides: object) -> list[OnDiskMainPdfCard]:
        c = replace(criteria, **overrides)
        return filter_main_pdf_cards(cards, c, pfm=pfm)

    sub_scopes = subset(scope="all")
    scopes = {c.scope for c in sub_scopes if c.scope}

    sub_roots = subset(root_id="all")
    root_ids_set = {c.root_id for c in sub_roots if c.root_id}

    sub_subjects = subset(subject="all")
    subjects = {
        c.subject for c in sub_subjects if c.subject and c.subject not in ("unknown", "all")
    }

    sub_grades = subset(grade="all")
    grades = {
        c.grade_or_scope
        for c in sub_grades
        if c.grade_or_scope and c.grade_or_scope not in ("unknown", "all")
    }

    sub_types = subset(doc_type="all")
    doc_types = {c.doc_type for c in sub_types if c.doc_type and c.doc_type not in ("unknown", "all")}

    sub_students = subset(student="")
    student_ids: set[str] = set()
    for c in sub_students:
        if c.student_id:
            student_ids.add(c.student_id)

    book_names_list = distinct_book_group_names(cards, criteria, pfm=pfm)
    sans_book = replace(criteria, book="", is_registered=None)
    sub_books = filter_main_pdf_cards(cards, sans_book, pfm=pfm)

    scope_values = _sorted_facet_values(scopes)
    subject_values = _sorted_facet_values(subjects)
    grade_values = _sorted_facet_values(grades)
    doc_type_values = _sorted_facet_values(doc_types)
    student_values = _sorted_facet_values(student_ids)
    book_values = tuple(book_names_list)
    root_values = _sorted_facet_values(root_ids_set)

    return FilterDropdownOptions(
        scopes=scope_values,
        scope_counts=_count_all_and_values(
            sub_scopes,
            scope_values,
            lambda c, v: c.scope == v,
            all_key="all",
        ),
        subjects=subject_values,
        subject_counts=_count_all_and_values(
            sub_subjects,
            subject_values,
            lambda c, v: c.subject == v,
        ),
        grades=grade_values,
        grade_counts=_count_all_and_values(
            sub_grades,
            grade_values,
            lambda c, v: c.grade_or_scope == v,
        ),
        doc_types=doc_type_values,
        doc_type_counts=_count_all_and_values(
            sub_types,
            doc_type_values,
            lambda c, v: c.doc_type == v,
        ),
        student_ids=student_values,
        student_counts=_count_all_and_values(
            sub_students,
            student_values,
            lambda c, v: c.student_id == v,
            all_key="",
        ),
        book_names=book_values,
        book_counts=_count_all_and_values(
            sub_books,
            book_values,
            lambda c, v: (c.book_group_name or "") == v,
            all_key="",
        ),
        root_ids=root_values,
        root_counts=_count_all_and_values(
            sub_roots,
            root_values,
            lambda c, v: c.root_id == v,
        ),
    )


def filter_meta_for_response(
    cards: list[OnDiskMainPdfCard],
    criteria: FilterCriteria,
    *,
    pfm: PdfFileManager | None = None,
) -> dict[str, Any]:
    """Contextual filter UI metadata for ``/api/config`` and ``/api/inventory``."""
    workflow = workflow_filter_options(cards, criteria, pfm=pfm)
    out = filter_dropdown_options(cards, criteria, pfm=pfm).to_dict()
    out.update(workflow.to_dict())
    return out


def enrich_on_disk_main_pdf(
    row: OnDiskMainPdfRow,
    *,
    index: RegistryPathIndex,
    pfm: PdfFileManager,
    review_repo: StudentReviewRepository,
    context_root: Path,
) -> OnDiskMainPdfCard:
    f = row.facets
    registered = is_pdf_registered(row.absolute_path, index)
    reg_row = registry_file_for_path(row.absolute_path, index) if registered else None

    card = OnDiskMainPdfCard(
        absolute_path=str(row.absolute_path),
        basename=row.basename,
        root_id=f.root_id,
        scope=f.scope,
        subject=f.subject,
        grade_or_scope=f.grade_or_scope,
        doc_type=f.doc_type,
        book_group_name=f.book_group_name,
        student_email=f.student_email,
        parse_status=f.parse_status,
        is_registered=registered,
    )
    if f.scope == "completion":
        card.student_id = resolve_card_student_id(card, pfm=pfm, registry_row=reg_row)

    if not registered:
        card.has_template = False
        card.has_marking = False
        card.has_marking_amendment = False
        card.review_status = None
        return card

    if reg_row is None:
        card.is_registered = False
        card.has_template = False
        card.has_marking = False
        card.has_marking_amendment = False
        card.review_status = None
        return card

    pdf_file: PdfFile = reg_row  # type: ignore[assignment]
    card.registry_file_id = pdf_file.id
    card.normal_name = pdf_file.normal_name
    card.registry_added_at = pdf_file.added_at

    if pdf_file.is_template:
        card.has_template = None
        card.has_marking = None
        card.has_marking_amendment = None
        card.review_status = None
        return card

    card.has_template = has_template_link(pfm, pdf_file.id)
    if card.has_template:
        template = pfm.get_template(pdf_file.id)
        if template is not None:
            card.template_file_id = template.id
        member_info = pfm.get_completion_series_member(pdf_file.id)
        if member_info is not None:
            series, member = member_info
            card.completion_series_id = series.series_id
            card.attempt_sequence = member.attempt_sequence
            card.attempt_count = series.attempt_count
    workflow = enrich_registered_completion(
        pdf_file,
        context_root=context_root,
        pfm=pfm,
        review_repo=review_repo,
    )
    card.has_marking = workflow.has_marking
    card.has_marking_amendment = workflow.has_marking_amendment
    card.review_status = workflow.review_status
    return card


def _student_matches(card: OnDiskMainPdfCard, student_filter: str, pfm: PdfFileManager) -> bool:
    if not student_filter:
        return True
    needle = student_filter.strip().lower()
    if card.student_id and card.student_id.lower() == needle:
        return True
    # Legacy URLs / localStorage may still store email.
    if card.student_email and card.student_email.lower() == needle:
        return True
    if card.registry_file_id:
        row = pfm.get_file(card.registry_file_id)
        if row and row.student_id:
            student = pfm.get_student(row.student_id)
            if student and student.email and student.email.lower() == needle:
                return True
    return False


def filter_main_pdf_cards(
    cards: list[OnDiskMainPdfCard],
    criteria: FilterCriteria,
    *,
    pfm: PdfFileManager | None = None,
) -> list[OnDiskMainPdfCard]:
    out: list[OnDiskMainPdfCard] = []
    for card in cards:
        if criteria.scope not in ("", "all") and card.scope != criteria.scope:
            continue
        if criteria.root_id not in ("", "all") and card.root_id != criteria.root_id:
            continue
        if criteria.subject != "all" and card.subject != criteria.subject:
            continue
        if criteria.grade != "all" and card.grade_or_scope != criteria.grade:
            continue
        if criteria.doc_type != "all" and card.doc_type != criteria.doc_type:
            continue
        if criteria.book and (card.book_group_name or "") != criteria.book:
            continue
        if criteria.is_registered == "true" and not card.is_registered:
            continue
        if criteria.is_registered == "false" and card.is_registered:
            continue
        if criteria.has_template == "true" and card.has_template is not True:
            continue
        if criteria.has_template == "false" and card.has_template is not False:
            continue
        if criteria.has_marking == "true" and card.has_marking is not True:
            continue
        if criteria.has_marking == "false" and card.has_marking is not False:
            continue
        if criteria.review_status and (card.review_status or "") != criteria.review_status:
            continue
        if criteria.student and pfm is not None:
            if not _student_matches(card, criteria.student, pfm):
                continue
        elif criteria.student:
            sid = (card.student_id or "").lower()
            email = (card.student_email or "").lower()
            needle = criteria.student.strip().lower()
            if sid != needle and email != needle:
                continue
        out.append(card)
    return out


def _display_name_key(card: OnDiskMainPdfCard) -> str:
    return (card.normal_name or card.basename).casefold()


def _path_key(card: OnDiskMainPdfCard) -> str:
    return card.absolute_path.casefold()


def sort_main_pdf_cards(
    cards: list[OnDiskMainPdfCard],
    sort: str = "recent",
) -> list[OnDiskMainPdfCard]:
    key = sort if sort in _VALID_SORT_KEYS else "recent"
    if key == "name":
        return sorted(cards, key=lambda c: (_display_name_key(c), _path_key(c)))
    registered = [c for c in cards if c.registry_added_at]
    unregistered = [c for c in cards if not c.registry_added_at]
    registered.sort(key=_path_key)
    registered.sort(key=lambda c: c.registry_added_at or "", reverse=True)
    unregistered.sort(key=_path_key)
    return registered + unregistered


def build_enriched_inventory(
    rows: list[OnDiskMainPdfRow],
    *,
    index: RegistryPathIndex,
    pfm: PdfFileManager,
    review_repo: StudentReviewRepository,
    context_root: Path,
) -> list[OnDiskMainPdfCard]:
    return [
        enrich_on_disk_main_pdf(
            row,
            index=index,
            pfm=pfm,
            review_repo=review_repo,
            context_root=context_root,
        )
        for row in rows
    ]
