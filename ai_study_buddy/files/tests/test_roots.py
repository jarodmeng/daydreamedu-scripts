"""Tests for ai_study_buddy.files.roots."""

from pathlib import Path

import ai_study_buddy.files.roots as roots_module


def test_resolve_daydreamedu_root_from_env(tmp_path, monkeypatch):
    d = tmp_path / "dd"
    d.mkdir()
    monkeypatch.setenv("DAYDREAMEDU_ROOT", str(d))
    assert roots_module.resolve_daydreamedu_root() == d.resolve()


def test_resolve_daydreamedu_root_env_overrides_file(tmp_path, monkeypatch):
    env_dir = tmp_path / "from_env"
    env_dir.mkdir()
    file_dir = tmp_path / "from_file"
    file_dir.mkdir()
    cfg = tmp_path / "local_daydreamedu_root.txt"
    cfg.write_text(str(file_dir), encoding="utf-8")
    monkeypatch.setattr(roots_module, "_LOCAL_DAYDREAMEDU_ROOT_FILE", cfg)
    monkeypatch.setenv("DAYDREAMEDU_ROOT", str(env_dir))
    assert roots_module.resolve_daydreamedu_root() == env_dir.resolve()


def test_resolve_daydreamedu_root_from_file(tmp_path, monkeypatch):
    d = tmp_path / "dd"
    d.mkdir()
    cfg = tmp_path / "local_daydreamedu_root.txt"
    cfg.write_text(f"# comment\n\n{d}\n", encoding="utf-8")
    monkeypatch.setattr(roots_module, "_LOCAL_DAYDREAMEDU_ROOT_FILE", cfg)
    monkeypatch.delenv("DAYDREAMEDU_ROOT", raising=False)
    assert roots_module.resolve_daydreamedu_root() == d.resolve()


def test_resolve_daydreamedu_root_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("DAYDREAMEDU_ROOT", raising=False)
    fake = Path("/nonexistent/local_daydreamedu_root_no_such_file_12345.txt")
    monkeypatch.setattr(roots_module, "_LOCAL_DAYDREAMEDU_ROOT_FILE", fake)
    assert roots_module.resolve_daydreamedu_root() is None


def test_resolve_goodnotes_root_from_env(tmp_path, monkeypatch):
    g = tmp_path / "GoodNotes"
    g.mkdir()
    monkeypatch.setenv("GOODNOTES_ROOT", str(g))
    monkeypatch.delenv("DAYDREAMEDU_ROOT", raising=False)
    assert roots_module.resolve_goodnotes_root() == g.resolve()


def test_resolve_goodnotes_root_env_overrides_file_and_sibling(tmp_path, monkeypatch):
    env_dir = tmp_path / "gn_from_env"
    env_dir.mkdir()
    file_dir = tmp_path / "gn_from_file"
    file_dir.mkdir()
    cfg = tmp_path / "local_goodnotes_root.txt"
    cfg.write_text(str(file_dir), encoding="utf-8")
    monkeypatch.setattr(roots_module, "_LOCAL_GOODNOTES_ROOT_FILE", cfg)
    monkeypatch.setenv("GOODNOTES_ROOT", str(env_dir))
    dd = tmp_path / "DaydreamEdu"
    dd.mkdir()
    sibling = tmp_path / "GoodNotes"
    sibling.mkdir()
    monkeypatch.setenv("DAYDREAMEDU_ROOT", str(dd))
    assert roots_module.resolve_goodnotes_root() == env_dir.resolve()


def test_resolve_goodnotes_root_from_file(tmp_path, monkeypatch):
    g = tmp_path / "GoodNotes"
    g.mkdir()
    cfg = tmp_path / "local_goodnotes_root.txt"
    cfg.write_text(f"# comment\n\n{g}\n", encoding="utf-8")
    monkeypatch.setattr(roots_module, "_LOCAL_GOODNOTES_ROOT_FILE", cfg)
    monkeypatch.delenv("GOODNOTES_ROOT", raising=False)
    monkeypatch.delenv("DAYDREAMEDU_ROOT", raising=False)
    assert roots_module.resolve_goodnotes_root() == g.resolve()


def test_resolve_goodnotes_root_sibling_of_daydreamedu(tmp_path, monkeypatch):
    dd = tmp_path / "DaydreamEdu"
    dd.mkdir()
    gn = tmp_path / "GoodNotes"
    gn.mkdir()
    monkeypatch.setenv("DAYDREAMEDU_ROOT", str(dd))
    monkeypatch.delenv("GOODNOTES_ROOT", raising=False)
    fake_cfg = Path("/nonexistent/local_goodnotes_root_no_such_file_67890.txt")
    monkeypatch.setattr(roots_module, "_LOCAL_GOODNOTES_ROOT_FILE", fake_cfg)
    assert roots_module.resolve_goodnotes_root() == gn.resolve()


def test_resolve_goodnotes_root_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("GOODNOTES_ROOT", raising=False)
    monkeypatch.delenv("DAYDREAMEDU_ROOT", raising=False)
    fake_gn = Path("/nonexistent/local_goodnotes_root_no_such_file_67890.txt")
    monkeypatch.setattr(roots_module, "_LOCAL_GOODNOTES_ROOT_FILE", fake_gn)
    fake_dd = Path("/nonexistent/local_daydreamedu_root_no_such_file_12345.txt")
    monkeypatch.setattr(roots_module, "_LOCAL_DAYDREAMEDU_ROOT_FILE", fake_dd)
    assert roots_module.resolve_goodnotes_root() is None


def test_resolve_goodnotes_root_none_when_sibling_missing(monkeypatch, tmp_path):
    dd = tmp_path / "DaydreamEdu"
    dd.mkdir()
    monkeypatch.setenv("DAYDREAMEDU_ROOT", str(dd))
    monkeypatch.delenv("GOODNOTES_ROOT", raising=False)
    fake_gn = Path("/nonexistent/local_goodnotes_root_no_such_file_67890.txt")
    monkeypatch.setattr(roots_module, "_LOCAL_GOODNOTES_ROOT_FILE", fake_gn)
    assert roots_module.resolve_goodnotes_root() is None
