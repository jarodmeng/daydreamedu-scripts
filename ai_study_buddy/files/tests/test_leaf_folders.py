"""Tests for ai_study_buddy.files.leaf_folders."""

from pathlib import Path

from ai_study_buddy.files.leaf_folders import (
    list_daydreamedu_leaf_folders_under_root,
    list_goodnotes_leaf_folders_under_root,
    list_leaf_folders_under_root,
)


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


def test_list_leaf_folders_matches_direct_suffixes_and_is_sorted(minimal_sorted_leaf_tree):
    root = minimal_sorted_leaf_tree
    leaves = list_leaf_folders_under_root(
        root,
        include_suffixes={".pdf", ".md"},
    )
    assert leaves == [root / "a_folder", root / "b_folder"]


def test_list_leaf_folders_applies_absolute_excluded_leaf_folders(tmp_path):
    root = tmp_path / "root"
    _touch(root / "keep" / "a.pdf")
    _touch(root / "drop" / "b.pdf")

    leaves = list_leaf_folders_under_root(
        root,
        include_suffixes={".pdf"},
        excluded_leaf_folders={(root / "drop").resolve()},
    )

    assert leaves == [root / "keep"]


def test_goodnotes_profile_exclusions(goodnotes_profile_root):
    leaves = list_goodnotes_leaf_folders_under_root(goodnotes_profile_root)
    assert leaves == [goodnotes_profile_root / "Math" / "Complete" / "Unit 2"]


def test_daydreamedu_profile_exclusions(daydreamedu_profile_root):
    leaves = list_daydreamedu_leaf_folders_under_root(daydreamedu_profile_root)
    assert leaves == [daydreamedu_profile_root / "Science" / "Exam"]
