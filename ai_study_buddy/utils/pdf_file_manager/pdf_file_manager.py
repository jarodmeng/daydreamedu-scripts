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

logger = logging.getLogger(__name__)

# Ensure we can import compress_pdf from sibling utils folder
_utils_dir = Path(__file__).resolve().parent.parent
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

@dataclass
class CompressResult:
    """Result of compress_and_register; includes main_file_id."""
    main_file_id: str
    compressed: bool  # True if we kept compressed output; False if restored original
    raw_archive_id: str | None  # Set if we created a _raw_ file

@dataclass
class ScanResult:
    file: PdfFile
    raw_archive: PdfFile | None
    compressed: bool

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
    group_type: str  # 'exam' | 'book_exercise' | 'collection'
    anchor_id: str | None
    created_at: str
    notes: str | None
    members: list[FileGroupMember]

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


@dataclass
class GoodNotesTemplateLinkOutcome:
    main_path: str
    template_path: str | None
    linked: bool
    already_linked: bool
    auto_fixed_template: bool
    dry_run: bool
    message: str | None


def _looks_like_compressed_main_name(name: str) -> bool:
    return name.startswith("_c_") or name.startswith("c_")

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
            self._ensure_schema()
        return self._conn

    def _ensure_schema(self):
        self._conn.executescript(_schema_sql())

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

    # ---------------------------------------------------------------------------
    # register_file
    # ---------------------------------------------------------------------------

    def register_file(
        self,
        path: str | Path,
        file_type: str | None = None,
        doc_type: str = "unknown",
        student_id: str | None = None,
        subject: str | None = None,
        is_template: bool = False,
        metadata: dict | None = None,
        notes: str | None = None,
    ) -> PdfFile:
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
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
        meta_json = json.dumps(metadata) if metadata is not None else None
        if subject is not None and subject not in ("english", "math", "science", "chinese"):
            raise ValueError(f"subject must be one of english, math, science, chinese; got {subject!r}")
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
                        raw_size, result.pages, row["metadata"], now, now, row["notes"],
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
                    row["metadata"], now, now, row["notes"],
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
    def _infer_from_path(path: Path) -> dict:
        """Infer subject, doc_type, is_template, and metadata from path segments (DaydreamEdu layout).
        is_template: True when path has a grade/scope segment (P3–P6, PSLE, Archive) and no *student folder*
        (a segment containing @ immediately followed by a grade/scope segment). False when such a student folder exists.
        So Drive paths like .../GoogleDrive-user@gmail.com/.../P6/Exam yield is_template=True;
        .../user@mail.com/P5/Exam yields is_template=False.
        """
        out: dict = {}
        resolved = path.resolve()
        parts = resolved.parts
        grade_scope = ("P3", "P4", "P5", "P6", "PSLE", "Archive")
        has_student_folder = any(
            "@" in parts[i] and i + 1 < len(parts) and parts[i + 1] in grade_scope
            for i in range(len(parts))
        )
        has_grade_scope = any(p in grade_scope for p in parts)
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
            if p == "Exercise":
                out["doc_type"] = "worksheet"
                out.setdefault("metadata", {})["content_folder"] = "Exercise"
                break
            if p == "Activity":
                out["doc_type"] = "activity"
                out.setdefault("metadata", {})["content_folder"] = "Activity"
                break
            if p == "Note":
                out["doc_type"] = "notes"
                out.setdefault("metadata", {})["content_folder"] = "Note"
                break
        for p in parts:
            if p in ("P3", "P4", "P5", "P6", "PSLE", "Archive"):
                out.setdefault("metadata", {})["grade_or_scope"] = p
                break
        # Chinese exam variant (foundation vs higher) from filename.
        # Applies only when subject is chinese and doc_type is exam.
        if out.get("subject") == "chinese" and out.get("doc_type") == "exam":
            name = resolved.name
            lower = name.lower()
            variant: str | None = None
            if "高华" in name or ".hc." in lower:
                variant = "higher"
            elif "华文" in name or ".chinese." in lower:
                variant = "foundation"
            if variant:
                out.setdefault("metadata", {})["chinese_variant"] = variant
        return out

    # ---------------------------------------------------------------------------
    # scan_for_new_files
    # ---------------------------------------------------------------------------

    def scan_for_new_files(
        self,
        roots: list[str | Path] | None = None,
        min_savings_pct: float = 10,
        dry_run: bool = False,
        on_file_start: Callable[[Path], None] | None = None,
    ) -> list[ScanResult]:
        conn = self._get_connection()
        if roots is not None:
            root_entries = [ (str(Path(p).resolve()), None) for p in roots ]
        else:
            scan_roots_list = self.list_scan_roots()
            if not scan_roots_list:
                raise ConfigError("No scan roots configured. Add one with: config add-root <path> [--student-id <id>]")
            root_entries = [ (r.path, r.student_id) for r in scan_roots_list ]
        registered_paths = { row[0] for row in conn.execute("SELECT path FROM pdf_files").fetchall() }
        results: list[ScanResult] = []
        for root_path, root_student_id in root_entries:
            root_p = Path(root_path)
            if not root_p.is_dir():
                continue
            for pdf_path in root_p.rglob("*.pdf"):
                path_str = str(pdf_path.resolve())
                if path_str in registered_paths:
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
                            (main_row["student_id"], main_row["subject"], main_row["doc_type"], main_row["metadata"], raw_size, raw_id),
                        )
                        conn.commit()
                    continue
                if _looks_like_compressed_main_name(name):
                    if dry_run:
                        results.append(ScanResult(
                            file=PdfFile(id="", name=name, path=path_str, file_type="main", doc_type="unknown", student_id=root_student_id, subject=None, is_template=False, size_bytes=None, page_count=None, has_raw=False, metadata=None, added_at="", updated_at="", notes=None),
                            raw_archive=None,
                            compressed=False,
                        ))
                        continue
                    reg = self.register_file(pdf_path)
                    registered_paths.add(path_str)
                    if root_student_id:
                        conn.execute("UPDATE pdf_files SET student_id = ? WHERE id = ?", (root_student_id, reg.id))
                        conn.commit()
                    inferred = self._infer_from_path(pdf_path)
                    if inferred:
                        kwargs = {k: v for k, v in inferred.items() if k != "metadata" and v is not None}
                        if inferred.get("metadata"):
                            kwargs["metadata"] = inferred["metadata"]
                        if kwargs:
                            self.update_metadata(reg.id, **kwargs)
                    main_file = self.get_file(reg.id)
                    if main_file:
                        results.append(ScanResult(file=main_file, raw_archive=None, compressed=False))
                    continue
                if dry_run:
                    results.append(ScanResult(
                        file=PdfFile(id="", name=name, path=path_str, file_type="unknown", doc_type="unknown", student_id=root_student_id, subject=None, is_template=False, size_bytes=None, page_count=None, has_raw=False, metadata=None, added_at="", updated_at="", notes=None),
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
                inferred = self._infer_from_path(pdf_path)
                if inferred:
                    kwargs = {k: v for k, v in inferred.items() if k != "metadata" and v is not None}
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
        return results

    # ---------------------------------------------------------------------------
    # Phase 3: update_metadata, rename_file, move_file, delete_file, open_file
    # ---------------------------------------------------------------------------

    _ALLOWED_SUBJECTS = ("english", "math", "science", "chinese")

    def update_metadata(
        self,
        file_id_or_path,
        doc_type: str | None = None,
        student_id: str | None = None,
        subject: str | None = None,
        is_template: bool | None = None,
        metadata: dict | None = None,
        notes: str | None = None,
    ) -> PdfFile:
        file_id, file_path, row = self._resolve_file_record(file_id_or_path)
        if subject is not None and subject not in self._ALLOWED_SUBJECTS:
            raise ValueError(f"subject must be one of {', '.join(self._ALLOWED_SUBJECTS)}; got {subject!r}")
        conn = self._get_connection()
        before = {k: row[k] for k in row.keys()}
        updates = []
        params = []
        if doc_type is not None:
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
            if template.doc_type and (completed.doc_type is None or completed.doc_type == "unknown"):
                updates.append("doc_type = ?")
                params.append(template.doc_type)
            if template.metadata and isinstance(template.metadata, dict):
                comp_meta = completed.metadata if isinstance(completed.metadata, dict) else {}
                merged = {**template.metadata, **(comp_meta or {})}
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
    # GoodNotes helper: resolve DaydreamEdu template/source path for a
    # GoodNotes main file according to the naming rules in
    # docs/proposals/05-goodnotes-exam-registration.md §4.
    # -----------------------------------------------------------------------

    @staticmethod
    def resolve_goodnotes_template_path(main_path: str | Path) -> Path:
        """
        Given the path to a GoodNotes *main* file (usually under a .../GoodNotes/...
        tree), return the corresponding DaydreamEdu template/source path by
        applying the general naming principles from 05-goodnotes-exam-registration.md:

        - Strip a leading `_c_` or `c_` from the basename (GoodNotes/Drive may
          drop the underscore).
        - Repeatedly strip trailing ` (attempt)` / ` (reviewed)` tags to get the
          **base name**.
        - Construct candidate DaydreamEdu `_c_` basenames from that base name,
          and search both:
          * the student-scoped DaydreamEdu folder that mirrors the GoodNotes
            hierarchy, and
          * the general-scope DaydreamEdu folder (subject/grade/content_folder
            without the student email segment).

        Raises ValueError if:
        - the path does not contain a `GoodNotes` segment, or
        - no matching `_c_*.pdf` file is found in any candidate DaydreamEdu folder.
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
            raise ValueError(f"GoodNotes filename does not look like a PDF: {name}")

        base_stem = core[:-4]  # drop '.pdf'

        # Candidate basenames to try in order
        candidate_basenames = [
            f"_c_{base_stem}.pdf",
            f"_c_{base_stem} (empty).pdf",
        ]

        parts = list(p.parts)
        try:
            idx = parts.index("GoodNotes")
        except ValueError as exc:
            raise ValueError(f"Path does not contain a 'GoodNotes' segment: {p}") from exc

        # Student-scoped DaydreamEdu directory: replace GoodNotes with DaydreamEdu
        daydream_parts = parts.copy()
        daydream_parts[idx] = "DaydreamEdu"
        student_dir = Path(*daydream_parts[:-1])

        # General-scope DaydreamEdu directory: drop the student email segment
        general_dir: Path | None = None
        if len(daydream_parts) >= idx + 3:
            # Heuristic: the first segment after subject that contains '@' is the student
            for j in range(idx + 2, len(daydream_parts) - 1):
                if "@" in daydream_parts[j]:
                    general_parts = daydream_parts.copy()
                    general_parts.pop(j)
                    general_dir = Path(*general_parts[:-1])
                    break

        search_dirs = [student_dir]
        if general_dir is not None and general_dir != student_dir:
            search_dirs.append(general_dir)

        # Try each candidate basename in each candidate directory
        for d in search_dirs:
            for bn in candidate_basenames:
                candidate = d / bn
                if candidate.exists():
                    return candidate

        raise ValueError(f"Could not resolve GoodNotes template for {name}: no matching _c_ file found in DaydreamEdu")

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
        if "GoodNotes" not in completed_path.parts:
            raise ValueError(f"Path does not contain a 'GoodNotes' segment: {completed_path}")

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
        if group_type not in ("exam", "book_exercise", "collection"):
            raise ValueError(f"group_type must be exam, book_exercise, or collection; got {group_type!r}")
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
        conn = self._get_connection()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "INSERT OR IGNORE INTO file_group_members (group_id, file_id, role, added_at) VALUES (?, ?, ?, ?)",
            (group_id, file_id, role, now),
        )
        conn.commit()
        self._log_operation("group_add", file_id=file_id, group_id=group_id)
        return FileGroupMember(group_id=group_id, file_id=file_id, role=role, added_at=now, file=row)

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
