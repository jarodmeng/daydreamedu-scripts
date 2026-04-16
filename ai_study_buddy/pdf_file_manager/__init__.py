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
    NotFoundError,
    OperationRecord,
    PdfFile,
    PdfFileManager,
    ScanResult,
    ScanRoot,
    Student,
    SuggestedGroup,
)

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
    "NotFoundError",
    "OperationRecord",
    "PdfFile",
    "PdfFileManager",
    "ScanResult",
    "ScanRoot",
    "Student",
    "SuggestedGroup",
]
