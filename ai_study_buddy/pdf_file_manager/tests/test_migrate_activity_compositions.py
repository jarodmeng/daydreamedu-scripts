import json
import subprocess
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

import pytest

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
from ai_study_buddy.pdf_file_manager.scripts import _migrate_activity_compositions_to_composition as mig


def test_is_composition_migration_candidate_requires_activity_and_d_root(tmp_path: Path):
    d_root = tmp_path / "DaydreamEdu"
    activity = (
        d_root
        / "completion/Singapore Primary English/student@example.com/P5/Activity/_c_Composition 1b.pdf"
    )
    activity.parent.mkdir(parents=True)
    activity.write_bytes(b"%PDF-1.4")
    book = (
        d_root
        / "completion/Singapore Primary English/student@example.com/PSLE/Book/Power Pack/c_PP English Situational Writing Practice 1.pdf"
    )
    book.parent.mkdir(parents=True)
    book.write_bytes(b"%PDF-1.4")

    assert mig.is_composition_migration_candidate(activity, d_root=d_root)
    assert not mig.is_composition_migration_candidate(book, d_root=d_root)


def test_plan_scan_root_updates_partial_vs_empty_leaf(tmp_path: Path):
    d_root = tmp_path / "DaydreamEdu"
    partial_activity = d_root / "completion/Singapore Primary English/student@example.com/P5/Activity"
    empty_activity = d_root / "completion/Singapore Primary Chinese/student@example.com/P3/Activity"
    partial_activity.mkdir(parents=True)
    empty_activity.mkdir(parents=True)

    comp_main = partial_activity / "_c_Composition 1b.pdf"
    comp_raw = partial_activity / "_raw_Composition 1b.pdf"
    other = partial_activity / "_c_Stellar Reading.pdf"
    only_main = empty_activity / "_c_三年级华文 期末考试 试卷一.pdf"
    only_raw = empty_activity / "_raw_三年级华文 期末考试 试卷一.pdf"
    for p in (comp_main, comp_raw, other, only_main, only_raw):
        p.write_bytes(b"%PDF-1.4")

    db_path = tmp_path / "registry.db"
    mgr = PdfFileManager(db_path=str(db_path))
    mgr.add_student("winston", "Winston", "student@example.com")
    mgr.add_scan_root(str(partial_activity), student_id="winston")
    mgr.add_scan_root(str(empty_activity), student_id="winston")

    move_rows = [
        {
            "old_path": str(comp_main),
            "new_path": str(mig.composition_target_path(comp_main)),
            "source_activity_dir": str(partial_activity),
            "target_composition_dir": str(mig.composition_target_dir(comp_main)),
        },
        {
            "old_path": str(comp_raw),
            "new_path": str(mig.composition_target_path(comp_raw)),
            "source_activity_dir": str(partial_activity),
            "target_composition_dir": str(mig.composition_target_dir(comp_raw)),
        },
        {
            "old_path": str(only_main),
            "new_path": str(mig.composition_target_path(only_main)),
            "source_activity_dir": str(empty_activity),
            "target_composition_dir": str(mig.composition_target_dir(only_main)),
        },
        {
            "old_path": str(only_raw),
            "new_path": str(mig.composition_target_path(only_raw)),
            "source_activity_dir": str(empty_activity),
            "target_composition_dir": str(mig.composition_target_dir(only_raw)),
        },
    ]

    actions, stats, dup = mig.plan_scan_root_updates(mgr, move_rows, d_root=d_root)
    assert dup == []
    assert stats["scan_root_activity_kept"] == 1
    assert stats["scan_root_remove_candidates"] == 1
    assert stats["scan_root_ensure_candidates"] == 2

    remove_paths = {a["path"] for a in actions if a["action"] == "remove_scan_root"}
    ensure_paths = {a["path"] for a in actions if a["action"] == "ensure_scan_root"}
    assert str(empty_activity.resolve()) in remove_paths
    assert str(partial_activity.resolve()) not in remove_paths
    assert str(mig.composition_target_dir(comp_main).resolve()) in ensure_paths


def test_migrate_script_execute_moves_files_and_updates_doc_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    d_root = tmp_path / "DaydreamEdu"
    activity = d_root / "completion/Singapore Primary English/student@example.com/P5/Activity"
    activity.mkdir(parents=True)
    comp_main = activity / "_c_Composition 1b.pdf"
    comp_raw = activity / "_raw_Composition 1b.pdf"
    other = activity / "_c_Stellar Reading.pdf"
    for p in (comp_main, comp_raw, other):
        p.write_bytes(b"%PDF-1.4")

    db_path = tmp_path / "registry.db"
    mgr = PdfFileManager(db_path=str(db_path))
    mgr.add_student("winston", "Winston", "student@example.com")
    mgr.add_scan_root(str(activity), student_id="winston")
    main_reg = mgr.register_file(comp_main, file_type="main", doc_type="activity", subject="english", student_id="winston")
    raw_reg = mgr.register_file(comp_raw, file_type="raw", doc_type="activity", subject="english", student_id="winston")
    mgr.register_file(other, file_type="main", doc_type="activity", subject="english", student_id="winston")

    monkeypatch.setattr(mig, "resolve_daydreamedu_root", lambda: d_root)
    monkeypatch.setattr(mig, "resolve_goodnotes_root", lambda: None)
    monkeypatch.setattr(mig, "PdfFileManager", lambda: mgr)

    dry = mig.run(Namespace(execute=False, preview_limit=50))
    assert dry["stats"]["file_candidates"] == 2
    assert dry["logical_items"] == 1

    result = mig.run(Namespace(execute=True, preview_limit=50))
    assert result["execute_result"]["files_moved"] == 2

    composition_dir = mig.composition_target_dir(comp_main)
    assert (composition_dir / comp_main.name).is_file()
    assert (composition_dir / comp_raw.name).is_file()
    assert (activity / other.name).is_file()
    assert not comp_main.is_file()

    refreshed_main = mgr.get_file(main_reg.id)
    refreshed_raw = mgr.get_file(raw_reg.id)
    assert refreshed_main is not None and refreshed_main.doc_type == "composition"
    assert refreshed_raw is not None and refreshed_raw.doc_type == "composition"
    assert (refreshed_main.metadata or {}).get("content_folder") == "Composition"

    scan_paths = {sr.path for sr in mgr.list_scan_roots()}
    assert str(activity.resolve()) in scan_paths
    assert str(composition_dir.resolve()) in scan_paths


def test_live_registry_dry_run_returns_zero_candidates_post_migration():
    """After proposal 18 migration (2026-05-30), no Activity-folder composition rows remain."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_study_buddy.pdf_file_manager.scripts._migrate_activity_compositions_to_composition",
            "--preview-limit",
            "5",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 and "DAYDREAMEDU_ROOT is not configured" in proc.stderr:
        pytest.skip("DAYDREAMEDU_ROOT is not configured")
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    report = json.loads(proc.stdout)
    assert report["mode"] == "dry_run"
    assert report.get("stats", {}).get("file_candidates", 0) == 0
    assert report["logical_items"] == 0
    assert report["file_moves_preview"] == []
