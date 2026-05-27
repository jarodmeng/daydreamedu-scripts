# Google Drive synced filesystem mtime → completion_date (proposal 17 §4.3).

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .page1 import inventory_root_from_path

DRIVE_MODIFIED_SOURCE = "drive_modified"
DRIVE_MODIFIED_CONFIDENCE = "medium"
SINGAPORE_TZ = ZoneInfo("Asia/Singapore")


@dataclass(frozen=True)
class DriveModifiedInference:
    completion_date: str
    source_detail: dict[str, Any]


def completion_date_from_mtime(
    mtime: float, *, tz: ZoneInfo = SINGAPORE_TZ
) -> tuple[str, str]:
    """Return (YYYY-MM-DD in tz, ISO UTC timestamp)."""
    dt_utc = datetime.fromtimestamp(mtime, tz=timezone.utc)
    dt_local = dt_utc.astimezone(tz)
    return dt_local.date().isoformat(), dt_utc.isoformat().replace("+00:00", "Z")


def infer_completion_date_from_drive_modified(
    path: str | Path,
    *,
    doc_type: str | None = None,
    inventory_root: str | None = None,
) -> DriveModifiedInference | None:
    """Read local synced file mtime; return None if missing or not d_root book."""
    if inventory_root is None:
        inventory_root = inventory_root_from_path(str(path))
    if inventory_root != "d_root":
        return None
    if doc_type is not None and doc_type != "book":
        return None

    file_path = Path(path)
    if not file_path.is_file():
        return None

    try:
        mtime = os.path.getmtime(file_path)
    except OSError:
        return None

    completion_date, mtime_utc = completion_date_from_mtime(mtime)
    return DriveModifiedInference(
        completion_date=completion_date,
        source_detail={
            "timezone": "Asia/Singapore",
            "mtime_utc": mtime_utc,
            "mtime_epoch": mtime,
            "path": str(file_path.resolve()),
        },
    )
