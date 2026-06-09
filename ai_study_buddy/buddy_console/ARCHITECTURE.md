# Buddy Console Architecture

This document describes the current architecture of `ai_study_buddy/buddy_console/`.

See also:

- [README.md](./README.md)
- [SPEC.md](./SPEC.md)
- [DATA_MODEL.md](./DATA_MODEL.md)
- [TESTING.md](./TESTING.md)

## Scope

`buddy_console` is the unified operator-facing app for:

1. browsing completion inventory
2. opening PDFs from controlled roots
3. reviewing marked attempts

It is not yet a full rewrite of every underlying feature, but it is the new app
surface that should eventually reach parity with the legacy apps.

## Runtime Shape

The app runs as:

1. FastAPI backend on `:8010`
2. React + Vite frontend on `:5178`

The frontend chooses one of three route surfaces:

1. `inventory`
2. `pdf`
3. `review`

## Backend Responsibilities

Backend entrypoint:

- [backend/app.py](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/buddy_console/backend/app.py)

Current backend responsibilities:

1. mount inventory and PDF routes from `backend/inventory_api.py`
2. include seeded review routes from `ai_study_buddy.marking.review.api_routes`
3. mount `review-workspace-static` assets from `ai_study_buddy/context/**`

Current backend composition:

1. `inventory_api.py`
   - `/api/config`
   - `/api/inventory`
   - `/api/pdf`
   - `/api/pdf-browser/config`
   - `/api/pdf-browser/list`
2. `marking.review.api_routes`
   - seeded review workspace backend contract

## Frontend Responsibilities

Frontend entrypoint:

- [frontend/src/main.tsx](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/buddy_console/frontend/src/main.tsx)

Current frontend modules:

1. [frontend/src/InventoryApp.tsx](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/buddy_console/frontend/src/InventoryApp.tsx)
   - inventory hub
   - filter state
   - card actions
   - new-tab deep links to PDF and review
2. [frontend/src/PdfApp.tsx](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/buddy_console/frontend/src/PdfApp.tsx)
   - root-style PDF browser
   - tree navigation
   - bookmark state
   - raw-file toggle
   - deep-linked PDF open
3. [frontend/src/App.tsx](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/ai_study_buddy/buddy_console/frontend/src/App.tsx)
   - seeded review UI from `review_workspace`

## Data Ownership

Owned here:

1. inventory/PDF browser shell behavior
2. unified route selection and deep-link handling
3. `buddy_console` visual integration

Owned outside this package:

1. registry-backed PDF and student metadata in `PdfFileManager`
2. canonical marking/review domain logic in `ai_study_buddy.marking.review`
3. context assets and persisted review/amendment artifacts under `ai_study_buddy/context/**`

## Current Constraints

1. review is still seeded from the copied `review_workspace` frontend/backend flow
2. inventory and PDF parity are in progress rather than complete

## Intended Direction

Near-term architecture direction:

1. keep `buddy_console` as the single app identity
2. preserve deep-link workflow from inventory to PDF/review
3. continue reducing behavioral gaps with the legacy apps
4. progressively replace legacy-seeded assumptions with `buddy_console`-native ones
5. do **not** mirror new Review Workspace frontend features into `review_workspace` (API changes in `marking.review` are shared; UI ships in `buddy_console` only)
