-- pdf_file_manager schema (Phase 1). See ARCHITECTURE.md.

-- Students
CREATE TABLE IF NOT EXISTS students (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT,
    added_at   TEXT NOT NULL
);

-- Core file registry
CREATE TABLE IF NOT EXISTS pdf_files (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    path           TEXT NOT NULL UNIQUE,
    file_type      TEXT NOT NULL DEFAULT 'unknown'
                   CHECK(file_type IN ('main', 'raw', 'unknown')),
    doc_type       TEXT NOT NULL DEFAULT 'unknown'
                   CHECK(doc_type IN ('exam', 'worksheet', 'book_exercise', 'activity', 'practice', 'notes', 'unknown')),
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

-- Raw ↔ main pairs; template ↔ completed pairs
CREATE TABLE IF NOT EXISTS file_relations (
    id            TEXT PRIMARY KEY,
    source_id     TEXT NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
    target_id     TEXT NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL
                  CHECK(relation_type IN ('raw_source', 'main_version', 'template_for', 'completed_from')),
    created_at    TEXT NOT NULL,
    UNIQUE(source_id, target_id, relation_type)
);

-- Named groups of files
CREATE TABLE IF NOT EXISTS file_groups (
    id         TEXT PRIMARY KEY,
    label      TEXT NOT NULL,
    group_type TEXT NOT NULL DEFAULT 'collection'
               CHECK(group_type IN ('exam', 'book_exercise', 'collection')),
    anchor_id  TEXT REFERENCES pdf_files(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    notes      TEXT
);

CREATE TABLE IF NOT EXISTS file_group_members (
    group_id   TEXT NOT NULL REFERENCES file_groups(id) ON DELETE CASCADE,
    file_id    TEXT NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
    role       TEXT,
    added_at   TEXT NOT NULL,
    PRIMARY KEY (group_id, file_id)
);

-- Append-only audit log (no FK so entries survive deletes)
CREATE TABLE IF NOT EXISTS operation_log (
    id           TEXT PRIMARY KEY,
    operation    TEXT NOT NULL,
    file_id      TEXT,
    group_id     TEXT,
    performed_at TEXT NOT NULL,
    performed_by TEXT,
    before_state TEXT,
    after_state  TEXT,
    notes        TEXT
);

-- Scan roots
CREATE TABLE IF NOT EXISTS scan_roots (
    id         TEXT PRIMARY KEY,
    path       TEXT NOT NULL UNIQUE,
    student_id TEXT REFERENCES students(id),
    added_at   TEXT NOT NULL
);
