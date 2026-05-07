"""Shared filesystem utilities for AI Study Buddy."""

from .leaf_folders import (
    is_goodnotes_excluded_relative_path,
    list_daydreamedu_leaf_folders_under_root,
    list_goodnotes_leaf_folders_under_root,
    list_leaf_folders_under_root,
)
from .pdf_registry_paths import (
    LeafFolderRegistryStatus,
    PdfFileRegistryStatus,
    RegistryPathIndex,
    ScanRootRegistrationBuckets,
    direct_pdf_paths_in_leaf_folder,
    is_pdf_registered,
    leaf_folder_registry_status,
    leaf_pdf_file_registry_statuses,
    leaf_registry_statuses_for_included_leaves,
    partition_daydreamedu_leaf_folders,
    partition_goodnotes_leaf_folders,
    pdf_file_registry_status,
    registration_buckets,
    resolved_path_from_registry_row,
    suspicious_all_leaves_marked_non_scan_root,
)
from .roots import resolve_daydreamedu_root, resolve_goodnotes_root

__all__ = [
    "resolve_daydreamedu_root",
    "resolve_goodnotes_root",
    "list_leaf_folders_under_root",
    "list_daydreamedu_leaf_folders_under_root",
    "list_goodnotes_leaf_folders_under_root",
    "is_goodnotes_excluded_relative_path",
    "resolved_path_from_registry_row",
    "RegistryPathIndex",
    "PdfFileRegistryStatus",
    "is_pdf_registered",
    "pdf_file_registry_status",
    "direct_pdf_paths_in_leaf_folder",
    "leaf_pdf_file_registry_statuses",
    "LeafFolderRegistryStatus",
    "leaf_folder_registry_status",
    "partition_daydreamedu_leaf_folders",
    "partition_goodnotes_leaf_folders",
    "leaf_registry_statuses_for_included_leaves",
    "ScanRootRegistrationBuckets",
    "registration_buckets",
    "suspicious_all_leaves_marked_non_scan_root",
]
