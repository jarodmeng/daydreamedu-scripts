from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_study_buddy.buddy_console.backend import goodnotes_airdrop
from ai_study_buddy.buddy_console.backend.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_airdrop_share_link_launches_helper(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    helper = tmp_path / "_airdrop_share_link"
    helper.write_text("#!/bin/bash\n", encoding="utf-8")
    helper.chmod(0o755)
    monkeypatch.setattr(goodnotes_airdrop, "_airdrop_helper_path", lambda: helper)

    launched: list[list[str]] = []

    def _fake_popen(cmd, **kwargs):
        launched.append(cmd)

        class _Proc:
            pass

        return _Proc()

    monkeypatch.setattr(goodnotes_airdrop.subprocess, "Popen", _fake_popen)

    url = "https://share.goodnotes.com/s/Amwv4ubzFA1GGgvqwo83b7"
    response = client.post("/api/goodnotes/airdrop-share-link", json={"url": url})

    assert response.status_code == 200
    assert response.json() == {"status": "launched"}
    assert launched == [[str(helper), url]]


def test_airdrop_share_link_rejects_invalid_url(client: TestClient) -> None:
    response = client.post("/api/goodnotes/airdrop-share-link", json={"url": "https://example.com/not-goodnotes"})
    assert response.status_code == 400


def test_airdrop_share_link_503_when_helper_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setattr(goodnotes_airdrop, "_airdrop_helper_path", lambda: missing)

    response = client.post(
        "/api/goodnotes/airdrop-share-link",
        json={"url": "https://share.goodnotes.com/s/Amwv4ubzFA1GGgvqwo83b7"},
    )
    assert response.status_code == 503
