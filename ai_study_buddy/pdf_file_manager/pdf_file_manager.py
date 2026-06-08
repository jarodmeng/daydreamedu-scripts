# pdf_file_manager — Phase 1+2+3+4: DB schema, students, scan roots, register, compress, scan, read/update/delete, relations & groups.
# See SPEC.md, ARCHITECTURE.md, TESTING.md.

import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .completion_date.core import (
    COMPLETION_DATE_SOURCES,
    CompletionDateRecord,
    InferCompletionDatesReport,
    merge_infer_completion_dates_report,
    normalize_completion_date,
    normalize_completion_date_confidence,
    normalize_completion_date_source,
    normalize_inference_model,
    validate_inferred_completion_date_provenance,
)
from .completion_date.page1 import (
    default_page1_work_dir,
    infer_completion_date_for_file_cached_page1,
    infer_completion_dates_cached_page1,
    inventory_root_from_path,
)
from .completion_date.filename_term import (
    FILENAME_TERM_CONFIDENCE,
    FILENAME_TERM_SOURCE,
    infer_completion_date_from_filename_term,
)
from .goodnotes_metadata import GoodnotesDocumentMatch, GoodnotesFolderScope, get_goodnotes_document_match

logger = logging.getLogger(__name__)

# Ensure we can import compress_pdf from ai_study_buddy/utils/compress_pdf
_ai_study_buddy_dir = Path(__file__).resolve().parent.parent
_utils_dir = _ai_study_buddy_dir / "utils"
if str(_utils_dir) not in sys.path:
    sys.path.insert(0, str(_utils_dir))

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AlreadyRegisteredError(Exception):
    """Path is already in the registry."""

class NotFoundError(Exception):
    """File or record not found."""

class ConfigError(Exception):
    """Configuration error (e.g. no scan roots)."""

class InvalidMetadataError(ValueError):
    """metadata JSON contains an invalid value (e.g. legacy chinese_variant)."""


class InvalidDocTypeError(ValueError):
    """doc_type is not one of the canonical allowed values."""

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Student:
    id: str
    name: str
    email: str | None
    added_at: str

@dataclass
class ScanRoot:
    id: str
    path: str
    student_id: str | None
    added_at: str

@dataclass
class PdfFile:
    id: str
    name: str
    path: str
    file_type: str
    doc_type: str
    student_id: str | None
    subject: str | None
    is_template: bool
    size_bytes: int | None
    page_count: int | None
    has_raw: bool
    metadata: dict | None
    added_at: str
    updated_at: str
    notes: str | None

    @property
    def normal_name(self) -> str:
        """Canonical display name with technical prefixes and extension removed."""
        return normalize_pdf_display_name(self.name)

@dataclass
class CompressResult:
    """Result of compress_and_register; includes main_file_id."""
    main_file_id: str
    compressed: bool  # True if we kept compressed output; False if restored original
    raw_archive_id: str | None  # Set if we created a _raw_ file

@dataclass
class GoodNotesTemplateLinkOutcome:
    main_path: str
    template_path: str | None
    linked: bool
    already_linked: bool
    auto_fixed_template: bool
    dry_run: bool
    message: str | None

@dataclass
class ScanResult:
    file: PdfFile
    raw_archive: PdfFile | None
    compressed: bool
    template_link: GoodNotesTemplateLinkOutcome | None = None

@dataclass
class OperationRecord:
    id: str
    operation: str
    file_id: str | None
    group_id: str | None
    performed_at: str
    performed_by: str | None
    before_state: dict | None
    after_state: dict | None
    notes: str | None

@dataclass
class FileRelation:
    id: str
    source_id: str
    target_id: str
    relation_type: str  # 'raw_source' | 'main_version' | 'template_for' | 'completed_from'
    created_at: str

@dataclass
class FileGroupMember:
    group_id: str
    file_id: str
    role: str | None
    added_at: str
    file: PdfFile

@dataclass
class FileGroup:
    id: str
    label: str
    group_type: str  # 'exam' | 'book' | 'book_exercise' | 'collection'
    anchor_id: str | None
    created_at: str
    notes: str | None
    members: list[FileGroupMember]

@dataclass
class BookAnswerMapping:
    id: str
    unit_file_id: str
    answer_file_id: str
    answer_page_start: int
    answer_page_end: int
    starts_mid_page: bool
    ends_mid_page: bool
    source: str | None
    notes: str | None
    created_at: str
    updated_at: str
    unit_file: PdfFile
    answer_file: PdfFile

@dataclass
class SuggestedGroup:
    group_type: str
    candidate_files: list[PdfFile]
    match_basis: dict

@dataclass
class CoverageReport:
    """Result of report_coverage: leaf dirs (from FS or registry) vs scan_roots."""
    leaf_dirs: set[str]
    scan_roots: set[str]
    leaf_not_in_roots: set[str]
    roots_without_leaf_pdfs: set[str]


def _looks_like_compressed_main_name(name: str) -> bool:
    return name.startswith("_c_") or name.startswith("c_")


def has_raw_pdf_prefix(name: str) -> bool:
    """Return True if basename starts with a known raw prefix."""
    return name.startswith("_raw_") or name.startswith("raw_")


def normalize_pdf_display_name(name_or_path: str | Path) -> str:
    """Normalize a PDF filename/path to a human-facing stem.

    Rules:
    - Keep only the basename.
    - Remove extension via ``Path(...).stem``.
    - Iteratively strip technical prefixes: ``_raw_``, ``_c_``, ``raw_``, ``c_``.
    """
    stem = Path(str(name_or_path)).stem
    prefixes = ("_raw_", "_c_", "raw_", "c_")
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if stem.startswith(prefix):
                stem = stem[len(prefix) :]
                changed = True
                break
    return stem


def _reject_invalid_chinese_variant_in_metadata(metadata: dict | None) -> None:
    """Raise InvalidMetadataError if metadata uses the invalid legacy spelling for Standard 华文.

    The string ``foundation`` must not appear in ``metadata.chinese_variant`` — it collided with
    SEAB Foundation Chinese Language. Use ``standard`` for Chinese Language (Standard) / 华文 exams.
    """
    if not metadata:
        return
    if metadata.get("chinese_variant") == "foundation":
        raise InvalidMetadataError(
            'Invalid metadata.chinese_variant "foundation": use "standard" for Standard 华文 '
            "(Chinese Language Standard). Fix the stored JSON or pass chinese_variant=\"standard\"."
        )


def _metadata_json_for_persist(metadata: dict | None) -> str | None:
    if metadata is None:
        return None
    d = dict(metadata)
    _reject_invalid_chinese_variant_in_metadata(d)
    return json.dumps(d)


def _reject_unit_for_non_book_doc_type(metadata: dict | None, doc_type: str | None) -> None:
    """Raise when metadata.unit is set for non-book doc_type."""
    if not metadata:
        return
    if metadata.get("unit") in (None, ""):
        return
    if doc_type != "book":
        raise InvalidMetadataError(
            "metadata.unit is only allowed when doc_type='book'; "
            f"got doc_type={doc_type!r} with metadata.unit={metadata.get('unit')!r}"
        )


def _metadata_json_from_sql_value(raw_meta) -> str | None:
    """Serialize DB metadata column for INSERT/UPDATE with chinese_variant validation."""
    if raw_meta is None:
        return None
    if isinstance(raw_meta, str):
        d = json.loads(raw_meta) if raw_meta else {}
    else:
        d = dict(raw_meta) if raw_meta else {}
    _reject_invalid_chinese_variant_in_metadata(d)
    return json.dumps(d)


# Default registry path: ai_study_buddy/db/pdf_registry.db relative to repo root.
# Repo root = directory that contains "ai_study_buddy" (found by walking up from this file).
def _repo_root() -> Path:
    p = Path(__file__).resolve().parent
    for _ in range(6):
        if (p / "ai_study_buddy").is_dir():
            return p
        p = p.parent
    return Path.cwd()

def _default_db_path() -> Path:
    env = os.environ.get("PDF_REGISTRY_PATH")
    if env:
        return Path(env).resolve()
    return _repo_root() / "ai_study_buddy" / "db" / "pdf_registry.db"


def _schema_sql() -> str:
    schema_file = Path(__file__).resolve().parent / "schema.sql"
    return schema_file.read_text()

class PdfFileManager:
    _ALLOWED_SUBJECTS = ("english", "math", "science", "chinese")
    # Canonical doc_type values; keep in sync with DATA_MODEL.md / SPEC.md / README.md.
    _ALLOWED_DOC_TYPES = ("exam", "exercise", "book", "activity", "composition", "note")
    _ALLOWED_GROUP_TYPES = ("exam", "book", "book_exercise", "collection")
    _GRADE_SCOPE_SEGMENTS = ("P1", "P2", "P3", "P4", "P5", "P6", "PSLE")

    def __init__(self, db_path=None):
        self._db_path = Path(db_path).resolve() if db_path else _default_db_path()
        self._conn = None

    @property
    def db_path(self):
        return self._db_path

    def _ensure_db_dir(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._ensure_db_dir()
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            # SQLite foreign key enforcement is connection-local and OFF by default.
            # Enable it for all manager-managed operations.
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._ensure_schema()
        return self._conn

    def _ensure_schema(self):
        self._conn.executescript(_schema_sql())
        self._migrate_schema_if_needed()

    def _migrate_schema_if_needed(self):
        conn = self._conn
        assert conn is not None
        pdf_sql_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'pdf_files'"
        ).fetchone()
        pdf_sql = (pdf_sql_row["sql"] or "") if pdf_sql_row else ""
        # Trigger rebuild when new enum values are missing (historical migration checks).
        if "'exercise'" not in pdf_sql or "'composition'" not in pdf_sql:
            self._rebuild_pdf_files_table()

        group_sql_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'file_groups'"
        ).fetchone()
        group_sql = (group_sql_row["sql"] or "") if group_sql_row else ""
        if "'book'" not in group_sql:
            self._rebuild_file_groups_table()

        completion_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'file_completion_dates'"
        ).fetchone()
        if completion_table is None:
            self._ensure_file_completion_dates_table()
        else:
            self._migrate_file_completion_dates_if_needed()

    def _migrate_file_completion_dates_if_needed(self) -> None:
        conn = self._conn
        assert conn is not None
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(file_completion_dates)").fetchall()
        }
        if "inference_model" not in cols:
            conn.execute(
                "ALTER TABLE file_completion_dates ADD COLUMN inference_model TEXT"
            )
            conn.commit()
        sql_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'file_completion_dates'"
        ).fetchone()
        table_sql = (sql_row[0] or "") if sql_row else ""
        if table_sql and "drive_modified" not in table_sql:
            self._rebuild_file_completion_dates_table()

    def _file_completion_dates_create_sql(self) -> str:
        return """
            CREATE TABLE file_completion_dates (
                file_id          TEXT PRIMARY KEY
                                 REFERENCES pdf_files(id) ON DELETE CASCADE,
                completion_date  TEXT NOT NULL
                                 CHECK (completion_date GLOB '????-??-??'),
                source           TEXT NOT NULL
                                 CHECK (source IN (
                                     'handwritten_page1',
                                     'filename_term',
                                     'drive_modified',
                                     'goodnotes_last_modified',
                                     'goodnotes_updated_at',
                                     'manual'
                                 )),
                confidence       TEXT
                                 CHECK (confidence IS NULL OR confidence IN ('high', 'medium', 'low')),
                inference_model  TEXT,
                source_detail    TEXT,
                inferred_at      TEXT NOT NULL,
                updated_at       TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_file_completion_dates_completion_date
                ON file_completion_dates (completion_date);
        """

    def _rebuild_file_completion_dates_table(self) -> None:
        conn = self._conn
        assert conn is not None
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(
            """
            BEGIN;
            CREATE TABLE file_completion_dates_new (
                file_id          TEXT PRIMARY KEY
                                 REFERENCES pdf_files(id) ON DELETE CASCADE,
                completion_date  TEXT NOT NULL
                                 CHECK (completion_date GLOB '????-??-??'),
                source           TEXT NOT NULL
                                 CHECK (source IN (
                                     'handwritten_page1',
                                     'filename_term',
                                     'drive_modified',
                                     'goodnotes_last_modified',
                                     'goodnotes_updated_at',
                                     'manual'
                                 )),
                confidence       TEXT
                                 CHECK (confidence IS NULL OR confidence IN ('high', 'medium', 'low')),
                inference_model  TEXT,
                source_detail    TEXT,
                inferred_at      TEXT NOT NULL,
                updated_at       TEXT NOT NULL
            );
            INSERT INTO file_completion_dates_new (
                file_id, completion_date, source, confidence, inference_model,
                source_detail, inferred_at, updated_at
            )
            SELECT
                file_id, completion_date, source, confidence, inference_model,
                source_detail, inferred_at, updated_at
            FROM file_completion_dates;
            DROP TABLE file_completion_dates;
            ALTER TABLE file_completion_dates_new RENAME TO file_completion_dates;
            CREATE INDEX idx_file_completion_dates_completion_date
                ON file_completion_dates (completion_date);
            COMMIT;
            """
        )
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()

    def _ensure_file_completion_dates_table(self) -> None:
        conn = self._conn
        assert conn is not None
        conn.executescript(self._file_completion_dates_create_sql())
        conn.commit()

    def _rebuild_pdf_files_table(self):
        conn = self._conn
        assert conn is not None
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(
            """
            BEGIN;
            CREATE TABLE pdf_files_new (
                id             TEXT PRIMARY KEY,
                name           TEXT NOT NULL,
                path           TEXT NOT NULL UNIQUE,
                file_type      TEXT NOT NULL DEFAULT 'unknown'
                               CHECK(file_type IN ('main', 'raw', 'unknown')),
                doc_type       TEXT NOT NULL
                               CHECK(doc_type IN ('exam', 'exercise', 'book', 'activity', 'composition', 'note')),
                student_id     TEXT REFERENCES students(id),
                subject        TEXT
                               CHECK(subject IN ('english', 'math', 'science', 'chinese')),
                is_template    BOOLEAN NOT NULL DEFAULT 0,
                size_bytes     INTEGER,
                page_count     INTEGER,
                has_raw        BOOLEAN NOT NULL DEFAULT 0,
                metadata       TEXT,
                added_at       TEXT NOT NULL,
                updated_at     TEXT NOT NULL,
                notes          TEXT
            );
            INSERT INTO pdf_files_new (
                id, name, path, file_type, doc_type, student_id, subject, is_template,
                size_bytes, page_count, has_raw, metadata, added_at, updated_at, notes
            )
            SELECT
                id,
                name,
                path,
                file_type,
                CASE doc_type
                    WHEN 'worksheet' THEN 'exercise'
                    WHEN 'notes' THEN 'note'
                    ELSE doc_type
                END AS doc_type,
                student_id,
                subject,
                is_template,
                size_bytes, page_count, has_raw, metadata, added_at, updated_at, notes
            FROM pdf_files;
            DROP TABLE pdf_files;
            ALTER TABLE pdf_files_new RENAME TO pdf_files;
            COMMIT;
            """
        )
        conn.execute("PRAGMA foreign_keys = ON")

    def _rebuild_file_groups_table(self):
        conn = self._conn
        assert conn is not None
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(
            """
            BEGIN;
            CREATE TABLE file_groups_new (
                id         TEXT PRIMARY KEY,
                label      TEXT NOT NULL,
                group_type TEXT NOT NULL DEFAULT 'collection'
                           CHECK(group_type IN ('exam', 'book', 'book_exercise', 'collection')),
                anchor_id  TEXT REFERENCES pdf_files(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL,
                notes      TEXT
            );
            INSERT INTO file_groups_new (id, label, group_type, anchor_id, created_at, notes)
            SELECT id, label, group_type, anchor_id, created_at, notes
            FROM file_groups;
            DROP TABLE file_groups;
            ALTER TABLE file_groups_new RENAME TO file_groups;
            COMMIT;
            """
        )
        conn.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def _normalize_doc_type(cls, doc_type: str) -> str:
        """Return canonical doc_type or raise InvalidDocTypeError.

        Single-shot migration: only canonical values are accepted; legacy/unknown
        values are rejected rather than mapped.
        """
        if doc_type is None:
            raise InvalidDocTypeError("doc_type cannot be None")
        value = str(doc_type).strip().lower()
        if value not in cls._ALLOWED_DOC_TYPES:
            raise InvalidDocTypeError(
                f"Invalid doc_type {doc_type!r}; expected one of {', '.join(cls._ALLOWED_DOC_TYPES)}"
            )
        return value

    @classmethod
    def _validate_doc_type(cls, doc_type: str):
        # Backward-compatible wrapper used by existing call sites.
        cls._normalize_doc_type(doc_type)

    @classmethod
    def _validate_group_type(cls, group_type: str):
        if group_type not in cls._ALLOWED_GROUP_TYPES:
            raise ValueError(f"group_type must be one of {', '.join(cls._ALLOWED_GROUP_TYPES)}; got {group_type!r}")

    def _log_operation(
        self,
        operation: str,
        *,
        file_id: str | None = None,
        group_id: str | None = None,
        performed_by: str | None = None,
        before_state: str | None = None,
        after_state: str | None = None,
        notes: str | None = None,
    ):
        conn = self._get_connection()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            """
            INSERT INTO operation_log (id, operation, file_id, group_id, performed_at, performed_by, before_state, after_state, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), operation, file_id, group_id, now, performed_by, before_state, after_state, notes),
        )
        conn.commit()

    def _row_to_pdf_file(self, row: sqlite3.Row) -> PdfFile:
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta) if meta else None
        if meta is not None:
            _reject_invalid_chinese_variant_in_metadata(meta)
        return PdfFile(
            id=row["id"],
            name=row["name"],
            path=row["path"],
            file_type=row["file_type"],
            doc_type=row["doc_type"],
            student_id=row["student_id"],
            subject=row["subject"],
            is_template=bool(row["is_template"]),
            size_bytes=row["size_bytes"],
            page_count=row["page_count"],
            has_raw=bool(row["has_raw"]),
            metadata=meta,
            added_at=row["added_at"],
            updated_at=row["updated_at"],
            notes=row["notes"],
        )

    def _row_to_completion_date_record(self, row: sqlite3.Row) -> CompletionDateRecord:
        detail = row["source_detail"]
        if isinstance(detail, str):
            detail = json.loads(detail) if detail else None
        inference_model = row["inference_model"] if "inference_model" in row.keys() else None
        return CompletionDateRecord(
            file_id=row["file_id"],
            completion_date=row["completion_date"],
            source=row["source"],
            confidence=row["confidence"],
            inference_model=inference_model,
            source_detail=detail,
            inferred_at=row["inferred_at"],
            updated_at=row["updated_at"],
        )

    def _validate_completion_date_target(self, file_id: str) -> PdfFile:
        pdf = self.get_file(file_id)
        if pdf.file_type != "main":
            raise ValueError("completion_date applies only to file_type='main'")
        if pdf.is_template:
            raise ValueError(
                "completion_date applies only to student completions (is_template=False)"
            )
        if not pdf.student_id:
            raise ValueError("completion_date requires a registered student_id (v1)")
        return pdf

    def _row_to_book_answer_mapping(self, row: sqlite3.Row) -> BookAnswerMapping:
        unit_file = self.get_file(row["unit_file_id"])
        answer_file = self.get_file(row["answer_file_id"])
        if unit_file is None:
            raise NotFoundError(f"Mapped unit file not found: {row['unit_file_id']}")
        if answer_file is None:
            raise NotFoundError(f"Mapped answer file not found: {row['answer_file_id']}")
        return BookAnswerMapping(
            id=row["id"],
            unit_file_id=row["unit_file_id"],
            answer_file_id=row["answer_file_id"],
            answer_page_start=row["answer_page_start"],
            answer_page_end=row["answer_page_end"],
            starts_mid_page=bool(row["starts_mid_page"]),
            ends_mid_page=bool(row["ends_mid_page"]),
            source=row["source"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            unit_file=unit_file,
            answer_file=answer_file,
        )

    def _resolve_file_record(self, file_id_or_path):
        """Return (id, path, row) for a file by id or path; raise NotFoundError if absent."""
        conn = self._get_connection()
        s = str(file_id_or_path)
        is_path = "/" in s or "\\" in s or s.endswith(".pdf") or (isinstance(file_id_or_path, Path) and file_id_or_path.suffix == ".pdf")
        if is_path:
            path = Path(file_id_or_path).resolve()
            row = conn.execute("SELECT * FROM pdf_files WHERE path = ?", (str(path),)).fetchone()
        else:
            row = conn.execute("SELECT * FROM pdf_files WHERE id = ?", (s,)).fetchone()
        if not row:
            raise NotFoundError(f"File not found: {file_id_or_path}")
        return row["id"], row["path"], row

    def _book_group_ids_for_file(self, file_id: str) -> set[str]:
        conn = self._get_connection()
        rows = conn.execute(
            """
            SELECT fgm.group_id
            FROM file_group_members fgm
            JOIN file_groups fg ON fg.id = fgm.group_id
            WHERE fgm.file_id = ? AND fg.group_type = 'book'
            """,
            (file_id,),
        ).fetchall()
        return {row["group_id"] for row in rows}

    def _validate_book_answer_mapping_files(self, unit_file_id: str, answer_file_id: str) -> str | None:
        unit_file = self.get_file(unit_file_id)
        if unit_file is None:
            raise NotFoundError(f"File not found: {unit_file_id}")
        answer_file = self.get_file(answer_file_id)
        if answer_file is None:
            raise NotFoundError(f"File not found: {answer_file_id}")
        if unit_file.file_type != "main" or answer_file.file_type != "main":
            raise ValueError("Book answer mappings require both files to have file_type='main'")
        if unit_file.doc_type != "book" or answer_file.doc_type != "book":
            raise ValueError("Book answer mappings require both files to have doc_type='book'")
        shared_group_ids = self._book_group_ids_for_file(unit_file_id) & self._book_group_ids_for_file(answer_file_id)
        if shared_group_ids:
            return sorted(shared_group_ids)[0]
        unit_group_ids = self._book_group_ids_for_file(unit_file_id)
        if unit_group_ids:
            return sorted(unit_group_ids)[0]
        answer_group_ids = self._book_group_ids_for_file(answer_file_id)
        if answer_group_ids:
            return sorted(answer_group_ids)[0]
        return None

    # ---------------------------------------------------------------------------
    # Student management
    # ---------------------------------------------------------------------------

    def add_student(self, id: str, name: str, email: str | None = None) -> Student:
        conn = self._get_connection()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "INSERT INTO students (id, name, email, added_at) VALUES (?, ?, ?, ?)",
            (id, name, email, now),
        )
        conn.commit()
        return Student(id=id, name=name, email=email, added_at=now)

    def get_student(self, student_id: str) -> Student | None:
        row = self._get_connection().execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)
        ).fetchone()
        if not row:
            return None
        return Student(id=row["id"], name=row["name"], email=row["email"], added_at=row["added_at"])

    def list_students(self) -> list[Student]:
        conn = self._get_connection()
        rows = conn.execute("SELECT * FROM students ORDER BY added_at").fetchall()
        return [Student(id=r["id"], name=r["name"], email=r["email"], added_at=r["added_at"]) for r in rows]

    # ---------------------------------------------------------------------------
    # Scan root management
    # ---------------------------------------------------------------------------

    def add_scan_root(self, path: str, student_id: str | None = None) -> ScanRoot:
        path = str(Path(path).resolve())
        if student_id is None:
            student_id = self._infer_student_id_from_path(path)
        conn = self._get_connection()
        root_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "INSERT INTO scan_roots (id, path, student_id, added_at) VALUES (?, ?, ?, ?)",
            (root_id, path, student_id, now),
        )
        conn.commit()
        return ScanRoot(id=root_id, path=path, student_id=student_id, added_at=now)

    def remove_scan_root(self, path: str) -> None:
        path = str(Path(path).resolve())
        conn = self._get_connection()
        conn.execute("DELETE FROM scan_roots WHERE path = ?", (path,))
        conn.commit()

    def list_scan_roots(self) -> list[ScanRoot]:
        rows = self._get_connection().execute(
            "SELECT * FROM scan_roots ORDER BY added_at"
        ).fetchall()
        return [
            ScanRoot(id=r["id"], path=r["path"], student_id=r["student_id"], added_at=r["added_at"])
            for r in rows
        ]

    def ensure_student(self, student_id: str, name: str, email: str | None = None) -> Student:
        """Return existing student or add and return. Idempotent."""
        existing = self.get_student(student_id)
        if existing is not None:
            return existing
        return self.add_student(student_id, name, email)

    def ensure_scan_root(self, path: str | Path, student_id: str | None = None) -> ScanRoot:
        """Return existing scan root for path or add and return. Idempotent. Path is resolved."""
        path_str = str(Path(path).resolve())
        for r in self.list_scan_roots():
            if r.path == path_str:
                return r
        return self.add_scan_root(path_str, student_id=student_id)

    def _infer_student_id_from_path(self, path: str | Path) -> str | None:
        """Resolve a registered student's email folder in the path to that student's id."""
        resolved = Path(path).resolve()
        parts = set(resolved.parts)
        matches: list[str] = []
        for student in self.list_students():
            if student.email and student.email in parts:
                matches.append(student.id)
        if len(matches) == 1:
            return matches[0]
        return None

    # ---------------------------------------------------------------------------
    # Coverage (find_leaf_dirs, report_coverage)
    # ---------------------------------------------------------------------------

    @staticmethod
    def find_leaf_dirs(base: Path) -> list[Path]:
        """Return sorted list of directories under base that have no subdirectories (leaf dirs). Includes base if it has no subdirs."""
        out: list[Path] = []
        base = base.resolve()
        if not base.is_dir():
            return []
        try:
            base_subs = [x for x in base.iterdir() if x.is_dir()]
        except OSError:
            return []
        if not base_subs:
            return [base]
        for p in sorted(base.rglob("*")):
            if not p.is_dir():
                continue
            try:
                subs = [x for x in p.iterdir() if x.is_dir()]
            except OSError:
                continue
            if not subs:
                out.append(p)
        return sorted(out)

    def report_coverage(
        self,
        base_path: Path | None = None,
        from_registry: bool = False,
    ) -> CoverageReport:
        """Compare leaf dirs (from filesystem or from pdf_files.path parents) to scan_roots."""
        scan_roots_set = {r.path for r in self.list_scan_roots()}
        if from_registry:
            conn = self._get_connection()
            rows = conn.execute("SELECT path FROM pdf_files").fetchall()
            leaf_dirs_set = {str(Path(r[0]).parent) for r in rows}
        elif base_path is not None:
            leaf_dirs_set = {str(p.resolve()) for p in self.find_leaf_dirs(Path(base_path))}
        else:
            leaf_dirs_set = set()
        leaf_not_in_roots = leaf_dirs_set - scan_roots_set
        roots_without_leaf_pdfs = scan_roots_set - leaf_dirs_set
        return CoverageReport(
            leaf_dirs=leaf_dirs_set,
            scan_roots=scan_roots_set,
            leaf_not_in_roots=leaf_not_in_roots,
            roots_without_leaf_pdfs=roots_without_leaf_pdfs,
        )

    # ---------------------------------------------------------------------------
    # Read (get_file used by register_file return and callers)
    # ---------------------------------------------------------------------------

    def get_file(self, file_id: str) -> PdfFile | None:
        row = self._get_connection().execute(
            "SELECT * FROM pdf_files WHERE id = ?", (file_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_pdf_file(row)

    def get_file_by_path(self, path: str | Path) -> PdfFile | None:
        path = str(Path(path).resolve())
        row = self._get_connection().execute(
            "SELECT * FROM pdf_files WHERE path = ?", (path,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_pdf_file(row)

    def find_files(
        self,
        query: str | None = None,
        file_type: str | None = None,
        doc_type: str | None = None,
        student_id: str | None = None,
        subject: str | None = None,
        is_template: bool | None = None,
        has_raw: bool | None = None,
    ) -> list[PdfFile]:
        conn = self._get_connection()
        sql = "SELECT * FROM pdf_files WHERE 1=1"
        params: list = []
        if query is not None:
            sql += " AND LOWER(name) LIKE LOWER(?)"
            params.append(f"%{query}%")
        if file_type is not None:
            sql += " AND file_type = ?"
            params.append(file_type)
        if doc_type is not None:
            sql += " AND doc_type = ?"
            params.append(doc_type)
        if student_id is not None:
            sql += " AND student_id = ?"
            params.append(student_id)
        if subject is not None:
            sql += " AND subject = ?"
            params.append(subject)
        if is_template is not None:
            sql += " AND is_template = ?"
            params.append(1 if is_template else 0)
        if has_raw is not None:
            sql += " AND has_raw = ?"
            params.append(1 if has_raw else 0)
        sql += " ORDER BY added_at"
        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_pdf_file(row) for row in rows]

    def _raw_source_stems_for_file(self, file_id: str) -> tuple[str, ...]:
        raw_stems: list[str] = []
        for related_file, _relation_type in self.get_related_files(file_id):
            if related_file.file_type == "raw":
                stem = Path(related_file.path).stem
                if stem not in raw_stems:
                    raw_stems.append(stem)
        return tuple(raw_stems)

    def get_goodnotes_document_timestamps_for_file(
        self,
        file_id: str,
        *,
        include_deleted: bool = False,
        folder_scope: GoodnotesFolderScope | None = None,
    ) -> GoodnotesDocumentMatch:
        """Return Goodnotes document timestamps/folder metadata for a registered g_root main.

        The lookup is read-only against Goodnotes' local macOS metadata DBs and returns a
        structured status rather than guessing for unsupported or unmatched files.

        When multiple Goodnotes notebooks share the same name, ``folder_scope`` disambiguates:
        ``attempt`` prefers notebooks outside a ``Review`` leaf folder; ``review`` prefers
        notebooks inside ``... / Review``.
        """
        pdf_file = self.get_file(file_id)
        if pdf_file is None:
            raise NotFoundError(f"File not found: {file_id}")
        return get_goodnotes_document_match(
            file_id=pdf_file.id,
            registered_path=pdf_file.path,
            file_type=pdf_file.file_type,
            raw_source_stems=self._raw_source_stems_for_file(pdf_file.id),
            include_deleted=include_deleted,
            folder_scope=folder_scope,
        )

    def get_goodnotes_document_timestamps_for_path(
        self,
        path: str | Path,
        *,
        include_deleted: bool = False,
        folder_scope: GoodnotesFolderScope | None = None,
    ) -> GoodnotesDocumentMatch:
        """Return Goodnotes document timestamps/folder metadata for a registered g_root path."""
        pdf_file = self.get_file_by_path(path)
        if pdf_file is None:
            raise NotFoundError(f"File not found: {path}")
        return self.get_goodnotes_document_timestamps_for_file(
            pdf_file.id,
            include_deleted=include_deleted,
            folder_scope=folder_scope,
        )

    # ---------------------------------------------------------------------------
    # register_file
    # ---------------------------------------------------------------------------

    def register_file(
        self,
        path: str | Path,
        file_type: str | None = None,
        doc_type: str = "exam",
        student_id: str | None = None,
        subject: str | None = None,
        is_template: bool = False,
        metadata: dict | None = None,
        notes: str | None = None,
    ) -> PdfFile:
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if student_id is None:
            student_id = self._infer_student_id_from_path(path)
        name = path.name
        if file_type is None:
            if name.startswith("_raw_"):
                file_type = "raw"
            elif _looks_like_compressed_main_name(name):
                file_type = "main"
            else:
                file_type = "unknown"
        conn = self._get_connection()
        existing = conn.execute("SELECT id FROM pdf_files WHERE path = ?", (str(path),)).fetchone()
        if existing:
            raise AlreadyRegisteredError(f"Already registered: {path}")
        meta_json = _metadata_json_for_persist(metadata)
        if subject is not None and subject not in ("english", "math", "science", "chinese"):
            raise ValueError(f"subject must be one of english, math, science, chinese; got {subject!r}")
        doc_type = self._normalize_doc_type(doc_type)
        _reject_unit_for_non_book_doc_type(metadata, doc_type)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        file_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO pdf_files (
                id, name, path, file_type, doc_type, student_id, subject, is_template,
                size_bytes, page_count, has_raw, metadata, added_at, updated_at, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
            (
                file_id, name, str(path), file_type, doc_type, student_id, subject,
                1 if is_template else 0,
                path.stat().st_size if path.exists() else None,
                None, meta_json, now, now, notes,
            ),
        )
        conn.commit()
        self._log_operation("register", file_id=file_id, after_state=json.dumps({"path": str(path), "file_type": file_type}))
        return self.get_file(file_id)

    # ---------------------------------------------------------------------------
    # compress_and_register
    # ---------------------------------------------------------------------------

    def compress_and_register(
        self,
        file_id_or_path,
        force: bool = False,
        min_savings_pct: float = 10,
        preserve_input: bool = False,
        **compress_kwargs,
    ) -> CompressResult:
        from compress_pdf.compress_pdf import compress_pdf as _do_compress

        conn = self._get_connection()
        s = str(file_id_or_path)
        is_path = "/" in s or "\\" in s or s.endswith(".pdf")
        if is_path:
            path = Path(file_id_or_path).resolve()
            row = conn.execute("SELECT * FROM pdf_files WHERE path = ?", (str(path),)).fetchone()
            if not row:
                self.register_file(path)
                row = conn.execute("SELECT * FROM pdf_files WHERE path = ?", (str(path),)).fetchone()
        else:
            row = conn.execute("SELECT * FROM pdf_files WHERE id = ?", (str(file_id_or_path),)).fetchone()
            if not row:
                raise NotFoundError(f"File not found: {file_id_or_path}")
        file_id, file_path, _ = row["id"], row["path"], row
        if row["file_type"] != "unknown":
            raise ValueError(f"compress_and_register requires file_type='unknown'; got {row['file_type']!r}")
        dir_path = Path(file_path).parent
        name = row["name"]
        # GoodNotes-safe variant: preserve the original input file and create a
        # new compressed copy alongside it, treating the original as raw.
        if preserve_input:
            raw_path = Path(file_path)
            raw_name = name
            main_name = f"_c_{name}"
            main_path = dir_path / main_name
            if main_path.exists():
                raise ValueError(f"Destination already exists: {main_path}")
        else:
            raw_name = f"_raw_{name}"
            raw_path = dir_path / raw_name
            if raw_path.exists():
                raise ValueError(f"Destination already exists: {raw_path}")
            shutil.move(str(file_path), str(raw_path))
            main_name = f"_c_{name}"
            main_path = dir_path / main_name
        try:
            result = _do_compress(
                str(raw_path),
                output_name=main_name,
                **compress_kwargs,
            )
            savings = result.savings_pct
        except Exception:
            # On failure, restore original location when we moved it.
            if not preserve_input:
                shutil.move(str(raw_path), str(file_path))
            raise
        if savings >= min_savings_pct and not result.skipped:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            main_id = str(uuid.uuid4())
            # When preserving input, the original row becomes the raw file; when
            # not preserving, we delete the original row and insert both main
            # and raw anew.
            if preserve_input:
                # Update existing row to represent the raw source at <file_path>
                conn.execute(
                    "UPDATE pdf_files SET file_type = 'raw', page_count = ?, updated_at = ? WHERE id = ?",
                    (result.pages, now, file_id),
                )
                raw_id = file_id
            else:
                conn.execute("DELETE FROM pdf_files WHERE id = ?", (file_id,))
                raw_id = str(uuid.uuid4())
                raw_size = raw_path.stat().st_size if raw_path.exists() else None
                conn.execute(
                    """INSERT INTO pdf_files (
                        id, name, path, file_type, doc_type, student_id, subject, is_template,
                        size_bytes, page_count, has_raw, metadata, added_at, updated_at, notes
                    ) VALUES (?, ?, ?, 'raw', ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
                    (
                        raw_id, raw_name, str(raw_path), row["doc_type"], row["student_id"], row["subject"],
                        1 if row["is_template"] else 0,
                        raw_size, result.pages, _metadata_json_from_sql_value(row["metadata"]), now, now, row["notes"],
                    ),
                )
            conn.execute(
                """INSERT INTO pdf_files (
                    id, name, path, file_type, doc_type, student_id, subject, is_template,
                    size_bytes, page_count, has_raw, metadata, added_at, updated_at, notes
                ) VALUES (?, ?, ?, 'main', ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
                (
                    main_id, main_name, str(main_path), row["doc_type"], row["student_id"], row["subject"],
                    1 if row["is_template"] else 0,
                    result.compressed_size, result.pages,
                    _metadata_json_from_sql_value(row["metadata"]), now, now, row["notes"],
                ),
            )
            rel_id1, rel_id2 = str(uuid.uuid4()), str(uuid.uuid4())
            conn.execute(
                "INSERT INTO file_relations (id, source_id, target_id, relation_type, created_at) VALUES (?, ?, ?, 'raw_source', ?)",
                (rel_id1, main_id, raw_id, now),
            )
            conn.execute(
                "INSERT INTO file_relations (id, source_id, target_id, relation_type, created_at) VALUES (?, ?, ?, 'main_version', ?)",
                (rel_id2, raw_id, main_id, now),
            )
            conn.commit()
            self._log_operation("compress", file_id=main_id, after_state=json.dumps({"savings_pct": savings}))
            if not preserve_input:
                self._log_operation("register", file_id=raw_id)
            self._log_operation("link", file_id=main_id)
            return CompressResult(main_file_id=main_id, compressed=True, raw_archive_id=raw_id)
        else:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if preserve_input:
                # Compression not worthwhile; keep original row as main at <file_path>.
                conn.execute(
                    "UPDATE pdf_files SET file_type = 'main', page_count = ?, updated_at = ? WHERE id = ?",
                    (result.pages, now, file_id),
                )
                # Clean up any temporary _c_ file if it was written.
                try:
                    if main_path.exists():
                        main_path.unlink()
                except OSError:
                    pass
                main_id, raw_id = file_id, None
            else:
                shutil.move(str(raw_path), str(file_path))  # restore original at <name>
                conn.execute(
                    "UPDATE pdf_files SET file_type = 'main', page_count = ?, updated_at = ? WHERE id = ?",
                    (result.pages, now, file_id),
                )
                main_id, raw_id = file_id, None
            conn.commit()
            self._log_operation("compress", file_id=main_id, notes="skipped=True")
            return CompressResult(main_file_id=main_id, compressed=False, raw_archive_id=raw_id)

    # ---------------------------------------------------------------------------
    # Path-based inference (L1 → subject, L3 → doc_type, L2 → grade_or_scope)
    # ---------------------------------------------------------------------------

    @staticmethod
    def _infer_book_folder(path: Path) -> Path | None:
        resolved = path.resolve()
        parts = resolved.parts
        try:
            book_idx = parts.index("Book")
        except ValueError:
            return None
        if book_idx + 1 >= len(parts):
            return None
        book_folder = Path(*parts[: book_idx + 2])
        return book_folder

    @staticmethod
    def _strip_technical_pdf_prefix(name: str) -> str:
        if name.startswith("_raw_"):
            return name[5:]
        if name.startswith("_c_"):
            return name[3:]
        if name.startswith("raw_"):
            return name[4:]
        if name.startswith("c_"):
            return name[2:]
        return name

    @staticmethod
    def _strip_redundant_leading_ascii_label(stem: str) -> str:
        for idx, char in enumerate(stem):
            if "\u4e00" <= char <= "\u9fff":
                prefix = stem[:idx]
                if prefix and all(ord(c) < 128 and (c.isalnum() or c in " ._-+&()[]") for c in prefix):
                    stripped = stem[idx:].lstrip(" -_.")
                    if stripped:
                        return stripped
                break
        return stem

    @classmethod
    def _infer_book_unit(cls, path: Path) -> str | None:
        book_folder = cls._infer_book_folder(path)
        if book_folder is None or path.suffix.lower() != ".pdf":
            return None
        current_stem = Path(cls._strip_technical_pdf_prefix(path.name)).stem.strip()
        if not current_stem:
            return None
        sibling_stems: list[str] = []
        try:
            for sibling in book_folder.glob("*.pdf"):
                stem = Path(cls._strip_technical_pdf_prefix(sibling.name)).stem.strip()
                if stem:
                    sibling_stems.append(stem)
        except OSError:
            sibling_stems = []
        if len(sibling_stems) <= 1:
            return cls._strip_redundant_leading_ascii_label(current_stem)
        common_prefix = os.path.commonprefix(sibling_stems).rstrip(" -_.")
        if common_prefix:
            remainder = current_stem[len(common_prefix):].lstrip(" -_.")
            if remainder:
                return remainder
        return cls._strip_redundant_leading_ascii_label(current_stem)

    @classmethod
    def _infer_from_path(cls, path: Path) -> dict:
        """Infer subject, doc_type, is_template, and metadata from path segments (DaydreamEdu layout).
        is_template: True when path has a grade/scope segment (P1–P6, PSLE) and no *student folder*
        (a segment containing @ immediately followed by a grade/scope segment). False when such a student folder exists.
        So Drive paths like .../GoogleDrive-user@gmail.com/.../P6/Exam yield is_template=True;
        .../user@mail.com/P5/Exam yields is_template=False.
        """
        out: dict = {}
        resolved = path.resolve()
        parts = resolved.parts
        has_student_folder = cls._path_has_student_mirror_layout(resolved)
        has_grade_scope = any(p in cls._GRADE_SCOPE_SEGMENTS for p in parts)
        if has_student_folder:
            out["is_template"] = False
        elif has_grade_scope:
            out["is_template"] = True
        for p in parts:
            lower = p.lower()
            if "science" in lower:
                out["subject"] = "science"
                break
            if "english" in lower:
                out["subject"] = "english"
                break
            if "math" in lower:
                out["subject"] = "math"
                break
            if "chinese" in lower:
                out["subject"] = "chinese"
                break
        for p in parts:
            if p == "Exam":
                out["doc_type"] = "exam"
                out.setdefault("metadata", {})["content_folder"] = "Exam"
                break
            if p == "Book":
                out["doc_type"] = "book"
                out.setdefault("metadata", {})["content_folder"] = "Book"
                unit = cls._infer_book_unit(resolved)
                if unit:
                    out.setdefault("metadata", {})["unit"] = unit
                break
            if p == "Exercise":
                out["doc_type"] = "exercise"
                out.setdefault("metadata", {})["content_folder"] = "Exercise"
                break
            if p == "Activity":
                out["doc_type"] = "activity"
                out.setdefault("metadata", {})["content_folder"] = "Activity"
                break
            if p == "Composition":
                out["doc_type"] = "composition"
                out.setdefault("metadata", {})["content_folder"] = "Composition"
                break
            if p == "Note":
                out["doc_type"] = "note"
                out.setdefault("metadata", {})["content_folder"] = "Note"
                break

        # Strictness: if the path is otherwise in-scope (has grade/scope and a subject),
        # but we couldn't resolve a content-folder segment, fail fast.
        if has_grade_scope and out.get("subject") and "doc_type" not in out:
            raise InvalidDocTypeError(
                "Could not infer doc_type from path (missing one of: Exam/Exercise/Book/Activity/Composition/Note): "
                f"{str(resolved)}"
            )
        for p in parts:
            if p in cls._GRADE_SCOPE_SEGMENTS:
                out.setdefault("metadata", {})["grade_or_scope"] = p
                break
        # Chinese exam variant (Standard 华文 vs 高华) from filename. Stored as 'standard'|'higher'.
        # Applies only when subject is chinese and doc_type is exam.
        if out.get("subject") == "chinese" and out.get("doc_type") == "exam":
            name = resolved.name
            lower = name.lower()
            variant: str | None = None
            if "高华" in name or ".hc." in lower:
                variant = "higher"
            elif "华文" in name or ".chinese." in lower:
                variant = "standard"  # Chinese Language (Standard) / 华文 — not SEAB Foundation Chinese Language
            if variant:
                out.setdefault("metadata", {})["chinese_variant"] = variant
        return out

    @classmethod
    def _path_has_student_mirror_layout(cls, path: Path) -> bool:
        """Return True when path contains a student email segment immediately followed by a grade/scope segment."""
        parts = path.resolve().parts
        return any(
            "@" in parts[i] and i + 1 < len(parts) and parts[i + 1] in cls._GRADE_SCOPE_SEGMENTS
            for i in range(len(parts))
        )

    # ---------------------------------------------------------------------------
    # GoodNotes template auto-link (scan helper)
    # ---------------------------------------------------------------------------

    def _preview_goodnotes_template_link(
        self,
        main_path: Path,
        *,
        auto_fix_template: bool = True,
    ) -> GoodNotesTemplateLinkOutcome:
        main_path = main_path.resolve()
        try:
            resolved_template_path = self.resolve_goodnotes_template_path(main_path)
        except ValueError as exc:
            return GoodNotesTemplateLinkOutcome(
                main_path=str(main_path),
                template_path=None,
                linked=False,
                already_linked=False,
                auto_fixed_template=False,
                dry_run=True,
                message=str(exc),
            )

        template_file = self.get_file_by_path(resolved_template_path)
        auto_fix_needed = template_file is not None and not template_file.is_template
        completed_file = self.get_file_by_path(main_path)
        existing_template = self.get_template(completed_file.id) if completed_file else None
        message = None
        already_linked = False
        if existing_template is not None:
            if Path(existing_template.path).resolve() == resolved_template_path:
                already_linked = True
                message = "Already linked to the resolved template"
            else:
                message = "Already linked to a different template"
        elif template_file is None:
            if resolved_template_path.exists():
                message = "Resolved template exists on disk but is not registered"
            else:
                message = "Resolved template path not found on disk or in registry"
        elif template_file.file_type != "main":
            message = "Resolved template is registered but is not a main file"
        elif auto_fix_needed and not auto_fix_template:
            message = "Resolved template is registered but is_template=False"
        elif auto_fix_needed:
            message = "Would auto-fix resolved template is_template and link"
        else:
            message = "Would link resolved template"

        return GoodNotesTemplateLinkOutcome(
            main_path=str(main_path),
            template_path=str(resolved_template_path),
            linked=False,
            already_linked=already_linked,
            auto_fixed_template=False,
            dry_run=True,
            message=message,
        )

    def _try_link_goodnotes_template_for_file(
        self,
        main_path: str | Path,
        *,
        auto_fix_template: bool = True,
        inherit_metadata: bool = True,
    ) -> GoodNotesTemplateLinkOutcome:
        resolved_path = Path(main_path).resolve()
        try:
            return self.link_goodnotes_template_for_file(
                main_path,
                auto_fix_template=auto_fix_template,
                inherit_metadata=inherit_metadata,
            )
        except (NotFoundError, ValueError) as exc:
            template_path: str | None = None
            try:
                template_path = str(self.resolve_goodnotes_template_path(resolved_path))
            except ValueError:
                pass
            return GoodNotesTemplateLinkOutcome(
                main_path=str(resolved_path),
                template_path=template_path,
                linked=False,
                already_linked=False,
                auto_fixed_template=False,
                dry_run=False,
                message=str(exc),
            )

    def _auto_link_goodnotes_after_scan(
        self,
        pdf_path: Path,
        *,
        dry_run: bool,
        auto_link_goodnotes: bool,
        auto_fix_template: bool = True,
        inherit_metadata: bool = True,
    ) -> GoodNotesTemplateLinkOutcome | None:
        if not auto_link_goodnotes or "GoodNotes" not in pdf_path.parts:
            return None
        inferred = self._infer_from_path(pdf_path)
        if inferred.get("is_template"):
            return None
        if dry_run:
            return self._preview_goodnotes_template_link(
                pdf_path,
                auto_fix_template=auto_fix_template,
            )
        return self._try_link_goodnotes_template_for_file(
            pdf_path,
            auto_fix_template=auto_fix_template,
            inherit_metadata=inherit_metadata,
        )

    # ---------------------------------------------------------------------------
    # scan_for_new_files
    # ---------------------------------------------------------------------------

    def scan_for_new_files(
        self,
        roots: list[str | Path] | None = None,
        min_savings_pct: float = 10,
        dry_run: bool = False,
        auto_link_goodnotes: bool = True,
        auto_fix_template: bool = True,
        inherit_metadata: bool = True,
        on_file_start: Callable[[Path], None] | None = None,
    ) -> list[ScanResult]:
        def _build_dry_run_preview(file_type: str, pdf_path: Path, inferred: dict, inferred_student_id: str | None) -> PdfFile:
            metadata = inferred.get("metadata")
            inferred_doc_type = self._normalize_doc_type(inferred.get("doc_type") or "exam")
            return PdfFile(
                id="",
                name=pdf_path.name,
                path=str(pdf_path.resolve()),
                file_type=file_type,
                doc_type=inferred_doc_type,
                student_id=inferred_student_id,
                subject=inferred.get("subject"),
                is_template=bool(inferred.get("is_template", False)),
                size_bytes=None,
                page_count=None,
                has_raw=False,
                metadata=metadata if metadata else None,
                added_at="",
                updated_at="",
                notes=None,
            )

        conn = self._get_connection()
        if roots is not None:
            configured_scan_roots = {r.path: r.student_id for r in self.list_scan_roots()}
            root_entries = [
                (resolved_path, configured_scan_roots.get(resolved_path))
                for resolved_path in (str(Path(p).resolve()) for p in roots)
            ]
        else:
            scan_roots_list = self.list_scan_roots()
            if not scan_roots_list:
                raise ConfigError("No scan roots configured. Add one with: config add-root <path> [--student-id <id>]")
            root_entries = [ (r.path, r.student_id) for r in scan_roots_list ]
        registered_paths = { row[0] for row in conn.execute("SELECT path FROM pdf_files").fetchall() }
        results: list[ScanResult] = []
        book_folders_to_sync: set[Path] = set()
        for root_path, root_student_id in root_entries:
            root_p = Path(root_path)
            if not root_p.is_dir():
                continue
            # Scan only direct PDF children of each root. Callers that want to
            # process nested folders should pass those folders explicitly.
            for pdf_path in root_p.glob("*.pdf"):
                path_str = str(pdf_path.resolve())
                inferred = self._infer_from_path(pdf_path)
                inferred_student_id = root_student_id or self._infer_student_id_from_path(pdf_path)
                if inferred.get("doc_type") == "book":
                    book_folder = self._infer_book_folder(pdf_path)
                    if book_folder is not None:
                        book_folders_to_sync.add(book_folder)
                if path_str in registered_paths:
                    existing = self.get_file_by_path(pdf_path)
                    if existing and existing.file_type == "unknown":
                        if dry_run:
                            results.append(
                                ScanResult(
                                    file=existing,
                                    raw_archive=None,
                                    compressed=False,
                                )
                            )
                            continue
                        if on_file_start is not None:
                            on_file_start(pdf_path)
                        is_goodnotes = "GoodNotes" in pdf_path.parts
                        if is_goodnotes:
                            result = self.compress_and_register(existing.id, min_savings_pct=min_savings_pct, preserve_input=True)
                        else:
                            result = self.compress_and_register(existing.id, min_savings_pct=min_savings_pct)
                        if root_student_id:
                            conn.execute("UPDATE pdf_files SET student_id = ? WHERE id = ?", (root_student_id, result.main_file_id))
                            if result.raw_archive_id:
                                conn.execute("UPDATE pdf_files SET student_id = ? WHERE id = ?", (root_student_id, result.raw_archive_id))
                            conn.commit()
                        if inferred:
                            kwargs = {k: v for k, v in inferred.items() if k != "metadata" and v is not None}
                            if inferred_student_id is not None:
                                kwargs["student_id"] = inferred_student_id
                            if inferred.get("metadata"):
                                kwargs["metadata"] = inferred["metadata"]
                            if kwargs:
                                self.update_metadata(result.main_file_id, **kwargs)
                                if result.raw_archive_id:
                                    self.update_metadata(result.raw_archive_id, **kwargs)
                        main_file = self.get_file(result.main_file_id)
                        raw_file = self.get_file(result.raw_archive_id) if result.raw_archive_id else None
                        if main_file:
                            results.append(ScanResult(file=main_file, raw_archive=raw_file, compressed=result.compressed))
                        continue
                    if not dry_run:
                        if existing and inferred:
                            kwargs = {k: v for k, v in inferred.items() if k != "metadata" and v is not None}
                            if inferred_student_id is not None:
                                kwargs["student_id"] = inferred_student_id
                            if inferred.get("metadata"):
                                kwargs["metadata"] = inferred["metadata"]
                            if kwargs:
                                self.update_metadata(existing.id, **kwargs)
                    continue
                name = pdf_path.name
                if name.startswith("_raw_"):
                    if dry_run:
                        continue
                    self.register_file(pdf_path)
                    main_name = name[5:]
                    parent = pdf_path.parent
                    main_path_plain = str((parent / main_name).resolve())
                    main_path_c = str((parent / f"_c_{main_name}").resolve())
                    main_row = conn.execute(
                        "SELECT id, student_id, subject, doc_type, metadata FROM pdf_files WHERE path IN (?, ?)",
                        (main_path_plain, main_path_c),
                    ).fetchone()
                    if main_row:
                        raw_id = conn.execute("SELECT id FROM pdf_files WHERE path = ?", (path_str,)).fetchone()[0]
                        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        for rel_type, src, tgt in [("raw_source", main_row["id"], raw_id), ("main_version", raw_id, main_row["id"])]:
                            conn.execute(
                                "INSERT INTO file_relations (id, source_id, target_id, relation_type, created_at) VALUES (?, ?, ?, ?, ?)",
                                (str(uuid.uuid4()), src, tgt, rel_type, now),
                            )
                        conn.execute("UPDATE pdf_files SET has_raw = 1 WHERE id = ?", (main_row["id"],))
                        raw_size = pdf_path.stat().st_size if pdf_path.exists() else None
                        conn.execute(
                            "UPDATE pdf_files SET student_id = ?, subject = ?, doc_type = ?, metadata = ?, size_bytes = ? WHERE id = ?",
                            (
                                main_row["student_id"],
                                main_row["subject"],
                                main_row["doc_type"],
                                _metadata_json_from_sql_value(main_row["metadata"]),
                                raw_size,
                                raw_id,
                            ),
                        )
                        conn.commit()
                    continue
                if _looks_like_compressed_main_name(name):
                    if dry_run:
                        template_link = self._auto_link_goodnotes_after_scan(
                            pdf_path,
                            dry_run=True,
                            auto_link_goodnotes=auto_link_goodnotes,
                            auto_fix_template=auto_fix_template,
                            inherit_metadata=inherit_metadata,
                        )
                        results.append(ScanResult(
                            file=_build_dry_run_preview("main", pdf_path, inferred, inferred_student_id),
                            raw_archive=None,
                            compressed=False,
                            template_link=template_link,
                        ))
                        continue
                    reg = self.register_file(pdf_path)
                    registered_paths.add(path_str)
                    if root_student_id:
                        conn.execute("UPDATE pdf_files SET student_id = ? WHERE id = ?", (root_student_id, reg.id))
                        conn.commit()
                    if inferred:
                        kwargs = {k: v for k, v in inferred.items() if k != "metadata" and v is not None}
                        if inferred_student_id is not None:
                            kwargs["student_id"] = inferred_student_id
                        if inferred.get("metadata"):
                            kwargs["metadata"] = inferred["metadata"]
                        if kwargs:
                            self.update_metadata(reg.id, **kwargs)
                    main_file = self.get_file(reg.id)
                    if main_file:
                        template_link = self._auto_link_goodnotes_after_scan(
                            pdf_path,
                            dry_run=False,
                            auto_link_goodnotes=auto_link_goodnotes,
                            auto_fix_template=auto_fix_template,
                            inherit_metadata=inherit_metadata,
                        )
                        results.append(ScanResult(
                            file=main_file,
                            raw_archive=None,
                            compressed=False,
                            template_link=template_link,
                        ))
                    continue
                if dry_run:
                    results.append(ScanResult(
                        file=_build_dry_run_preview("unknown", pdf_path, inferred, inferred_student_id),
                        raw_archive=None,
                        compressed=False,
                    ))
                    continue
                if on_file_start is not None:
                    on_file_start(pdf_path)
                # For GoodNotes trees, prefer preserve_input=True so originals
                # are never renamed or moved; elsewhere keep existing behaviour.
                is_goodnotes = "GoodNotes" in pdf_path.parts
                if is_goodnotes:
                    result = self.compress_and_register(pdf_path, min_savings_pct=min_savings_pct, preserve_input=True)
                else:
                    result = self.compress_and_register(pdf_path, min_savings_pct=min_savings_pct)
                if root_student_id:
                    conn.execute("UPDATE pdf_files SET student_id = ? WHERE id = ?", (root_student_id, result.main_file_id))
                    if result.raw_archive_id:
                        conn.execute("UPDATE pdf_files SET student_id = ? WHERE id = ?", (root_student_id, result.raw_archive_id))
                    conn.commit()
                if inferred:
                    kwargs = {k: v for k, v in inferred.items() if k != "metadata" and v is not None}
                    if inferred_student_id is not None:
                        kwargs["student_id"] = inferred_student_id
                    if inferred.get("metadata"):
                        kwargs["metadata"] = inferred["metadata"]
                    if kwargs:
                        self.update_metadata(result.main_file_id, **kwargs)
                        if result.raw_archive_id:
                            self.update_metadata(result.raw_archive_id, **kwargs)
                main_file = self.get_file(result.main_file_id)
                raw_file = self.get_file(result.raw_archive_id) if result.raw_archive_id else None
                if main_file:
                    template_link = None
                    if is_goodnotes:
                        template_link = self._auto_link_goodnotes_after_scan(
                            Path(main_file.path),
                            dry_run=False,
                            auto_link_goodnotes=auto_link_goodnotes,
                            auto_fix_template=auto_fix_template,
                            inherit_metadata=inherit_metadata,
                        )
                    results.append(ScanResult(
                        file=main_file,
                        raw_archive=raw_file,
                        compressed=result.compressed,
                        template_link=template_link,
                    ))
        if not dry_run:
            for book_folder in sorted(book_folders_to_sync):
                self.ensure_book_group_from_path(book_folder)
        return results

    # ---------------------------------------------------------------------------
    # Phase 3: update_metadata, rename_file, move_file, delete_file, open_file
    # ---------------------------------------------------------------------------

    def update_metadata(
        self,
        file_id_or_path,
        doc_type: str | None = None,
        student_id: str | None = None,
        subject: str | None = None,
        is_template: bool | None = None,
        metadata: dict | None = None,
        notes: str | None = None,
        file_type: str | None = None,
        _skip_main_raw_sync: bool = False,
    ) -> PdfFile:
        file_id, file_path, row = self._resolve_file_record(file_id_or_path)
        if subject is not None and subject not in self._ALLOWED_SUBJECTS:
            raise ValueError(f"subject must be one of {', '.join(self._ALLOWED_SUBJECTS)}; got {subject!r}")
        if doc_type is not None:
            doc_type = self._normalize_doc_type(doc_type)
        if file_type is not None and file_type not in ("main", "raw", "unknown"):
            raise ValueError(f"file_type must be one of main, raw, unknown; got {file_type!r}")
        conn = self._get_connection()
        before = {k: row[k] for k in row.keys()}
        updates = []
        params = []
        if file_type is not None:
            updates.append("file_type = ?")
            params.append(file_type)
        if doc_type is not None:
            doc_type = self._normalize_doc_type(doc_type)
            updates.append("doc_type = ?")
            params.append(doc_type)
        if student_id is not None:
            updates.append("student_id = ?")
            params.append(student_id)
        if subject is not None:
            updates.append("subject = ?")
            params.append(subject)
        if is_template is not None:
            updates.append("is_template = ?")
            params.append(1 if is_template else 0)
        if metadata is not None:
            current = row["metadata"]
            if isinstance(current, str):
                current = json.loads(current) if current else {}
            else:
                current = dict(current) if current else {}
            merged = {**current, **metadata}
            effective_doc_type = doc_type if doc_type is not None else row["doc_type"]
            _reject_unit_for_non_book_doc_type(merged, effective_doc_type)
            _reject_invalid_chinese_variant_in_metadata(merged)
            updates.append("metadata = ?")
            params.append(json.dumps(merged) if merged else None)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if not updates:
            return self.get_file(file_id)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        updates.append("updated_at = ?")
        params.append(now)
        params.append(file_id)
        conn.execute(
            "UPDATE pdf_files SET " + ", ".join(updates) + " WHERE id = ?",
            params,
        )
        conn.commit()
        after_row = conn.execute("SELECT * FROM pdf_files WHERE id = ?", (file_id,)).fetchone()
        after = {k: after_row[k] for k in after_row.keys()} if after_row else {}
        self._log_operation(
            "update_metadata",
            file_id=file_id,
            before_state=json.dumps(before),
            after_state=json.dumps(after),
        )
        if not _skip_main_raw_sync:
            sync_kwargs = {}
            if doc_type is not None:
                sync_kwargs["doc_type"] = doc_type
            if student_id is not None:
                sync_kwargs["student_id"] = student_id
            if subject is not None:
                sync_kwargs["subject"] = subject
            if is_template is not None:
                sync_kwargs["is_template"] = is_template
            if metadata is not None:
                sync_kwargs["metadata"] = metadata
            if sync_kwargs:
                raw_file, main_file = self._get_raw_main_pair(file_id)
                counterpart = None
                effective_type = after_row["file_type"] if after_row else row["file_type"]
                if raw_file and main_file:
                    counterpart = raw_file if effective_type == "main" else main_file
                if counterpart and counterpart.id != file_id:
                    self.update_metadata(counterpart.id, _skip_main_raw_sync=True, **sync_kwargs)
        return self.get_file(file_id)

    def delete_metadata_keys(
        self,
        file_id_or_path,
        keys: list[str],
        _skip_main_raw_sync: bool = False,
    ) -> PdfFile:
        if not keys:
            raise ValueError("keys must be a non-empty list of metadata keys")
        if any((not isinstance(k, str)) or (not k.strip()) for k in keys):
            raise ValueError("keys must contain only non-empty strings")

        file_id, _, row = self._resolve_file_record(file_id_or_path)
        current = row["metadata"]
        if isinstance(current, str):
            current = json.loads(current) if current else {}
        else:
            current = dict(current) if current else {}
        if not current:
            return self.get_file(file_id)

        keys_set = set(keys)
        mutated = False
        for key in keys_set:
            if key in current:
                current.pop(key, None)
                mutated = True
        if not mutated:
            return self.get_file(file_id)

        _reject_invalid_chinese_variant_in_metadata(current)
        conn = self._get_connection()
        before = {k: row[k] for k in row.keys()}
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "UPDATE pdf_files SET metadata = ?, updated_at = ? WHERE id = ?",
            (json.dumps(current) if current else None, now, file_id),
        )
        conn.commit()
        after_row = conn.execute("SELECT * FROM pdf_files WHERE id = ?", (file_id,)).fetchone()
        after = {k: after_row[k] for k in after_row.keys()} if after_row else {}
        self._log_operation(
            "delete_metadata_keys",
            file_id=file_id,
            before_state=json.dumps(before),
            after_state=json.dumps(after),
            notes=json.dumps({"keys": sorted(keys_set)}),
        )

        if not _skip_main_raw_sync:
            raw_file, main_file = self._get_raw_main_pair(file_id)
            counterpart = None
            effective_type = after_row["file_type"] if after_row else row["file_type"]
            if raw_file and main_file:
                counterpart = raw_file if effective_type == "main" else main_file
            if counterpart and counterpart.id != file_id:
                self.delete_metadata_keys(counterpart.id, list(keys_set), _skip_main_raw_sync=True)

        return self.get_file(file_id)

    def rename_file(self, file_id_or_path, new_name: str) -> PdfFile:
        file_id, file_path, row = self._resolve_file_record(file_id_or_path)
        old_path = Path(file_path)
        new_path = old_path.parent / new_name
        if new_path == old_path:
            return self.get_file(file_id)
        conn = self._get_connection()
        if new_path.exists() and not old_path.exists():
            # File was moved externally; sync DB to new path/name
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if new_path.is_file():
                sz = new_path.stat().st_size
                conn.execute(
                    "UPDATE pdf_files SET name = ?, path = ?, size_bytes = ?, updated_at = ? WHERE id = ?",
                    (new_name, str(new_path.resolve()), sz, now, file_id),
                )
            else:
                conn.execute(
                    "UPDATE pdf_files SET name = ?, path = ?, updated_at = ? WHERE id = ?",
                    (new_name, str(new_path.resolve()), now, file_id),
                )
            conn.commit()
            self._log_operation("rename", file_id=file_id, before_state=json.dumps({"path": file_path}), after_state=json.dumps({"path": str(new_path.resolve()), "name": new_name}))
            return self.get_file(file_id)
        if new_path.exists():
            raise ValueError(f"Destination already exists: {new_path}")
        existing = conn.execute("SELECT id FROM pdf_files WHERE path = ?", (str(new_path.resolve()),)).fetchone()
        if existing:
            raise ValueError(f"Destination already exists: {new_path}")
        shutil.move(str(old_path), str(new_path))
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "UPDATE pdf_files SET name = ?, path = ?, updated_at = ? WHERE id = ?",
            (new_name, str(new_path.resolve()), now, file_id),
        )
        conn.commit()
        self._log_operation("rename", file_id=file_id, before_state=json.dumps({"path": file_path}), after_state=json.dumps({"path": str(new_path.resolve()), "name": new_name}))
        return self.get_file(file_id)

    def _reapply_path_scope_fields(self, file_id: str, pdf_path: Path) -> None:
        """Refresh student_id, subject, doc_type, is_template, and path-derived metadata from the file path."""
        conn = self._get_connection()
        row = conn.execute("SELECT * FROM pdf_files WHERE id = ?", (file_id,)).fetchone()
        if not row:
            return
        inferred = self._infer_from_path(pdf_path)
        student_id = self._infer_student_id_from_path(pdf_path)
        subject = inferred.get("subject", row["subject"])
        doc_type = inferred.get("doc_type") or row["doc_type"]
        doc_type = self._normalize_doc_type(doc_type)
        if "is_template" in inferred:
            is_template = 1 if inferred["is_template"] else 0
        else:
            is_template = row["is_template"]
        current_meta = row["metadata"]
        if isinstance(current_meta, str):
            current_meta = json.loads(current_meta) if current_meta else {}
        else:
            current_meta = dict(current_meta) if current_meta else {}
        merged_meta = {**current_meta, **(inferred.get("metadata") or {})}
        _reject_invalid_chinese_variant_in_metadata(merged_meta)
        meta_json = json.dumps(merged_meta) if merged_meta else None
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            """UPDATE pdf_files SET student_id = ?, subject = ?, doc_type = ?, is_template = ?, metadata = ?, updated_at = ?
               WHERE id = ?""",
            (student_id, subject, doc_type, is_template, meta_json, now, file_id),
        )
        conn.commit()

    def move_file(self, file_id_or_path, new_dir: str | Path) -> PdfFile:
        file_id, file_path, row = self._resolve_file_record(file_id_or_path)
        old_path = Path(file_path)
        new_dir_p = Path(new_dir).resolve()
        new_path = new_dir_p / old_path.name
        if new_path == old_path:
            return self.get_file(file_id)
        conn = self._get_connection()
        if new_path.exists():
            raise ValueError(f"Destination already exists: {new_path}")
        existing = conn.execute("SELECT id FROM pdf_files WHERE path = ?", (str(new_path),)).fetchone()
        if existing:
            raise ValueError(f"Destination already exists: {new_path}")
        new_dir_p.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_path), str(new_path))
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "UPDATE pdf_files SET path = ?, updated_at = ? WHERE id = ?",
            (str(new_path), now, file_id),
        )
        conn.commit()
        self._log_operation("move", file_id=file_id, before_state=json.dumps({"path": file_path}), after_state=json.dumps({"path": str(new_path)}))
        self._reapply_path_scope_fields(file_id, new_path)
        return self.get_file(file_id)

    def delete_file(
        self,
        file_id_or_path,
        keep_related: bool = False,
        notes: str | None = None,
        deleted_by: str = "api",
    ) -> OperationRecord:
        file_id, file_path, row = self._resolve_file_record(file_id_or_path)
        conn = self._get_connection()
        file_type = row["file_type"]
        def _row_to_dict(r):
            return {k: r[k] for k in r.keys()}
        before_state = {
            "file": _row_to_dict(row),
            "relations": [_row_to_dict(r) for r in conn.execute(
                "SELECT * FROM file_relations WHERE source_id = ? OR target_id = ?", (file_id, file_id)
            ).fetchall()],
            "group_members": [_row_to_dict(r) for r in conn.execute(
                "SELECT * FROM file_group_members WHERE file_id = ?", (file_id,)
            ).fetchall()],
        }
        raw_id_to_cascade = None
        main_id_clear_has_raw = None
        if keep_related is False and file_type == "main":
            raw_row = conn.execute(
                "SELECT target_id FROM file_relations WHERE relation_type = 'raw_source' AND source_id = ?", (file_id,)
            ).fetchone()
            if raw_row:
                raw_id_to_cascade = raw_row["target_id"]
        if keep_related is False and file_type == "raw":
            main_row = conn.execute(
                "SELECT source_id FROM file_relations WHERE relation_type = 'raw_source' AND target_id = ?", (file_id,)
            ).fetchone()
            if main_row:
                main_id_clear_has_raw = main_row["source_id"]

        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            """INSERT INTO operation_log (id, operation, file_id, group_id, performed_at, performed_by, before_state, after_state, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (log_id, "delete", file_id, None, now, deleted_by, json.dumps(before_state), None, notes),
        )
        conn.commit()
        conn.execute("UPDATE file_groups SET anchor_id = NULL WHERE anchor_id = ?", (file_id,))
        conn.execute("DELETE FROM file_group_members WHERE file_id = ?", (file_id,))
        conn.execute(
            "DELETE FROM file_relations WHERE source_id = ? OR target_id = ?",
            (file_id, file_id),
        )
        try:
            os.remove(file_path)
        except FileNotFoundError:
            logger.warning("delete_file: path already absent on disk: %s", file_path)
        conn.execute("DELETE FROM pdf_files WHERE id = ?", (file_id,))
        conn.commit()

        if main_id_clear_has_raw:
            conn = self._get_connection()
            conn.execute("UPDATE pdf_files SET has_raw = 0 WHERE id = ?", (main_id_clear_has_raw,))
            conn.commit()
        if raw_id_to_cascade:
            self.delete_file(raw_id_to_cascade, keep_related=False, deleted_by="cascade")
        return OperationRecord(
            id=log_id,
            operation="delete",
            file_id=file_id,
            group_id=None,
            performed_at=now,
            performed_by=deleted_by,
            before_state=before_state,
            after_state=None,
            notes=notes,
        )

    def open_file(self, file_id_or_path) -> None:
        file_id, file_path, row = self._resolve_file_record(file_id_or_path)
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not on disk: {file_path}")
        if sys.platform == "darwin":
            subprocess.run(["open", str(p)], check=True)
        else:
            os.startfile(str(p)) if sys.platform == "win32" else subprocess.run(["xdg-open", str(p)], check=True)

    # ---------------------------------------------------------------------------
    # Phase 4: Relations & groups
    # ---------------------------------------------------------------------------

    def get_related_files(self, file_id: str) -> list[tuple[PdfFile, str]]:
        """Return raw/main counterpart (raw_source and main_version only). Each element is (PdfFile, relation_type)."""
        conn = self._get_connection()
        rows = conn.execute(
            """SELECT source_id, target_id, relation_type FROM file_relations
               WHERE (source_id = ? OR target_id = ?) AND relation_type IN ('raw_source', 'main_version')""",
            (file_id, file_id),
        ).fetchall()
        result = []
        for row in rows:
            other_id = row["target_id"] if row["source_id"] == file_id else row["source_id"]
            other = self.get_file(other_id)
            if other:
                result.append((other, row["relation_type"]))
        return result

    def _get_raw_main_pair(self, file_id: str) -> tuple[PdfFile | None, PdfFile | None]:
        current = self.get_file(file_id)
        if current is None:
            return None, None
        raw_file = current if current.file_type == "raw" else None
        main_file = current if current.file_type == "main" else None
        for other, _relation_type in self.get_related_files(file_id):
            if other.file_type == "raw":
                raw_file = other
            elif other.file_type == "main":
                main_file = other
        return raw_file, main_file

    def repair_main_raw_metadata_drift(self) -> list[dict]:
        """Repair invariant metadata drift by copying main-file values onto linked raw files."""
        conn = self._get_connection()
        rows = conn.execute(
            """
            SELECT raw.id AS raw_id, main.id AS main_id
            FROM file_relations fr
            JOIN pdf_files raw ON raw.id = fr.source_id
            JOIN pdf_files main ON main.id = fr.target_id
            WHERE fr.relation_type = 'main_version'
              AND raw.file_type = 'raw'
              AND main.file_type = 'main'
            ORDER BY raw.path
            """
        ).fetchall()
        repairs: list[dict] = []
        seen_raw_ids: set[str] = set()
        for row in rows:
            raw_id = row["raw_id"]
            main_id = row["main_id"]
            if raw_id in seen_raw_ids:
                continue
            seen_raw_ids.add(raw_id)
            raw_file = self.get_file(raw_id)
            main_file = self.get_file(main_id)
            if raw_file is None or main_file is None:
                continue
            repair_kwargs = {}
            if raw_file.doc_type != main_file.doc_type:
                repair_kwargs["doc_type"] = main_file.doc_type
            if raw_file.student_id != main_file.student_id:
                repair_kwargs["student_id"] = main_file.student_id
            if raw_file.subject != main_file.subject:
                repair_kwargs["subject"] = main_file.subject
            if raw_file.is_template != main_file.is_template:
                repair_kwargs["is_template"] = main_file.is_template
            if (raw_file.metadata or {}) != (main_file.metadata or {}):
                repair_kwargs["metadata"] = main_file.metadata or {}
            if repair_kwargs:
                self.update_metadata(raw_id, _skip_main_raw_sync=True, **repair_kwargs)
                repairs.append({"raw_id": raw_id, "main_id": main_id, "fields": sorted(repair_kwargs.keys())})
        return repairs

    def link_files(self, source_id: str, target_id: str, relation_type: str):
        """Create raw_source or main_version relation; inverse row created automatically. Updates has_raw on main."""
        if relation_type not in ("raw_source", "main_version"):
            raise ValueError(f"relation_type must be raw_source or main_version; got {relation_type!r}")
        conn = self._get_connection()
        main_id = source_id if relation_type == "raw_source" else target_id
        raw_id = target_id if relation_type == "raw_source" else source_id
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rid1, rid2 = str(uuid.uuid4()), str(uuid.uuid4())
        conn.execute(
            "INSERT INTO file_relations (id, source_id, target_id, relation_type, created_at) VALUES (?, ?, ?, ?, ?)",
            (rid1, source_id, target_id, relation_type, now),
        )
        inv_type = "main_version" if relation_type == "raw_source" else "raw_source"
        inv_src, inv_tgt = target_id, source_id
        conn.execute(
            "INSERT INTO file_relations (id, source_id, target_id, relation_type, created_at) VALUES (?, ?, ?, ?, ?)",
            (rid2, inv_src, inv_tgt, inv_type, now),
        )
        conn.execute("UPDATE pdf_files SET has_raw = 1 WHERE id = ?", (main_id,))
        conn.commit()
        self._log_operation("link", file_id=main_id)
        return FileRelation(id=rid1, source_id=source_id, target_id=target_id, relation_type=relation_type, created_at=now)

    def unlink_files(self, source_id: str, target_id: str) -> None:
        conn = self._get_connection()
        conn.execute(
            "DELETE FROM file_relations WHERE (source_id = ? AND target_id = ?) OR (source_id = ? AND target_id = ?)",
            (source_id, target_id, target_id, source_id),
        )
        for main_id in (source_id, target_id):
            row = conn.execute("SELECT id FROM pdf_files WHERE id = ? AND file_type = 'main'", (main_id,)).fetchone()
            if row:
                has_raw = conn.execute(
                    "SELECT 1 FROM file_relations WHERE relation_type = 'raw_source' AND source_id = ?", (main_id,)
                ).fetchone()
                conn.execute("UPDATE pdf_files SET has_raw = ? WHERE id = ?", (1 if has_raw else 0, main_id))
        conn.commit()
        self._log_operation("unlink", file_id=source_id)

    def link_to_template(self, completed_id: str, template_id: str, inherit_metadata: bool = True):
        completed = self.get_file(completed_id)
        template = self.get_file(template_id)
        if not completed or not template:
            raise NotFoundError(f"File not found: {completed_id or template_id}")
        if completed.file_type != "main" or template.file_type != "main":
            raise ValueError("link_to_template requires both files to be file_type='main'")
        if not template.is_template:
            raise ValueError("Template must have is_template=True")
        if completed.is_template:
            raise ValueError("Completed file must have is_template=False")
        conn = self._get_connection()
        existing = conn.execute(
            "SELECT 1 FROM file_relations WHERE source_id = ? AND relation_type = 'completed_from'", (completed_id,)
        ).fetchone()
        if existing:
            raise ValueError("Completed file is already linked to a template")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rid1, rid2 = str(uuid.uuid4()), str(uuid.uuid4())
        conn.execute(
            "INSERT INTO file_relations (id, source_id, target_id, relation_type, created_at) VALUES (?, ?, ?, 'template_for', ?)",
            (rid1, template_id, completed_id, now),
        )
        conn.execute(
            "INSERT INTO file_relations (id, source_id, target_id, relation_type, created_at) VALUES (?, ?, ?, 'completed_from', ?)",
            (rid2, completed_id, template_id, now),
        )
        if inherit_metadata:
            updates, params = [], []
            if template.subject and (completed.subject is None or completed.subject == "unknown"):
                updates.append("subject = ?")
                params.append(template.subject)
            if template.doc_type and completed.doc_type is None:
                updates.append("doc_type = ?")
                params.append(template.doc_type)
            if template.metadata and isinstance(template.metadata, dict):
                comp_meta = completed.metadata if isinstance(completed.metadata, dict) else {}
                merged = {**template.metadata, **(comp_meta or {})}
                _reject_invalid_chinese_variant_in_metadata(merged)
                updates.append("metadata = ?")
                params.append(json.dumps(merged) if merged else None)
            if updates:
                params.append(now)
                params.append(completed_id)
                conn.execute(
                    "UPDATE pdf_files SET " + ", ".join(updates) + ", updated_at = ? WHERE id = ?",
                    params,
                )
        conn.commit()
        self._log_operation("link_template", file_id=completed_id)
        return FileRelation(id=rid1, source_id=template_id, target_id=completed_id, relation_type="template_for", created_at=now)

    def unlink_template(self, completed_id: str) -> None:
        conn = self._get_connection()
        conn.execute(
            "DELETE FROM file_relations WHERE (source_id = ? AND relation_type = 'completed_from') OR (target_id = ? AND relation_type = 'template_for')",
            (completed_id, completed_id),
        )
        conn.commit()
        self._log_operation("unlink_template", file_id=completed_id)

    def get_template(self, file_id: str) -> PdfFile | None:
        conn = self._get_connection()
        row = conn.execute(
            "SELECT target_id FROM file_relations WHERE source_id = ? AND relation_type = 'completed_from'",
            (file_id,),
        ).fetchone()
        if not row:
            return None
        return self.get_file(row["target_id"])

    def get_completions(self, template_id: str) -> list[PdfFile]:
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT target_id FROM file_relations WHERE source_id = ? AND relation_type = 'template_for'",
            (template_id,),
        ).fetchall()
        out = []
        for row in rows:
            f = self.get_file(row["target_id"])
            if f:
                out.append(f)
        return out

    # -----------------------------------------------------------------------
    # Completion series (derived from template_for / completed_from)
    # -----------------------------------------------------------------------

    def completion_series_id(self, student_id: str, template_file_id: str) -> str | None:
        from ai_study_buddy.pdf_file_manager.completion_series import series_id_for

        template = self.get_file(template_file_id)
        if template is None or not template.is_template:
            return None
        student = self.get_student(student_id)
        name = student.name if student else None
        sid = student.id if student else student_id
        return series_id_for(sid, name, template_file_id)

    def get_completion_series(self, student_id: str, template_file_id: str):
        from ai_study_buddy.pdf_file_manager.completion_series import build_completion_series

        template = self.get_file(template_file_id)
        if template is None or not template.is_template:
            return None
        student = self.get_student(student_id)
        student_name = student.name if student else None
        sid = student.id if student else student_id
        return build_completion_series(
            student_id=sid,
            student_name=student_name,
            template_file_id=template_file_id,
            completions=self.get_completions(template_file_id),
        )

    def get_completion_series_for_file(self, file_id: str):
        completion = self.get_file(file_id)
        if completion is None or not completion.student_id:
            return None
        template = self.get_template(file_id)
        if template is None:
            return None
        return self.get_completion_series(completion.student_id, template.id)

    def get_completion_series_member(self, file_id: str):
        series = self.get_completion_series_for_file(file_id)
        if series is None:
            return None
        for member in series.members:
            if member.file_id == file_id:
                return series, member
        return None

    def next_attempt_sequence_for_completion(self, file_id: str) -> int | None:
        completion = self.get_file(file_id)
        if completion is None or not completion.student_id:
            return None
        template = self.get_template(file_id)
        if template is None:
            return None
        series = self.get_completion_series(completion.student_id, template.id)
        if series is None:
            return 1
        for member in series.members:
            if member.file_id == file_id:
                return member.attempt_sequence
        return series.attempt_count + 1

    # -----------------------------------------------------------------------
    # GoodNotes helper: resolve DaydreamEdu template/source path for a
    # GoodNotes main file according to the naming rules in
    # docs/proposals/05-goodnotes-exam-registration.md §4.
    # -----------------------------------------------------------------------

    @staticmethod
    def resolve_goodnotes_template_path(main_path: str | Path) -> Path:
        """
        Given the path to a student *main* completion file under either:

        - a ``.../GoodNotes/...`` tree (mirrored to DaydreamEdu), or
        - a student-scoped ``.../DaydreamEdu/...`` tree (same layout as the mirror),

        return the corresponding general-scope DaydreamEdu template/source path by
        applying the general naming principles from 05-goodnotes-exam-registration.md:

        - Strip a leading `_c_` or `c_` from the basename (GoodNotes/Drive may
          drop the underscore).
        - Repeatedly strip trailing ` (attempt)` / ` (reviewed)` tags to get the
          **base name**.
        - Construct candidate DaydreamEdu `_c_` basenames from that base name and
          search the general-scope DaydreamEdu directory (subject/grade/content
          without the student email segment).

        Daydream layouts:

        - **Legacy:** ``DaydreamEdu/<subject>/…/<folder>``
        - **Prefab branches:** ``DaydreamEdu/template/<subject>/…/<folder>``

        Resolution tries ``template/<subject>/…`` first, then the legacy path (no
        top-level branch), so mirrored GoodNotes completions still resolve after
        a template/completion-branch migration.

        Raises ValueError if:
        - the path does not contain a ``GoodNotes`` or (student) ``DaydreamEdu``
          segment, or
        - no matching `_c_*.pdf` file is found in the candidate DaydreamEdu folder.
        """
        p = Path(main_path)
        name = p.name

        # Strip leading _c_ or c_ for normalised matching
        core = name
        if core.startswith("_c_"):
            core = core[3:]
        elif core.startswith("c_"):
            core = core[2:]

        # Strip trailing attempt/reviewed tags repeatedly to get the base name
        for suffix in (" (attempt).pdf", " (reviewed).pdf"):
            while core.endswith(suffix):
                core = core[: -len(suffix)] + ".pdf"

        if not core.lower().endswith(".pdf"):
            raise ValueError(f"Completion filename does not look like a PDF: {name}")

        base_stem = core[:-4]  # drop '.pdf'

        # Candidate basenames to try in order
        candidate_basenames = [
            f"_c_{base_stem}.pdf",
            f"_c_{base_stem} (empty).pdf",
        ]

        parts = list(p.parts)
        if "GoodNotes" in parts:
            idx = parts.index("GoodNotes")
            daydream_parts = parts.copy()
            daydream_parts[idx] = "DaydreamEdu"
        elif "DaydreamEdu" in parts:
            daydream_parts = parts.copy()
            idx = parts.index("DaydreamEdu")
        else:
            raise ValueError(
                f"Path does not contain a 'GoodNotes' or 'DaydreamEdu' segment: {p}"
            )

        # Directory segments under DaydreamEdu (exclude filename).
        segments = daydream_parts[idx + 1 : -1]

        # Strip migrated top-level branch so we can build both template-branch and legacy paths.
        if segments[:1] == ["completion"]:
            segments = segments[1:]
        elif segments[:1] == ["template"]:
            segments = segments[1:]

        # Drop the mirrored student-folder segment (`...@...`) once; templates are general-scope only.
        for si, seg in enumerate(segments):
            if "@" in seg:
                segments = segments[:si] + segments[si + 1 :]
                break

        if not segments:
            raise ValueError(
                f"Could not resolve mirrored template for {name}: "
                "unable to derive a general-scope DaydreamEdu directory"
            )

        daydream_root = Path(*daydream_parts[: idx + 1])
        remainder_dir = Path(*segments)

        # Prefer migrated template-branch layout first, then legacy (no branch prefix).
        search_dirs = [daydream_root / "template" / remainder_dir, daydream_root / remainder_dir]

        # Try each candidate basename in each candidate directory
        for d in search_dirs:
            for bn in candidate_basenames:
                candidate = d / bn
                if candidate.exists():
                    return candidate

        raise ValueError(
            f"Could not resolve mirrored template for {name}: no matching _c_ file found in DaydreamEdu"
        )

    def link_template_by_paths(
        self,
        completed_path: str | Path,
        template_path: str | Path,
        inherit_metadata: bool = True,
    ) -> FileRelation:
        """Find both files by path, set is_template flags, and link. Raises NotFoundError if either path missing; ValueError if completed already linked."""
        template_file = self.get_file_by_path(template_path)
        completed_file = self.get_file_by_path(completed_path)
        if template_file is None:
            raise NotFoundError(f"Template file not found: {template_path}")
        if completed_file is None:
            raise NotFoundError(f"Completed file not found: {completed_path}")
        if self.get_template(completed_file.id) is not None:
            raise ValueError("Completed file is already linked to a template")
        self.update_metadata(template_file.id, is_template=True)
        self.update_metadata(completed_file.id, is_template=False)
        return self.link_to_template(completed_file.id, template_file.id, inherit_metadata=inherit_metadata)

    def link_goodnotes_template_for_file(
        self,
        main_path: str | Path,
        *,
        auto_fix_template: bool = True,
        inherit_metadata: bool = True,
    ) -> GoodNotesTemplateLinkOutcome:
        completed_path = Path(main_path).resolve()
        if "GoodNotes" not in completed_path.parts and "DaydreamEdu" not in completed_path.parts:
            raise ValueError(
                f"Path does not contain a 'GoodNotes' or 'DaydreamEdu' segment: {completed_path}"
            )

        completed_file = self.get_file_by_path(completed_path)
        if completed_file is None:
            raise NotFoundError(f"Completed file not found in registry: {completed_path}")
        if completed_file.file_type != "main":
            raise ValueError("GoodNotes template linking requires file_type='main'")
        if completed_file.is_template:
            raise ValueError("GoodNotes completion file must have is_template=False")

        resolved_template_path = self.resolve_goodnotes_template_path(completed_path)
        template_file = self.get_file_by_path(resolved_template_path)
        if template_file is None:
            if resolved_template_path.exists():
                raise NotFoundError(
                    f"Resolved GoodNotes template exists on disk but is not registered: {resolved_template_path}"
                )
            raise NotFoundError(f"Resolved GoodNotes template not found in registry: {resolved_template_path}")
        if template_file.file_type != "main":
            raise ValueError("Resolved GoodNotes template must have file_type='main'")

        existing_template = self.get_template(completed_file.id)
        if existing_template is not None:
            if Path(existing_template.path).resolve() == resolved_template_path:
                return GoodNotesTemplateLinkOutcome(
                    main_path=str(completed_path),
                    template_path=str(resolved_template_path),
                    linked=False,
                    already_linked=True,
                    auto_fixed_template=False,
                    dry_run=False,
                    message="Completed file is already linked to the resolved template",
                )
            raise ValueError("Completed file is already linked to a different template")

        auto_fixed = False
        if not template_file.is_template:
            if not auto_fix_template:
                raise ValueError("Resolved GoodNotes template is registered but is_template=False")
            template_file = self.update_metadata(template_file.id, is_template=True)
            auto_fixed = True

        self.link_to_template(completed_file.id, template_file.id, inherit_metadata=inherit_metadata)
        return GoodNotesTemplateLinkOutcome(
            main_path=str(completed_path),
            template_path=str(resolved_template_path),
            linked=True,
            already_linked=False,
            auto_fixed_template=auto_fixed,
            dry_run=False,
            message=None,
        )

    def link_goodnotes_templates_for_root(
        self,
        root: str | Path,
        *,
        dry_run: bool = False,
        auto_fix_template: bool = True,
        inherit_metadata: bool = True,
    ) -> list[GoodNotesTemplateLinkOutcome]:
        root_path = Path(root).resolve()
        if not root_path.is_dir():
            raise ValueError(f"Root is not a directory: {root_path}")
        if "GoodNotes" not in root_path.parts:
            raise ValueError(f"Root does not contain a 'GoodNotes' segment: {root_path}")

        conn = self._get_connection()
        like_pattern = f"{root_path}%"
        rows = conn.execute(
            """SELECT path FROM pdf_files
               WHERE file_type = 'main' AND path LIKE ?
               ORDER BY path""",
            (like_pattern,),
        ).fetchall()

        outcomes: list[GoodNotesTemplateLinkOutcome] = []
        for row in rows:
            main_path = Path(row["path"]).resolve()
            if "GoodNotes" not in main_path.parts:
                continue

            completed_file = self.get_file_by_path(main_path)
            if completed_file is None or completed_file.is_template:
                continue

            resolved_template_path = self.resolve_goodnotes_template_path(main_path)
            template_file = self.get_file_by_path(resolved_template_path)
            auto_fix_needed = template_file is not None and not template_file.is_template
            existing_template = self.get_template(completed_file.id)
            if dry_run:
                message = None
                already_linked = False
                if existing_template is not None:
                    if Path(existing_template.path).resolve() == resolved_template_path:
                        already_linked = True
                        message = "Already linked to the resolved template"
                    else:
                        message = "Already linked to a different template"
                elif template_file is None:
                    if resolved_template_path.exists():
                        message = "Resolved template exists on disk but is not registered"
                    else:
                        message = "Resolved template path not found on disk or in registry"
                elif template_file.file_type != "main":
                    message = "Resolved template is registered but is not a main file"
                elif auto_fix_needed and not auto_fix_template:
                    message = "Resolved template is registered but is_template=False"
                elif auto_fix_needed:
                    message = "Would auto-fix resolved template is_template and link"
                else:
                    message = "Would link resolved template"

                outcomes.append(
                    GoodNotesTemplateLinkOutcome(
                        main_path=str(main_path),
                        template_path=str(resolved_template_path),
                        linked=False,
                        already_linked=already_linked,
                        auto_fixed_template=False,
                        dry_run=True,
                        message=message,
                    )
                )
                continue

            outcomes.append(
                self.link_goodnotes_template_for_file(
                    main_path,
                    auto_fix_template=auto_fix_template,
                    inherit_metadata=inherit_metadata,
                )
            )

        return outcomes

    def create_file_group(self, label: str, group_type: str = "collection", anchor_id: str | None = None, notes: str | None = None) -> FileGroup:
        self._validate_group_type(group_type)
        conn = self._get_connection()
        gid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "INSERT INTO file_groups (id, label, group_type, anchor_id, created_at, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (gid, label, group_type, anchor_id, now, notes),
        )
        conn.commit()
        self._log_operation("group_create", group_id=gid, after_state=json.dumps({"label": label, "group_type": group_type}))
        return self.get_file_group(gid)

    def add_to_file_group(self, group_id: str, file_id: str, role: str | None = None) -> FileGroupMember:
        row = self.get_file(file_id)
        if not row:
            raise NotFoundError(f"File not found: {file_id}")
        if row.file_type != "main":
            raise ValueError("Only main files may be added to a group; raw files are not allowed")
        # Canonical per-file function labels now live in metadata.unit.
        # Keep accepting `role` for compatibility, but store it on the file
        # metadata (if unit is not already set) instead of relying on
        # file_group_members.role.
        if role is not None:
            if row.doc_type != "book":
                raise ValueError("add_to_file_group(role=...) is only allowed for doc_type='book' files")
            current_meta = row.metadata if isinstance(row.metadata, dict) else {}
            if not current_meta.get("unit"):
                self.update_metadata(file_id, metadata={"unit": role})
        conn = self._get_connection()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "INSERT OR IGNORE INTO file_group_members (group_id, file_id, role, added_at) VALUES (?, ?, ?, ?)",
            (group_id, file_id, None, now),
        )
        conn.commit()
        self._log_operation("group_add", file_id=file_id, group_id=group_id)
        refreshed = self.get_file(file_id) or row
        return FileGroupMember(group_id=group_id, file_id=file_id, role=None, added_at=now, file=refreshed)

    def remove_from_file_group(self, group_id: str, file_id: str) -> None:
        conn = self._get_connection()
        conn.execute("UPDATE file_groups SET anchor_id = NULL WHERE anchor_id = ? AND id = ?", (file_id, group_id))
        conn.execute("DELETE FROM file_group_members WHERE group_id = ? AND file_id = ?", (group_id, file_id))
        conn.commit()
        self._log_operation("group_remove", file_id=file_id, group_id=group_id)

    def set_file_group_anchor(self, group_id: str, file_id: str) -> None:
        conn = self._get_connection()
        conn.execute("UPDATE file_groups SET anchor_id = ? WHERE id = ?", (file_id, group_id))
        conn.commit()
        self._log_operation("group_anchor_set", file_id=file_id, group_id=group_id)

    def update_file_group_notes(self, group_id: str, notes: str | None) -> FileGroup:
        conn = self._get_connection()
        conn.execute("UPDATE file_groups SET notes = ? WHERE id = ?", (notes, group_id))
        conn.commit()
        self._log_operation("group_update_notes", group_id=group_id)
        return self.get_file_group(group_id)

    def get_file_group(self, group_id: str) -> FileGroup:
        conn = self._get_connection()
        row = conn.execute("SELECT * FROM file_groups WHERE id = ?", (group_id,)).fetchone()
        if not row:
            raise NotFoundError(f"File group not found: {group_id}")
        members = []
        for m in conn.execute(
            "SELECT group_id, file_id, role, added_at FROM file_group_members WHERE group_id = ?", (group_id,)
        ).fetchall():
            f = self.get_file(m["file_id"])
            if f:
                members.append(
                    FileGroupMember(
                        group_id=m["group_id"],
                        file_id=m["file_id"],
                        role=m["role"],
                        added_at=m["added_at"],
                        file=f,
                    )
                )
        return FileGroup(
            id=row["id"],
            label=row["label"],
            group_type=row["group_type"],
            anchor_id=row["anchor_id"],
            created_at=row["created_at"],
            notes=row["notes"],
            members=members,
        )

    def list_file_groups(self, group_type: str | None = None) -> list[FileGroup]:
        conn = self._get_connection()
        if group_type:
            rows = conn.execute("SELECT id FROM file_groups WHERE group_type = ?", (group_type,)).fetchall()
        else:
            rows = conn.execute("SELECT id FROM file_groups").fetchall()
        return [self.get_file_group(r["id"]) for r in rows]

    def get_file_group_membership(self, file_id: str) -> list[FileGroup]:
        conn = self._get_connection()
        rows = conn.execute("SELECT group_id FROM file_group_members WHERE file_id = ?", (file_id,)).fetchall()
        return [self.get_file_group(r["group_id"]) for r in rows]

    def delete_file_group(self, group_id: str) -> None:
        conn = self._get_connection()
        group = self.get_file_group(group_id)
        members_snapshot = [{"group_id": m.group_id, "file_id": m.file_id, "role": m.role} for m in group.members]
        conn.execute("DELETE FROM file_group_members WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM file_groups WHERE id = ?", (group_id,))
        conn.commit()
        self._log_operation("group_delete", group_id=group_id, before_state=json.dumps({"members": members_snapshot}))

    def open_file_group(self, group_id: str) -> None:
        g = self.get_file_group(group_id)
        if not g.anchor_id:
            raise ConfigError("No anchor set for this group. Set one with: group anchor <group_id> <file_id>")
        self.open_file(g.anchor_id)

    def suggest_groups(self) -> list[SuggestedGroup]:
        conn = self._get_connection()
        rows = conn.execute(
            """SELECT id, student_id, subject, metadata FROM pdf_files
               WHERE file_type = 'main' AND doc_type = 'exam' AND is_template = 0
               AND student_id IS NOT NULL AND subject IS NOT NULL""",
        ).fetchall()
        by_key = {}
        for row in rows:
            meta = row["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta) if meta else {}
            exam_date = (meta or {}).get("exam_date") if isinstance(meta, dict) else None
            if not exam_date:
                continue
            key = (row["student_id"], row["subject"], exam_date)
            by_key.setdefault(key, []).append(row["id"])
        result = []
        for (student_id, subject, exam_date), file_ids in by_key.items():
            if len(file_ids) < 2:
                continue
            result.append(
                SuggestedGroup(
                    group_type="exam",
                    candidate_files=[self.get_file(fid) for fid in file_ids if self.get_file(fid)],
                    match_basis={"student_id": student_id, "subject": subject, "exam_date": exam_date},
                )
            )
        return result

    def get_operation_log(
        self,
        file_id: str | None = None,
        group_id: str | None = None,
        operation: str | None = None,
        since: str | None = None,
        log_id: str | None = None,
    ) -> list[OperationRecord]:
        conn = self._get_connection()
        if log_id is not None:
            row = conn.execute(
                "SELECT * FROM operation_log WHERE id = ?", (log_id,)
            ).fetchone()
            rows = [row] if row else []
        else:
            sql = "SELECT * FROM operation_log WHERE 1=1"
            params = []
            if file_id is not None:
                sql += " AND file_id = ?"
                params.append(file_id)
            if group_id is not None:
                sql += " AND group_id = ?"
                params.append(group_id)
            if operation is not None:
                sql += " AND operation = ?"
                params.append(operation)
            if since is not None:
                sql += " AND performed_at >= ?"
                params.append(since)
            sql += " ORDER BY performed_at ASC"
            rows = conn.execute(sql, params).fetchall()
        out = []
        for row in rows:
            before = row["before_state"]
            if isinstance(before, str):
                before = json.loads(before) if before else None
            after = row["after_state"]
            if isinstance(after, str):
                after = json.loads(after) if after else None
            out.append(
                OperationRecord(
                    id=row["id"],
                    operation=row["operation"],
                    file_id=row["file_id"],
                    group_id=row["group_id"],
                    performed_at=row["performed_at"],
                    performed_by=row["performed_by"],
                    before_state=before,
                    after_state=after,
                    notes=row["notes"],
                )
            )
        return out

    def set_book_answer_mapping(
        self,
        unit_file_id_or_path: str | Path,
        answer_file_id_or_path: str | Path,
        answer_page_start: int,
        answer_page_end: int,
        starts_mid_page: bool = False,
        ends_mid_page: bool = False,
        source: str | None = None,
        notes: str | None = None,
    ) -> BookAnswerMapping:
        if answer_page_start > answer_page_end:
            raise ValueError("answer_page_start must be <= answer_page_end")
        unit_file_id, _, _ = self._resolve_file_record(unit_file_id_or_path)
        answer_file_id, _, _ = self._resolve_file_record(answer_file_id_or_path)
        book_group_id = self._validate_book_answer_mapping_files(unit_file_id, answer_file_id)
        conn = self._get_connection()
        existing = conn.execute(
            "SELECT * FROM book_answer_mappings WHERE unit_file_id = ?",
            (unit_file_id,),
        ).fetchone()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        after_payload = {
            "unit_file_id": unit_file_id,
            "answer_file_id": answer_file_id,
            "answer_page_start": answer_page_start,
            "answer_page_end": answer_page_end,
            "starts_mid_page": bool(starts_mid_page),
            "ends_mid_page": bool(ends_mid_page),
            "source": source,
            "notes": notes,
        }
        if existing is None:
            mapping_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO book_answer_mappings (
                    id, unit_file_id, answer_file_id, answer_page_start, answer_page_end,
                    starts_mid_page, ends_mid_page, source, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mapping_id,
                    unit_file_id,
                    answer_file_id,
                    answer_page_start,
                    answer_page_end,
                    1 if starts_mid_page else 0,
                    1 if ends_mid_page else 0,
                    source,
                    notes,
                    now,
                    now,
                ),
            )
            conn.commit()
            self._log_operation(
                "book_answer_mapping_set",
                file_id=unit_file_id,
                group_id=book_group_id,
                after_state=json.dumps(after_payload),
            )
        else:
            before_payload = {
                "unit_file_id": existing["unit_file_id"],
                "answer_file_id": existing["answer_file_id"],
                "answer_page_start": existing["answer_page_start"],
                "answer_page_end": existing["answer_page_end"],
                "starts_mid_page": bool(existing["starts_mid_page"]),
                "ends_mid_page": bool(existing["ends_mid_page"]),
                "source": existing["source"],
                "notes": existing["notes"],
            }
            mapping_id = existing["id"]
            conn.execute(
                """
                UPDATE book_answer_mappings
                SET answer_file_id = ?, answer_page_start = ?, answer_page_end = ?,
                    starts_mid_page = ?, ends_mid_page = ?, source = ?, notes = ?, updated_at = ?
                WHERE unit_file_id = ?
                """,
                (
                    answer_file_id,
                    answer_page_start,
                    answer_page_end,
                    1 if starts_mid_page else 0,
                    1 if ends_mid_page else 0,
                    source,
                    notes,
                    now,
                    unit_file_id,
                ),
            )
            conn.commit()
            self._log_operation(
                "book_answer_mapping_update",
                file_id=unit_file_id,
                group_id=book_group_id,
                before_state=json.dumps(before_payload),
                after_state=json.dumps(after_payload),
            )
        row = conn.execute(
            "SELECT * FROM book_answer_mappings WHERE id = ?",
            (mapping_id,),
        ).fetchone()
        assert row is not None
        return self._row_to_book_answer_mapping(row)

    def get_book_answer_mapping(self, unit_file_id_or_path: str | Path) -> BookAnswerMapping | None:
        unit_file_id, _, _ = self._resolve_file_record(unit_file_id_or_path)
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM book_answer_mappings WHERE unit_file_id = ?",
            (unit_file_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_book_answer_mapping(row)

    def list_book_answer_mappings(
        self,
        *,
        book_group_id: str | None = None,
        answer_file_id_or_path: str | Path | None = None,
        source: str | None = None,
    ) -> list[BookAnswerMapping]:
        conn = self._get_connection()
        sql = "SELECT bam.* FROM book_answer_mappings bam"
        params: list[object] = []
        if book_group_id is not None:
            group = self.get_file_group(book_group_id)
            if group.group_type != "book":
                raise ValueError("book_group_id must refer to a group_type='book' file group")
            sql += " JOIN file_group_members fgm ON fgm.file_id = bam.unit_file_id"
        sql += " WHERE 1=1"
        if book_group_id is not None:
            sql += " AND fgm.group_id = ?"
            params.append(book_group_id)
        if answer_file_id_or_path is not None:
            answer_file_id, _, _ = self._resolve_file_record(answer_file_id_or_path)
            sql += " AND bam.answer_file_id = ?"
            params.append(answer_file_id)
        if source is not None:
            sql += " AND bam.source = ?"
            params.append(source)
        sql += " ORDER BY bam.created_at ASC"
        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_book_answer_mapping(row) for row in rows]

    def delete_book_answer_mapping(self, unit_file_id_or_path: str | Path) -> None:
        unit_file_id, _, _ = self._resolve_file_record(unit_file_id_or_path)
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM book_answer_mappings WHERE unit_file_id = ?",
            (unit_file_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Book answer mapping not found for unit file: {unit_file_id_or_path}")
        book_group_ids = self._book_group_ids_for_file(unit_file_id)
        before_payload = {
            "unit_file_id": row["unit_file_id"],
            "answer_file_id": row["answer_file_id"],
            "answer_page_start": row["answer_page_start"],
            "answer_page_end": row["answer_page_end"],
            "starts_mid_page": bool(row["starts_mid_page"]),
            "ends_mid_page": bool(row["ends_mid_page"]),
            "source": row["source"],
            "notes": row["notes"],
        }
        conn.execute(
            "DELETE FROM book_answer_mappings WHERE unit_file_id = ?",
            (unit_file_id,),
        )
        conn.commit()
        self._log_operation(
            "book_answer_mapping_delete",
            file_id=unit_file_id,
            group_id=sorted(book_group_ids)[0] if book_group_ids else None,
            before_state=json.dumps(before_payload),
        )

    # ---------------------------------------------------------------------------
    # Completion dates (proposal 17)
    # ---------------------------------------------------------------------------

    def get_completion_date(self, file_id: str) -> CompletionDateRecord | None:
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM file_completion_dates WHERE file_id = ?",
            (file_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_completion_date_record(row)

    def get_completion_dates_for_files(
        self, file_ids: list[str]
    ) -> dict[str, CompletionDateRecord]:
        if not file_ids:
            return {}
        conn = self._get_connection()
        placeholders = ",".join("?" for _ in file_ids)
        rows = conn.execute(
            f"SELECT * FROM file_completion_dates WHERE file_id IN ({placeholders})",
            file_ids,
        ).fetchall()
        return {
            row["file_id"]: self._row_to_completion_date_record(row) for row in rows
        }

    def set_completion_date(
        self,
        file_id: str,
        completion_date: str,
        *,
        source: str = "manual",
        confidence: str | None = None,
        inference_model: str | None = None,
        source_detail: dict | None = None,
    ) -> CompletionDateRecord:
        completion_date = normalize_completion_date(completion_date)
        source = normalize_completion_date_source(source)
        confidence = normalize_completion_date_confidence(confidence)
        inference_model = normalize_inference_model(inference_model)
        validate_inferred_completion_date_provenance(
            source=source,
            confidence=confidence,
            inference_model=inference_model,
        )
        self._validate_completion_date_target(file_id)
        detail_json = json.dumps(source_detail) if source_detail is not None else None
        conn = self._get_connection()
        existing = conn.execute(
            "SELECT * FROM file_completion_dates WHERE file_id = ?",
            (file_id,),
        ).fetchone()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        after_payload = {
            "file_id": file_id,
            "completion_date": completion_date,
            "source": source,
            "confidence": confidence,
            "inference_model": inference_model,
            "source_detail": source_detail,
            "inferred_at": now,
            "updated_at": now,
        }
        if existing is None:
            conn.execute(
                """
                INSERT INTO file_completion_dates (
                    file_id, completion_date, source, confidence, inference_model,
                    source_detail, inferred_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    completion_date,
                    source,
                    confidence,
                    inference_model,
                    detail_json,
                    now,
                    now,
                ),
            )
            conn.commit()
            self._log_operation(
                "set_completion_date",
                file_id=file_id,
                after_state=json.dumps(after_payload),
            )
        else:
            before_payload = {
                "file_id": existing["file_id"],
                "completion_date": existing["completion_date"],
                "source": existing["source"],
                "confidence": existing["confidence"],
                "inference_model": existing["inference_model"]
                if "inference_model" in existing.keys()
                else None,
                "source_detail": json.loads(existing["source_detail"])
                if existing["source_detail"]
                else None,
                "inferred_at": existing["inferred_at"],
                "updated_at": existing["updated_at"],
            }
            after_payload["inferred_at"] = existing["inferred_at"]
            conn.execute(
                """
                UPDATE file_completion_dates
                SET completion_date = ?, source = ?, confidence = ?, inference_model = ?,
                    source_detail = ?, updated_at = ?
                WHERE file_id = ?
                """,
                (
                    completion_date,
                    source,
                    confidence,
                    inference_model,
                    detail_json,
                    now,
                    file_id,
                ),
            )
            conn.commit()
            after_payload["updated_at"] = now
            self._log_operation(
                "set_completion_date",
                file_id=file_id,
                before_state=json.dumps(before_payload),
                after_state=json.dumps(after_payload),
            )
        row = conn.execute(
            "SELECT * FROM file_completion_dates WHERE file_id = ?",
            (file_id,),
        ).fetchone()
        assert row is not None
        return self._row_to_completion_date_record(row)

    def clear_completion_date(self, file_id: str) -> None:
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM file_completion_dates WHERE file_id = ?",
            (file_id,),
        ).fetchone()
        if row is None:
            return
        before_payload = {
            "file_id": row["file_id"],
            "completion_date": row["completion_date"],
            "source": row["source"],
            "confidence": row["confidence"],
            "inference_model": row["inference_model"]
            if "inference_model" in row.keys()
            else None,
            "source_detail": json.loads(row["source_detail"])
            if row["source_detail"]
            else None,
            "inferred_at": row["inferred_at"],
            "updated_at": row["updated_at"],
        }
        conn.execute(
            "DELETE FROM file_completion_dates WHERE file_id = ?",
            (file_id,),
        )
        conn.commit()
        self._log_operation(
            "clear_completion_date",
            file_id=file_id,
            before_state=json.dumps(before_payload),
        )

    def infer_completion_date_for_file(
        self,
        file_id: str,
        *,
        force: bool = False,
        force_manual: bool = False,
        methods: frozenset[str] | None = None,
        work_dir: str | Path | None = None,
    ) -> CompletionDateRecord | None:
        """Infer and persist completion_date over the full proposal 17 matrix.

        Priority order when enabled in ``methods``:
        1. ``handwritten_page1``  – cached page-1/2 agent JSON in work_dir
        2. ``goodnotes_*``        – GoodNotes timestamps for g_root cohort
        3. ``filename_term``      – WA/Term/EoY filename heuristics for d_root exam/exercise
        4. ``drive_modified``     – filesystem mtime for d_root book

        Existing rows:
        - When no row exists, any successful method may write one.
        - When a non-manual row exists, ``force=True`` allows overwrite; otherwise keep.
        - When ``source='manual'``, never overwrite unless ``force_manual=True``.
        """
        active = methods if methods is not None else COMPLETION_DATE_SOURCES
        # Only keep known sources so typos do not silently no-op.
        active = frozenset(s for s in active if s in COMPLETION_DATE_SOURCES)
        if not active:
            return self.get_completion_date(file_id)

        existing = self.get_completion_date(file_id)
        if existing is not None:
            if existing.source == "manual" and not force_manual:
                return existing
            if existing.source != "manual" and not force:
                return existing

        pdf = self.get_file(file_id)
        if pdf is None:
            raise NotFoundError(f"file not found for completion-date inference: {file_id}")

        path = Path(pdf.path)
        inventory_root = inventory_root_from_path(str(path))

        # 1. Page-1/2 handwritten / printed date (cached agent JSON).
        if "handwritten_page1" in active:
            wd = Path(work_dir) if work_dir is not None else default_page1_work_dir()
            result = infer_completion_date_for_file_cached_page1(
                self,
                file_id,
                wd,
                force=force,
                force_manual=force_manual,
            )
            if result is not None:
                return result

        # 2. GoodNotes timestamps (g_root cohort only).
        if inventory_root == "g_root" and (
            "goodnotes_last_modified" in active or "goodnotes_updated_at" in active
        ):
            from .completion_date.goodnotes import infer_completion_date_from_goodnotes_match

            match = get_goodnotes_document_match(self, file_id)
            if isinstance(match, GoodnotesDocumentMatch):
                inf = infer_completion_date_from_goodnotes_match(match)
                if inf is not None and inf.source in active:
                    return self.set_completion_date(
                        file_id,
                        inf.completion_date,
                        source=inf.source,
                        confidence=inf.confidence,
                        inference_model=None,
                        source_detail=inf.source_detail,
                    )

        # 3. Filename / title heuristics (d_root exam/exercise).
        if inventory_root == "d_root" and "filename_term" in active:
            title = pdf.normal_name or Path(pdf.name).stem
            inf = infer_completion_date_from_filename_term(
                title,
                student_id=pdf.student_id,
                path=pdf.path,
                name=pdf.name,
            )
            if inf is not None:
                return self.set_completion_date(
                    file_id,
                    inf.completion_date,
                    source=FILENAME_TERM_SOURCE,
                    confidence=FILENAME_TERM_CONFIDENCE,
                    inference_model=None,
                    source_detail=inf.source_detail,
                )

        # 4. Drive mtime (d_root books only).
        if "drive_modified" in active:
            from .completion_date.drive_modified import (
                DRIVE_MODIFIED_CONFIDENCE,
                DRIVE_MODIFIED_SOURCE,
                infer_completion_date_from_drive_modified,
            )

            drive_inf = infer_completion_date_from_drive_modified(
                pdf.path,
                doc_type=pdf.doc_type,
                inventory_root=inventory_root,
            )
            if drive_inf is not None:
                return self.set_completion_date(
                    file_id,
                    drive_inf.completion_date,
                    source=DRIVE_MODIFIED_SOURCE,
                    confidence=DRIVE_MODIFIED_CONFIDENCE,
                    inference_model=None,
                    source_detail=drive_inf.source_detail,
                )

        # No method produced a date; leave registry unchanged.
        return None

    def infer_completion_dates(
        self,
        *,
        file_ids: list[str] | None = None,
        student_id: str | None = None,
        root: str | None = None,
        doc_types: list[str] | None = None,
        methods: frozenset[str] | None = None,
        work_dir: str | Path | None = None,
        dry_run: bool = False,
        force: bool = False,
        force_manual: bool = False,
    ) -> InferCompletionDatesReport:
        """Batch completion-date inference over a selected cohort.

        Cohort selection:
        - When ``file_ids`` is provided, operate on that explicit list.
        - Otherwise, select main, non-template files via filters on ``student_id``,
          ``root`` (d_root / g_root / None), and ``doc_types``.

        Delegates per-file work to ``infer_completion_date_for_file`` and accumulates
        counts in an ``InferCompletionDatesReport``. When ``dry_run=True``, this still
        walks the cohort but does **not** write any rows.
        """
        report = InferCompletionDatesReport()
        active = methods if methods is not None else COMPLETION_DATE_SOURCES
        active = frozenset(s for s in active if s in COMPLETION_DATE_SOURCES)

        candidates: list[PdfFile] = []
        if file_ids:
            for fid in file_ids:
                pdf = self.get_file(fid)
                if pdf is None:
                    continue
                if pdf.file_type != "main" or pdf.is_template:
                    continue
                candidates.append(pdf)
        else:
            query_kwargs: dict[str, object] = {
                "file_type": "main",
                "is_template": False,
            }
            if student_id is not None:
                query_kwargs["student_id"] = student_id

            doc_type_filters: list[str | None]
            if doc_types is None:
                doc_type_filters = [None]
            else:
                doc_type_filters = list(doc_types)

            seen_ids: set[str] = set()
            for dt in doc_type_filters:
                kwargs = dict(query_kwargs)
                if dt is not None:
                    kwargs["doc_type"] = dt
                for pdf in self.find_files(**kwargs):
                    if pdf.id in seen_ids:
                        continue
                    seen_ids.add(pdf.id)
                    inv_root = inventory_root_from_path(pdf.path)
                    if root is not None and inv_root != root:
                        continue
                    candidates.append(pdf)

        if not candidates or not active:
            return report

        for pdf in candidates:
            report = merge_infer_completion_dates_report(
                report, processed=report.processed + 1
            )
            existing = self.get_completion_date(pdf.id)
            if existing is not None:
                if existing.source == "manual" and not force_manual:
                    report = merge_infer_completion_dates_report(
                        report, skipped_manual=report.skipped_manual + 1
                    )
                    continue
                if existing.source != "manual" and not force:
                    report = merge_infer_completion_dates_report(
                        report, skipped_existing=report.skipped_existing + 1
                    )
                    continue

            if dry_run:
                if existing is None:
                    report = merge_infer_completion_dates_report(
                        report, still_undated=report.still_undated + 1
                    )
                continue

            try:
                result = self.infer_completion_date_for_file(
                    pdf.id,
                    force=force,
                    force_manual=force_manual,
                    methods=active,
                    work_dir=work_dir,
                )
            except Exception:
                logger.exception("completion-date inference failed for %s", pdf.id)
                report = merge_infer_completion_dates_report(
                    report, failed=report.failed + 1
                )
                continue

            if result is None:
                if self.get_completion_date(pdf.id) is None:
                    report = merge_infer_completion_dates_report(
                        report, still_undated=report.still_undated + 1
                    )
                else:
                    report = merge_infer_completion_dates_report(
                        report, written=report.written + 1
                    )
            else:
                report = merge_infer_completion_dates_report(
                    report, written=report.written + 1
                )

        return report

    def import_book_answer_mappings_from_json(
        self,
        json_path: str | Path,
        *,
        source: str = "imported_ground_truth",
    ) -> list[BookAnswerMapping]:
        payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
        book_label = payload.get("book_label")
        answer_file_name = payload.get("answer_file")
        mappings = payload.get("mappings") or []
        if not book_label or not answer_file_name:
            raise ValueError("Ground-truth JSON must include book_label and answer_file")
        groups = [group for group in self.list_file_groups(group_type="book") if group.label == book_label]
        if not groups:
            raise NotFoundError(f"Book file group not found for label: {book_label}")
        if len(groups) > 1:
            raise ValueError(f"Multiple book file groups found for label: {book_label}")
        group = groups[0]
        members_by_name = {member.file.name: member.file for member in group.members}
        answer_file = members_by_name.get(answer_file_name)
        if answer_file is None:
            raise NotFoundError(f"Answer file not found in book group '{book_label}': {answer_file_name}")

        imported: list[BookAnswerMapping] = []
        for item in mappings:
            unit_file_name = item.get("unit_file")
            if not unit_file_name:
                raise ValueError("Each mapping row must include unit_file")
            unit_file = members_by_name.get(unit_file_name)
            if unit_file is None:
                raise NotFoundError(f"Unit file not found in book group '{book_label}': {unit_file_name}")
            imported.append(
                self.set_book_answer_mapping(
                    unit_file.id,
                    answer_file.id,
                    int(item["answer_page_start"]),
                    int(item["answer_page_end"]),
                    starts_mid_page=bool(item.get("starts_mid_page", False)),
                    ends_mid_page=bool(item.get("ends_mid_page", False)),
                    source=source,
                    notes=item.get("notes") or None,
                )
            )
        return imported

    def ensure_book_group_from_path(self, path: str | Path) -> FileGroup | None:
        """Ensure/sync the canonical book file group for a general-scope Book folder.

        Returns None for student-mirror Book paths. Student mains are represented via
        template links and are not members of group_type='book' groups.
        """
        target = Path(path).resolve()
        book_folder = target if target.is_dir() else self._infer_book_folder(target)
        if book_folder is None or book_folder.parent.name != "Book":
            raise ValueError(f"Path is not under a .../Book/<book name>/ folder: {path}")
        if self._path_has_student_mirror_layout(book_folder):
            return None
        label = book_folder.name
        existing = [
            group for group in self.list_file_groups(group_type="book")
            if group.label == label
        ]
        group = existing[0] if existing else self.create_file_group(label=label, group_type="book")
        current_members_by_id = {member.file_id: member for member in group.members}
        desired_files = [
            file
            for file in self.find_files(doc_type="book", file_type="main", is_template=True)
            if Path(file.path).resolve().parent == book_folder
            and not self._path_has_student_mirror_layout(Path(file.path))
        ]
        desired_member_ids = {file.id for file in desired_files}

        for file in desired_files:
            if file.id not in current_members_by_id:
                self.add_to_file_group(group.id, file.id)

        for member in group.members:
            if member.file_id not in desired_member_ids:
                self.remove_from_file_group(group.id, member.file_id)

        group = self.get_file_group(group.id)
        if group.anchor_id is None and group.members:
            anchor = sorted(group.members, key=lambda member: member.file.name)[0]
            self.set_file_group_anchor(group.id, anchor.file_id)
            group = self.get_file_group(group.id)
        return group
