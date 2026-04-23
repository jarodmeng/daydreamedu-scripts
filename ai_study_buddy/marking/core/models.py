from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Marks may be whole numbers or fractional (e.g. 1.5 / 2) on teacher-marked papers.
MarkingScore = int | float


@dataclass(frozen=True)
class QuestionSelection:
    raw_text: str | None
    canonical_refs: tuple[str, ...] = ()
    section_hint: str | None = None


@dataclass(frozen=True)
class MarkingContext:
    student_id: str | None
    student_name: str | None

    attempt_file_id: str
    attempt_file_path: str

    template_file_id: str
    template_file_path: str

    book_group_id: str | None
    book_label: str | None

    unit_file_id: str
    unit_file_path: str
    unit_label: str | None

    answer_file_id: str
    answer_file_path: str

    answer_page_start: int
    answer_page_end: int
    starts_mid_page: bool
    ends_mid_page: bool
    answer_mapping_source: str | None
    answer_mapping_notes: str | None

    question_selection: QuestionSelection

    needs_visual_attempt_pages: bool = True
    needs_visual_answer_pages: bool = True


@dataclass(frozen=True)
class Diagnosis:
    mistake_type: str | None = None
    reasoning: str | None = None
    confidence: str | None = None


@dataclass(frozen=True)
class ArtifactQuestionResult:
    """Per-question row in ``marking_result.v1``.

    ``skill_tags``: array of strings; subject policy in ``ai_study_buddy/docs/L4_MARKING_RESULT_ARTIFACT.md``
    (math/science: full path per element with `` > ``; English/Chinese/HC: prefer empty;
    legacy data may use one hierarchy segment per tuple element).
    """

    result_id: str
    max_marks: MarkingScore
    earned_marks: MarkingScore
    outcome: str
    student_answer: str | None
    correct_answer: str | None
    scoring_status: str = "counted"
    feedback: str | None = None
    error_tags: tuple[str, ...] = ()
    skill_tags: tuple[str, ...] = ()
    diagnosis: Diagnosis = Diagnosis()
    human_note: str | None = None


@dataclass(frozen=True)
class ArtifactSummary:
    total_marks: MarkingScore
    earned_marks: MarkingScore
    percentage: float
    overall_assessment: str
    human_note: str | None = None


@dataclass(frozen=True)
class ReviewMeta:
    updated_at: str | None = None
    updated_by: str | None = None


@dataclass(frozen=True)
class GenerationMeta:
    produced_by: str
    mode: str
    notes: str | None = None


@dataclass(frozen=True)
class QuestionPageMapEntry:
    result_id: str
    attempt_page_start: int
    confidence: str
    source: str
    evidence_image: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class MarkingArtifactContext:
    student_id: str | None
    student_name: str | None
    subject_context: str

    attempt_file_id: str | None
    attempt_file_path: str

    template_file_id: str | None
    template_file_path: str | None

    book_group_id: str | None
    book_label: str | None

    unit_file_id: str | None
    unit_file_path: str | None
    unit_label: str | None

    answer_file_id: str | None
    answer_file_path: str | None

    answer_page_start: int | None
    answer_page_end: int | None
    starts_mid_page: bool = False
    ends_mid_page: bool = False
    answer_mapping_source: str | None = None
    answer_mapping_notes: str | None = None
    marking_asset: str | None = None
    is_partial: bool | None = None
    template_attempt_group_id: str | None = None
    attempt_sequence: int | None = None
    attempt_label: str | None = None
    question_page_map: tuple[QuestionPageMapEntry, ...] = ()

    question_selection: QuestionSelection = QuestionSelection(raw_text=None)

    @classmethod
    def from_marking_context(
        cls,
        context: MarkingContext,
        *,
        subject_context: str,
    ) -> "MarkingArtifactContext":
        return cls(
            student_id=context.student_id,
            student_name=context.student_name,
            subject_context=subject_context,
            attempt_file_id=context.attempt_file_id,
            attempt_file_path=context.attempt_file_path,
            template_file_id=context.template_file_id,
            template_file_path=context.template_file_path,
            book_group_id=context.book_group_id,
            book_label=context.book_label,
            unit_file_id=context.unit_file_id,
            unit_file_path=context.unit_file_path,
            unit_label=context.unit_label,
            answer_file_id=context.answer_file_id,
            answer_file_path=context.answer_file_path,
            answer_page_start=context.answer_page_start,
            answer_page_end=context.answer_page_end,
            starts_mid_page=context.starts_mid_page,
            ends_mid_page=context.ends_mid_page,
            answer_mapping_source=context.answer_mapping_source,
            answer_mapping_notes=context.answer_mapping_notes,
            marking_asset=None,
            is_partial=None,
            template_attempt_group_id=None,
            attempt_sequence=None,
            attempt_label=None,
            question_page_map=(),
            question_selection=context.question_selection,
        )


@dataclass(frozen=True)
class MarkingArtifact:
    schema_version: str
    created_at: str
    updated_at: str
    context: MarkingArtifactContext
    summary: ArtifactSummary
    question_results: tuple[ArtifactQuestionResult, ...]
    review_meta: ReviewMeta
    generation: GenerationMeta

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MarkingArtifact":
        context_payload = payload["context"]
        summary_payload = payload["summary"]
        review_meta_payload = payload["review_meta"]
        generation_payload = payload["generation"]

        question_selection_payload = context_payload.get("question_selection", {})
        context = MarkingArtifactContext(
            student_id=context_payload.get("student_id"),
            student_name=context_payload.get("student_name"),
            subject_context=context_payload["subject_context"],
            attempt_file_id=context_payload.get("attempt_file_id"),
            attempt_file_path=context_payload["attempt_file_path"],
            template_file_id=context_payload.get("template_file_id"),
            template_file_path=context_payload.get("template_file_path"),
            book_group_id=context_payload.get("book_group_id"),
            book_label=context_payload.get("book_label"),
            unit_file_id=context_payload.get("unit_file_id"),
            unit_file_path=context_payload.get("unit_file_path"),
            unit_label=context_payload.get("unit_label"),
            answer_file_id=context_payload.get("answer_file_id"),
            answer_file_path=context_payload.get("answer_file_path"),
            answer_page_start=context_payload.get("answer_page_start"),
            answer_page_end=context_payload.get("answer_page_end"),
            starts_mid_page=bool(context_payload.get("starts_mid_page", False)),
            ends_mid_page=bool(context_payload.get("ends_mid_page", False)),
            answer_mapping_source=context_payload.get("answer_mapping_source"),
            answer_mapping_notes=context_payload.get("answer_mapping_notes"),
            marking_asset=context_payload.get("marking_asset"),
            is_partial=context_payload.get("is_partial") if isinstance(context_payload.get("is_partial"), bool) else None,
            template_attempt_group_id=context_payload.get("template_attempt_group_id"),
            attempt_sequence=context_payload.get("attempt_sequence"),
            attempt_label=context_payload.get("attempt_label"),
            question_page_map=tuple(
                QuestionPageMapEntry(
                    result_id=entry["result_id"],
                    attempt_page_start=entry["attempt_page_start"],
                    confidence=entry["confidence"],
                    source=entry["source"],
                    evidence_image=entry.get("evidence_image"),
                    note=entry.get("note"),
                )
                for entry in context_payload.get("question_page_map", ())
                if isinstance(entry, dict)
            ),
            question_selection=QuestionSelection(
                raw_text=question_selection_payload.get("raw_text"),
                canonical_refs=tuple(question_selection_payload.get("canonical_refs", ())),
                section_hint=question_selection_payload.get("section_hint"),
            ),
        )
        summary = ArtifactSummary(
            total_marks=summary_payload["total_marks"],
            earned_marks=summary_payload["earned_marks"],
            percentage=float(summary_payload["percentage"]),
            overall_assessment=summary_payload["overall_assessment"],
            human_note=summary_payload.get("human_note"),
        )
        question_results = tuple(
            ArtifactQuestionResult(
                result_id=row["result_id"],
                scoring_status=row.get("scoring_status", "counted"),
                max_marks=row["max_marks"],
                earned_marks=row["earned_marks"],
                outcome=row["outcome"],
                student_answer=row.get("student_answer"),
                correct_answer=row.get("correct_answer"),
                feedback=row.get("feedback"),
                error_tags=tuple(row.get("error_tags", ())),
                skill_tags=tuple(row.get("skill_tags", ())),
                diagnosis=Diagnosis(**row.get("diagnosis", {})),
                human_note=row.get("human_note"),
            )
            for row in payload.get("question_results", ())
        )
        review_meta = ReviewMeta(
            updated_at=review_meta_payload.get("updated_at"),
            updated_by=review_meta_payload.get("updated_by"),
        )
        generation = GenerationMeta(
            produced_by=generation_payload["produced_by"],
            mode=generation_payload["mode"],
            notes=generation_payload.get("notes"),
        )
        return cls(
            schema_version=payload["schema_version"],
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            context=context,
            summary=summary,
            question_results=question_results,
            review_meta=review_meta,
            generation=generation,
        )
