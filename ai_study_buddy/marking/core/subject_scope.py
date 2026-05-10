from __future__ import annotations


def subject_context_from_pdf_subject(subject: str | None) -> str:
    normalized = (subject or "").strip().casefold()
    if normalized == "english":
        return "singapore_primary_english"
    if normalized == "math":
        return "singapore_primary_math"
    if normalized == "science":
        return "singapore_primary_science"
    if normalized == "chinese":
        return "singapore_primary_chinese"
    raise ValueError(f"unsupported or missing pdf subject: {subject!r}")

