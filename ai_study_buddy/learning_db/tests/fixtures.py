"""Shared test payloads for importer tests."""


def _minimal_mr(attempt_file_id: str, student: str, subject: str, stem: str = "paper") -> dict:
    """Tiny valid-ish dict for DB insert path; importer validates strictly — use fixture for real run."""

    return {
        "schema_version": "marking_result.v1.5",
        "created_at": "2026-05-01T12:00:00+08:00",
        "updated_at": "2026-05-01T12:00:00+08:00",
        "context": {
            "student_id": student,
            "student_name": student,
            "subject_context": subject,
            "attempt_file_id": attempt_file_id,
            "attempt_file_path": "/tmp/x.pdf",
            "template_file_id": "t",
            "template_file_path": "/tmp/t.pdf",
            "unit_file_id": "t",
            "unit_file_path": "/tmp/t.pdf",
            "unit_label": "U",
            "answer_file_id": "a",
            "answer_file_path": "/tmp/a.pdf",
            "answer_page_start": 1,
            "answer_page_end": 1,
            "starts_mid_page": False,
            "ends_mid_page": False,
            "answer_mapping_source": "manual_verified",
            "marking_asset": f"marking_assets/{student}/{subject}/m",
            "is_partial": False,
            "template_attempt_group_id": f"{student}::t",
            "attempt_sequence": 1,
            "question_page_map": [
                {
                    "result_id": "Q1",
                    "attempt_page_start": 1,
                    "confidence": "high",
                    "source": "manual_visual",
                }
            ],
            "question_selection": {"canonical_refs": []},
        },
        "summary": {"total_marks": 1, "earned_marks": 1, "percentage": 100.0, "overall_assessment": "ok"},
        "question_results": [
            {
                "result_id": "Q1",
                "max_marks": 1,
                "earned_marks": 1,
                "outcome": "correct",
                "student_answer": "1",
                "correct_answer": "1",
                "scoring_status": "counted",
                "error_tags": [],
                "skill_tags": [],
                "diagnosis": {},
            }
        ],
        "review_meta": {},
        "generation": {"produced_by": "t", "mode": "manual"},
    }
