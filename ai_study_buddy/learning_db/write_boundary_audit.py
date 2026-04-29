from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_study_buddy.learning_db.connection import default_db_path, get_connection
from ai_study_buddy.learning_db.migrate import apply_migrations
from ai_study_buddy.learning_db.repository import OperationEvent, validate_actor, write_operation_log


def audit_write_boundary_event(
    *,
    operation_type: str,
    entity_type: str,
    entity_id: str,
    status: str,
    actor: str,
    db_path: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """Best-effort operation-log write for marking/repository write boundaries."""
    try:
        resolved_db = Path(db_path).expanduser().resolve() if db_path else default_db_path()
        apply_migrations(db_path=resolved_db)
        conn = get_connection(resolved_db)
        try:
            write_operation_log(
                conn,
                OperationEvent(
                    operation_type=operation_type,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    status=status,
                    actor=validate_actor(actor),
                    metadata=metadata or {},
                    error_code=error_code,
                    error_message=error_message,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # Never block primary write path on audit logging failures.
        return
