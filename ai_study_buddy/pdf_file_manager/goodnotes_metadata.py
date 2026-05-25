from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


GoodnotesDocumentMatchStatus = Literal[
    "matched_exact",
    "matched_leading_underscore_restored",
    "matched_raw_source",
    "matched_raw_source_leading_underscore_restored",
    "not_goodnotes_root",
    "not_main_file",
    "metadata_unavailable",
    "not_found",
    "ambiguous",
]


@dataclass(frozen=True)
class GoodnotesDocumentTimestamps:
    created_at: str | None
    updated_at: str | None
    last_modified: str | None
    created_at_raw: float | None
    updated_at_raw: float | None
    last_modified_raw: str | None


@dataclass(frozen=True)
class GoodnotesDocumentMatch:
    status: GoodnotesDocumentMatchStatus
    file_id: str
    registered_path: str
    backup_stem: str
    candidate_names: tuple[str, ...]
    matched_candidate_name: str | None
    goodnotes_document_id: str | None
    goodnotes_document_name: str | None
    goodnotes_folder_path: str | None
    goodnotes_folder_ids: tuple[str, ...]
    timestamps: GoodnotesDocumentTimestamps | None
    message: str | None = None


@dataclass(frozen=True)
class _Candidate:
    name: str
    status: GoodnotesDocumentMatchStatus


def _default_projection_db_path() -> Path:
    return Path.home() / "Library/Containers/com.goodnotesapp.x/Data/Library/Databases/projection.sqlite"


def _default_fts_db_path() -> Path:
    return Path.home() / "Library/Containers/com.goodnotesapp.x/Data/Library/Databases/fts.sqlite"


def _projection_db_path() -> Path:
    return Path(os.environ.get("GOODNOTES_PROJECTION_DB", "") or _default_projection_db_path()).expanduser()


def _fts_db_path() -> Path:
    return Path(os.environ.get("GOODNOTES_FTS_DB", "") or _default_fts_db_path()).expanduser()


def _resolve_goodnotes_root() -> Path | None:
    env = os.environ.get("GOODNOTES_ROOT", "").strip()
    if env:
        root = Path(env).expanduser().resolve()
        return root if root.is_dir() else None

    config_file = Path(__file__).resolve().parents[1] / "local_goodnotes_root.txt"
    if config_file.is_file():
        for line in config_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            root = Path(line).expanduser().resolve()
            return root if root.is_dir() else None
    return None


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _is_goodnotes_path(path: Path) -> bool:
    root = _resolve_goodnotes_root()
    if root is not None:
        return _is_under(path, root)
    return "GoodNotes" in path.parts


def _iso_utc_from_unix_ms(value: float | int | None) -> str | None:
    if value is None:
        return None
    try:
        if float(value) <= 0:
            return None
        dt = datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
    except (OSError, OverflowError, TypeError, ValueError):
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_utc_from_sqlite_datetime(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        return text
    # Goodnotes stores document_meta.last_modified as a UTC datetime string.
    parsed = text.replace(" ", "T", 1)
    return f"{parsed}Z"


def _add_candidate(candidates: list[_Candidate], name: str, status: GoodnotesDocumentMatchStatus) -> None:
    if not name:
        return
    if any(candidate.name == name for candidate in candidates):
        return
    candidates.append(_Candidate(name=name, status=status))


def _raw_source_stem_from_main_stem(stem: str) -> str | None:
    if stem.startswith("_c_"):
        return stem[len("_c_") :]
    if stem.startswith("c_"):
        return stem[len("c_") :]
    return None


def _candidate_names(backup_stem: str, raw_source_stems: tuple[str, ...]) -> tuple[_Candidate, ...]:
    candidates: list[_Candidate] = []
    _add_candidate(candidates, backup_stem, "matched_exact")
    _add_candidate(candidates, f"_{backup_stem}", "matched_leading_underscore_restored")
    candidates.extend(_raw_source_candidates(backup_stem, raw_source_stems))
    return tuple(candidates)


def _primary_candidates(backup_stem: str) -> tuple[_Candidate, ...]:
    candidates: list[_Candidate] = []
    _add_candidate(candidates, backup_stem, "matched_exact")
    _add_candidate(candidates, f"_{backup_stem}", "matched_leading_underscore_restored")
    return tuple(candidates)


def _raw_source_candidates(backup_stem: str, raw_source_stems: tuple[str, ...]) -> tuple[_Candidate, ...]:
    candidates: list[_Candidate] = []
    raw_stems: list[str] = []
    for stem in raw_source_stems:
        if stem and stem not in raw_stems:
            raw_stems.append(stem)
    derived = _raw_source_stem_from_main_stem(backup_stem)
    if derived and derived not in raw_stems:
        raw_stems.append(derived)

    for stem in raw_stems:
        _add_candidate(candidates, stem, "matched_raw_source")
        _add_candidate(candidates, f"_{stem}", "matched_raw_source_leading_underscore_restored")
    return tuple(candidates)


def _empty_match(
    *,
    status: GoodnotesDocumentMatchStatus,
    file_id: str,
    registered_path: str,
    backup_stem: str,
    candidates: tuple[_Candidate, ...] = (),
    message: str | None = None,
) -> GoodnotesDocumentMatch:
    return GoodnotesDocumentMatch(
        status=status,
        file_id=file_id,
        registered_path=registered_path,
        backup_stem=backup_stem,
        candidate_names=tuple(candidate.name for candidate in candidates),
        matched_candidate_name=None,
        goodnotes_document_id=None,
        goodnotes_document_name=None,
        goodnotes_folder_path=None,
        goodnotes_folder_ids=(),
        timestamps=None,
        message=message,
    )


def _connect_projection_db() -> sqlite3.Connection | None:
    projection = _projection_db_path()
    fts = _fts_db_path()
    if not projection.is_file() or not fts.is_file():
        return None
    conn = sqlite3.connect(f"file:{projection}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS fts", (f"file:{fts}?mode=ro",))
    return conn


def _fetch_matches(
    conn: sqlite3.Connection,
    candidate_names: tuple[str, ...],
    *,
    include_deleted: bool,
) -> list[sqlite3.Row]:
    if not candidate_names:
        return []
    placeholders = ",".join("?" for _ in candidate_names)
    sql = f"""
        SELECT
            d.id,
            d.name,
            d.created_at,
            d.updated_at,
            d.deleted,
            m.last_modified,
            m.is_deleted AS meta_is_deleted
        FROM documents d
        LEFT JOIN fts.document_meta m ON m.document_id = d.id
        WHERE d.name IN ({placeholders})
    """
    params: list[object] = list(candidate_names)
    if not include_deleted:
        sql += " AND d.deleted = 0 AND COALESCE(m.is_deleted, 0) = 0"
    sql += " ORDER BY d.name, d.id"
    return conn.execute(sql, params).fetchall()


def _folder_path_for_document(conn: sqlite3.Connection, document_id: str) -> tuple[str | None, tuple[str, ...]]:
    row = conn.execute(
        """
        SELECT parent_folder_id
        FROM folder_to_folder_items
        WHERE item_id = ? AND deleted = 0
        ORDER BY id
        LIMIT 1
        """,
        (document_id,),
    ).fetchone()
    if row is None or not row["parent_folder_id"]:
        return None, ()

    folder_ids_leaf_to_root: list[str] = []
    folder_names_leaf_to_root: list[str] = []
    current_id = row["parent_folder_id"]
    seen: set[str] = set()
    while current_id and current_id not in seen and len(seen) < 50:
        seen.add(current_id)
        folder_row = conn.execute("SELECT name FROM folders WHERE id = ?", (current_id,)).fetchone()
        if folder_row is not None and folder_row["name"]:
            folder_ids_leaf_to_root.append(current_id)
            folder_names_leaf_to_root.append(folder_row["name"])
        parent_row = conn.execute(
            """
            SELECT parent_folder_id
            FROM folder_to_folder_items
            WHERE item_id = ? AND deleted = 0
            ORDER BY id
            LIMIT 1
            """,
            (current_id,),
        ).fetchone()
        current_id = parent_row["parent_folder_id"] if parent_row is not None else None

    folder_ids = tuple(reversed(folder_ids_leaf_to_root))
    folder_names = tuple(reversed(folder_names_leaf_to_root))
    folder_path = " / ".join(folder_names) if folder_names else None
    return folder_path, folder_ids


def get_goodnotes_document_match(
    *,
    file_id: str,
    registered_path: str,
    file_type: str,
    raw_source_stems: tuple[str, ...] = (),
    include_deleted: bool = False,
) -> GoodnotesDocumentMatch:
    path = Path(registered_path)
    backup_stem = path.stem
    if not _is_goodnotes_path(path):
        return _empty_match(
            status="not_goodnotes_root",
            file_id=file_id,
            registered_path=registered_path,
            backup_stem=backup_stem,
        )
    if file_type != "main":
        return _empty_match(
            status="not_main_file",
            file_id=file_id,
            registered_path=registered_path,
            backup_stem=backup_stem,
        )

    primary_candidates = _primary_candidates(backup_stem)
    raw_candidates = _raw_source_candidates(backup_stem, raw_source_stems)
    candidates = primary_candidates + tuple(candidate for candidate in raw_candidates if candidate.name not in {c.name for c in primary_candidates})
    try:
        conn = _connect_projection_db()
    except sqlite3.Error as exc:
        return _empty_match(
            status="metadata_unavailable",
            file_id=file_id,
            registered_path=registered_path,
            backup_stem=backup_stem,
            candidates=candidates,
            message=str(exc),
        )
    if conn is None:
        return _empty_match(
            status="metadata_unavailable",
            file_id=file_id,
            registered_path=registered_path,
            backup_stem=backup_stem,
            candidates=candidates,
            message="Goodnotes metadata databases not found",
        )

    try:
        active_candidates = primary_candidates
        rows = _fetch_matches(conn, tuple(candidate.name for candidate in active_candidates), include_deleted=include_deleted)
        if not rows and raw_candidates:
            active_candidates = raw_candidates
            rows = _fetch_matches(conn, tuple(candidate.name for candidate in active_candidates), include_deleted=include_deleted)
        if not rows:
            return _empty_match(
                status="not_found",
                file_id=file_id,
                registered_path=registered_path,
                backup_stem=backup_stem,
                candidates=candidates,
            )
        if len(rows) > 1:
            return _empty_match(
                status="ambiguous",
                file_id=file_id,
                registered_path=registered_path,
                backup_stem=backup_stem,
                candidates=candidates,
                message=f"Matched {len(rows)} Goodnotes documents",
            )

        row = rows[0]
        candidate_by_name = {candidate.name: candidate for candidate in active_candidates}
        matched_candidate = candidate_by_name.get(row["name"])
        status: GoodnotesDocumentMatchStatus = matched_candidate.status if matched_candidate else "matched_exact"
        folder_path, folder_ids = _folder_path_for_document(conn, row["id"])
        timestamps = GoodnotesDocumentTimestamps(
            created_at=_iso_utc_from_unix_ms(row["created_at"]),
            updated_at=_iso_utc_from_unix_ms(row["updated_at"]),
            last_modified=_iso_utc_from_sqlite_datetime(row["last_modified"]),
            created_at_raw=row["created_at"],
            updated_at_raw=row["updated_at"],
            last_modified_raw=row["last_modified"],
        )
        return GoodnotesDocumentMatch(
            status=status,
            file_id=file_id,
            registered_path=registered_path,
            backup_stem=backup_stem,
            candidate_names=tuple(candidate.name for candidate in candidates),
            matched_candidate_name=row["name"],
            goodnotes_document_id=row["id"],
            goodnotes_document_name=row["name"],
            goodnotes_folder_path=folder_path,
            goodnotes_folder_ids=folder_ids,
            timestamps=timestamps,
        )
    except sqlite3.Error as exc:
        return _empty_match(
            status="metadata_unavailable",
            file_id=file_id,
            registered_path=registered_path,
            backup_stem=backup_stem,
            candidates=candidates,
            message=str(exc),
        )
    finally:
        conn.close()
