from __future__ import annotations

import re

ERROR_TAGS: tuple[str, ...] = (
    "concept_gap",
    "misread_question",
    "careless_error",
    "incomplete_explanation",
    "wrong_method",
    "missing_units",
    "computation_error",
    "vocabulary_gap",
    "other",
)

DIAGNOSIS_MISTAKE_TYPES: tuple[str, ...] = ERROR_TAGS

DIAGNOSIS_CONFIDENCE_LEVELS: tuple[str, ...] = ("high", "medium", "low")

_MARKDOWN_LINK_RE = re.compile(r"^\[(?P<label>.+)\]\((?P<url>.+)\)$")


def normalize_skill_tag(value: str) -> str:
    text = value.strip().casefold()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _strip_markdown_link_wrapper(value: str) -> str:
    match = _MARKDOWN_LINK_RE.match(value.strip())
    if match is None:
        return value
    return match.group("label").strip()


def derive_skill_tags_from_embedding_label(label: str) -> tuple[str, ...]:
    label = _strip_markdown_link_wrapper(label)
    parts = [part.strip() for part in label.split(">")]
    normalized: list[str] = []
    seen_casefold: set[str] = set()
    for part in parts:
        if not part:
            continue
        tag = _strip_markdown_link_wrapper(part)
        tag = re.sub(r"\s+", " ", tag).strip()
        if not tag:
            continue
        folded = tag.casefold()
        if folded in seen_casefold:
            continue
        seen_casefold.add(folded)
        normalized.append(tag)
    return tuple(normalized)


def prettify_skill_tags(skill_tags: tuple[str, ...] | list[str]) -> str:
    """Join ``skill_tags`` for markdown tables.

    **Legacy (hierarchy across elements):** each array entry is one level, e.g.
    ``("Forces", "effects of force", "direction")`` → ``Forces > effects of force > direction``.

    **Path per element:** when *every* non-empty tag contains ``" > "`` (typical for
    syllabus-aligned marking: e.g. Singapore primary math ``strand > sub-strand > topic``,
    or science ``theme > chapter > topic``), multiple entries are joined with ``"; "`` so
    internal `` > `` are not flattened into one ambiguous path. Some contexts use the
    legacy shape (one hierarchy level per array element); subjects without a taxonomy
    may use an empty list.
    """
    tags = [str(t).strip() for t in skill_tags if str(t).strip()]
    if not tags:
        return ""
    if len(tags) == 1:
        return tags[0]
    if all(" > " in t for t in tags):
        return "; ".join(tags)
    return " > ".join(tags)
