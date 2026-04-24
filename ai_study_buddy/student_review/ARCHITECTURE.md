# Student Review Architecture

Status: active module baseline.

Version baseline: `v0.1.0`.

## 1) Purpose

`student_review` is the domain layer for:

- student-scoped attempt discovery
- marking-result selection for one attempt
- review-state read/write

It is app-surface agnostic and currently consumed by `review_workspace`.

## 2) Module Boundaries

Owns:

- API-oriented payload shaping for student review flows
- companion review-state persistence
- deterministic attempt ordering and latest-artifact selection usage

Does not own:

- canonical marking schema/writer (`ai_study_buddy/marking`)
- registry internals (`ai_study_buddy/pdf_file_manager`)
- frontend rendering (`ai_study_buddy/review_workspace/frontend`)

## 3) Runtime Dependencies

- `PdfFileManager` for students and completion files
- `find_marking_artifacts_for_attempt(...)` for artifact lookup
- `ai_study_buddy/context/**` for marking artifacts and review-state files

## 4) Internal Split

- `models.py`: shared normalization helpers and defaults
- `repository.py`: file-system persistence for review-state artifacts
- `attempt_service.py`: student + attempts index shaping
- `detail_service.py`: one-attempt detail response shaping
- `note_service.py`: review-state validation and writes
- `api_routes.py`: FastAPI routes using the services

## 5) Current Constraints

- no auth boundary enforcement at this layer
- no pagination on attempt listing
- no optimistic locking / concurrency control for write conflicts
- no schema migration engine for review-state artifacts

