"""Tests for student_file_browser.path_guard."""

from pathlib import Path

from ai_study_buddy.student_file_browser.path_guard import safe_resolve_under_root


def test_safe_resolve_under_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    f = root / "a.pdf"
    f.write_bytes(b"x")
    assert safe_resolve_under_root(root, "a.pdf") == f.resolve()
    assert safe_resolve_under_root(root, "../outside") is None
