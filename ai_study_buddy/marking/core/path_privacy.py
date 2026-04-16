from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from ai_study_buddy.files.roots import resolve_daydreamedu_root, resolve_goodnotes_root
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

_CONTEXT_PATH_FIELDS = (
    "attempt_file_path",
    "template_file_path",
    "unit_file_path",
    "answer_file_path",
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_GOODNOTES_PREFIX_RE = re.compile(r"/Users/[^\n`\"]*?/My Drive/GoodNotes")
_DAYDREAMEDU_PREFIX_RE = re.compile(r"/Users/[^\n`\"]*?/My Drive/DaydreamEdu")

_PDF_MANAGER: PdfFileManager | None = None
_PDF_MANAGER_LOADED = False


def sanitize_marking_artifact_paths(payload: dict[str, Any]) -> dict[str, Any]:
    """Return payload copy with path fields normalized and de-identified."""
    out = copy.deepcopy(payload)
    context = out.get("context")
    if not isinstance(context, dict):
        return out
    for key in _CONTEXT_PATH_FIELDS:
        value = context.get(key)
        if isinstance(value, str):
            context[key] = _sanitize_path_text(value)
    return out


def resolve_marking_artifact_paths(payload: dict[str, Any]) -> dict[str, Any]:
    """Return payload copy with placeholder path tokens expanded when possible."""
    out = copy.deepcopy(payload)
    context = out.get("context")
    if not isinstance(context, dict):
        return out
    student_email = _resolve_student_email(context.get("student_id"))
    goodnotes_root = resolve_goodnotes_root()
    daydreamedu_root = resolve_daydreamedu_root()
    for key in _CONTEXT_PATH_FIELDS:
        value = context.get(key)
        if isinstance(value, str):
            context[key] = _resolve_path_text(
                value,
                student_email=student_email,
                goodnotes_root=goodnotes_root,
                daydreamedu_root=daydreamedu_root,
            )
    return out


def _sanitize_path_text(text: str) -> str:
    sanitized = _GOODNOTES_PREFIX_RE.sub("GOODNOTES_ROOT", text)
    sanitized = _DAYDREAMEDU_PREFIX_RE.sub("DAYDREAMEDU_ROOT", sanitized)
    return _EMAIL_RE.sub("<student_email>", sanitized)


def _resolve_path_text(
    text: str,
    *,
    student_email: str | None,
    goodnotes_root: Path | None,
    daydreamedu_root: Path | None,
) -> str:
    resolved = text
    if goodnotes_root is not None:
        resolved = resolved.replace("GOODNOTES_ROOT", str(goodnotes_root))
    if daydreamedu_root is not None:
        resolved = resolved.replace("DAYDREAMEDU_ROOT", str(daydreamedu_root))
    if student_email:
        resolved = resolved.replace("<student_email>", student_email)
    return resolved


def _resolve_student_email(student_id: Any) -> str | None:
    if not isinstance(student_id, str) or not student_id.strip():
        return None
    manager = _get_pdf_file_manager()
    if manager is None:
        return None
    try:
        student = manager.get_student(student_id)
    except Exception:
        return None
    if student is None:
        return None
    return student.email


def _get_pdf_file_manager() -> PdfFileManager | None:
    global _PDF_MANAGER, _PDF_MANAGER_LOADED
    if _PDF_MANAGER_LOADED:
        return _PDF_MANAGER
    _PDF_MANAGER_LOADED = True
    try:
        _PDF_MANAGER = PdfFileManager()
    except Exception:
        _PDF_MANAGER = None
    return _PDF_MANAGER
