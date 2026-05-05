from __future__ import annotations


class FileQuestionInfoError(ValueError):
    """Base error for file_question_info helper failures."""


class MissingGradeOrScopeError(FileQuestionInfoError):
    """Raised when metadata.grade_or_scope is missing or blank."""


class InvalidGradeOrScopeError(FileQuestionInfoError):
    """Raised when metadata.grade_or_scope is present but not in the allowlist."""


class UnsupportedPdfSubjectError(FileQuestionInfoError):
    """Raised when PdfFile.subject is unsupported for file_question_info layout."""


class UnknownQuestionSectionsSchemaVersionError(FileQuestionInfoError):
    """Raised when payload.schema_version is missing/unknown."""


class QuestionSectionsSchemaLoadError(FileQuestionInfoError):
    """Raised when a schema file cannot be loaded/read."""


class QuestionSectionsValidationError(FileQuestionInfoError):
    """Raised when question_sections payload fails schema/runtime validation."""

