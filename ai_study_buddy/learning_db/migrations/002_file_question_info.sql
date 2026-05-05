CREATE TABLE IF NOT EXISTS file_question_info_runs (
    run_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    subject_scope TEXT NOT NULL,
    grade TEXT NOT NULL,
    slug TEXT NOT NULL,
    primary_file_id TEXT NOT NULL,
    primary_file_path TEXT,
    source_rel_path TEXT NOT NULL UNIQUE,
    source_content_hash TEXT NOT NULL,
    detector_model TEXT,
    detector_confidence TEXT,
    detector_notes TEXT,
    raw_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    row_version INTEGER NOT NULL DEFAULT 1,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    UNIQUE (primary_file_id, source_content_hash)
);

CREATE INDEX IF NOT EXISTS idx_fqi_runs_primary_file_updated
    ON file_question_info_runs(primary_file_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_fqi_runs_scope
    ON file_question_info_runs(subject_scope, grade, slug);

CREATE TABLE IF NOT EXISTS file_question_info_sections (
    run_id TEXT NOT NULL REFERENCES file_question_info_runs(run_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    question_type TEXT NOT NULL,
    printed_section_title TEXT,
    section_total_marks REAL,
    questions_page_range_json TEXT NOT NULL,
    stem_page_range_json TEXT,
    answers_page_range_json TEXT,
    answers_in_separate_booklet INTEGER,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (run_id, ordinal)
);

CREATE TABLE IF NOT EXISTS file_question_info_items (
    run_id TEXT NOT NULL REFERENCES file_question_info_runs(run_id) ON DELETE CASCADE,
    section_ordinal INTEGER NOT NULL,
    question_index TEXT NOT NULL,
    question_mark REAL,
    start_page INTEGER,
    extra_json TEXT,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (run_id, section_ordinal, question_index)
);

-- Expand artifact family checks to include file_question_info.
ALTER TABLE import_identity_map RENAME TO import_identity_map_old;

CREATE TABLE import_identity_map (
    map_id TEXT PRIMARY KEY,
    artifact_family TEXT NOT NULL CHECK (artifact_family IN ('marking_result', 'marking_amendment', 'student_review_state', 'file_question_info')),
    source_path TEXT NOT NULL,
    source_content_hash TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE (artifact_family, source_path, source_content_hash)
);

INSERT INTO import_identity_map(map_id, artifact_family, source_path, source_content_hash, artifact_id, first_seen_at, last_seen_at)
SELECT map_id, artifact_family, source_path, source_content_hash, artifact_id, first_seen_at, last_seen_at
FROM import_identity_map_old;

DROP TABLE import_identity_map_old;

CREATE INDEX IF NOT EXISTS idx_import_identity_artifact_id
    ON import_identity_map(artifact_id);

ALTER TABLE import_quarantine RENAME TO import_quarantine_old;

CREATE TABLE import_quarantine (
    quarantine_id TEXT PRIMARY KEY,
    artifact_family TEXT NOT NULL CHECK (artifact_family IN ('marking_result', 'marking_amendment', 'student_review_state', 'file_question_info')),
    source_path TEXT NOT NULL,
    source_content_hash TEXT,
    schema_version_detected TEXT,
    failure_stage TEXT NOT NULL CHECK (failure_stage IN ('read_json', 'schema_validate', 'fk_resolve', 'transform', 'upsert', 'io')),
    error_code TEXT NOT NULL,
    error_message TEXT NOT NULL,
    raw_payload_json TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'ignored')),
    retry_count INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    resolved_at TEXT,
    resolution_note TEXT
);

INSERT INTO import_quarantine(
    quarantine_id, artifact_family, source_path, source_content_hash, schema_version_detected,
    failure_stage, error_code, error_message, raw_payload_json, status, retry_count,
    first_seen_at, last_seen_at, resolved_at, resolution_note
)
SELECT
    quarantine_id, artifact_family, source_path, source_content_hash, schema_version_detected,
    failure_stage, error_code, error_message, raw_payload_json, status, retry_count,
    first_seen_at, last_seen_at, resolved_at, resolution_note
FROM import_quarantine_old;

DROP TABLE import_quarantine_old;

CREATE INDEX IF NOT EXISTS idx_import_quarantine_status
    ON import_quarantine(status);
CREATE INDEX IF NOT EXISTS idx_import_quarantine_family_stage
    ON import_quarantine(artifact_family, failure_stage);
