# Students and scan roots (config). See TESTING.md § Phase 2 (students, scan roots).

import tempfile
from pathlib import Path

import pytest

import ai_study_buddy.pdf_file_manager.pdf_file_manager as pfm_module
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def test_add_student_then_list_students():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        s = mgr.add_student("w", "Test Student", email="w@x.com")
        assert s.id == "w" and s.name == "Test Student" and s.email == "w@x.com"
        lst = mgr.list_students()
        assert len(lst) == 1
        assert lst[0].id == "w" and lst[0].email == "w@x.com"
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_list_students_empty_at_first():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        assert mgr.list_students() == []
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_add_scan_root_then_list_scan_roots():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        r = mgr.add_scan_root("/tmp/foo", student_id="w")
        roots = mgr.list_scan_roots()
        assert len(roots) == 1
        assert roots[0].path.endswith("foo") or "foo" in roots[0].path
        assert roots[0].student_id == "w"
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_remove_scan_root():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr.add_scan_root("/tmp/foo", student_id="w")
        mgr.remove_scan_root("/tmp/foo")
        assert mgr.list_scan_roots() == []
    finally:
        Path(tmp).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# ensure_student / ensure_scan_root (Proposal 1)
# ---------------------------------------------------------------------------

def test_ensure_student_creates_when_missing():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        s = mgr.ensure_student("w", "Test Student", email="w@x.com")
        assert s.id == "w" and s.name == "Test Student" and s.email == "w@x.com"
        assert mgr.get_student("w") is not None
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_ensure_student_idempotent_returns_existing():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr.add_student("w", "Test Student", email="w@x.com")
        s = mgr.ensure_student("w", "Other", email="other@x.com")
        assert s.id == "w" and s.name == "Test Student" and s.email == "w@x.com"
        assert len(mgr.list_students()) == 1
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_ensure_scan_root_creates_when_missing():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        r = mgr.ensure_scan_root("/tmp/foo", student_id="w")
        assert r.path.endswith("foo") or "foo" in r.path
        assert r.student_id == "w"
        assert len(mgr.list_scan_roots()) == 1
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_ensure_scan_root_idempotent_returns_existing():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr.add_scan_root("/tmp/foo", student_id="w")
        r = mgr.ensure_scan_root("/tmp/foo", student_id=None)
        assert r.path.endswith("foo") or "foo" in r.path
        assert r.student_id == "w"  # unchanged
        assert len(mgr.list_scan_roots()) == 1
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_add_scan_root_infers_student_id_from_path_when_omitted():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr.add_student("winston", "Winston", email="winston.ry.meng@gmail.com")
        r = mgr.add_scan_root(
            "/tmp/DaydreamEdu/Singapore Primary English/winston.ry.meng@gmail.com/P6/Exam"
        )
        assert r.student_id == "winston"
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_add_scan_root_keeps_explicit_student_id_over_inference():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr.add_student("winston", "Winston", email="winston.ry.meng@gmail.com")
        r = mgr.add_scan_root(
            "/tmp/DaydreamEdu/Singapore Primary English/winston.ry.meng@gmail.com/P6/Exam",
            student_id="manual",
        )
        assert r.student_id == "manual"
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_add_scan_root_without_student_email_keeps_none():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        r = mgr.add_scan_root("/tmp/DaydreamEdu/Singapore Primary English/P6/Exam")
        assert r.student_id is None
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_ensure_scan_root_infers_student_id_when_creating():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        mgr = PdfFileManager(db_path=tmp)
        mgr.add_student("emma", "Emma", email="emma.rs.meng@gmail.com")
        r = mgr.ensure_scan_root(
            "/tmp/GoodNotes/Singapore Primary Science/emma.rs.meng@gmail.com/P4/Exam"
        )
        assert r.student_id == "emma"
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_resolve_daydreamedu_root_from_env(tmp_path, monkeypatch):
    d = tmp_path / "dd"
    d.mkdir()
    monkeypatch.setenv("DAYDREAMEDU_ROOT", str(d))
    assert pfm_module.resolve_daydreamedu_root() == d.resolve()


def test_resolve_daydreamedu_root_env_overrides_file(tmp_path, monkeypatch):
    env_dir = tmp_path / "from_env"
    env_dir.mkdir()
    file_dir = tmp_path / "from_file"
    file_dir.mkdir()
    cfg = tmp_path / "local_daydreamedu_root.txt"
    cfg.write_text(str(file_dir), encoding="utf-8")
    monkeypatch.setattr(pfm_module, "_LOCAL_DAYDREAMEDU_ROOT_FILE", cfg)
    monkeypatch.setenv("DAYDREAMEDU_ROOT", str(env_dir))
    assert pfm_module.resolve_daydreamedu_root() == env_dir.resolve()


def test_resolve_daydreamedu_root_from_file(tmp_path, monkeypatch):
    d = tmp_path / "dd"
    d.mkdir()
    cfg = tmp_path / "local_daydreamedu_root.txt"
    cfg.write_text(f"# comment\n\n{d}\n", encoding="utf-8")
    monkeypatch.setattr(pfm_module, "_LOCAL_DAYDREAMEDU_ROOT_FILE", cfg)
    monkeypatch.delenv("DAYDREAMEDU_ROOT", raising=False)
    assert pfm_module.resolve_daydreamedu_root() == d.resolve()


def test_resolve_daydreamedu_root_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("DAYDREAMEDU_ROOT", raising=False)
    fake = Path("/nonexistent/local_daydreamedu_root_no_such_file_12345.txt")
    monkeypatch.setattr(pfm_module, "_LOCAL_DAYDREAMEDU_ROOT_FILE", fake)
    assert pfm_module.resolve_daydreamedu_root() is None


# ---------------------------------------------------------------------------
# resolve_goodnotes_root
# ---------------------------------------------------------------------------


def test_resolve_goodnotes_root_from_env(tmp_path, monkeypatch):
    g = tmp_path / "GoodNotes"
    g.mkdir()
    monkeypatch.setenv("GOODNOTES_ROOT", str(g))
    monkeypatch.delenv("DAYDREAMEDU_ROOT", raising=False)
    assert pfm_module.resolve_goodnotes_root() == g.resolve()


def test_resolve_goodnotes_root_env_overrides_file_and_sibling(tmp_path, monkeypatch):
    env_dir = tmp_path / "gn_from_env"
    env_dir.mkdir()
    file_dir = tmp_path / "gn_from_file"
    file_dir.mkdir()
    cfg = tmp_path / "local_goodnotes_root.txt"
    cfg.write_text(str(file_dir), encoding="utf-8")
    monkeypatch.setattr(pfm_module, "_LOCAL_GOODNOTES_ROOT_FILE", cfg)
    monkeypatch.setenv("GOODNOTES_ROOT", str(env_dir))
    # Even with DaydreamEdu + sibling GoodNotes, env wins
    dd = tmp_path / "DaydreamEdu"
    dd.mkdir()
    sibling = tmp_path / "GoodNotes"
    sibling.mkdir()
    monkeypatch.setenv("DAYDREAMEDU_ROOT", str(dd))
    assert pfm_module.resolve_goodnotes_root() == env_dir.resolve()


def test_resolve_goodnotes_root_from_file(tmp_path, monkeypatch):
    g = tmp_path / "GoodNotes"
    g.mkdir()
    cfg = tmp_path / "local_goodnotes_root.txt"
    cfg.write_text(f"# comment\n\n{g}\n", encoding="utf-8")
    monkeypatch.setattr(pfm_module, "_LOCAL_GOODNOTES_ROOT_FILE", cfg)
    monkeypatch.delenv("GOODNOTES_ROOT", raising=False)
    monkeypatch.delenv("DAYDREAMEDU_ROOT", raising=False)
    assert pfm_module.resolve_goodnotes_root() == g.resolve()


def test_resolve_goodnotes_root_sibling_of_daydreamedu(tmp_path, monkeypatch):
    dd = tmp_path / "DaydreamEdu"
    dd.mkdir()
    gn = tmp_path / "GoodNotes"
    gn.mkdir()
    monkeypatch.setenv("DAYDREAMEDU_ROOT", str(dd))
    monkeypatch.delenv("GOODNOTES_ROOT", raising=False)
    fake_cfg = Path("/nonexistent/local_goodnotes_root_no_such_file_67890.txt")
    monkeypatch.setattr(pfm_module, "_LOCAL_GOODNOTES_ROOT_FILE", fake_cfg)
    assert pfm_module.resolve_goodnotes_root() == gn.resolve()


def test_resolve_goodnotes_root_none_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv("GOODNOTES_ROOT", raising=False)
    monkeypatch.delenv("DAYDREAMEDU_ROOT", raising=False)
    fake_gn = Path("/nonexistent/local_goodnotes_root_no_such_file_67890.txt")
    monkeypatch.setattr(pfm_module, "_LOCAL_GOODNOTES_ROOT_FILE", fake_gn)
    fake_dd = Path("/nonexistent/local_daydreamedu_root_no_such_file_12345.txt")
    monkeypatch.setattr(pfm_module, "_LOCAL_DAYDREAMEDU_ROOT_FILE", fake_dd)
    assert pfm_module.resolve_goodnotes_root() is None


def test_resolve_goodnotes_root_none_when_sibling_missing(monkeypatch, tmp_path):
    dd = tmp_path / "DaydreamEdu"
    dd.mkdir()
    monkeypatch.setenv("DAYDREAMEDU_ROOT", str(dd))
    monkeypatch.delenv("GOODNOTES_ROOT", raising=False)
    fake_gn = Path("/nonexistent/local_goodnotes_root_no_such_file_67890.txt")
    monkeypatch.setattr(pfm_module, "_LOCAL_GOODNOTES_ROOT_FILE", fake_gn)
    assert pfm_module.resolve_goodnotes_root() is None
