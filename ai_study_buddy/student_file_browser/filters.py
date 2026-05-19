"""URL query parameters ↔ ``FilterCriteria``."""

from __future__ import annotations

from ai_study_buddy.files.on_disk_inventory import FilterCriteria


def filter_criteria_from_query(params: dict[str, list[str]]) -> FilterCriteria:
    def _one(key: str, default: str = "") -> str:
        vals = params.get(key) or []
        return vals[0] if vals else default

    is_reg = _one("is_registered")
    has_tpl = _one("has_template")
    has_mk = _one("has_marking")
    review = _one("review_status")
    return FilterCriteria(
        scope=_one("scope", "completion") or "completion",
        student=_one("student"),
        subject=_one("subject", "all") or "all",
        grade=_one("grade", "all") or "all",
        doc_type=_one("doc_type", "all") or "all",
        book=_one("book"),
        is_registered=is_reg if is_reg in ("true", "false") else None,
        has_template=has_tpl if has_tpl in ("true", "false") else None,
        has_marking=has_mk if has_mk in ("true", "false") else None,
        review_status=review if review else None,
    )
