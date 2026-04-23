from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


REPO_ROOT = _repo_root()
CONTEXT_ROOT = REPO_ROOT / "ai_study_buddy" / "context"
REVIEW_STATES_ROOT = CONTEXT_ROOT / "student_review_states"
DEFAULT_PILOT_JSON = (
    CONTEXT_ROOT
    / "marking_results"
    / "winston"
    / "singapore_primary_math"
    / "PP Math PSLE Part D P6 Topical Practice Circles__20260416_205158.json"
)
PILOT_JSON_PATH = Path(os.environ.get("REVIEW_WORKSPACE_PILOT_JSON", str(DEFAULT_PILOT_JSON)))
STATIC_ROUTE_PREFIX = "/review-workspace-static"


@dataclass(frozen=True)
class PilotArtifact:
    path: Path
    payload: dict[str, Any]


def _load_pilot_artifact() -> PilotArtifact:
    if not PILOT_JSON_PATH.exists():
        raise RuntimeError(f"Pilot JSON does not exist: {PILOT_JSON_PATH}")
    payload = json.loads(PILOT_JSON_PATH.read_text(encoding="utf-8"))
    return PilotArtifact(path=PILOT_JSON_PATH, payload=payload)


def _extract_page_num(path: Path) -> int:
    # Supports names like "attempt-page-01.png", "page-01.png", "p1.png".
    match = re.search(r"(\d+)(?!.*\d)", path.stem)
    if not match:
        return 10_000_000
    return int(match.group(1))


def _list_images(asset_dir: Path, subdir: str) -> list[dict[str, Any]]:
    target = asset_dir / subdir
    if not target.is_dir():
        return []
    candidates = [
        p
        for p in target.iterdir()
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    out: list[dict[str, Any]] = []
    for path in sorted(candidates, key=lambda p: (_extract_page_num(p), p.name)):
        rel = path.relative_to(CONTEXT_ROOT).as_posix()
        out.append(
            {
                "name": path.name,
                "page_num": _extract_page_num(path),
                "url": f"{STATIC_ROUTE_PREFIX}/{rel}",
            }
        )
    return out


def _attempt_title_from_context(context: dict[str, Any]) -> str:
    unit_label = context.get("unit_label")
    if isinstance(unit_label, str) and unit_label.strip():
        return unit_label.strip()
    attempt_path = context.get("attempt_file_path")
    if isinstance(attempt_path, str) and attempt_path.strip():
        return Path(attempt_path).stem
    return "Untitled Attempt"


def _attempt_id_from_context(context: dict[str, Any], artifact_path: Path) -> str:
    attempt_file_id = context.get("attempt_file_id")
    if isinstance(attempt_file_id, str) and attempt_file_id.strip():
        return attempt_file_id
    return artifact_path.stem


def _review_state_path(student_id: str, subject_context: str, artifact_stem: str) -> Path:
    return REVIEW_STATES_ROOT / student_id / subject_context / f"{artifact_stem}.json"


def _load_review_state(student_id: str, subject_context: str, artifact_stem: str) -> dict[str, Any] | None:
    path = _review_state_path(student_id, subject_context, artifact_stem)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_review_state(student_id: str, subject_context: str, artifact_stem: str, payload: dict[str, Any]) -> Path:
    path = _review_state_path(student_id, subject_context, artifact_stem)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def _find_attempt_page_for_result(
    question_page_map: list[dict[str, Any]], result_id: str
) -> int | None:
    for entry in question_page_map:
        if entry.get("result_id") == result_id and isinstance(entry.get("attempt_page_start"), int):
            return entry["attempt_page_start"]
    return None


app = FastAPI(title="AI Study Buddy Review Workspace Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Makes marking assets and other context files available for the frontend.
app.mount(STATIC_ROUTE_PREFIX, StaticFiles(directory=str(CONTEXT_ROOT)), name="review-workspace-static")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/students")
def students() -> dict[str, list[dict[str, str]]]:
    artifact = _load_pilot_artifact()
    context = artifact.payload.get("context", {})
    student_id = str(context.get("student_id") or "winston")
    student_name = str(context.get("student_name") or "Winston")
    return {
        "students": [
            {
                "student_id": student_id,
                "display_name": student_name,
                "grade_level": "PSLE",
            }
        ]
    }


@app.get("/api/student/attempts")
def attempts(student_id: str = Query(...)) -> dict[str, list[dict[str, Any]]]:
    artifact = _load_pilot_artifact()
    payload = artifact.payload
    context = payload.get("context", {})
    summary = payload.get("summary", {})

    resolved_student_id = str(context.get("student_id") or "")
    if student_id != resolved_student_id:
        return {"items": []}

    attempt_id = _attempt_id_from_context(context, artifact.path)
    return {
        "items": [
            {
                "attempt_id": attempt_id,
                "title": _attempt_title_from_context(context),
                "student_id": resolved_student_id,
                "subject_context": context.get("subject_context"),
                "grade_bucket": "PSLE",
                "collection_kind": "book",
                "book_label": context.get("book_label"),
                "marking_status": "marked",
                "review_status": "not_started",
                "latest_marked_at": payload.get("created_at"),
                "attempt_sequence": context.get("attempt_sequence"),
                "is_partial": context.get("is_partial"),
                "score": {
                    "earned_marks": summary.get("earned_marks"),
                    "total_marks": summary.get("total_marks"),
                    "percentage": summary.get("percentage"),
                },
            }
        ]
    }


@app.get("/api/student/attempts/{attempt_id}")
def attempt_detail(attempt_id: str) -> dict[str, Any]:
    artifact = _load_pilot_artifact()
    payload = artifact.payload
    context = payload.get("context", {})
    summary = payload.get("summary", {})
    question_results = payload.get("question_results", [])
    question_page_map = context.get("question_page_map", [])

    resolved_attempt_id = _attempt_id_from_context(context, artifact.path)
    if attempt_id != resolved_attempt_id:
        raise HTTPException(status_code=404, detail="attempt not found")

    marking_asset = context.get("marking_asset")
    if not isinstance(marking_asset, str) or not marking_asset.strip():
        raise HTTPException(status_code=500, detail="marking_asset missing in pilot artifact")
    asset_dir = CONTEXT_ROOT / marking_asset

    attempt_images = _list_images(asset_dir, "attempt")
    answer_images = _list_images(asset_dir, "answers")

    normalized_questions: list[dict[str, Any]] = []
    for row in question_results:
        if not isinstance(row, dict):
            continue
        result_id = str(row.get("result_id") or "")
        normalized_questions.append(
            {
                "result_id": result_id,
                "outcome": row.get("outcome"),
                "earned_marks": row.get("earned_marks"),
                "max_marks": row.get("max_marks"),
                "student_answer": row.get("student_answer"),
                "correct_answer": row.get("correct_answer"),
                "feedback": row.get("feedback"),
                "skill_tags": row.get("skill_tags") or [],
                "diagnosis": row.get("diagnosis") or {},
                "tutor_note": row.get("human_note"),
                "attempt_page_start": _find_attempt_page_for_result(question_page_map, result_id),
            }
        )

    student_id = str(context.get("student_id") or "unknown")
    subject_context = str(context.get("subject_context") or "unknown")
    review_state = _load_review_state(student_id, subject_context, artifact.path.stem)

    return {
        "attempt": {
            "attempt_id": resolved_attempt_id,
            "title": _attempt_title_from_context(context),
            "student_id": context.get("student_id"),
            "subject_context": context.get("subject_context"),
            "collection_kind": "book",
            "book_label": context.get("book_label"),
        },
        "marking_status": "marked",
        "marking_result": {
            "artifact_path": artifact.path.relative_to(CONTEXT_ROOT).as_posix(),
            "schema_version": payload.get("schema_version"),
            "created_at": payload.get("created_at"),
            "context": {
                "unit_label": context.get("unit_label"),
                "attempt_sequence": context.get("attempt_sequence"),
                "template_attempt_group_id": context.get("template_attempt_group_id"),
                "answer_page_start": context.get("answer_page_start"),
                "answer_page_end": context.get("answer_page_end"),
                "is_partial": context.get("is_partial"),
                "question_page_map": question_page_map,
            },
            "summary": {
                "earned_marks": summary.get("earned_marks"),
                "total_marks": summary.get("total_marks"),
                "percentage": summary.get("percentage"),
                "overall_assessment": summary.get("overall_assessment"),
            },
            "question_results": normalized_questions,
        },
        "review_state": review_state
        if isinstance(review_state, dict)
        else {
            "review_status": "not_started",
            "question_reviews": [],
            "attempt_notes": [],
            "student_subject_notes": [],
        },
        "viewer": {
            "mode_default": "attempt",
            "attempt_images": attempt_images,
            "answer_images": answer_images,
            "answer_page_start": context.get("answer_page_start"),
            "answer_page_end": context.get("answer_page_end"),
            "marking_asset": marking_asset,
        },
    }


@app.put("/api/student/attempts/{attempt_id}/review-state")
def put_review_state(attempt_id: str, body: dict[str, Any]) -> dict[str, Any]:
    artifact = _load_pilot_artifact()
    context = artifact.payload.get("context", {})
    resolved_attempt_id = _attempt_id_from_context(context, artifact.path)
    if attempt_id != resolved_attempt_id:
        raise HTTPException(status_code=404, detail="attempt not found")

    student_id = str(context.get("student_id") or "unknown")
    subject_context = str(context.get("subject_context") or "unknown")
    artifact_stem = artifact.path.stem

    review_status = body.get("review_status")
    if review_status not in {"not_started", "in_progress", "completed"}:
        raise HTTPException(status_code=400, detail="review_status must be not_started|in_progress|completed")

    payload = {
        "schema_version": "student_review_state.v1",
        "context": {
            "student_id": student_id,
            "subject_context": subject_context,
            "attempt_file_id": context.get("attempt_file_id"),
            "marking_result_path": artifact.path.relative_to(CONTEXT_ROOT).as_posix(),
        },
        "review_status": review_status,
        "question_reviews": body.get("question_reviews") if isinstance(body.get("question_reviews"), list) else [],
        "attempt_notes": body.get("attempt_notes") if isinstance(body.get("attempt_notes"), list) else [],
        "student_subject_notes": body.get("student_subject_notes")
        if isinstance(body.get("student_subject_notes"), list)
        else [],
        "updated_by": body.get("updated_by") if isinstance(body.get("updated_by"), str) else "review_workspace",
    }
    path = _save_review_state(student_id, subject_context, artifact_stem, payload)
    return {
        "ok": True,
        "saved_path": path.relative_to(CONTEXT_ROOT).as_posix(),
        "review_state": payload,
    }
