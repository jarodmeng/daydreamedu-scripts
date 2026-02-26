# Testing Philosophy

This document explains the testing approach for the Chinese character app so future contributors (including AI agents) can make consistent choices.

## Goals

We optimize for:

- High confidence in core user flows
- Fast feedback during development
- Deterministic tests with low flake rate
- Clear separation between frontend regressions and backend/integration issues

## What We Measure

Test count is not the same as confidence.

When evaluating coverage, consider three layers:

- Route/Page coverage: did we exercise each user-visible route?
- Behavior coverage: did we exercise happy paths and important edge/error branches?
- Integration coverage: did we verify real auth/backend/external services work together?

The Playwright suite is primarily for behavior and integration confidence, not code coverage percentages.

## Test Mix (Recommended)

Use a mixed strategy:

- Real E2E smoke tests (backend + frontend running): verify core flows still work end-to-end
- Mocked E2E tests (Playwright `page.route(...)`): verify frontend error states, rare branches, and hard-to-reproduce conditions

Do not force every Playwright test to hit the real backend. That increases flakiness and makes it hard to cover failure branches.

## When To Mock vs Use Real Backend

Use real backend for:

- Core happy paths users rely on daily
- Cross-page flows where backend state changes matter (for example, play game then view profile)
- Regression checks for routing/proxy wiring

Use API mocks for:

- Error states (`401`, `500`, invalid payloads, empty states)
- Rare branches (for example, game submit failure, no data, invalid category)
- Deterministic data needed for assertions
- Tests that would otherwise depend on specific DB seed data

Rule of thumb:

- If the goal is "frontend renders the right UI for response X", mock it.
- If the goal is "the full stack wiring works", use the real backend.

## Current App-Specific Constraints

- The suite runs with `VITE_E2E_AUTH_BYPASS=1` by default in Playwright config.
- This is intentional for stable testing of auth-gated UI without real Google/Supabase login.
- Real auth smoke tests can be added separately when secrets/environment are available.

## Stability Guidelines

- Prefer assertions on user-visible text/roles over implementation details.
- Use `data-testid` only for elements that are hard to target semantically.
- Mock only the endpoints needed for the scenario.
- Keep mocked payloads minimal but valid for the UI branch being tested.
- Avoid long sleep/timeouts; wait on visible UI states instead.
- Keep one test focused on one behavior branch, even if it spans multiple UI steps.

## Playwright Patterns We Use

- `page.route(...)` to intercept API calls and return deterministic responses
- Route handlers that branch by pathname/query to support multiple scenarios in one test
- Existing fixtures for stroke animation data (`e2e/fixtures/hanzi-writer`)

## Coverage Priorities (Ongoing)

Prioritize new tests in this order:

1. Untested routes/pages
2. Error/loading/retry states on core pages
3. Stateful game logic branches
4. Profile and progress edge cases
5. Real-auth / production-like integration smoke tests

## For AI Agents

Before adding tests:

- Check whether the target behavior is already covered by route-level smoke tests
- Decide whether the test intent is behavior vs integration
- Prefer mocks for deterministic branch coverage
- Keep the suite readable: colocate tests by feature (`profile`, `pinyin-recall`, `search`, etc.)

When proposing coverage estimates, report:

- Route coverage estimate
- Behavior depth estimate
- Integration confidence estimate

