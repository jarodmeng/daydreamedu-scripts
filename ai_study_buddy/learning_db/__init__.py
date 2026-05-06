"""Learning DB package for AI Study Buddy."""

from ai_study_buddy.learning_db.core.connection import (
    default_db_path,
    default_context_root,
    get_connection,
)

__all__ = [
    "default_db_path",
    "default_context_root",
    "get_connection",
]

