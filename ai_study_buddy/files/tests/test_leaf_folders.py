"""Tests for ai_study_buddy.files.leaf_folders."""

from pathlib import Path

from ai_study_buddy.files.leaf_folders import (
    is_goodnotes_excluded_relative_path,
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
    assert leaves == [
        (goodnotes_profile_root / "Coding").resolve(),
        (goodnotes_profile_root / "Math" / "Complete" / "Unit 2").resolve(),
    ]


def test_goodnotes_includes_not_completed_when_exclude_flag_false(goodnotes_profile_root):
    leaves = list_goodnotes_leaf_folders_under_root(
        goodnotes_profile_root,
        exclude_not_completed=False,
    )
    assert leaves == [
        (goodnotes_profile_root / "Coding").resolve(),
        (goodnotes_profile_root / "Math" / "Complete" / "Unit 2").resolve(),
        (goodnotes_profile_root / "Math" / "Not completed" / "Unit 1").resolve(),
    ]


def test_daydreamedu_profile_exclusions(daydreamedu_profile_root):
    leaves = list_daydreamedu_leaf_folders_under_root(daydreamedu_profile_root)
    root = daydreamedu_profile_root
    assert leaves == [
        (root / "Science" / "Exam").resolve(),
        (root / "Science" / "Note").resolve(),
        (root / "Science" / "Notes").resolve(),
    ]


def test_is_goodnotes_excluded_relative_path_empty_and_not_completed_toggle() -> None:
    assert not is_goodnotes_excluded_relative_path("")
    assert not is_goodnotes_excluded_relative_path("", exclude_not_completed=False)
    assert is_goodnotes_excluded_relative_path("Subject/Not completed/Unit1")
    assert not is_goodnotes_excluded_relative_path(
        "Subject/Not completed/Unit1",
        exclude_not_completed=False,
    )
    assert is_goodnotes_excluded_relative_path("xNotes")
    assert is_goodnotes_excluded_relative_path("Math/xArchived", exclude_not_completed=False)
    assert is_goodnotes_excluded_relative_path("P6/Exam/Review")
    assert is_goodnotes_excluded_relative_path("P6/Exam/Review", exclude_not_completed=False)


def test_goodnotes_excludes_review_subtree_even_when_not_completed_included(
    goodnotes_profile_root,
):
    leaves = list_goodnotes_leaf_folders_under_root(
        goodnotes_profile_root,
        exclude_not_completed=False,
    )
    paths = {str(p) for p in leaves}
    assert not any("/Review" in p or p.endswith("/Review") for p in paths)


def test_goodnotes_x_prefix_requires_uppercase_second_letter(tmp_path: Path):
    """`^x[A-Z].*$` excludes xWork but not xwater (second letter not uppercase)."""
    root = tmp_path / "g"
    (root / "keep" / "a.pdf").parent.mkdir(parents=True)
    (root / "keep" / "a.pdf").write_bytes(b"%PDF")
    (root / "xWork" / "b.pdf").parent.mkdir(parents=True)
    (root / "xWork" / "b.pdf").write_bytes(b"%PDF")
    # Not `xwork`: same path as `xWork` on case-insensitive volumes (e.g. macOS default).
    (root / "xwater" / "c.pdf").parent.mkdir(parents=True)
    (root / "xwater" / "c.pdf").write_bytes(b"%PDF")

    leaves = list_goodnotes_leaf_folders_under_root(root)
    assert set(leaves) == {(root / "keep").resolve(), (root / "xwater").resolve()}
