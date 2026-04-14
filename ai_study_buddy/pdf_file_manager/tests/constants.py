"""Shared placeholders for pdf_file_manager tests (no real PII).

``STUDENT_FOLDER_EMAIL`` is used as the path segment that behaves like a synced
Google “student folder” (contains ``@``). Inference keys off ``@`` plus an
adjacent grade/scope segment (P3–P6, PSLE, Archive), not on this exact string.

``STUDENT_DISPLAY_NAME`` is a neutral display name for ``add_student`` in tests
(no real PII).
"""

STUDENT_FOLDER_EMAIL = "student.fixture@example.com"
STUDENT_DISPLAY_NAME = "Test Student"
