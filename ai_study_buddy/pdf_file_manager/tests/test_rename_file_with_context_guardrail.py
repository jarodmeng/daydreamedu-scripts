import json
from pathlib import Path
import uuid

from ai_study_buddy.learning_db.core.connection import get_connection
from ai_study_buddy.learning_db.core.migrate import apply_migrations
from ai_study_buddy.marking.core.artifact_paths import slugify_student
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
from ai_study_buddy.pdf_file_manager.scripts.rename_file_with_context_guardrail import (
    rename_file_with_context_guardrail,
)


def _write_marking_bundle(
    *,
    context_root: Path,
    student_slug: str,
    subject_context: str,
    stem: str,
    completion_id: str,
    template_id: str,
) -> None:
    marking_path = context_root / "marking_results" / student_slug / subject_context / f"{stem}.json"
    marking_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.6",
        "created_at": "2026-01-01T01:01:01Z",
        "updated_at": "2026-01-01T01:01:01Z",
        "context": {
            "attempt_file_id": completion_id,
            "template_file_id": template_id,
            "attempt_file_path": "/tmp/old.pdf",
            "student_id": "emma",
            "student_name": "Emma",
            "subject_context": subject_context,
            "marking_asset": f"marking_assets/{student_slug}/{subject_context}/{stem}",
            "context_resolution": {
                "method": "resolve_marking_context",
                "resolver_version": "test",
                "resolved_at": "2026-01-01T01:01:01Z",
                "mode": "standard_mapped_answer",
            },
            "unit_label": "unit",
            "answer_file_id": template_id,
            "answer_file_path": "/tmp/template.pdf",
            "answer_page_start": 1,
            "answer_page_end": 1,
        },
        "marking_results": [],
    }
    marking_path.write_text(json.dumps(payload), encoding="utf-8")

    report_path = context_root / "learning_reports" / student_slug / subject_context / f"{stem} - Marking Report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("report", encoding="utf-8")

    review_path = context_root / "student_review_states" / student_slug / subject_context / f"{stem}.json"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text('{"status":"new"}', encoding="utf-8")

    amend_path = context_root / "marking_amendments" / student_slug / subject_context / f"{stem}.json"
    amend_path.parent.mkdir(parents=True, exist_ok=True)
    amend_path.write_text('{"changes":[]}', encoding="utf-8")

    asset_dir = context_root / "marking_assets" / student_slug / subject_context / stem
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "attempt").mkdir(parents=True, exist_ok=True)


def _seed_learning_db_rows(
    *,
    learning_db_path: Path,
    marking_rel: str,
    review_rel: str,
    amendment_rel: str,
    asset_rel: str,
    completion_id: str,
) -> None:
    apply_migrations(learning_db_path)
    conn = get_connection(learning_db_path)
    artifact_id = str(uuid.uuid4())
    review_state_id = str(uuid.uuid4())
    amendment_id = str(uuid.uuid4())
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO marking_artifacts(
                    artifact_id, schema_version, artifact_path, artifact_stem, source_content_hash,
                    created_at, updated_at, attempt_file_id, marking_asset, context_json, summary_json, raw_json
                ) VALUES (?, '1.6', ?, ?, 'h', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', ?, ?, '{}', '{}', '{}')
                """,
                (artifact_id, marking_rel, Path(marking_rel).stem, completion_id, asset_rel),
            )
            conn.execute(
                """
                INSERT INTO student_review_states(
                    review_state_id, artifact_id, schema_version, review_state_path, source_content_hash,
                    attempt_file_id, marking_result_path, created_at, updated_at, context_json, raw_json
                ) VALUES (?, ?, 'student_review_state.v1', ?, 'h', ?, ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', '{}', '{}')
                """,
                (review_state_id, artifact_id, review_rel, completion_id, marking_rel),
            )
            conn.execute(
                """
                INSERT INTO marking_amendments(
                    amendment_id, artifact_id, schema_version, amendment_path, source_content_hash,
                    attempt_file_id, marking_result_path, context_json, raw_json
                ) VALUES (?, ?, 'marking_amendment.v1', ?, 'h', ?, ?, '{}', '{}')
                """,
                (amendment_id, artifact_id, amendment_rel, completion_id, marking_rel),
            )
            conn.execute(
                """
                INSERT INTO import_identity_map(
                    map_id, artifact_family, source_path, source_content_hash, artifact_id, first_seen_at, last_seen_at
                ) VALUES (?, 'student_review_state', ?, 'h', ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
                """,
                (str(uuid.uuid4()), review_rel, review_state_id),
            )
            conn.execute(
                """
                INSERT INTO import_identity_map(
                    map_id, artifact_family, source_path, source_content_hash, artifact_id, first_seen_at, last_seen_at
                ) VALUES (?, 'student_review_state', ?, 'h', ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
                """,
                (str(uuid.uuid4()), f"{review_rel}::question::q1", review_state_id),
            )
    finally:
        conn.close()


def test_rename_guardrail_dry_run_plans_linked_moves_and_ignores_archive(tmp_path):
    db_path = tmp_path / "registry.db"
    context_root = tmp_path / "context"
    manager = PdfFileManager(db_path=str(db_path))
    manager.add_student("emma", "Emma")

    template_pdf = tmp_path / "templates" / "_c_Old Name.pdf"
    template_pdf.parent.mkdir(parents=True, exist_ok=True)
    template_pdf.write_bytes(b"%PDF-1.4 template")
    completion_pdf = tmp_path / "completions" / "_c_Old Name.pdf"
    completion_pdf.parent.mkdir(parents=True, exist_ok=True)
    completion_pdf.write_bytes(b"%PDF-1.4 completion")

    template = manager.register_file(template_pdf, file_type="main", student_id="emma", is_template=True)
    completion = manager.register_file(completion_pdf, file_type="main", student_id="emma", is_template=False)
    manager.link_to_template(completion.id, template.id)

    student_slug = slugify_student("emma", "Emma")
    subject_context = "singapore_primary_math"
    stem = "Old Name__20260101_010101"
    _write_marking_bundle(
        context_root=context_root,
        student_slug=student_slug,
        subject_context=subject_context,
        stem=stem,
        completion_id=completion.id,
        template_id=template.id,
    )

    archived = context_root / "marking_results" / "archive" / student_slug / subject_context / f"{stem}.json"
    archived.parent.mkdir(parents=True, exist_ok=True)
    archived.write_text("{}", encoding="utf-8")

    result = rename_file_with_context_guardrail(
        file_id_or_path=completion.id,
        new_name="_c_New Name.pdf",
        context_root=context_root,
        db_path=db_path,
        dry_run=True,
    )

    assert result["dry_run"] is True
    moves = result["planned_moves"]
    families = {m["family"] for m in moves}
    assert families == {
        "learning_reports",
        "marking_amendments",
        "marking_assets",
        "marking_results",
        "student_review_states",
    }
    assert all("/archive/" not in m["src"] for m in moves)


def test_rename_guardrail_apply_moves_files_and_writes_manifest(tmp_path):
    db_path = tmp_path / "registry.db"
    learning_db_path = tmp_path / "study_buddy.db"
    context_root = tmp_path / "context"
    manifest_path = tmp_path / "manifest.json"
    manager = PdfFileManager(db_path=str(db_path))
    manager.add_student("emma", "Emma")

    template_pdf = tmp_path / "_c_Old Name.pdf"
    template_pdf.write_bytes(b"%PDF-1.4 template")
    completion_pdf = tmp_path / "_c_Old Name completion.pdf"
    completion_pdf.write_bytes(b"%PDF-1.4 completion")

    template = manager.register_file(template_pdf, file_type="main", student_id="emma", is_template=True)
    completion = manager.register_file(completion_pdf, file_type="main", student_id="emma", is_template=False)
    manager.link_to_template(completion.id, template.id)

    student_slug = slugify_student("emma", "Emma")
    subject_context = "singapore_primary_math"
    old_stem = "Old Name completion__20260101_010101"
    new_stem = "New Name completion__20260101_010101"
    _write_marking_bundle(
        context_root=context_root,
        student_slug=student_slug,
        subject_context=subject_context,
        stem=old_stem,
        completion_id=completion.id,
        template_id=template.id,
    )
    old_marking_rel = f"marking_results/{student_slug}/{subject_context}/{old_stem}.json"
    old_review_rel = f"student_review_states/{student_slug}/{subject_context}/{old_stem}.json"
    old_amend_rel = f"marking_amendments/{student_slug}/{subject_context}/{old_stem}.json"
    old_asset_rel = f"marking_assets/{student_slug}/{subject_context}/{old_stem}"
    _seed_learning_db_rows(
        learning_db_path=learning_db_path,
        marking_rel=old_marking_rel,
        review_rel=old_review_rel,
        amendment_rel=old_amend_rel,
        asset_rel=old_asset_rel,
        completion_id=completion.id,
    )

    result = rename_file_with_context_guardrail(
        file_id_or_path=completion.id,
        new_name="_c_New Name completion.pdf",
        context_root=context_root,
        db_path=db_path,
        learning_db_path=learning_db_path,
        dry_run=False,
        manifest_path=manifest_path,
    )

    assert result["registry_rename_applied"] is True
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["errors"] == []
    assert len(manifest["applied_moves"]) == 5
    assert manifest["learning_db_remap"]["status"] == "updated"

    marking_new = context_root / "marking_results" / student_slug / subject_context / f"{new_stem}.json"
    report_new = context_root / "learning_reports" / student_slug / subject_context / f"{new_stem} - Marking Report.md"
    review_new = context_root / "student_review_states" / student_slug / subject_context / f"{new_stem}.json"
    amend_new = context_root / "marking_amendments" / student_slug / subject_context / f"{new_stem}.json"
    assets_new = context_root / "marking_assets" / student_slug / subject_context / new_stem
    assert marking_new.exists()
    assert report_new.exists()
    assert review_new.exists()
    assert amend_new.exists()
    assert assets_new.exists()

    new_marking_rel = f"marking_results/{student_slug}/{subject_context}/{new_stem}.json"
    new_review_rel = f"student_review_states/{student_slug}/{subject_context}/{new_stem}.json"
    new_amend_rel = f"marking_amendments/{student_slug}/{subject_context}/{new_stem}.json"
    new_asset_rel = f"marking_assets/{student_slug}/{subject_context}/{new_stem}"

    conn = get_connection(learning_db_path)
    try:
        row = conn.execute("SELECT artifact_path, artifact_stem, marking_asset FROM marking_artifacts").fetchone()
        assert row is not None
        assert row["artifact_path"] == new_marking_rel
        assert row["artifact_stem"] == new_stem
        assert row["marking_asset"] == new_asset_rel

        row = conn.execute("SELECT review_state_path, marking_result_path FROM student_review_states").fetchone()
        assert row is not None
        assert row["review_state_path"] == new_review_rel
        assert row["marking_result_path"] == new_marking_rel

        row = conn.execute("SELECT amendment_path, marking_result_path FROM marking_amendments").fetchone()
        assert row is not None
        assert row["amendment_path"] == new_amend_rel
        assert row["marking_result_path"] == new_marking_rel

        id_rows = conn.execute(
            "SELECT source_path FROM import_identity_map ORDER BY source_path"
        ).fetchall()
        src_paths = [r["source_path"] for r in id_rows]
        assert new_review_rel in src_paths
        assert f"{new_review_rel}::question::q1" in src_paths
    finally:
        conn.close()
