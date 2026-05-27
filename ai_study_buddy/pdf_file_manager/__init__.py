"""Public package exports for ai_study_buddy.pdf_file_manager.

Canonical import style for callers:
    from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
or:
    from ai_study_buddy.pdf_file_manager import PdfFileManager
"""

from .completion_date.core import CompletionDateRecord, InferCompletionDatesReport
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
    "CompletionDateRecord",
    "CompressResult",
    "ConfigError",
    "CoverageReport",
    "FileGroup",
    "FileGroupMember",
    "FileRelation",
    "GoodNotesTemplateLinkOutcome",
    "GoodnotesDocumentMatch",
    "GoodnotesDocumentTimestamps",
    "InferCompletionDatesReport",
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
