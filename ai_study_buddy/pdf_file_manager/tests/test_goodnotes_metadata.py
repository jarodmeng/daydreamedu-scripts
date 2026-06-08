import sqlite3
from pathlib import Path

import pytest

from ai_study_buddy.pdf_file_manager.pdf_file_manager import NotFoundError, PdfFileManager


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"pdf")


def _create_goodnotes_dbs(base: Path, docs: list[dict]) -> tuple[Path, Path]:
    projection = base / "projection.sqlite"
    fts = base / "fts.sqlite"
    projection.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(projection)
    conn.executescript(
        """
        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at DOUBLE DEFAULT 0,
            updated_at DOUBLE DEFAULT 0,
            deleted BOOLEAN DEFAULT 0
        );
        CREATE TABLE folders (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE folder_to_folder_items (
            id TEXT PRIMARY KEY,
            parent_folder_id TEXT,
            root_folder_id TEXT,
            item_id TEXT,
            item_name TEXT,
            item_type INTEGER,
            deleted BOOLEAN DEFAULT 0
        );
        CREATE TABLE document_share (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            current_user_id TEXT NOT NULL,
            updated_at DOUBLE NOT NULL,
            service NUMERIC NOT NULL,
            data BLOB NOT NULL,
            created_at DOUBLE NOT NULL DEFAULT 0
        );
        """
    )
    conn.executemany(
        "INSERT INTO folders (id, name) VALUES (?, ?)",
        [("SUBJECT", "Singapore Primary Science"), ("GRADE", "P6"), ("TYPE", "Exam")],
    )
    conn.executemany(
        """
        INSERT INTO folder_to_folder_items
            (id, parent_folder_id, root_folder_id, item_id, item_name, item_type, deleted)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        [
            ("ffi-subject", "ROOT", "ROOT", "SUBJECT", "Singapore Primary Science", 0),
            ("ffi-grade", "SUBJECT", "ROOT", "GRADE", "P6", 0),
            ("ffi-type", "GRADE", "ROOT", "TYPE", "Exam", 0),
        ],
    )
    for doc in docs:
        conn.execute(
            "INSERT INTO documents (id, name, created_at, updated_at, deleted) VALUES (?, ?, ?, ?, ?)",
            (
                doc["id"],
                doc["name"],
                doc.get("created_at", 1773322677015.2),
                doc.get("updated_at", 1779245963351.69),
                1 if doc.get("deleted") else 0,
            ),
        )
        conn.execute(
            """
            INSERT INTO folder_to_folder_items
                (id, parent_folder_id, root_folder_id, item_id, item_name, item_type, deleted)
            VALUES (?, 'TYPE', 'ROOT', ?, ?, 1, 0)
            """,
            (f"ffi-{doc['id']}", doc["id"], doc["name"]),
        )
        share_alias = doc.get("share_alias")
        if share_alias:
            payload = (
                f'{{"documentResponse":{{"documentAlias":"{share_alias}",'
                f'"documentId":"{doc["id"]}"}}}}'
            ).encode("utf-8")
            conn.execute(
                """
                INSERT INTO document_share
                    (id, document_id, owner_id, current_user_id, updated_at, service, data, created_at)
                VALUES (?, ?, 'owner', 'owner', 1.0, 2, ?, 0)
                """,
                (f"{doc['id']}:1", doc["id"], payload),
            )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(fts)
    conn.execute(
        """
        CREATE TABLE document_meta (
            document_id TEXT UNIQUE,
            name TEXT,
            last_modified DATETIME,
            is_deleted BOOLEAN
        )
        """
    )
    for doc in docs:
        conn.execute(
            "INSERT INTO document_meta (document_id, name, last_modified, is_deleted) VALUES (?, ?, ?, ?)",
            (
                doc["id"],
                doc["name"],
                doc.get("last_modified", "2026-03-18 14:54:04.072"),
                1 if doc.get("deleted") else 0,
            ),
        )
    conn.commit()
    conn.close()
    return projection, fts


@pytest.fixture
def goodnotes_env(tmp_path, monkeypatch):
    goodnotes_root = tmp_path / "GoodNotes"
    goodnotes_root.mkdir()
    monkeypatch.setenv("GOODNOTES_ROOT", str(goodnotes_root))
    projection, fts = _create_goodnotes_dbs(
        tmp_path / "goodnotes-db",
        [
            {"id": "DOC1", "name": "_c_p6.science.wa1.4"},
        ],
    )
    monkeypatch.setenv("GOODNOTES_PROJECTION_DB", str(projection))
    monkeypatch.setenv("GOODNOTES_FTS_DB", str(fts))
    return goodnotes_root


def test_goodnotes_share_link_from_document_share(tmp_path, monkeypatch):
    goodnotes_root = tmp_path / "GoodNotes"
    goodnotes_root.mkdir()
    monkeypatch.setenv("GOODNOTES_ROOT", str(goodnotes_root))
    projection, fts = _create_goodnotes_dbs(
        tmp_path / "goodnotes-db",
        [{"id": "DOC-SHARE", "name": "_c_numbers_laq", "share_alias": "Amwv4ubzFA1GGgvqwo83b7"}],
    )
    monkeypatch.setenv("GOODNOTES_PROJECTION_DB", str(projection))
    monkeypatch.setenv("GOODNOTES_FTS_DB", str(fts))

    pdf_path = goodnotes_root / "c_numbers_laq.pdf"
    _touch(pdf_path)
    mgr = PdfFileManager(db_path=tmp_path / "registry.db")
    pdf_file = mgr.register_file(pdf_path, file_type="main")

    match = mgr.get_goodnotes_document_timestamps_for_file(pdf_file.id)

    assert match.status == "matched_leading_underscore_restored"
    assert match.share_link == "https://share.goodnotes.com/s/Amwv4ubzFA1GGgvqwo83b7"


def test_goodnotes_timestamps_match_leading_underscore_and_folder_path(tmp_path, goodnotes_env):
    pdf_path = goodnotes_env / "Singapore Primary Science" / "winston@example.com" / "P6" / "Exam" / "c_p6.science.wa1.4.pdf"
    _touch(pdf_path)
    mgr = PdfFileManager(db_path=tmp_path / "registry.db")
    pdf_file = mgr.register_file(pdf_path, file_type="main")

    match = mgr.get_goodnotes_document_timestamps_for_file(pdf_file.id)

    assert match.status == "matched_leading_underscore_restored"
    assert match.matched_candidate_name == "_c_p6.science.wa1.4"
    assert match.goodnotes_document_id == "DOC1"
    assert match.goodnotes_folder_path == "Singapore Primary Science / P6 / Exam"
    assert match.goodnotes_folder_ids == ("SUBJECT", "GRADE", "TYPE")
    assert match.timestamps is not None
    assert match.timestamps.created_at == "2026-03-12T13:37:57Z"
    assert match.timestamps.updated_at == "2026-05-20T02:59:23Z"
    assert match.timestamps.last_modified == "2026-03-18T14:54:04.072Z"


def test_goodnotes_timestamps_match_exact_by_path(tmp_path, goodnotes_env):
    pdf_path = goodnotes_env / "_c_p6.science.wa1.4.pdf"
    _touch(pdf_path)
    mgr = PdfFileManager(db_path=tmp_path / "registry.db")
    pdf_file = mgr.register_file(pdf_path, file_type="main")

    match = mgr.get_goodnotes_document_timestamps_for_path(pdf_path)

    assert match.file_id == pdf_file.id
    assert match.status == "matched_exact"
    assert match.goodnotes_document_name == "_c_p6.science.wa1.4"


def test_goodnotes_timestamps_match_raw_source_fallback(tmp_path, monkeypatch):
    goodnotes_root = tmp_path / "GoodNotes"
    goodnotes_root.mkdir()
    monkeypatch.setenv("GOODNOTES_ROOT", str(goodnotes_root))
    projection, fts = _create_goodnotes_dbs(
        tmp_path / "goodnotes-db",
        [{"id": "DOC-RAW", "name": "EPO_Comprehension_Cloze_04"}],
    )
    monkeypatch.setenv("GOODNOTES_PROJECTION_DB", str(projection))
    monkeypatch.setenv("GOODNOTES_FTS_DB", str(fts))

    raw_path = goodnotes_root / "EPO_Comprehension_Cloze_04.pdf"
    main_path = goodnotes_root / "_c_EPO_Comprehension_Cloze_04.pdf"
    _touch(raw_path)
    _touch(main_path)
    mgr = PdfFileManager(db_path=tmp_path / "registry.db")
    raw = mgr.register_file(raw_path, file_type="raw")
    main = mgr.register_file(main_path, file_type="main")
    mgr.link_files(main.id, raw.id, "raw_source")

    match = mgr.get_goodnotes_document_timestamps_for_file(main.id)

    assert match.status == "matched_raw_source"
    assert match.matched_candidate_name == "EPO_Comprehension_Cloze_04"
    assert "EPO_Comprehension_Cloze_04" in match.candidate_names


def test_goodnotes_timestamps_statuses_for_unsupported_files(tmp_path, monkeypatch, goodnotes_env):
    mgr = PdfFileManager(db_path=tmp_path / "registry.db")
    daydream_path = tmp_path / "DaydreamEdu" / "_c_other.pdf"
    _touch(daydream_path)
    daydream_file = mgr.register_file(daydream_path, file_type="main")

    not_goodnotes = mgr.get_goodnotes_document_timestamps_for_file(daydream_file.id)
    assert not_goodnotes.status == "not_goodnotes_root"

    raw_path = goodnotes_env / "raw.pdf"
    _touch(raw_path)
    raw_file = mgr.register_file(raw_path, file_type="raw")

    not_main = mgr.get_goodnotes_document_timestamps_for_file(raw_file.id)
    assert not_main.status == "not_main_file"


def test_goodnotes_timestamps_metadata_unavailable(tmp_path, monkeypatch):
    goodnotes_root = tmp_path / "GoodNotes"
    goodnotes_root.mkdir()
    monkeypatch.setenv("GOODNOTES_ROOT", str(goodnotes_root))
    monkeypatch.setenv("GOODNOTES_PROJECTION_DB", str(tmp_path / "missing-projection.sqlite"))
    monkeypatch.setenv("GOODNOTES_FTS_DB", str(tmp_path / "missing-fts.sqlite"))
    pdf_path = goodnotes_root / "c_missing.pdf"
    _touch(pdf_path)
    mgr = PdfFileManager(db_path=tmp_path / "registry.db")
    pdf_file = mgr.register_file(pdf_path, file_type="main")

    match = mgr.get_goodnotes_document_timestamps_for_file(pdf_file.id)

    assert match.status == "metadata_unavailable"


def test_goodnotes_share_link_disambiguates_attempt_vs_review_folder(tmp_path, monkeypatch):
    goodnotes_root = tmp_path / "GoodNotes"
    goodnotes_root.mkdir()
    monkeypatch.setenv("GOODNOTES_ROOT", str(goodnotes_root))
    projection, fts = _create_goodnotes_dbs(
        tmp_path / "goodnotes-db",
        [
            {
                "id": "DOC-ATTEMPT",
                "name": "_c_PP Math PSLE Part D P6 Topical Practice Percentage",
                "share_alias": "attempt-alias",
            },
            {
                "id": "DOC-REVIEW",
                "name": "_c_PP Math PSLE Part D P6 Topical Practice Percentage",
                "share_alias": "review-alias",
            },
        ],
    )
    monkeypatch.setenv("GOODNOTES_PROJECTION_DB", str(projection))
    monkeypatch.setenv("GOODNOTES_FTS_DB", str(fts))

    conn = sqlite3.connect(projection)
    conn.execute("INSERT INTO folders (id, name) VALUES ('REVIEW', 'Review')")
    conn.execute(
        """
        INSERT INTO folder_to_folder_items
            (id, parent_folder_id, root_folder_id, item_id, item_name, item_type, deleted)
        VALUES ('ffi-review-parent', 'TYPE', 'ROOT', 'REVIEW', 'Review', 0, 0)
        """
    )
    conn.execute(
        """
        UPDATE folder_to_folder_items
        SET parent_folder_id = 'REVIEW'
        WHERE item_id = 'DOC-REVIEW'
        """
    )
    conn.commit()
    conn.close()

    pdf_path = goodnotes_root / "c_PP Math PSLE Part D P6 Topical Practice Percentage.pdf"
    _touch(pdf_path)
    mgr = PdfFileManager(db_path=tmp_path / "registry.db")
    pdf_file = mgr.register_file(pdf_path, file_type="main")

    attempt_match = mgr.get_goodnotes_document_timestamps_for_file(pdf_file.id, folder_scope="attempt")
    review_match = mgr.get_goodnotes_document_timestamps_for_file(pdf_file.id, folder_scope="review")

    assert attempt_match.status == "matched_leading_underscore_restored"
    assert attempt_match.goodnotes_document_id == "DOC-ATTEMPT"
    assert attempt_match.share_link == "https://share.goodnotes.com/s/attempt-alias"
    assert attempt_match.goodnotes_folder_path.endswith("Exam")

    assert review_match.status == "matched_leading_underscore_restored"
    assert review_match.goodnotes_document_id == "DOC-REVIEW"
    assert review_match.share_link == "https://share.goodnotes.com/s/review-alias"
    assert review_match.goodnotes_folder_path.endswith("Review")


def test_goodnotes_timestamps_not_found_and_ambiguous(tmp_path, monkeypatch):
    goodnotes_root = tmp_path / "GoodNotes"
    goodnotes_root.mkdir()
    monkeypatch.setenv("GOODNOTES_ROOT", str(goodnotes_root))
    projection, fts = _create_goodnotes_dbs(
        tmp_path / "goodnotes-db",
        [
            {"id": "A", "name": "_c_duplicate"},
            {"id": "B", "name": "_c_duplicate"},
        ],
    )
    monkeypatch.setenv("GOODNOTES_PROJECTION_DB", str(projection))
    monkeypatch.setenv("GOODNOTES_FTS_DB", str(fts))
    mgr = PdfFileManager(db_path=tmp_path / "registry.db")

    missing_path = goodnotes_root / "c_missing.pdf"
    _touch(missing_path)
    missing_file = mgr.register_file(missing_path, file_type="main")
    assert mgr.get_goodnotes_document_timestamps_for_file(missing_file.id).status == "not_found"

    duplicate_path = goodnotes_root / "c_duplicate.pdf"
    _touch(duplicate_path)
    duplicate_file = mgr.register_file(duplicate_path, file_type="main")
    assert mgr.get_goodnotes_document_timestamps_for_file(duplicate_file.id).status == "ambiguous"


def test_goodnotes_timestamps_missing_registry_file_raises(tmp_path):
    mgr = PdfFileManager(db_path=tmp_path / "registry.db")

    with pytest.raises(NotFoundError):
        mgr.get_goodnotes_document_timestamps_for_file("missing")
