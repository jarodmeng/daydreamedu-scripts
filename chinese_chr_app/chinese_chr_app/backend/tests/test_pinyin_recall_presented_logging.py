#!/usr/bin/env python3
"""Regression coverage for serve-time priority metadata in item_presented logging."""

import importlib
import os
import sys
import types
from pathlib import Path


def test_log_pinyin_recall_event_persists_priority_metadata(monkeypatch):
    backend_dir = Path(__file__).parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example:example@example.com:5432/example")

    captured = []

    class _FakeConn:
        def close(self):
            return None

    fake_db_module = types.SimpleNamespace(
        _get_connection=lambda: _FakeConn(),
        insert_pinyin_recall_item_presented=lambda payload: captured.append(payload),
    )

    monkeypatch.setitem(sys.modules, "database", fake_db_module)
    monkeypatch.delitem(sys.modules, "app", raising=False)

    app = importlib.import_module("app")

    app._log_pinyin_recall_event(
        "item_presented",
        items=[
            {
                "unit_id": "乐|yue4",
                "character": "乐",
                "reading_key": "yue4",
                "reading_display": "yuè",
                "prompt_type": "hanzi_to_pinyin",
                "correct_pinyin": "yuè",
                "choices": ["yuè", "lè", "yào", "wěi"],
                "batch_category": "new",
                "from_user_priority": True,
                "priority_label": "第二学期听写",
                "priority_source": "p4_4a_dictation_2026_category_ii",
            }
        ],
        user_id="user-1",
        session_id="session-1",
        batch_id="batch-1",
        batch_mode="expansion",
    )

    assert len(captured) == 1
    payload = captured[0]
    assert payload["from_user_priority"] is True
    assert payload["priority_label"] == "第二学期听写"
    assert payload["priority_source"] == "p4_4a_dictation_2026_category_ii"
    assert payload["unit_id"] == "乐|yue4"
