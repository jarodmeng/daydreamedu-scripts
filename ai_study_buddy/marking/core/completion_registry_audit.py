"""Shared rules for the completion-files registry audit (research tallies).

GoodNotes chapter PDFs under certain *Science Revision Guide* book folders are
chapter revisions without gradable questions; they are excluded from the audit
population so template/marking buckets are not inflated.

When extending the list, add the **exact** folder name as it appears in the path
under ``.../Book/<folder name>/...`` (see ``GOODNOTES_SCIENCE_REVISION_GUIDE_BOOK_FOLDERS_EXCLUDED``).
"""

from __future__ import annotations

from pathlib import Path

# Folder names under GoodNotes ``.../Book/<name>/`` to drop from completion audit.
GOODNOTES_SCIENCE_REVISION_GUIDE_BOOK_FOLDERS_EXCLUDED: frozenset[str] = frozenset(
    {
        "Science Revision Guide Primary 4",
        "Science PSLE Revision Guide",
    }
)


def is_goodnotes_science_revision_guide_book_excluded(path: Path | str) -> bool:
    """True when ``path`` is under GoodNotes and passes through an excluded book folder."""
    parts = Path(path).resolve().parts
    return any(p in GOODNOTES_SCIENCE_REVISION_GUIDE_BOOK_FOLDERS_EXCLUDED for p in parts)
