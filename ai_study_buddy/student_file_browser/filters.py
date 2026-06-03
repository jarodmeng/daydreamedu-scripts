"""URL query parameters ↔ ``FilterCriteria``."""

from __future__ import annotations

from ai_study_buddy.files.on_disk_inventory import FilterCriteria, normalize_facet_values

_VALID_ROOT_IDS = frozenset({"all", "daydreamedu", "goodnotes"})
_VALID_SORT_KEYS = frozenset({"name", "recent"})


def filter_criteria_from_query(params: dict[str, list[str]]) -> FilterCriteria:
    def _one(key: str, default: str = "") -> str:
        vals = params.get(key) or []
        return vals[0] if vals else default

    def _many(key: str) -> tuple[str, ...]:
        return normalize_facet_values(params.get(key) or [])

    is_reg = _one("is_registered")
    has_tpl = _one("has_template")
    has_mk = _one("has_marking")
    review = _one("review_status")
    root_raw = (_one("root_id", "all") or "all").strip().lower()
    root_id = root_raw if root_raw in _VALID_ROOT_IDS else "all"
    sort_raw = (_one("sort", "recent") or "recent").strip().lower()
    sort = sort_raw if sort_raw in _VALID_SORT_KEYS else "recent"
    return FilterCriteria(
        scope=_one("scope", "completion") or "completion",
        root_id=root_id,
        student=_one("student"),
        subject=_many("subject"),
        grade=_many("grade"),
        doc_type=_many("doc_type"),
        book=_one("book"),
        is_registered=is_reg if is_reg in ("true", "false") else None,
        has_template=has_tpl if has_tpl in ("true", "false") else None,
        has_marking=has_mk if has_mk in ("true", "false") else None,
        review_status=review if review else None,
        sort=sort,
    )
