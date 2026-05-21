from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ai_study_buddy.marking import (
    build_marking_run_paths,
    find_marking_artifacts_for_attempt,
    resolve_marking_context,
    validate_marking_artifact_dict,
    write_marking_artifact,
)
from ai_study_buddy.marking.assets.paths import marking_asset_rel_path_from_artifact_path
from ai_study_buddy.marking.core.artifact_paths import slugify_student
from ai_study_buddy.marking.core.artifact_schema import compute_percentage
from ai_study_buddy.marking.core.models import (
    ArtifactQuestionResult,
    ArtifactSummary,
    Diagnosis,
    GenerationMeta,
    MarkingArtifact,
    MarkingArtifactContext,
    ReviewMeta,
)
from ai_study_buddy.marking.file_question_info import (
    QuestionSectionsNotFoundError,
    iter_questions_ordered,
    iter_sections_ordered,
    question_page_map_from_question_sections,
    resolve_question_sections_for_template_file,
    section_hint_strings_for_context,
    validate_question_sections_dict,
)
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.pdf_file_manager.pdf_file_manager import (
    PdfFile,
    PdfFileManager,
    normalize_pdf_display_name,
)
from ai_study_buddy.marking.workflows.v3_helpers import (
    MergeResult,
    build_authoritative_marks_by_question,
    find_human_note_policy_violations,
    find_language_violations,
    merge_phase2_phase3_rows,
    select_phase3_question_ids,
)

V3_MODE_BOOK_PRACTICE = "book-practice"
V3_MODE_EMBEDDED_ANSWER = "embedded-answer"
V3_MODE_TEACHER_ANNOTATED = "teacher-annotated"
V3_MODE_REDO_PRACTICE = "redo-practice"


class V3WorkflowError(ValueError):
    pass


@dataclass(frozen=True)
class V3InputRequest:
    attempt_file_id_or_path: str | None = None
    student_name: str | None = None
    file_name: str | None = None


@dataclass(frozen=True)
class V3ModeSignals:
    embedded_answer_requested: bool = False
    redo_practice_requested: bool = False
    has_linked_template: bool = True
    has_mapped_answer_range: bool = True


@dataclass(frozen=True)
class RedoPracticeReference:
    marking_result_path: str
    marking_result_payload: Mapping[str, Any]
    amendment_payload: Mapping[str, Any] | None
    artifact_stem: str


@dataclass(frozen=True)
class QuestionSectionsAuthority:
    payload: Mapping[str, object]
    sections: tuple[Mapping[str, object], ...]
    questions: tuple[Mapping[str, object], ...]
    question_page_map: Mapping[str, Mapping[str, object]]
    section_hints: tuple[str, ...]
    source: str


@dataclass(frozen=True)
class V3ContextResolutionDebug:
    attempt_input: str
    resolved_attempt_file_id: str
    resolved_attempt_file_path: str
    resolved_template_file_id: str | None
    resolved_template_file_path: str | None
    marking_mode: str
    context_resolution: Mapping[str, Any] | None


@dataclass(frozen=True)
class V3BundleCandidate:
    bundle_root: Path
    finalized: bool
    run_state: Mapping[str, Any] | None


@dataclass(frozen=True)
class V3BundleSelection:
    bundle_root: Path
    artifact_json_path: Path
    marking_asset_rel: str
    resumed_existing: bool


def _is_path_like(value: str) -> bool:
    return "/" in value or "\\" in value or value.lower().endswith(".pdf")


def resolve_attempt_input_to_pdf_file(
    *,
    manager: PdfFileManager,
    request: V3InputRequest,
) -> PdfFile:
    direct = request.attempt_file_id_or_path
    if isinstance(direct, str) and direct.strip():
        raw = direct.strip()
        if _is_path_like(raw):
            path = Path(raw).resolve()
            if not path.exists():
                raise V3WorkflowError(f"Attempt path does not exist: {path}")
            existing = manager.get_file_by_path(path)
            if existing is not None:
                return existing
            return manager.register_file(path)
        file_obj = manager.get_file(raw)
        if file_obj is None:
            raise V3WorkflowError(f"Attempt file_id not found: {raw}")
        return file_obj

    if not (request.student_name and request.file_name):
        raise V3WorkflowError("Provide attempt_file_id_or_path, or student_name + file_name")

    students = [s for s in manager.list_students() if s.name.casefold() == request.student_name.casefold()]
    if not students:
        raise V3WorkflowError(f"Student not found by name: {request.student_name}")
    if len(students) > 1:
        ids = ", ".join(sorted(s.id for s in students))
        raise V3WorkflowError(f"Multiple students matched name {request.student_name!r}: {ids}")
    student_id = students[0].id

    candidates = manager.find_files(
        query=request.file_name,
        student_id=student_id,
        file_type="main",
        is_template=False,
    )
    exact = [f for f in candidates if f.name.casefold() == request.file_name.casefold()]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        ids = ", ".join(sorted(f.id for f in exact))
        raise V3WorkflowError(f"Multiple completion files matched student+filename: {ids}")
    raise V3WorkflowError(
        f"No completion file matched student_name={request.student_name!r}, file_name={request.file_name!r}"
    )


def resolve_v3_marking_context(
    *,
    manager: PdfFileManager,
    request: V3InputRequest,
    question_request: str | None = None,
    question_refs: Sequence[str] | None = None,
    section_hint: str | None = None,
    manual_answer_pages: tuple[int, int] | None = None,
    marking_mode: str | None = None,
):
    attempt_file = resolve_attempt_input_to_pdf_file(manager=manager, request=request)
    return resolve_marking_context(
        attempt_file_id_or_path=attempt_file.id,
        question_request=question_request,
        question_refs=list(question_refs) if question_refs else None,
        section_hint=section_hint,
        manual_answer_pages=manual_answer_pages,
        marking_mode=marking_mode,
        manager=manager,
    )


def build_context_resolution_debug_record(
    *,
    request: V3InputRequest,
    context,
) -> V3ContextResolutionDebug:
    if request.attempt_file_id_or_path and request.attempt_file_id_or_path.strip():
        attempt_input = request.attempt_file_id_or_path.strip()
    elif request.student_name and request.file_name:
        attempt_input = f"{request.student_name}::{request.file_name}"
    else:
        attempt_input = "<unknown-input>"

    context_resolution = None
    raw_ctx_res = getattr(context, "context_resolution", None)
    if raw_ctx_res is not None:
        if hasattr(raw_ctx_res, "__dict__"):
            context_resolution = dict(raw_ctx_res.__dict__)
        elif isinstance(raw_ctx_res, Mapping):
            context_resolution = dict(raw_ctx_res)

    return V3ContextResolutionDebug(
        attempt_input=attempt_input,
        resolved_attempt_file_id=context.attempt_file_id,
        resolved_attempt_file_path=context.attempt_file_path,
        resolved_template_file_id=context.template_file_id,
        resolved_template_file_path=context.template_file_path,
        marking_mode=context.marking_mode,
        context_resolution=context_resolution,
    )


def write_context_resolution_debug_artifact(
    *,
    bundle_root: Path,
    record: V3ContextResolutionDebug,
) -> Path:
    debug_dir = bundle_root / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    out_path = debug_dir / "context_resolution_provenance.json"
    payload = {
        "attempt_input": record.attempt_input,
        "resolved_attempt_file_id": record.resolved_attempt_file_id,
        "resolved_attempt_file_path": record.resolved_attempt_file_path,
        "resolved_template_file_id": record.resolved_template_file_id,
        "resolved_template_file_path": record.resolved_template_file_path,
        "marking_mode": record.marking_mode,
        "context_resolution": record.context_resolution,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return out_path


def _run_state_path(bundle_root: Path) -> Path:
    return bundle_root / "debug" / "run_state.json"


def read_run_state(*, bundle_root: Path) -> Mapping[str, Any] | None:
    path = _run_state_path(bundle_root)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, Mapping) else None


def write_run_state(
    *,
    bundle_root: Path,
    state: str,
    metadata: Mapping[str, Any] | None = None,
) -> Path:
    debug_dir = bundle_root / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    out = _run_state_path(bundle_root)
    payload: dict[str, Any] = {"state": state, "updated_at": _utc_now_iso()}
    if metadata:
        payload["metadata"] = dict(metadata)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return out


def list_attempt_bundle_candidates(
    *,
    context_root: Path,
    attempt_file_path: str | Path,
    student_id: str | None,
    student_name: str | None,
    subject_context: str,
) -> tuple[V3BundleCandidate, ...]:
    student_slug = slugify_student(student_id, student_name)
    root = (Path(context_root) / "marking_assets" / student_slug / subject_context).resolve()
    if not root.exists():
        return ()

    stem = normalize_pdf_display_name(attempt_file_path)
    prefix = f"{stem}__"
    out: list[V3BundleCandidate] = []
    for child in root.iterdir():
        if not child.is_dir() or not child.name.startswith(prefix):
            continue
        finalized = (child / "debug" / "phasee_finalization_trace.json").exists()
        out.append(
            V3BundleCandidate(
                bundle_root=child,
                finalized=finalized,
                run_state=read_run_state(bundle_root=child),
            )
        )
    out.sort(key=lambda item: item.bundle_root.name)
    return tuple(out)


def find_latest_in_progress_bundle(
    *,
    context_root: Path,
    attempt_file_path: str | Path,
    student_id: str | None,
    student_name: str | None,
    subject_context: str,
) -> Path | None:
    candidates = list_attempt_bundle_candidates(
        context_root=context_root,
        attempt_file_path=attempt_file_path,
        student_id=student_id,
        student_name=student_name,
        subject_context=subject_context,
    )
    in_progress = [c for c in candidates if not c.finalized]
    if not in_progress:
        return None
    return in_progress[-1].bundle_root


def collect_stale_partial_bundle_paths(
    *,
    context_root: Path,
    attempt_file_path: str | Path,
    student_id: str | None,
    student_name: str | None,
    subject_context: str,
    keep_bundle_root: Path | None,
) -> tuple[Path, ...]:
    keep = keep_bundle_root.resolve() if keep_bundle_root is not None else None
    candidates = list_attempt_bundle_candidates(
        context_root=context_root,
        attempt_file_path=attempt_file_path,
        student_id=student_id,
        student_name=student_name,
        subject_context=subject_context,
    )
    out: list[Path] = []
    for c in candidates:
        if c.finalized:
            continue
        resolved = c.bundle_root.resolve()
        if keep is not None and resolved == keep:
            continue
        out.append(resolved)
    return tuple(out)


def move_bundle_to_trash(*, bundle_root: Path) -> Path:
    src = Path(bundle_root).resolve()
    if not src.exists():
        return src
    trash_root = Path.home() / ".Trash"
    trash_root.mkdir(parents=True, exist_ok=True)
    dest = trash_root / src.name
    if dest.exists():
        suffix = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest = trash_root / f"{src.name}__{suffix}"
    src.rename(dest)
    return dest


def _derive_artifact_path_for_bundle(
    *,
    context_root: Path,
    bundle_root: Path,
    student_id: str | None,
    student_name: str | None,
    subject_context: str,
) -> Path:
    student_slug = slugify_student(student_id, student_name)
    return (
        Path(context_root).resolve()
        / "marking_results"
        / student_slug
        / subject_context
        / f"{bundle_root.name}.json"
    )


def resolve_or_create_bundle_for_v3_run(
    *,
    context_root: Path,
    attempt_file_path: str | Path,
    student_id: str | None,
    student_name: str | None,
    subject_context: str,
    run_marked_at: str,
    allow_resume: bool = True,
) -> V3BundleSelection:
    root = Path(context_root).resolve()
    resumed = False
    bundle_root: Path
    artifact_json_path: Path
    marking_asset_rel: str

    if allow_resume:
        existing = find_latest_in_progress_bundle(
            context_root=root,
            attempt_file_path=attempt_file_path,
            student_id=student_id,
            student_name=student_name,
            subject_context=subject_context,
        )
        if existing is not None:
            bundle_root = existing.resolve()
            artifact_json_path = _derive_artifact_path_for_bundle(
                context_root=root,
                bundle_root=bundle_root,
                student_id=student_id,
                student_name=student_name,
                subject_context=subject_context,
            )
            marking_asset_rel = str(bundle_root.relative_to(root)).replace("\\", "/")
            resumed = True
            bundle_root.mkdir(parents=True, exist_ok=True)
            return V3BundleSelection(
                bundle_root=bundle_root,
                artifact_json_path=artifact_json_path,
                marking_asset_rel=marking_asset_rel,
                resumed_existing=resumed,
            )

    artifact_json_path, marking_asset_rel, bundle_root = build_marking_run_paths(
        attempt_file_path=attempt_file_path,
        student_id=student_id,
        student_name=student_name,
        subject_context=subject_context,
        marked_at=run_marked_at,
        context_root=root,
    )
    bundle_root = bundle_root.resolve()
    bundle_root.mkdir(parents=True, exist_ok=True)
    return V3BundleSelection(
        bundle_root=bundle_root,
        artifact_json_path=artifact_json_path,
        marking_asset_rel=marking_asset_rel,
        resumed_existing=resumed,
    )


def cleanup_stale_partials_for_v3_run(
    *,
    context_root: Path,
    attempt_file_path: str | Path,
    student_id: str | None,
    student_name: str | None,
    subject_context: str,
    keep_bundle_root: Path,
) -> tuple[Path, ...]:
    stale = collect_stale_partial_bundle_paths(
        context_root=Path(context_root).resolve(),
        attempt_file_path=attempt_file_path,
        student_id=student_id,
        student_name=student_name,
        subject_context=subject_context,
        keep_bundle_root=keep_bundle_root,
    )
    moved: list[Path] = []
    for candidate in stale:
        moved.append(move_bundle_to_trash(bundle_root=candidate))
    return tuple(moved)


def resolve_v3_mode(signals: V3ModeSignals) -> str:
    if not signals.has_linked_template:
        raise V3WorkflowError("v3 requires linked template; no bypass override is allowed")
    if signals.redo_practice_requested and signals.embedded_answer_requested:
        raise V3WorkflowError("Ambiguous mode: both redo-practice and embedded-answer were requested")
    if signals.redo_practice_requested:
        return V3_MODE_REDO_PRACTICE
    if signals.embedded_answer_requested:
        return V3_MODE_EMBEDDED_ANSWER
    if signals.has_mapped_answer_range:
        return V3_MODE_BOOK_PRACTICE
    return V3_MODE_TEACHER_ANNOTATED


def require_no_user_asset_contradiction(*, has_contradiction: bool) -> None:
    if has_contradiction:
        raise V3WorkflowError("User direction contradicts available assets; stop and confirm with user")


def resolve_redo_practice_reference(
    *,
    manager: PdfFileManager,
    attempt_file_id_or_path: str,
    context_root: Path,
) -> RedoPracticeReference:
    normalized_context_root = context_root.resolve()
    refs = find_marking_artifacts_for_attempt(
        attempt_file_id_or_path,
        manager=manager,
        context_root=normalized_context_root,
        match_condition="json_only",
    )
    if not refs:
        raise V3WorkflowError("redo-practice requested but no prior marking artifacts were found for attempt")

    # artifacts are returned newest-first; redo-practice golden should be first/original attempt result
    golden = refs[-1]
    try:
        payload = json.loads(golden.marking_result_json.read_text(encoding="utf-8"))
    except Exception as exc:
        raise V3WorkflowError(f"Unable to load redo-practice golden artifact: {golden.marking_result_json}") from exc
    if not isinstance(payload, dict):
        raise V3WorkflowError(f"Redo-practice golden artifact must be a JSON object: {golden.marking_result_json}")

    context = payload.get("context")
    if not isinstance(context, dict):
        raise V3WorkflowError("Redo-practice golden artifact missing context object")
    student_id = context.get("student_id")
    subject_context = context.get("subject_context")
    if not isinstance(student_id, str) or not student_id.strip():
        raise V3WorkflowError("Redo-practice golden artifact missing context.student_id")
    if not isinstance(subject_context, str) or not subject_context.strip():
        raise V3WorkflowError("Redo-practice golden artifact missing context.subject_context")

    artifact_stem = golden.marking_result_json.stem
    repo = StudentReviewRepository(context_root=normalized_context_root)
    amendment = repo.load_raw_amendment(
        student_id=student_id.strip(),
        subject_context=subject_context.strip(),
        artifact_stem=artifact_stem,
    )
    if amendment is None:
        amendment_path = repo.amendment_path(
            student_id=student_id.strip(),
            subject_context=subject_context.strip(),
            artifact_stem=artifact_stem,
        )
        if amendment_path.exists():
            try:
                loaded = json.loads(amendment_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    amendment = loaded
            except Exception:
                amendment = None
    return RedoPracticeReference(
        marking_result_path=str(golden.marking_result_json),
        marking_result_payload=payload,
        amendment_payload=amendment,
        artifact_stem=artifact_stem,
    )


def resolve_authoritative_question_sections_for_context(*, template_file) -> dict[str, object]:
    authority = resolve_question_sections_authority(
        template_file=template_file,
        detector_fallback=None,
    )
    return dict(authority.payload)


def require_template_link_for_v3(*, template_file) -> None:
    if template_file is None:
        raise V3WorkflowError("v3 requires linked template; no completion-only structure inference is allowed")


def resolve_question_sections_authority(
    *,
    template_file,
    detector_fallback: Callable[[Any], Mapping[str, object] | None] | None = None,
    detect_divergence: bool = True,
) -> QuestionSectionsAuthority:
    require_template_link_for_v3(template_file=template_file)
    try:
        source = resolve_question_sections_for_template_file(
            template_file=template_file,
            detect_divergence=detect_divergence,
        )
        payload = source["payload"]
        source_label = f"lookup:{source.get('source_kind', 'unknown')}"
    except QuestionSectionsNotFoundError:
        if detector_fallback is None:
            raise V3WorkflowError(
                "No authoritative template question_sections found; detector fallback orchestration required"
            )
        generated = detector_fallback(template_file)
        if generated is None:
            # Fallback may have persisted artifact; resolve again through reader path.
            source = resolve_question_sections_for_template_file(
                template_file=template_file,
                detect_divergence=detect_divergence,
            )
            payload = source["payload"]
            source_label = f"detector-fallback:{source.get('source_kind', 'unknown')}"
        else:
            validate_question_sections_dict(dict(generated))
            payload = dict(generated)
            source_label = "detector-fallback:in-memory"

    sections = tuple(iter_sections_ordered(payload))
    questions = tuple(iter_questions_ordered(payload))
    page_map = question_page_map_from_question_sections(payload)
    hints = section_hint_strings_for_context(payload)
    return QuestionSectionsAuthority(
        payload=payload,
        sections=sections,
        questions=questions,
        question_page_map=page_map,
        section_hints=hints,
        source=source_label,
    )


@dataclass(frozen=True)
class V3FinalizePrepResult:
    merged_rows: tuple[dict[str, Any], ...]
    phase3_question_ids: tuple[str, ...]
    language_violations: tuple[str, ...]
    human_note_violations: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class Phase2SectionInput:
    section_index: int
    section_label: str
    question_ids: tuple[str, ...]
    page_numbers: tuple[int, ...]
    stem_page_range: Mapping[str, int] | None
    questions_page_range: Mapping[str, int]
    answers_page_range: Mapping[str, int] | None
    question_rows: tuple[Mapping[str, object], ...]


@dataclass(frozen=True)
class Phase2SectionExecutionResult:
    section_index: int
    rows: tuple[dict[str, Any], ...]
    attempts: int
    succeeded: bool
    error: str | None = None


@dataclass(frozen=True)
class Phase2ExecutionSummary:
    aggregated_rows: tuple[dict[str, Any], ...]
    retry_targets: tuple[str, ...]
    section_results: tuple[Phase2SectionExecutionResult, ...]
    trace_path: Path


@dataclass(frozen=True)
class Phase3QuestionInput:
    question_id: str
    page_numbers: tuple[int, ...]
    section_index: int


@dataclass(frozen=True)
class Phase3QuestionExecutionResult:
    question_id: str
    row: dict[str, Any] | None
    attempts: int
    succeeded: bool
    error: str | None = None


@dataclass(frozen=True)
class Phase3ExecutionSummary:
    remediated_rows: tuple[dict[str, Any], ...]
    results: tuple[Phase3QuestionExecutionResult, ...]
    trace_path: Path


@dataclass(frozen=True)
class PhaseEFinalizeResult:
    artifact_path: Path
    debug_trace_path: Path
    telemetry: Mapping[str, Any]


def _pages_from_range(range_map: Mapping[str, int] | None) -> list[int]:
    if range_map is None:
        return []
    start = range_map.get("start_page")
    end = range_map.get("end_page")
    if not isinstance(start, int) or not isinstance(end, int):
        return []
    if end < start:
        return []
    return list(range(start, end + 1))


def build_phase2_section_inputs(authority: QuestionSectionsAuthority) -> tuple[Phase2SectionInput, ...]:
    by_section_questions: dict[int, list[Mapping[str, object]]] = {}
    for qrow in authority.questions:
        idx = qrow.get("section_index")
        if isinstance(idx, int):
            by_section_questions.setdefault(idx, []).append(qrow)

    out: list[Phase2SectionInput] = []
    for srow in authority.sections:
        section_index = int(srow["section_index"])
        question_rows = tuple(by_section_questions.get(section_index, []))
        question_ids = tuple(
            q["question_index"]
            for q in question_rows
            if isinstance(q.get("question_index"), str) and q["question_index"].strip()
        )
        pages: set[int] = set()
        for page in _pages_from_range(srow.get("stem_page_range")):
            pages.add(page)
        for page in _pages_from_range(srow.get("questions_page_range")):
            pages.add(page)
        for page in _pages_from_range(srow.get("answers_page_range")):
            pages.add(page)
        out.append(
            Phase2SectionInput(
                section_index=section_index,
                section_label=f"S{section_index + 1}: {srow['question_type']}",
                question_ids=question_ids,
                page_numbers=tuple(sorted(pages)),
                stem_page_range=srow.get("stem_page_range"),
                questions_page_range=srow["questions_page_range"],
                answers_page_range=srow.get("answers_page_range"),
                question_rows=question_rows,
            )
        )
    return tuple(out)


def plan_phase2_batches(
    section_inputs: Sequence[Phase2SectionInput],
    *,
    max_concurrency: int = 5,
) -> tuple[tuple[Phase2SectionInput, ...], ...]:
    cap = max(1, int(max_concurrency))
    batches: list[tuple[Phase2SectionInput, ...]] = []
    current: list[Phase2SectionInput] = []
    for section_input in section_inputs:
        current.append(section_input)
        if len(current) >= cap:
            batches.append(tuple(current))
            current = []
    if current:
        batches.append(tuple(current))
    return tuple(batches)


def aggregate_phase2_section_rows(
    section_rows: Mapping[int, Sequence[Mapping[str, Any]]],
    *,
    authority: QuestionSectionsAuthority,
) -> tuple[dict[str, Any], ...]:
    expected_order = [q["question_index"] for q in authority.questions if isinstance(q.get("question_index"), str)]
    section_by_question: dict[str, int] = {}
    for q in authority.questions:
        qid = q.get("question_index")
        section_index = q.get("section_index")
        if isinstance(qid, str) and isinstance(section_index, int):
            section_by_question[qid] = section_index

    by_qid: dict[str, dict[str, Any]] = {}
    for section_index, rows in section_rows.items():
        for row in rows:
            qid = row.get("question_id") or row.get("result_id")
            if not isinstance(qid, str) or not qid.strip():
                continue
            qid = qid.strip()
            expected_section = section_by_question.get(qid)
            if expected_section is None or expected_section != section_index:
                raise V3WorkflowError(
                    f"Phase 2 section output contains out-of-section question_id={qid} (section_index={section_index})"
                )
            by_qid[qid] = dict(row)

    ordered: list[dict[str, Any]] = []
    for qid in expected_order:
        if qid in by_qid:
            ordered.append(by_qid[qid])
    return tuple(ordered)


def build_phase2_retry_targets(
    rows: Sequence[Mapping[str, Any]],
    *,
    english_required: bool,
) -> tuple[str, ...]:
    bad_qids: set[str] = set(find_language_violations(rows, english_required=english_required))
    for item in find_human_note_policy_violations(rows):
        qid = item.get("question_id")
        if isinstance(qid, str) and qid.strip():
            bad_qids.add(qid.strip())
    return tuple(sorted(bad_qids))


def write_phase2_execution_trace(
    *,
    bundle_root: Path,
    section_results: Sequence[Phase2SectionExecutionResult],
) -> Path:
    debug_dir = bundle_root / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    out = debug_dir / "phase2_section_execution_trace.json"
    payload = {
        "sections": [
            {
                "section_index": r.section_index,
                "succeeded": r.succeeded,
                "attempts": r.attempts,
                "error": r.error,
                "row_count": len(r.rows),
            }
            for r in section_results
        ]
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return out


def execute_phase2_section_runtime(
    *,
    section_inputs: Sequence[Phase2SectionInput],
    authority: QuestionSectionsAuthority,
    worker: Callable[[Phase2SectionInput], Sequence[Mapping[str, Any]]],
    bundle_root: Path,
    english_required: bool,
    max_concurrency: int = 5,
    max_retries: int = 1,
) -> Phase2ExecutionSummary:
    _ = plan_phase2_batches(section_inputs, max_concurrency=max_concurrency)
    successful: dict[int, tuple[dict[str, Any], ...]] = {}
    results: list[Phase2SectionExecutionResult] = []

    for section_input in section_inputs:
        last_error: str | None = None
        rows: tuple[dict[str, Any], ...] = ()
        attempts = 0
        for _attempt in range(max_retries + 1):
            attempts += 1
            try:
                produced = worker(section_input)
                rows = tuple(dict(r) for r in produced)
                successful[section_input.section_index] = rows
                last_error = None
                break
            except Exception as exc:
                last_error = str(exc)
        succeeded = section_input.section_index in successful
        results.append(
            Phase2SectionExecutionResult(
                section_index=section_input.section_index,
                rows=successful.get(section_input.section_index, ()),
                attempts=attempts,
                succeeded=succeeded,
                error=last_error if not succeeded else None,
            )
        )

    failed = [r for r in results if not r.succeeded]
    if failed:
        detail = ", ".join(f"S{r.section_index + 1}: {r.error or 'unknown'}" for r in failed)
        raise V3WorkflowError(f"Phase 2 section runtime failed after retries: {detail}")

    aggregated = aggregate_phase2_section_rows(successful, authority=authority)
    retry_targets = build_phase2_retry_targets(aggregated, english_required=english_required)
    trace = write_phase2_execution_trace(bundle_root=bundle_root, section_results=results)
    return Phase2ExecutionSummary(
        aggregated_rows=aggregated,
        retry_targets=retry_targets,
        section_results=tuple(results),
        trace_path=trace,
    )


def build_phase3_question_inputs(
    *,
    authority: QuestionSectionsAuthority,
    phase2_rows: Sequence[Mapping[str, Any]],
) -> tuple[Phase3QuestionInput, ...]:
    targets = set(select_phase3_question_ids(phase2_rows))
    if not targets:
        return ()
    questions = [q for q in authority.questions if isinstance(q.get("question_index"), str)]
    by_qid = {q["question_index"]: q for q in questions}
    section_map = {int(s["section_index"]): s for s in authority.sections}

    out: list[Phase3QuestionInput] = []
    for idx, q in enumerate(questions):
        qid = q["question_index"]
        if qid not in targets:
            continue
        section_index = int(q["section_index"])
        srow = section_map[section_index]
        start = q.get("start_page")
        if not isinstance(start, int):
            raise V3WorkflowError(f"Phase 3 requires start_page for question_id={qid}")
        next_start: int | None = None
        if idx + 1 < len(questions):
            nxt = questions[idx + 1]
            ns = nxt.get("start_page")
            if isinstance(ns, int):
                next_start = ns
        if next_start is not None:
            end = max(start, next_start - 1)
        else:
            qpr = srow["questions_page_range"]
            end = int(qpr["end_page"])
            if end < start:
                end = start
        pages: set[int] = set(range(start, end + 1))
        for p in _pages_from_range(srow.get("stem_page_range")):
            pages.add(p)
        for p in _pages_from_range(srow.get("answers_page_range")):
            pages.add(p)
        out.append(
            Phase3QuestionInput(
                question_id=qid,
                page_numbers=tuple(sorted(pages)),
                section_index=section_index,
            )
        )
    return tuple(out)


def plan_phase3_batches(
    question_inputs: Sequence[Phase3QuestionInput],
    *,
    max_concurrency: int = 5,
) -> tuple[tuple[Phase3QuestionInput, ...], ...]:
    cap = max(1, int(max_concurrency))
    batches: list[tuple[Phase3QuestionInput, ...]] = []
    current: list[Phase3QuestionInput] = []
    for item in question_inputs:
        current.append(item)
        if len(current) >= cap:
            batches.append(tuple(current))
            current = []
    if current:
        batches.append(tuple(current))
    return tuple(batches)


def write_phase3_execution_trace(
    *,
    bundle_root: Path,
    results: Sequence[Phase3QuestionExecutionResult],
) -> Path:
    debug_dir = bundle_root / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    out = debug_dir / "phase3_question_execution_trace.json"
    payload = {
        "questions": [
            {
                "question_id": r.question_id,
                "succeeded": r.succeeded,
                "attempts": r.attempts,
                "error": r.error,
            }
            for r in results
        ]
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return out


def execute_phase3_question_runtime(
    *,
    question_inputs: Sequence[Phase3QuestionInput],
    worker: Callable[[Phase3QuestionInput], Mapping[str, Any]],
    bundle_root: Path,
    max_concurrency: int = 5,
    max_retries: int = 1,
) -> Phase3ExecutionSummary:
    _ = plan_phase3_batches(question_inputs, max_concurrency=max_concurrency)
    successes: dict[str, dict[str, Any]] = {}
    results: list[Phase3QuestionExecutionResult] = []
    for qinput in question_inputs:
        attempts = 0
        last_error: str | None = None
        for _attempt in range(max_retries + 1):
            attempts += 1
            try:
                row = dict(worker(qinput))
                qid = row.get("question_id") or qinput.question_id
                row["question_id"] = qid
                successes[qinput.question_id] = row
                last_error = None
                break
            except Exception as exc:
                last_error = str(exc)
        succeeded = qinput.question_id in successes
        results.append(
            Phase3QuestionExecutionResult(
                question_id=qinput.question_id,
                row=successes.get(qinput.question_id),
                attempts=attempts,
                succeeded=succeeded,
                error=last_error if not succeeded else None,
            )
        )
    failed = [r for r in results if not r.succeeded]
    if failed:
        detail = ", ".join(f"{r.question_id}: {r.error or 'unknown'}" for r in failed)
        raise V3WorkflowError(f"Phase 3 runtime failed after retries: {detail}")
    ordered_rows = tuple(successes[q.question_id] for q in question_inputs if q.question_id in successes)
    trace = write_phase3_execution_trace(bundle_root=bundle_root, results=results)
    return Phase3ExecutionSummary(remediated_rows=ordered_rows, results=tuple(results), trace_path=trace)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_subject_context_from_runtime_context(context: Any) -> str:
    explicit = getattr(context, "subject_context", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    attempt_file_id = getattr(context, "attempt_file_id", None)
    template_file_id = getattr(context, "template_file_id", None)
    attempt_file_path = getattr(context, "attempt_file_path", None)
    template_file_path = getattr(context, "template_file_path", None)
    raise V3WorkflowError(
        "Unable to resolve subject_context from runtime context; expected resolved "
        f"context.subject_context. attempt_file_id={attempt_file_id!r}, template_file_id={template_file_id!r}, "
        f"attempt_file_path={attempt_file_path!r}, template_file_path={template_file_path!r}"
    )


def _build_marking_artifact_from_rows(
    *,
    context,
    rows: Sequence[Mapping[str, Any]],
    mode: str,
    notes: str | None,
    telemetry: Mapping[str, Any],
    created_at: str,
) -> MarkingArtifact:
    subject_context = _resolve_subject_context_from_runtime_context(context)
    artifact_context = MarkingArtifactContext.from_marking_context(
        context,
        subject_context=subject_context,
        resolved_at=created_at,
    )
    question_results: list[ArtifactQuestionResult] = []
    total = 0.0
    earned = 0.0
    page_map: list[Any] = []
    from ai_study_buddy.marking.core.models import QuestionPageMapEntry

    for row in rows:
        qid = str(row.get("result_id") or row.get("question_id") or "").strip()
        if not qid:
            continue
        max_marks = float(row.get("max_marks", 0))
        earned_marks = float(row.get("earned_marks", 0))
        outcome = str(row.get("outcome", "wrong"))
        diagnosis_obj = row.get("diagnosis") if isinstance(row.get("diagnosis"), Mapping) else {}
        question_results.append(
            ArtifactQuestionResult(
                result_id=qid,
                max_marks=max_marks,
                earned_marks=earned_marks,
                outcome=outcome,
                student_answer=row.get("student_answer"),
                correct_answer=row.get("correct_answer"),
                scoring_status="counted",
                error_tags=tuple(row.get("error_tags", ())) if isinstance(row.get("error_tags"), (list, tuple)) else (),
                skill_tags=(),
                diagnosis=Diagnosis(
                    mistake_type=diagnosis_obj.get("mistake_type"),
                    reasoning=diagnosis_obj.get("reasoning"),
                    confidence=diagnosis_obj.get("confidence"),
                ),
                human_note=row.get("human_note"),
            )
        )
        total += max_marks
        earned += earned_marks
        aps = row.get("attempt_page_start")
        if isinstance(aps, int) and aps >= 1:
            page_map.append(QuestionPageMapEntry(result_id=qid, attempt_page_start=aps, confidence="high", source="script_inferred"))

    artifact_context = MarkingArtifactContext(
        **{**artifact_context.__dict__, "question_page_map": tuple(page_map), "is_partial": False}
    )
    summary = ArtifactSummary(
        total_marks=total,
        earned_marks=earned,
        percentage=compute_percentage(earned, total),
        overall_assessment="needs_review" if total and earned < total else "good",
        human_note=None,
    )
    return MarkingArtifact(
        schema_version="marking_result.v1.6",
        created_at=created_at,
        updated_at=created_at,
        context=artifact_context,
        summary=summary,
        question_results=tuple(question_results),
        review_meta=ReviewMeta(updated_at=created_at, updated_by="v3-orchestrator"),
        generation=GenerationMeta(produced_by="mark-student-work-multi-agent-v3", mode=mode, notes=notes, telemetry=dict(telemetry)),
    )


def finalize_phase_e_artifact(
    *,
    context,
    merged_rows: Sequence[Mapping[str, Any]],
    mode: str,
    bundle_root: Path,
    context_root: Path,
    deep_dive_count: int,
    phase2_subagents: int,
    run_start_iso: str | None = None,
) -> PhaseEFinalizeResult:
    created_at = run_start_iso or _utc_now_iso()
    telemetry = {
        "fast_pass_count": max(0, int(phase2_subagents)),
        "deep_dive_count": max(0, int(deep_dive_count)),
        "total_duration_seconds": None,
    }
    try:
        artifact = _build_marking_artifact_from_rows(
            context=context,
            rows=merged_rows,
            mode=mode,
            notes="phase-e-finalize",
            telemetry=telemetry,
            created_at=created_at,
        )
    except V3WorkflowError as exc:
        debug_dir = bundle_root / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        failure_path = debug_dir / "phasee_subject_context_failure.json"
        failure_payload = {
            "error": str(exc),
            "attempt_file_id": getattr(context, "attempt_file_id", None),
            "attempt_file_path": getattr(context, "attempt_file_path", None),
            "template_file_id": getattr(context, "template_file_id", None),
            "template_file_path": getattr(context, "template_file_path", None),
            "answer_file_id": getattr(context, "answer_file_id", None),
            "answer_file_path": getattr(context, "answer_file_path", None),
            "subject_context": getattr(context, "subject_context", None),
        }
        failure_path.write_text(json.dumps(failure_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        raise
    bundle_root = bundle_root.resolve()
    context_root = Path(context_root).resolve()
    subject_context = _resolve_subject_context_from_runtime_context(context)
    artifact_path = _derive_artifact_path_for_bundle(
        context_root=context_root,
        bundle_root=bundle_root,
        student_id=getattr(context, "student_id", None),
        student_name=getattr(context, "student_name", None),
        subject_context=subject_context,
    )
    marking_asset_rel = marking_asset_rel_path_from_artifact_path(
        artifact_json_path=artifact_path,
        context_root=context_root,
    )
    if marking_asset_rel is None:
        raise V3WorkflowError(
            f"Unable to derive marking_asset path for bundle {bundle_root.name!r} under {context_root}"
        )
    artifact = replace(
        artifact,
        context=replace(artifact.context, marking_asset=marking_asset_rel),
    )
    artifact_path = write_marking_artifact(
        artifact,
        context_root=context_root,
        output_path=artifact_path,
    )

    debug_dir = bundle_root / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    trace_path = debug_dir / "phasee_finalization_trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "artifact_path": str(artifact_path),
                "mode": mode,
                "deep_dive_count": deep_dive_count,
                "phase2_subagents": phase2_subagents,
                "row_count": len(merged_rows),
            },
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return PhaseEFinalizeResult(
        artifact_path=artifact_path,
        debug_trace_path=trace_path,
        telemetry=telemetry,
    )


def prepare_finalize_rows(
    *,
    question_sections_payload: Mapping[str, object],
    phase2_rows: Sequence[Mapping[str, Any]],
    phase3_rows: Sequence[Mapping[str, Any]],
    english_required: bool,
) -> V3FinalizePrepResult:
    marks = build_authoritative_marks_by_question(question_sections_payload)
    authority_page_map = question_page_map_from_question_sections(question_sections_payload)
    merged: MergeResult = merge_phase2_phase3_rows(
        phase2_rows,
        phase3_rows,
        authoritative_marks=marks,
    )
    enriched_rows: list[dict[str, Any]] = []
    for row in merged.merged_rows:
        qid_raw = row.get("result_id") or row.get("question_id")
        qid = qid_raw.strip() if isinstance(qid_raw, str) and qid_raw.strip() else None
        updated = dict(row)
        if qid and not (isinstance(updated.get("attempt_page_start"), int) and updated.get("attempt_page_start") >= 1):
            mapped = authority_page_map.get(qid)
            aps = mapped.get("attempt_page_start") if isinstance(mapped, Mapping) else None
            if isinstance(aps, int) and aps >= 1:
                updated["attempt_page_start"] = aps
        enriched_rows.append(updated)
    language_violations = find_language_violations(enriched_rows, english_required=english_required)
    human_note_violations = find_human_note_policy_violations(enriched_rows)
    phase3_targets = select_phase3_question_ids(phase2_rows)
    return V3FinalizePrepResult(
        merged_rows=tuple(enriched_rows),
        phase3_question_ids=phase3_targets,
        language_violations=language_violations,
        human_note_violations=human_note_violations,
    )
