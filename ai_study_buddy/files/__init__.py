"""Shared filesystem utilities for AI Study Buddy."""

from .leaf_folders import (
    is_goodnotes_excluded_relative_path,
    list_daydreamedu_leaf_folders_under_root,
    list_goodnotes_leaf_folders_under_root,
    list_leaf_folders_under_root,
)
from .roots import resolve_daydreamedu_root, resolve_goodnotes_root

__all__ = [
    "resolve_daydreamedu_root",
    "resolve_goodnotes_root",
    "list_leaf_folders_under_root",
    "list_daydreamedu_leaf_folders_under_root",
    "list_goodnotes_leaf_folders_under_root",
    "is_goodnotes_excluded_relative_path",
]
