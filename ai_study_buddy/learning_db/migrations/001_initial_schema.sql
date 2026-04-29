CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS marking_artifacts (
    artifact_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    artifact_path TEXT NOT NULL UNIQUE,
    artifact_stem TEXT NOT NULL,
    source_content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    student_id TEXT,
    student_name TEXT,
    subject_context TEXT,
    attempt_file_id TEXT,
    attempt_file_path TEXT,
    template_file_id TEXT,
    template_file_path TEXT,
    book_group_id TEXT,
    book_label TEXT,
    unit_file_id TEXT,
    unit_file_path TEXT,
    unit_label TEXT,
    answer_file_id TEXT,
    answer_file_path TEXT,
    answer_page_start INTEGER,
    answer_page_end INTEGER,
    starts_mid_page INTEGER NOT NULL DEFAULT 0,
    ends_mid_page INTEGER NOT NULL DEFAULT 0,
    answer_mapping_source TEXT,
    answer_mapping_notes TEXT,
    marking_asset TEXT,
    is_partial INTEGER NOT NULL DEFAULT 0,
    template_attempt_group_id TEXT,
    attempt_sequence INTEGER,
    attempt_label TEXT,
    question_selection_json TEXT,
    context_resolution_json TEXT,
    summary_total_marks REAL,
    summary_earned_marks REAL,
    summary_percentage REAL,
    summary_overall_assessment TEXT,
    summary_human_note TEXT,
    review_meta_updated_at TEXT,
    review_meta_updated_by TEXT,
    generation_produced_by TEXT,
    generation_mode TEXT,
    generation_notes TEXT,
    review_meta_json TEXT,
    generation_json TEXT,
    context_json TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    row_version INTEGER NOT NULL DEFAULT 1,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT,
    delete_reason TEXT,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_marking_artifacts_attempt_file_id
    ON marking_artifacts(attempt_file_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_marking_artifacts_subject
    ON marking_artifacts(subject_context);
CREATE INDEX IF NOT EXISTS idx_marking_artifacts_not_deleted
    ON marking_artifacts(is_deleted);

CREATE TABLE IF NOT EXISTS marking_question_results (
    artifact_id TEXT NOT NULL REFERENCES marking_artifacts(artifact_id) ON DELETE CASCADE,
    result_id TEXT NOT NULL,
    scoring_status TEXT,
    outcome TEXT,
    max_marks REAL,
    earned_marks REAL,
    student_answer TEXT,
    correct_answer TEXT,
    diagnosis_mistake_type TEXT,
    diagnosis_reasoning TEXT,
    diagnosis_confidence TEXT,
    human_note TEXT,
    error_tags_json TEXT,
    skill_tags_json TEXT,
    diagnosis_json TEXT,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (artifact_id, result_id)
);

CREATE TABLE IF NOT EXISTS marking_question_page_map (
    artifact_id TEXT NOT NULL REFERENCES marking_artifacts(artifact_id) ON DELETE CASCADE,
    result_id TEXT NOT NULL,
    attempt_page_start INTEGER,
    confidence TEXT,
    source TEXT,
    evidence_image TEXT,
    note TEXT,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (artifact_id, result_id)
);

CREATE TABLE IF NOT EXISTS marking_amendments (
    amendment_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES marking_artifacts(artifact_id) ON DELETE CASCADE,
    schema_version TEXT NOT NULL,
    amendment_path TEXT NOT NULL UNIQUE,
    source_content_hash TEXT NOT NULL,
    student_id TEXT,
    subject_context TEXT,
    attempt_file_id TEXT,
    marking_result_path TEXT NOT NULL,
    review_meta_updated_at TEXT,
    review_meta_updated_by TEXT,
    summary_overrides_json TEXT,
    question_amendments_json TEXT,
    question_page_map_amendments_json TEXT,
    context_json TEXT NOT NULL,
    review_meta_json TEXT,
    row_version INTEGER NOT NULL DEFAULT 1,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT,
    delete_reason TEXT,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_marking_amendments_artifact_id
    ON marking_amendments(artifact_id);
CREATE INDEX IF NOT EXISTS idx_marking_amendments_not_deleted
    ON marking_amendments(is_deleted);

CREATE TABLE IF NOT EXISTS marking_question_amendments (
    amendment_id TEXT NOT NULL REFERENCES marking_amendments(amendment_id) ON DELETE CASCADE,
    result_id TEXT NOT NULL,
    fields_json TEXT,
    reviewer_reason TEXT,
    evidence_json TEXT,
    updated_at TEXT,
    updated_by TEXT,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (amendment_id, result_id)
);

CREATE TABLE IF NOT EXISTS marking_page_map_amendments (
    amendment_id TEXT NOT NULL REFERENCES marking_amendments(amendment_id) ON DELETE CASCADE,
    result_id TEXT NOT NULL,
    attempt_page_start INTEGER,
    confidence TEXT,
    updated_at TEXT,
    updated_by TEXT,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (amendment_id, result_id)
);

CREATE TABLE IF NOT EXISTS student_review_states (
    review_state_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES marking_artifacts(artifact_id) ON DELETE CASCADE,
    schema_version TEXT NOT NULL,
    review_state_path TEXT NOT NULL UNIQUE,
    source_content_hash TEXT NOT NULL,
    student_id TEXT,
    subject_context TEXT,
    attempt_file_id TEXT,
    marking_result_path TEXT NOT NULL,
    template_attempt_group_id TEXT,
    attempt_sequence INTEGER,
    review_status TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT,
    summary_json TEXT,
    question_reviews_json TEXT,
    attempt_notes_json TEXT,
    student_subject_notes_json TEXT,
    context_json TEXT NOT NULL,
    review_meta_json TEXT,
    row_version INTEGER NOT NULL DEFAULT 1,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT,
    delete_reason TEXT,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_student_review_states_artifact_id
    ON student_review_states(artifact_id);
CREATE INDEX IF NOT EXISTS idx_student_review_states_not_deleted
    ON student_review_states(is_deleted);

CREATE TABLE IF NOT EXISTS student_review_notes (
    note_id TEXT PRIMARY KEY,
    review_state_id TEXT NOT NULL REFERENCES student_review_states(review_state_id) ON DELETE CASCADE,
    artifact_id TEXT NOT NULL REFERENCES marking_artifacts(artifact_id) ON DELETE CASCADE,
    scope TEXT NOT NULL,
    result_id TEXT,
    review_status TEXT,
    author_role TEXT,
    note_text TEXT,
    updated_at TEXT,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_student_review_notes_review_state_id
    ON student_review_notes(review_state_id);

CREATE TABLE IF NOT EXISTS operation_log (
    operation_id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('started', 'succeeded', 'failed')),
    error_code TEXT,
    error_message TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_operation_log_occurred_at
    ON operation_log(occurred_at);
CREATE INDEX IF NOT EXISTS idx_operation_log_operation_type
    ON operation_log(operation_type);

CREATE TABLE IF NOT EXISTS import_identity_map (
    map_id TEXT PRIMARY KEY,
    artifact_family TEXT NOT NULL CHECK (artifact_family IN ('marking_result', 'marking_amendment', 'student_review_state')),
    source_path TEXT NOT NULL,
    source_content_hash TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE (artifact_family, source_path, source_content_hash)
);

CREATE INDEX IF NOT EXISTS idx_import_identity_artifact_id
    ON import_identity_map(artifact_id);

CREATE TABLE IF NOT EXISTS import_quarantine (
    quarantine_id TEXT PRIMARY KEY,
    artifact_family TEXT NOT NULL CHECK (artifact_family IN ('marking_result', 'marking_amendment', 'student_review_state')),
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

CREATE INDEX IF NOT EXISTS idx_import_quarantine_status
    ON import_quarantine(status);
CREATE INDEX IF NOT EXISTS idx_import_quarantine_family_stage
    ON import_quarantine(artifact_family, failure_stage);

