"""Resolve GoodNotes Review-folder PDFs for supervised redo evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile, PdfFileManager, normalize_pdf_display_name


@dataclass(frozen=True)
class SupervisedReviewRedoResolution:
    available: bool
    resolved_path: Path | None = None

    def resolved_path_relative_to(self, root: Path) -> str | None:
        if self.resolved_path is None:
            return None
        resolved_root = root.expanduser().resolve()
        resolved_file = self.resolved_path.expanduser().resolve()
        try:
            return resolved_file.relative_to(resolved_root).as_posix()
        except ValueError:
            return resolved_file.as_posix()


def _goodnotes_mirror_segments_from_attempt_path(attempt_path: Path) -> tuple[str, ...] | None:
    """Return directory segments under GoodNotes root (excluding PDF basename)."""
    parts = attempt_path.expanduser().resolve().parts
    if not parts:
        return None

    for index, segment in enumerate(parts):
        if segment == "GoodNotes" and index + 1 < len(parts):
            return parts[index + 1 : -1]

    for index, segment in enumerate(parts):
        if (
            segment == "DaydreamEdu"
            and index + 2 < len(parts)
            and parts[index + 1] == "completion"
            and index + 3 < len(parts)
        ):
            return parts[index + 2 : -1]

    return None


def _review_pdf_basename_candidates(template_name: str) -> list[str]:
    display_stem = normalize_pdf_display_name(template_name)
    candidates = [f"c_{display_stem}.pdf", f"_c_{display_stem}.pdf"]
    seen: set[str] = set()
    ordered: list[str] = []
    for name in candidates:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def resolve_supervised_review_pdf_for_attempt(
    attempt: PdfFile,
    *,
    manager: PdfFileManager,
    goodnotes_root: Path | None,
) -> SupervisedReviewRedoResolution:
    """Attempt → template → GoodNotes Review PDF path (stat only; no registry lookup)."""
    if goodnotes_root is None:
        return SupervisedReviewRedoResolution(available=False)

    template = manager.get_template(attempt.id)
    if template is None:
        return SupervisedReviewRedoResolution(available=False)

    mirror_segments = _goodnotes_mirror_segments_from_attempt_path(Path(attempt.path))
    if not mirror_segments:
        return SupervisedReviewRedoResolution(available=False)

    review_dir = goodnotes_root.expanduser().resolve().joinpath(*mirror_segments, "Review")
    for basename in _review_pdf_basename_candidates(template.name):
        candidate = review_dir / basename
        if candidate.is_file():
            return SupervisedReviewRedoResolution(available=True, resolved_path=candidate)

    return SupervisedReviewRedoResolution(available=False)
