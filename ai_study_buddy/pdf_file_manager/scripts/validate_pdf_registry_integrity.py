#!/usr/bin/env python3
"""Validate common PDF registry integrity issues.

This is a reproducible audit for the main problems previously discovered by
ad hoc investigation:

1. files under a registered student's email folder that are missing student_id
2. linked raw/main pairs whose invariant metadata has drifted
3. metadata.chinese_variant set to invalid legacy value ``foundation`` (must be ``standard`` for Standard 华文)

Health checks (for large registry operations):

4. all registered rows point to an existing on-disk file
5. general-scope ``.../Book/<book name>/`` mains share one book file group and have non-empty ``metadata.unit``
6. all student-scope files have ``student_id``
7. all general-scope files have ``is_template=true``
8. all student-scope files have ``is_template=false``
9. any stored ``subject`` must be in the allowed enum set
10. any populated ``metadata.grade_or_scope`` must be in the allowed token set
11. raw/main relation graph is consistent (has_raw, reciprocal edges, and valid endpoint types)
12. template files are constrained to ``doc_type`` in ``exam``, ``exercise``, ``book``
13. ``file_relations`` rows whose ``source_id`` or ``target_id`` does not exist in ``pdf_files``
    (orphan edges — e.g. leftover template/completion links after rows were removed without CASCADE
    when SQLite ``PRAGMA foreign_keys`` was off)

Usage:
  python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity
  python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity --json
  python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity --db /path/to/pdf_registry.db
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

SCRIPT_DIR = Path(__file__).resolve().parent


INVARIANT_METADATA_KEYS = (
    "subject",
    "doc_type",
    "student_id",
    "is_template",
    "metadata.grade_or_scope",
    "metadata.content_folder",
    "metadata.chinese_variant",
)


def repo_root() -> Path:
    return SCRIPT_DIR.parent.parent.parent


def default_db_path() -> Path:
    return repo_root() / "ai_study_buddy" / "db" / "pdf_registry.db"


def collect_invalid_chinese_variant_foundation(mgr: PdfFileManager) -> list[dict]:
    """Rows where metadata.chinese_variant is the invalid legacy value ``foundation``."""
    conn = mgr._get_connection()
    rows = conn.execute(
        "SELECT id, path, file_type, metadata FROM pdf_files WHERE metadata IS NOT NULL"
    ).fetchall()
    bad: list[dict] = []
    for row in rows:
        try:
            m = json.loads(row["metadata"]) if row["metadata"] else {}
        except json.JSONDecodeError:
            continue
        if isinstance(m, dict) and m.get("chinese_variant") == "foundation":
            bad.append(
                {
                    "id": row["id"],
                    "path": row["path"],
                    "file_type": row["file_type"],
                }
            )
    return bad


def collect_invalid_subject_values(mgr: PdfFileManager) -> list[dict]:
    conn = mgr._get_connection()
    rows = conn.execute(
        """
        SELECT id, path, file_type, doc_type, subject
        FROM pdf_files
        WHERE subject IS NOT NULL
        ORDER BY path
        """
    ).fetchall()
    allowed = set(mgr._ALLOWED_SUBJECTS)
    bad: list[dict] = []
    for row in rows:
        if row["subject"] in allowed:
            continue
        bad.append(
            {
                "id": row["id"],
                "path": row["path"],
                "file_type": row["file_type"],
                "doc_type": row["doc_type"],
                "subject": row["subject"],
            }
        )
    return bad


def collect_invalid_grade_or_scope_values(mgr: PdfFileManager) -> list[dict]:
    conn = mgr._get_connection()
    rows = conn.execute(
        """
        SELECT id, path, file_type, doc_type, metadata
        FROM pdf_files
        WHERE metadata IS NOT NULL
        ORDER BY path
        """
    ).fetchall()
    allowed = set(mgr._GRADE_SCOPE_SEGMENTS)
    bad: list[dict] = []
    for row in rows:
        try:
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        except json.JSONDecodeError:
            continue
        if not isinstance(metadata, dict):
            continue
        grade = metadata.get("grade_or_scope")
        if grade is None:
            continue
        if isinstance(grade, str) and grade in allowed:
            continue
        bad.append(
            {
                "id": row["id"],
                "path": row["path"],
                "file_type": row["file_type"],
                "doc_type": row["doc_type"],
                "grade_or_scope": grade,
            }
        )
    return bad


def collect_template_invalid_doc_type(mgr: PdfFileManager) -> list[dict]:
    allowed_template_doc_types = {"exam", "exercise", "book"}
    bad: list[dict] = []
    for file in mgr.find_files(is_template=True):
        if file.doc_type in allowed_template_doc_types:
            continue
        bad.append(
            {
                "id": file.id,
                "path": file.path,
                "file_type": file.file_type,
                "doc_type": file.doc_type,
                "is_template": file.is_template,
            }
        )
    return bad


def collect_missing_student_id(mgr: PdfFileManager) -> list[dict]:
    items = []
    for f in mgr.find_files():
        inferred_student_id = mgr._infer_student_id_from_path(f.path)
        if inferred_student_id is not None and not f.student_id:
            items.append(
                {
                    "id": f.id,
                    "path": f.path,
                    "file_type": f.file_type,
                    "expected_student_id": inferred_student_id,
                }
            )
    return items


def _path_scope(mgr: PdfFileManager, file_path: str | Path) -> str | None:
    path = Path(file_path).resolve()
    if mgr._path_has_student_mirror_layout(path):
        return "student"
    if any(part in mgr._GRADE_SCOPE_SEGMENTS for part in path.parts):
        return "general"
    return None


def _infer_book_folder(path: str | Path) -> str | None:
    resolved = Path(path).resolve()
    parts = resolved.parts
    try:
        book_idx = parts.index("Book")
    except ValueError:
        return None
    if book_idx + 1 >= len(parts):
        return None
    return str(Path(*parts[: book_idx + 2]))


def collect_missing_on_disk_files(mgr: PdfFileManager) -> list[dict]:
    missing: list[dict] = []
    for file in mgr.find_files():
        if not Path(file.path).exists():
            missing.append(
                {
                    "id": file.id,
                    "path": file.path,
                    "file_type": file.file_type,
                    "doc_type": file.doc_type,
                }
            )
    return missing


def collect_student_scope_missing_student_id(mgr: PdfFileManager) -> list[dict]:
    items: list[dict] = []
    for file in mgr.find_files():
        if _path_scope(mgr, file.path) != "student":
            continue
        if file.student_id:
            continue
        items.append(
            {
                "id": file.id,
                "path": file.path,
                "file_type": file.file_type,
                "expected_student_id": mgr._infer_student_id_from_path(file.path),
            }
        )
    return items


def collect_general_scope_non_template(mgr: PdfFileManager) -> list[dict]:
    items: list[dict] = []
    for file in mgr.find_files():
        if _path_scope(mgr, file.path) != "general":
            continue
        if file.is_template:
            continue
        items.append(
            {
                "id": file.id,
                "path": file.path,
                "file_type": file.file_type,
                "is_template": file.is_template,
            }
        )
    return items


def collect_student_scope_template_true(mgr: PdfFileManager) -> list[dict]:
    items: list[dict] = []
    for file in mgr.find_files():
        if _path_scope(mgr, file.path) != "student":
            continue
        if not file.is_template:
            continue
        items.append(
            {
                "id": file.id,
                "path": file.path,
                "file_type": file.file_type,
                "is_template": file.is_template,
            }
        )
    return items


def collect_book_folder_group_unit_issues(mgr: PdfFileManager) -> list[dict]:
    conn = mgr._get_connection()
    group_rows = conn.execute(
        """
        SELECT fg.id AS group_id, fg.label AS group_label, fgm.file_id AS file_id
        FROM file_groups fg
        LEFT JOIN file_group_members fgm ON fgm.group_id = fg.id
        WHERE fg.group_type = 'book'
        """
    ).fetchall()
    file_to_book_group_ids: dict[str, set[str]] = {}
    label_to_book_group_ids: dict[str, set[str]] = {}
    for row in group_rows:
        group_id = row["group_id"]
        label = row["group_label"]
        label_to_book_group_ids.setdefault(label, set()).add(group_id)
        file_id = row["file_id"]
        if file_id:
            file_to_book_group_ids.setdefault(file_id, set()).add(group_id)

    files_by_book_folder: dict[str, list] = {}
    for file in mgr.find_files(doc_type="book", file_type="main", is_template=True):
        book_folder = _infer_book_folder(file.path)
        if book_folder is None:
            continue
        if _path_scope(mgr, file.path) != "general":
            continue
        files_by_book_folder.setdefault(book_folder, []).append(file)

    issues: list[dict] = []
    for book_folder, files in sorted(files_by_book_folder.items(), key=lambda item: item[0]):
        book_name = Path(book_folder).name
        expected_group_ids = label_to_book_group_ids.get(book_name, set())
        folder_issue_types: list[str] = []
        if not expected_group_ids:
            folder_issue_types.append("missing_book_group_for_folder_label")
        elif len(expected_group_ids) > 1:
            folder_issue_types.append("duplicate_book_groups_for_folder_label")

        file_checks: list[dict] = []
        shared_group_ids: set[str] = set()
        for file in files:
            metadata = file.metadata or {}
            unit_value = metadata.get("unit")
            group_ids = set(file_to_book_group_ids.get(file.id, set()))
            shared_group_ids.update(group_ids)
            file_issue_types: list[str] = []

            if not isinstance(unit_value, str) or not unit_value.strip():
                file_issue_types.append("missing_or_empty_metadata_unit")
            if not group_ids:
                file_issue_types.append("missing_book_group_membership")
            if len(group_ids) > 1:
                file_issue_types.append("multiple_book_group_memberships")
            if expected_group_ids and group_ids and not (group_ids & expected_group_ids):
                file_issue_types.append("book_group_label_mismatch")

            file_checks.append(
                {
                    "id": file.id,
                    "path": file.path,
                    "group_ids": sorted(group_ids),
                    "unit": unit_value,
                    "issues": file_issue_types,
                }
            )

        if len(shared_group_ids) > 1:
            folder_issue_types.append("files_do_not_share_one_book_group")
        if len(shared_group_ids) == 1 and expected_group_ids and not (shared_group_ids & expected_group_ids):
            folder_issue_types.append("folder_group_does_not_match_book_label_group")

        if folder_issue_types or any(item["issues"] for item in file_checks):
            issues.append(
                {
                    "book_folder": book_folder,
                    "book_name": book_name,
                    "folder_issues": folder_issue_types,
                    "files": file_checks,
                }
            )
    return issues


def collect_main_raw_metadata_drift(mgr: PdfFileManager) -> list[dict]:
    conn = mgr._get_connection()
    rows = conn.execute(
        """
        SELECT raw.id AS raw_id, raw.path AS raw_path, raw.file_type AS raw_file_type,
               raw.subject AS raw_subject, raw.doc_type AS raw_doc_type, raw.student_id AS raw_student_id,
               raw.is_template AS raw_is_template, raw.metadata AS raw_metadata,
               main.id AS main_id, main.path AS main_path, main.file_type AS main_file_type,
               main.subject AS main_subject, main.doc_type AS main_doc_type, main.student_id AS main_student_id,
               main.is_template AS main_is_template, main.metadata AS main_metadata
        FROM file_relations fr
        JOIN pdf_files raw ON raw.id = fr.source_id
        JOIN pdf_files main ON main.id = fr.target_id
        WHERE fr.relation_type = 'main_version'
          AND raw.file_type = 'raw'
          AND main.file_type = 'main'
        ORDER BY raw.path
        """
    ).fetchall()
    issues = []
    seen_raw_ids: set[str] = set()
    for row in rows:
        raw_id = row["raw_id"]
        if raw_id in seen_raw_ids:
            continue
        seen_raw_ids.add(raw_id)
        raw_meta = json.loads(row["raw_metadata"]) if row["raw_metadata"] else {}
        main_meta = json.loads(row["main_metadata"]) if row["main_metadata"] else {}
        field_diffs = []
        comparisons = {
            "subject": (row["raw_subject"], row["main_subject"]),
            "doc_type": (row["raw_doc_type"], row["main_doc_type"]),
            "student_id": (row["raw_student_id"], row["main_student_id"]),
            "is_template": (bool(row["raw_is_template"]), bool(row["main_is_template"])),
            "metadata.grade_or_scope": (raw_meta.get("grade_or_scope"), main_meta.get("grade_or_scope")),
            "metadata.content_folder": (raw_meta.get("content_folder"), main_meta.get("content_folder")),
            "metadata.chinese_variant": (raw_meta.get("chinese_variant"), main_meta.get("chinese_variant")),
        }
        for field, (raw_value, main_value) in comparisons.items():
            if raw_value != main_value:
                field_diffs.append(
                    {
                        "field": field,
                        "raw_value": raw_value,
                        "main_value": main_value,
                    }
                )
        if field_diffs:
            issues.append(
                {
                    "raw_id": row["raw_id"],
                    "raw_path": row["raw_path"],
                    "main_id": row["main_id"],
                    "main_path": row["main_path"],
                    "fields": field_diffs,
                }
            )
    return issues


def collect_dangling_file_relations(mgr: PdfFileManager) -> list[dict]:
    """Rows in file_relations referencing a deleted pdf_files id (FK drift).

    Normal deletes through PdfFileManager run with foreign_keys enabled so CASCADE
    removes these edges; raw SQL or tools that omit PRAGMA foreign_keys=ON can leave orphans.
    """
    conn = mgr._get_connection()
    rows = conn.execute(
        """
        SELECT r.id AS relation_id, r.relation_type, r.source_id, r.target_id,
               s.path AS source_path, t.path AS target_path
        FROM file_relations r
        LEFT JOIN pdf_files s ON s.id = r.source_id
        LEFT JOIN pdf_files t ON t.id = r.target_id
        WHERE s.id IS NULL OR t.id IS NULL
        ORDER BY r.relation_type, r.source_id, r.target_id
        """
    ).fetchall()
    items: list[dict] = []
    for row in rows:
        missing_source = row["source_path"] is None
        missing_target = row["target_path"] is None
        items.append(
            {
                "relation_id": row["relation_id"],
                "relation_type": row["relation_type"],
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "source_path": row["source_path"],
                "target_path": row["target_path"],
                "missing_source": missing_source,
                "missing_target": missing_target,
            }
        )
    return items


def collect_raw_main_relation_issues(mgr: PdfFileManager) -> list[dict]:
    conn = mgr._get_connection()
    rows = conn.execute(
        """
        SELECT id, path, file_type, has_raw
        FROM pdf_files
        ORDER BY path
        """
    ).fetchall()
    files_by_id: dict[str, dict] = {row["id"]: dict(row) for row in rows}

    rel_rows = conn.execute(
        """
        SELECT source_id, target_id, relation_type
        FROM file_relations
        WHERE relation_type IN ('raw_source', 'main_version')
        """
    ).fetchall()
    raw_source_edges = {(row["source_id"], row["target_id"]) for row in rel_rows if row["relation_type"] == "raw_source"}
    main_version_edges = {(row["source_id"], row["target_id"]) for row in rel_rows if row["relation_type"] == "main_version"}

    issues: list[dict] = []

    # main -> raw edge must point to main/raw and have reciprocal raw -> main edge
    for main_id, raw_id in sorted(raw_source_edges):
        main = files_by_id.get(main_id)
        raw = files_by_id.get(raw_id)
        if main is None or raw is None:
            issues.append(
                {
                    "issue": "raw_source_dangling_endpoint",
                    "main_id": main_id,
                    "raw_id": raw_id,
                }
            )
            continue
        if main["file_type"] != "main" or raw["file_type"] != "raw":
            issues.append(
                {
                    "issue": "raw_source_wrong_endpoint_types",
                    "main_id": main_id,
                    "main_path": main["path"],
                    "main_file_type": main["file_type"],
                    "raw_id": raw_id,
                    "raw_path": raw["path"],
                    "raw_file_type": raw["file_type"],
                }
            )
        if (raw_id, main_id) not in main_version_edges:
            issues.append(
                {
                    "issue": "missing_main_version_reciprocal",
                    "main_id": main_id,
                    "main_path": main["path"],
                    "raw_id": raw_id,
                    "raw_path": raw["path"],
                }
            )

    # raw -> main edge must point to raw/main and have reciprocal main -> raw edge
    for raw_id, main_id in sorted(main_version_edges):
        raw = files_by_id.get(raw_id)
        main = files_by_id.get(main_id)
        if raw is None or main is None:
            issues.append(
                {
                    "issue": "main_version_dangling_endpoint",
                    "raw_id": raw_id,
                    "main_id": main_id,
                }
            )
            continue
        if raw["file_type"] != "raw" or main["file_type"] != "main":
            issues.append(
                {
                    "issue": "main_version_wrong_endpoint_types",
                    "raw_id": raw_id,
                    "raw_path": raw["path"],
                    "raw_file_type": raw["file_type"],
                    "main_id": main_id,
                    "main_path": main["path"],
                    "main_file_type": main["file_type"],
                }
            )
        if (main_id, raw_id) not in raw_source_edges:
            issues.append(
                {
                    "issue": "missing_raw_source_reciprocal",
                    "raw_id": raw_id,
                    "raw_path": raw["path"],
                    "main_id": main_id,
                    "main_path": main["path"],
                }
            )

    # has_raw on main files should mirror raw_source existence
    main_ids_with_raw_source = {main_id for main_id, _raw_id in raw_source_edges}
    for row in rows:
        if row["file_type"] != "main":
            continue
        has_raw_expected = row["id"] in main_ids_with_raw_source
        has_raw_actual = bool(row["has_raw"])
        if has_raw_expected == has_raw_actual:
            continue
        issues.append(
            {
                "issue": "main_has_raw_mismatch",
                "id": row["id"],
                "path": row["path"],
                "has_raw": has_raw_actual,
                "expected_has_raw": has_raw_expected,
            }
        )

    return issues


def build_report(mgr: PdfFileManager) -> dict:
    missing_on_disk_files = collect_missing_on_disk_files(mgr)
    book_folder_group_unit_issues = collect_book_folder_group_unit_issues(mgr)
    student_scope_missing_student_id = collect_student_scope_missing_student_id(mgr)
    general_scope_non_template = collect_general_scope_non_template(mgr)
    student_scope_template_true = collect_student_scope_template_true(mgr)

    missing_student_id = collect_missing_student_id(mgr)
    main_raw_drift = collect_main_raw_metadata_drift(mgr)
    invalid_chinese_variant_foundation = collect_invalid_chinese_variant_foundation(mgr)
    invalid_subject_values = collect_invalid_subject_values(mgr)
    invalid_grade_or_scope_values = collect_invalid_grade_or_scope_values(mgr)
    raw_main_relation_issues = collect_raw_main_relation_issues(mgr)
    template_invalid_doc_type = collect_template_invalid_doc_type(mgr)
    dangling_file_relations = collect_dangling_file_relations(mgr)
    return {
        "db_path": str(Path(mgr.db_path).resolve()),
        "summary": {
            "missing_on_disk_files": len(missing_on_disk_files),
            "book_folder_group_unit_issues": len(book_folder_group_unit_issues),
            "student_scope_missing_student_id": len(student_scope_missing_student_id),
            "general_scope_non_template": len(general_scope_non_template),
            "student_scope_template_true": len(student_scope_template_true),
            "missing_student_id": len(missing_student_id),
            "main_raw_metadata_drift": len(main_raw_drift),
            "invalid_chinese_variant_foundation": len(invalid_chinese_variant_foundation),
            "invalid_subject_values": len(invalid_subject_values),
            "invalid_grade_or_scope_values": len(invalid_grade_or_scope_values),
            "raw_main_relation_issues": len(raw_main_relation_issues),
            "template_invalid_doc_type": len(template_invalid_doc_type),
            "dangling_file_relations": len(dangling_file_relations),
        },
        "checks": {
            "missing_on_disk_files": missing_on_disk_files,
            "book_folder_group_unit_issues": book_folder_group_unit_issues,
            "student_scope_missing_student_id": student_scope_missing_student_id,
            "general_scope_non_template": general_scope_non_template,
            "student_scope_template_true": student_scope_template_true,
            "missing_student_id": missing_student_id,
            "main_raw_metadata_drift": main_raw_drift,
            "invalid_chinese_variant_foundation": invalid_chinese_variant_foundation,
            "invalid_subject_values": invalid_subject_values,
            "invalid_grade_or_scope_values": invalid_grade_or_scope_values,
            "raw_main_relation_issues": raw_main_relation_issues,
            "template_invalid_doc_type": template_invalid_doc_type,
            "dangling_file_relations": dangling_file_relations,
        },
    }


def _print_human_report(report: dict, *, limit: int) -> None:
    print(f"DB: {report['db_path']}")
    print("Summary:")
    for key, value in report["summary"].items():
        print(f"- {key}: {value}")

    print("\nMissing on-disk files (registered path no longer exists):")
    for item in report["checks"]["missing_on_disk_files"][:limit]:
        print(f"- {item['path']} [{item['file_type']}/{item['doc_type']}] id={item['id']}")

    print("\nBook folder group + unit issues (general-scope book mains):")
    for item in report["checks"]["book_folder_group_unit_issues"][:limit]:
        print(f"- {item['book_folder']}")
        if item["folder_issues"]:
            print(f"  folder_issues={', '.join(item['folder_issues'])}")
        bad_files = [f for f in item["files"] if f["issues"]]
        if not bad_files:
            continue
        for file_item in bad_files[:limit]:
            print(f"  file={file_item['path']}")
            print(f"  issues={', '.join(file_item['issues'])}")

    print("\nStudent-scope files missing student_id:")
    for item in report["checks"]["student_scope_missing_student_id"][:limit]:
        print(f"- {item['path']} [{item['file_type']}] expected={item['expected_student_id']}")

    print("\nGeneral-scope files where is_template != true:")
    for item in report["checks"]["general_scope_non_template"][:limit]:
        print(f"- {item['path']} [{item['file_type']}] is_template={item['is_template']}")

    print("\nStudent-scope files where is_template != false:")
    for item in report["checks"]["student_scope_template_true"][:limit]:
        print(f"- {item['path']} [{item['file_type']}] is_template={item['is_template']}")

    print("\nMissing student_id:")
    for item in report["checks"]["missing_student_id"][:limit]:
        print(f"- {item['path']} [{item['file_type']}] expected={item['expected_student_id']}")

    print("\nMain/raw metadata drift:")
    for item in report["checks"]["main_raw_metadata_drift"][:limit]:
        field_names = ", ".join(diff["field"] for diff in item["fields"])
        print(f"- raw={item['raw_path']}")
        print(f"  main={item['main_path']}")
        print(f"  fields={field_names}")

    print("\nInvalid metadata.chinese_variant=foundation (use 'standard' for Standard 华文):")
    for item in report["checks"]["invalid_chinese_variant_foundation"][:limit]:
        print(f"- {item['path']} [{item['file_type']}] id={item['id']}")

    print("\nInvalid subject enum values:")
    for item in report["checks"]["invalid_subject_values"][:limit]:
        print(f"- {item['path']} [{item['file_type']}/{item['doc_type']}] subject={item['subject']!r}")

    print("\nInvalid metadata.grade_or_scope values:")
    for item in report["checks"]["invalid_grade_or_scope_values"][:limit]:
        print(
            f"- {item['path']} [{item['file_type']}/{item['doc_type']}] "
            f"grade_or_scope={item['grade_or_scope']!r}"
        )

    print("\nRaw/main relation consistency issues:")
    for item in report["checks"]["raw_main_relation_issues"][:limit]:
        issue = item.get("issue")
        if issue == "main_has_raw_mismatch":
            print(
                f"- {item['path']} [main] has_raw={item['has_raw']} "
                f"expected={item['expected_has_raw']}"
            )
        else:
            print(f"- {issue}: {item}")

    print("\nTemplate files with invalid doc_type (allowed: exam, exercise, book):")
    for item in report["checks"]["template_invalid_doc_type"][:limit]:
        print(f"- {item['path']} [{item['file_type']}/{item['doc_type']}] id={item['id']}")

    print("\nDangling file_relations (source or target id not in pdf_files):")
    for item in report["checks"]["dangling_file_relations"][:limit]:
        parts = []
        if item["missing_source"]:
            parts.append("missing_source")
        if item["missing_target"]:
            parts.append("missing_target")
        sp = item["source_path"] or "(no pdf_files row)"
        tp = item["target_path"] or "(no pdf_files row)"
        print(
            f"- {item['relation_type']} relation_id={item['relation_id']} "
            f"[{', '.join(parts)}]"
        )
        print(f"  source_id={item['source_id']} -> {sp}")
        print(f"  target_id={item['target_id']} -> {tp}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate common pdf_registry integrity issues.")
    parser.add_argument("--db", default=str(default_db_path()), help="Path to pdf_registry.db")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--limit", type=int, default=20, help="Max examples per section for human-readable output")
    args = parser.parse_args()

    mgr = PdfFileManager(db_path=args.db)
    report = build_report(mgr)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human_report(report, limit=max(args.limit, 0))

    return 1 if any(report["summary"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
