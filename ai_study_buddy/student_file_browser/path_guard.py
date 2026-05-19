"""Path guard for serving PDFs under configured sync roots."""

from __future__ import annotations

from pathlib import Path


def safe_resolve_under_root(root: Path, rel: str) -> Path | None:
    """Return resolved path if *rel* stays under *root*; else None."""
    root_resolved = root.resolve()
    rel = (rel or "").strip()
    if rel.startswith("/"):
        return None
    rel_path = Path(rel)
    if rel_path.is_absolute():
        return None
    try:
        full = (root_resolved / rel_path).resolve()
    except OSError:
        return None
    if not full.is_relative_to(root_resolved):
        return None
    return full
