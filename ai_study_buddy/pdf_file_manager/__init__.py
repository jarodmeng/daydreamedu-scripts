"""Public package exports for ai_study_buddy.pdf_file_manager.

Canonical import style for callers:
    from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
or:
    from ai_study_buddy.pdf_file_manager import PdfFileManager
"""

from .pdf_file_manager import (
    AlreadyRegisteredError,
    BookAnswerMapping,
    CompressResult,
    ConfigError,
    CoverageReport,
    FileGroup,
    FileGroupMember,
    FileRelation,
    GoodNotesTemplateLinkOutcome,
    InvalidMetadataError,
    NotFoundError,
    OperationRecord,
    PdfFile,
    PdfFileManager,
    ScanResult,
    ScanRoot,
    Student,
    SuggestedGroup,
)
from .goodnotes_metadata import GoodnotesDocumentMatch, GoodnotesDocumentTimestamps

__all__ = [
    "AlreadyRegisteredError",
    "BookAnswerMapping",
    "CompressResult",
    "ConfigError",
    "CoverageReport",
    "FileGroup",
    "FileGroupMember",
    "FileRelation",
    "GoodNotesTemplateLinkOutcome",
    "GoodnotesDocumentMatch",
    "GoodnotesDocumentTimestamps",
    "InvalidMetadataError",
    "NotFoundError",
    "OperationRecord",
    "PdfFile",
    "PdfFileManager",
    "ScanResult",
    "ScanRoot",
    "Student",
    "SuggestedGroup",
]
