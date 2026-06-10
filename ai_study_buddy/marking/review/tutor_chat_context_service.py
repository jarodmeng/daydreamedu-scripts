from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ai_study_buddy.marking.review.detail_service import AttemptNotFoundError, get_attempt_detail
from ai_study_buddy.marking.review.models import STATIC_ROUTE_PREFIX
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.marking.review.tutor_chat_stale import build_context_snapshot
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

_PEDAGOGY_FILES: dict[str, tuple[str, ...]] = {
    "singapore_primary_math": (
        "subject_understandings/singapore_primary_math/math_error_types.md",
        "subject_understandings/singapore_primary_math/math_question_skill.md",
    ),
    "singapore_primary_science": (
        "subject_understandings/singapore_primary_science/skill_understanding.md",
    ),
}

_MAX_PEDAGOGY_CHARS = 8000


class TutorChatContextError(ValueError):
    pass


def tutor_chat_debug_enabled() -> bool:
    return os.environ.get("BUDDY_CONSOLE_TUTOR_CHAT_DEBUG", "").strip() == "1"


def _question_row(detail: dict[str, Any], result_id: str) -> dict[str, Any]:
    marking = detail.get("marking_result")
    if not isinstance(marking, dict):
        raise TutorChatContextError("attempt is not marked")
    rows = marking.get("question_results")
    if not isinstance(rows, list):
        raise TutorChatContextError(f"unknown result_id: {result_id}")
    for row in rows:
        if isinstance(row, dict) and row.get("result_id") == result_id:
            return row
    raise TutorChatContextError(f"unknown result_id: {result_id}")


def _amendment_overlay_for_result(amendment_state: dict[str, Any] | None, result_id: str) -> dict[str, Any] | None:
    if not isinstance(amendment_state, dict):
        return None
    amendments = amendment_state.get("question_amendments")
    if not isinstance(amendments, list):
        return None
    for entry in amendments:
        if isinstance(entry, dict) and entry.get("result_id") == result_id:
            return entry
    return None


def _question_review_blocks(
    review_state: dict[str, Any],
    *,
    active_result_id: str,
) -> list[str]:
    question_reviews = review_state.get("question_reviews")
    if not isinstance(question_reviews, list):
        question_reviews = []

    active_rows = [row for row in question_reviews if isinstance(row, dict) and row.get("result_id") == active_result_id]
    other_rows = sorted(
        [row for row in question_reviews if isinstance(row, dict) and row.get("result_id") != active_result_id],
        key=lambda row: str(row.get("result_id") or ""),
    )

    blocks: list[str] = []
    for row in active_rows + other_rows:
        result_id = row.get("result_id")
        if not isinstance(result_id, str) or not result_id.strip():
            continue
        note_text = row.get("note_text") if isinstance(row.get("note_text"), str) else ""
        review_status = row.get("review_status") if isinstance(row.get("review_status"), str) else "not_reviewed"
        if not note_text.strip() and review_status != "reviewed":
            continue

        lines = [f"[QUESTION — {result_id}]", f"review_status: {review_status}"]
        if note_text.strip():
            lines.append(note_text.strip())
        author_role = row.get("author_role")
        updated_at = row.get("updated_at")
        meta_parts: list[str] = []
        if isinstance(author_role, str) and author_role.strip():
            meta_parts.append(f"author_role={author_role.strip()}")
        if isinstance(updated_at, str) and updated_at.strip():
            meta_parts.append(f"updated_at={updated_at.strip()}")
        if meta_parts:
            lines.append(f"({', '.join(meta_parts)})")
        blocks.append("\n".join(lines))
    return blocks


def _note_list_blocks(label: str, notes: Any) -> list[str]:
    if not isinstance(notes, list):
        return []
    lines = [label]
    for note in notes:
        if not isinstance(note, dict):
            continue
        note_text = note.get("note_text") if isinstance(note.get("note_text"), str) else ""
        if not note_text.strip():
            continue
        lines.append(note_text.strip())
        author_role = note.get("author_role")
        updated_at = note.get("updated_at")
        meta_parts: list[str] = []
        if isinstance(author_role, str) and author_role.strip():
            meta_parts.append(f"author_role={author_role.strip()}")
        if isinstance(updated_at, str) and updated_at.strip():
            meta_parts.append(f"updated_at={updated_at.strip()}")
        if meta_parts:
            lines.append(f"({', '.join(meta_parts)})")
    if len(lines) == 1:
        return []
    return ["\n".join(lines)]


def format_labeled_review_notes(
    review_state: dict[str, Any],
    *,
    active_result_id: str,
    subject_context: str,
) -> list[str]:
    blocks = _question_review_blocks(review_state, active_result_id=active_result_id)
    blocks.extend(_note_list_blocks("[ATTEMPT]", review_state.get("attempt_notes")))
    blocks.extend(
        _note_list_blocks(f"[STUDENT_SUBJECT — {subject_context}]", review_state.get("student_subject_notes"))
    )
    return blocks


def load_pedagogy_refs(*, context_root: Path, subject_context: str) -> list[dict[str, str]]:
    rel_paths = _PEDAGOGY_FILES.get(subject_context, ())
    out: list[dict[str, str]] = []
    for rel in rel_paths:
        path = context_root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        truncated = False
        if len(text) > _MAX_PEDAGOGY_CHARS:
            text = text[:_MAX_PEDAGOGY_CHARS]
            truncated = True
        out.append(
            {
                "path": rel,
                "text": text,
                "truncated": truncated,
            }
        )
    return out


def resolve_attempt_page(
    *,
    context_root: Path,
    viewer: dict[str, Any],
    page_num: int | None,
) -> dict[str, Any]:
    if not isinstance(page_num, int):
        return {"page_num": None, "url": None, "absolute_path": None}

    attempt_images = viewer.get("attempt_images")
    if isinstance(attempt_images, list):
        for image in attempt_images:
            if not isinstance(image, dict):
                continue
            if image.get("page_num") == page_num:
                url = image.get("url") if isinstance(image.get("url"), str) else None
                absolute_path = None
                if url and url.startswith(f"{STATIC_ROUTE_PREFIX}/"):
                    rel = url[len(f"{STATIC_ROUTE_PREFIX}/") :]
                    candidate = (context_root / rel).resolve()
                    if candidate.is_file():
                        absolute_path = str(candidate)
                return {
                    "page_num": page_num,
                    "url": url,
                    "absolute_path": absolute_path,
                }

    marking_asset = viewer.get("marking_asset") if isinstance(viewer.get("marking_asset"), str) else None
    if marking_asset:
        stem = f"page-{page_num:02d}.png"
        candidate = (context_root / marking_asset / "attempt" / stem).resolve()
        if candidate.is_file():
            rel = candidate.relative_to(context_root.resolve()).as_posix()
            return {
                "page_num": page_num,
                "url": f"{STATIC_ROUTE_PREFIX}/{rel}",
                "absolute_path": str(candidate),
            }

    return {"page_num": page_num, "url": None, "absolute_path": None}


def build_attempt_meta(detail: dict[str, Any]) -> dict[str, Any]:
    attempt = detail.get("attempt") if isinstance(detail.get("attempt"), dict) else {}
    marking = detail.get("marking_result") if isinstance(detail.get("marking_result"), dict) else {}
    context = marking.get("context") if isinstance(marking.get("context"), dict) else {}
    return {
        "attempt_id": attempt.get("attempt_id"),
        "student_id": attempt.get("student_id"),
        "title": attempt.get("title"),
        "subject_context": attempt.get("subject_context"),
        "book_label": attempt.get("book_label"),
        "unit_label": context.get("unit_label"),
        "is_partial": context.get("is_partial"),
        "collection_kind": attempt.get("collection_kind"),
    }


def build_attempt_summary(detail: dict[str, Any]) -> dict[str, Any]:
    marking = detail.get("marking_result") if isinstance(detail.get("marking_result"), dict) else {}
    summary = marking.get("summary") if isinstance(marking.get("summary"), dict) else {}
    return {
        "earned_marks": summary.get("earned_marks"),
        "total_marks": summary.get("total_marks"),
        "percentage": summary.get("percentage"),
        "overall_assessment": summary.get("overall_assessment"),
        "human_note": summary.get("human_note"),
    }


def render_context_bundle_prompt(bundle: dict[str, Any]) -> str:
    lines = [
        "You are a Socratic tutor helping a student review one marked question.",
        "",
        "### Evidence hierarchy",
        "1. **Primary ground truth:** question stem, attempt page image, and the student's written work.",
        "2. **Authoritative overrides:** human amendments (when present) — supersede conflicting base-marking fields.",
        (
            "3. **Reference only (may be wrong):** base marking fields (`outcome`, `correct_answer`, "
            "`diagnosis`, `earned_marks`) from the automated grader run. Treat them as hypotheses to "
            "check against clues and evidence, not as absolute truth."
        ),
        "",
        "### Tutor behavior",
        "- Use only the context below; do not fabricate scores, amendments, teacher comments, or files.",
        "- Do not modify files or marking artifacts.",
        (
            "- When the student disputes the mark, compare their reasoning to question clues and visible "
            "evidence. Clearly say when base marking looks inconsistent, incomplete, or mistaken."
        ),
        (
            "- Human amendments and labeled review notes outrank automated `correct_answer` / `diagnosis` "
            "when they conflict."
        ),
        "- Prefer Socratic hints before full solutions unless the student explicitly asks for the answer.",
        (
            "- Reference the attempt page image when visible details matter; do not invent diagrams or "
            "teacher markings."
        ),
        "",
        "## Attempt",
        str(bundle.get("attempt_meta")),
        "",
        "## Base marking (AI grader output — challengeable)",
        str(bundle.get("question")),
        "",
    ]
    amendments = bundle.get("amendments")
    if amendments:
        lines.extend(
            [
                "## Human amendments (authoritative overrides)",
                str(amendments),
                "",
            ]
        )

    review_notes = bundle.get("review_notes_labeled")
    if isinstance(review_notes, list) and review_notes:
        lines.append("## Review notes (labeled by scope)")
        lines.extend(str(block) for block in review_notes)
        lines.append("")

    page = bundle.get("page")
    if isinstance(page, dict) and page.get("absolute_path"):
        lines.extend(["## Attempt page image", f"absolute_path: {page.get('absolute_path')}", ""])

    summary = bundle.get("attempt_summary")
    if summary:
        lines.extend(["## Attempt summary", str(summary), ""])

    pedagogy = bundle.get("pedagogy_refs")
    if isinstance(pedagogy, list) and pedagogy:
        lines.append("## Subject pedagogy references")
        for ref in pedagogy:
            if not isinstance(ref, dict):
                continue
            lines.append(f"### {ref.get('path')}")
            lines.append(str(ref.get("text") or ""))
        lines.append("")

    lines.append("Answer only about the active question unless the student clearly asks about attempt-level context.")
    return "\n".join(lines)


def build_context_bundle_from_detail(
    *,
    detail: dict[str, Any],
    result_id: str,
    context_root: Path,
    review_state_updated_at: str | None,
) -> dict[str, Any]:
    question = _question_row(detail, result_id)
    attempt = detail.get("attempt") if isinstance(detail.get("attempt"), dict) else {}
    subject_context = attempt.get("subject_context")
    if not isinstance(subject_context, str) or not subject_context.strip():
        subject_context = "unknown"

    marking = detail.get("marking_result")
    artifact_path = ""
    if isinstance(marking, dict) and isinstance(marking.get("artifact_path"), str):
        artifact_path = marking["artifact_path"]

    review_state = detail.get("review_state") if isinstance(detail.get("review_state"), dict) else {}
    viewer = detail.get("viewer") if isinstance(detail.get("viewer"), dict) else {}
    amendment_state = detail.get("amendment_state") if isinstance(detail.get("amendment_state"), dict) else None

    bundle: dict[str, Any] = {
        "attempt_id": attempt.get("attempt_id"),
        "result_id": result_id,
        "attempt_meta": build_attempt_meta(detail),
        "question": question,
        "amendments": _amendment_overlay_for_result(amendment_state, result_id),
        "review_notes_labeled": format_labeled_review_notes(
            review_state,
            active_result_id=result_id,
            subject_context=subject_context,
        ),
        "page": resolve_attempt_page(
            context_root=context_root,
            viewer=viewer,
            page_num=question.get("attempt_page_start") if isinstance(question.get("attempt_page_start"), int) else None,
        ),
        "attempt_summary": build_attempt_summary(detail),
        "pedagogy_refs": load_pedagogy_refs(context_root=context_root, subject_context=subject_context),
    }
    bundle["context_snapshot"] = build_context_snapshot(
        marking_result_path=artifact_path,
        amendment_state=amendment_state,
        review_state_updated_at=review_state_updated_at,
        resolved_question_row=question,
    )
    bundle["prompt_text"] = render_context_bundle_prompt(bundle)
    return bundle


def build_context_bundle(
    *,
    attempt_id: str,
    result_id: str,
    context_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
) -> dict[str, Any]:
    """Assemble tutor context via get_attempt_detail (DB-first marking, amendments, review notes)."""
    try:
        detail = get_attempt_detail(
            attempt_id=attempt_id,
            context_root=context_root,
            manager=manager,
            review_repo=review_repo,
        )
    except AttemptNotFoundError as exc:
        raise TutorChatContextError(str(exc)) from exc

    if detail.get("marking_status") != "marked":
        raise TutorChatContextError("attempt is not marked")

    attempt = detail.get("attempt") if isinstance(detail.get("attempt"), dict) else {}
    student_id = attempt.get("student_id")
    subject_context = attempt.get("subject_context")
    marking = detail.get("marking_result") if isinstance(detail.get("marking_result"), dict) else {}
    artifact_path = marking.get("artifact_path") if isinstance(marking.get("artifact_path"), str) else ""
    artifact_stem = Path(artifact_path).stem if artifact_path else ""

    review_state_updated_at = None
    if (
        isinstance(student_id, str)
        and isinstance(subject_context, str)
        and artifact_stem
    ):
        raw_review = review_repo.load_raw_review_state(
            student_id=student_id,
            subject_context=subject_context,
            artifact_stem=artifact_stem,
        )
        if isinstance(raw_review, dict) and isinstance(raw_review.get("updated_at"), str):
            review_state_updated_at = raw_review["updated_at"]

    return build_context_bundle_from_detail(
        detail=detail,
        result_id=result_id,
        context_root=context_root,
        review_state_updated_at=review_state_updated_at,
    )
