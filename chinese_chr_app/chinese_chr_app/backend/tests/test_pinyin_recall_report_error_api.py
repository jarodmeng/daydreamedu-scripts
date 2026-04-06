#!/usr/bin/env python3
"""Focused API checks for report-error global disable behavior."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ["IMPORT_SMOKE_TEST"] = "1"

sys.path.insert(0, str(Path(__file__).parent.parent))

import app as app_module


def test_report_error_real_user_disables_unit_globally(monkeypatch):
    app_module.app.config["TESTING"] = True

    monkeypatch.setattr(
        app_module,
        "_get_profile_user",
        lambda: SimpleNamespace(user_id="real-user", user_metadata=None),
    )
    monkeypatch.setattr(app_module, "_get_pinyin_recall_dev_user", lambda: None)

    calls = {"report": None, "disable": None}

    def _insert_report_error(**kwargs):
        calls["report"] = kwargs
        return "report-1"

    def _disable_unit(**kwargs):
        calls["disable"] = kwargs

    fake_db = SimpleNamespace(
        insert_pinyin_recall_report_error=_insert_report_error,
        disable_pinyin_recall_unit_globally=_disable_unit,
    )
    monkeypatch.setitem(sys.modules, "database", fake_db)

    client = app_module.app.test_client()
    response = client.post(
        "/api/games/pinyin-recall/report-error",
        json={
            "session_id": "session-1",
            "batch_id": "batch-1",
            "unit_id": "行|hang2",
            "character": "行",
            "page": "wrong",
        },
        headers={"Authorization": "Bearer real-token"},
    )

    assert response.status_code == 200
    assert calls["report"] == {
        "user_id": "real-user",
        "session_id": "session-1",
        "batch_id": "batch-1",
        "unit_id": "行|hang2",
        "character": "行",
        "page": "wrong",
    }
    assert calls["disable"] == {
        "unit_id": "行|hang2",
        "character": "行",
        "disabled_by_user_id": "real-user",
        "triggering_report_error_id": "report-1",
    }


def test_report_error_dev_user_logs_only_without_global_disable(monkeypatch):
    app_module.app.config["TESTING"] = True

    monkeypatch.setattr(app_module, "_get_profile_user", lambda: None)
    monkeypatch.setattr(
        app_module,
        "_get_pinyin_recall_dev_user",
        lambda: SimpleNamespace(user_id="e2e-dev", user_metadata=None),
    )

    calls = {"report": None, "disable_count": 0}

    def _insert_report_error(**kwargs):
        calls["report"] = kwargs
        return "report-2"

    def _disable_unit(**kwargs):
        calls["disable_count"] += 1

    fake_db = SimpleNamespace(
        insert_pinyin_recall_report_error=_insert_report_error,
        disable_pinyin_recall_unit_globally=_disable_unit,
    )
    monkeypatch.setitem(sys.modules, "database", fake_db)

    client = app_module.app.test_client()
    response = client.post(
        "/api/games/pinyin-recall/report-error",
        json={
            "session_id": "session-2",
            "batch_id": "batch-2",
            "unit_id": "行|hang2",
            "character": "行",
            "page": "wrong",
        },
        headers={"Authorization": "Bearer fake-e2e-token"},
    )

    assert response.status_code == 200
    assert calls["report"] == {
        "user_id": "e2e-dev",
        "session_id": "session-2",
        "batch_id": "batch-2",
        "unit_id": "行|hang2",
        "character": "行",
        "page": "wrong",
    }
    assert calls["disable_count"] == 0


def test_report_error_real_user_without_unit_id_logs_only(monkeypatch):
    app_module.app.config["TESTING"] = True

    monkeypatch.setattr(
        app_module,
        "_get_profile_user",
        lambda: SimpleNamespace(user_id="real-user", user_metadata=None),
    )
    monkeypatch.setattr(app_module, "_get_pinyin_recall_dev_user", lambda: None)

    calls = {"report": None, "disable_count": 0}

    def _insert_report_error(**kwargs):
        calls["report"] = kwargs
        return "report-3"

    def _disable_unit(**kwargs):
        calls["disable_count"] += 1

    fake_db = SimpleNamespace(
        insert_pinyin_recall_report_error=_insert_report_error,
        disable_pinyin_recall_unit_globally=_disable_unit,
    )
    monkeypatch.setitem(sys.modules, "database", fake_db)

    client = app_module.app.test_client()
    response = client.post(
        "/api/games/pinyin-recall/report-error",
        json={
            "session_id": "session-3",
            "character": "行",
            "page": "question",
        },
        headers={"Authorization": "Bearer real-token"},
    )

    assert response.status_code == 200
    assert calls["report"] == {
        "user_id": "real-user",
        "session_id": "session-3",
        "batch_id": None,
        "unit_id": None,
        "character": "行",
        "page": "question",
    }
    assert calls["disable_count"] == 0
