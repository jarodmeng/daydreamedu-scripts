# Testing — `ai_study_buddy.student_review`

## Current Status

- smoke validation is available through FastAPI `TestClient` at adapter layer
- focused amendment-flow tests exist in `ai_study_buddy/marking/tests/test_review_workspace_amendments.py`
- no dedicated automated unit-test suite for all services/repository modules yet

## 1) Quick Smoke

From repo root:

```bash
python3 - <<'PY'
from fastapi.testclient import TestClient
from ai_study_buddy.review_workspace.backend.app import app

client = TestClient(app)
assert client.get("/api/health").status_code == 200
students = client.get("/api/students").json().get("students", [])
assert isinstance(students, list)
if students:
    sid = students[0]["student_id"]
    attempts = client.get("/api/student/attempts", params={"student_id": sid}).json().get("items", [])
    assert isinstance(attempts, list)
    if attempts:
        aid = attempts[0]["attempt_id"]
        detail = client.get(f"/api/student/attempts/{aid}")
        assert detail.status_code == 200
        payload = detail.json()
        assert "review_state" in payload
        if payload.get("marking_status") == "marked":
            assert "marking_result_base" in payload
            assert "marking_result_resolved" in payload
            assert "amendment_state" in payload
print("student_review smoke ok")
PY
```

## 2) Compile Check

```bash
python3 -m py_compile ai_study_buddy/student_review/*.py
```

## 3) Recommended Automated Coverage

1. `attempt_service`: inclusion/exclusion rules and ordering
2. `detail_service`: marked vs unmarked detail shape behavior
3. `note_service`: enum validation and write-path guarantees
4. `amendment_service`: amendment validation, merge, and score recompute behavior
5. `repository`: review-state/amendment read-write roundtrip and default fallback behavior
