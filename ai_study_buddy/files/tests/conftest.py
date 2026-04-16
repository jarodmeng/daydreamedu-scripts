"""Pytest fixtures for ai_study_buddy.files tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def minimal_sorted_leaf_tree(tmp_path: Path) -> Path:
    """Copy generic leaf-folder tree (suffix filter + sort order)."""
    root = tmp_path / "root"
    shutil.copytree(_FIXTURES / "minimal_sorted_tree", root)
    return root


@pytest.fixture
def goodnotes_profile_root(tmp_path: Path) -> Path:
    """Copy GoodNotes-shaped tree for profile exclusion tests."""
    dest = tmp_path / "goodnotes_case"
    shutil.copytree(_FIXTURES / "goodnotes_profile_tree", dest)
    return dest / "GoodNotes"


@pytest.fixture
def daydreamedu_profile_root(tmp_path: Path) -> Path:
    """Copy DaydreamEdu-shaped tree for profile exclusion tests."""
    dest = tmp_path / "daydreamedu_case"
    shutil.copytree(_FIXTURES / "daydreamedu_profile_tree", dest)
    return dest / "DaydreamEdu"
