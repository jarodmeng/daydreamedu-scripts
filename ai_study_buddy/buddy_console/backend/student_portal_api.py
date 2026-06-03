from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Query

from ai_study_buddy.buddy_console.backend.student_portal_service import (
    StudyDatabaseUnavailableError,
    build_marks_by_question_type_response,
)

router = APIRouter(prefix="/api/student", tags=["student-portal"])


@router.get("/marks-by-question-type")
def get_marks_by_question_type(
    student_id: str = Query(default=""),
    subject: str = Query(default=""),
) -> dict:
    try:
        return build_marks_by_question_type_response(
            student_id=student_id,
            subject=subject,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StudyDatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Study database error: {exc}") from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"Compute failed: {exc}") from exc
