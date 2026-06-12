# Pulsechecks Production Hardening Plan

> **For Hermes:** implement this plan task-by-task with subagents, then verify in Docker and re-review the final diff.

**Goal:** Fix the remaining production-readiness issues in `pulsechecks`, with tests that prove each fix and a final containerized verification pass.

**Architecture:** Keep the current FastAPI/React structure. Focus on fail-closed auth, SSRF hardening, cleanup of duplicated backend handlers, and safer frontend OAuth callback handling. Keep the Docker test harness as the source of truth.

**Tech Stack:** FastAPI, pytest, Vitest, Docker Compose, React, Cognito/Firebase auth helpers.

---

## Task 1: Enforce API token expiry and auth fail-closed behavior

**Objective:** Reject expired API tokens during auth lookup and ensure token lookup failures never authenticate a user.

**Files:**
- Modify: `backend/app/dependencies.py`
- Modify/add tests: `backend/tests/test_api.py` (or the closest auth/token test file already used in the repo)

**Requirements:**
- When a `pc_...` API token is looked up, check `expires_at` before returning `CurrentUser`.
- If `expires_at` exists and is in the past, raise `UnauthorizedError("Invalid API token")` or equivalent fail-closed auth failure.
- If the token document is malformed or lookup/update fails, auth must still fail closed.
- Preserve best-effort `last_used_at` tracking, but do not let tracking failures break auth.

**Tests to add:**
- valid token authenticates
- expired token is rejected
- malformed/invalid `expires_at` is rejected
- lookup failure still returns unauthorized, not a crash

**Verification:**
- `docker compose -f docker-compose.test.yml run --rm backend-tests pytest -q tests/test_api.py`

---

## Task 2: Remove duplicate Lambda handler and tighten backend security surface

**Objective:** Clean up the duplicated handler definition and reduce obvious production security footguns in backend middleware.

**Files:**
- Modify: `backend/app/handlers.py`
- Modify: `backend/app/main.py`
- Modify/add tests: `backend/tests/test_internal_endpoints.py` and/or a new backend security test file if needed

**Requirements:**
- Keep only one `late_detector_handler` definition in `backend/app/handlers.py`.
- Make `late_detector_handler` export cleanly with `__all__`.
- Replace `allow_headers=["*"]` in `backend/app/main.py` with an explicit allowlist of headers actually used by the frontend/auth flow.
- Add baseline security headers in FastAPI middleware if the repo already has a clear place for them (at minimum `X-Content-Type-Options: nosniff`; more if low-risk and already supported by the app design).
- Do not break existing CORS/auth behavior.

**Tests to add:**
- a regression test proving the handler symbol is unique or that the intended exported handler works
- a test for the CORS/header behavior if practical in the current test suite

**Verification:**
- `docker compose -f docker-compose.test.yml run --rm backend-tests pytest -q`

---

## Task 3: Harden SSRF handling for outbound webhook delivery

**Objective:** Reduce SSRF DNS-rebinding risk and keep webhook validation fail-closed.

**Files:**
- Modify: `backend/app/security/ssrf.py`
- Modify: `backend/app/integrations/mattermost.py` (if needed to re-check safety immediately before outbound webhook send)
- Modify/add tests: `backend/tests/test_ssrf_protection.py`, `backend/tests/test_mattermost.py`

**Requirements:**
- Keep URL validation fail-closed on DNS/hostname resolution errors.
- Ensure outbound webhook delivery re-validates safety as close as practical to the actual request.
- If the implementation cannot fully eliminate TOCTOU with the current webhook approach, at least reduce the attack window and fail closed on any validation ambiguity.
- No unsafe fallback to permissive behavior.

**Tests to add:**
- safe external URL passes
- blocked/private hostnames/IPs fail
- DNS resolution failure fails
- webhook send path refuses unsafe URL even if validation helper is bypassed earlier

**Verification:**
- `docker compose -f docker-compose.test.yml run --rm backend-tests pytest -q tests/test_ssrf_protection.py tests/test_mattermost.py`

---

## Task 4: Fix frontend OAuth callback fail-closed behavior

**Objective:** Remove the silent empty-state branch in the Cognito callback path and make callback validation fail closed.

**Files:**
- Modify: `frontend/src/lib/auth.js`
- Modify/add tests: `frontend/src/__tests__/DashboardPage.test.jsx`, `frontend/src/__tests__/ChecksPage.test.jsx`, or a new auth-specific test if needed

**Requirements:**
- If `oauth_state` is missing, the callback must fail closed with a clear error.
- Do not silently continue when `savedState` is missing.
- Preserve the existing PKCE flow and token storage behavior unless a test proves a safe improvement.
- Keep any auth/logout flow cleanup consistent.

**Tests to add:**
- missing state fails
- mismatched state fails
- valid state passes

**Verification:**
- `docker compose -f docker-compose.test.yml run --rm frontend-tests`

---

## Task 5: Final integration verification

**Objective:** Confirm the combined patch is clean and production-readiness checks pass end-to-end.

**Files:**
- All files changed in Tasks 1-4

**Requirements:**
- Run the full backend and frontend Docker suites.
- Check `git diff --check`.
- Inspect the final diff for any remaining security regressions or accidental debug output.
- Summarize any remaining non-blocking risks separately from blockers.

**Verification commands:**
- `docker compose -f docker-compose.test.yml build backend-tests frontend-tests`
- `docker compose -f docker-compose.test.yml run --rm backend-tests pytest -q`
- `docker compose -f docker-compose.test.yml run --rm frontend-tests`
- `git diff --check`

**Done when:**
- backend and frontend suites pass in Docker
- the new/updated tests cover each fix above
- no duplicate handler remains
- token expiry is enforced
- SSRF handling is fail-closed
- frontend callback fails closed on invalid/missing state

---

## Notes
- Do not rely on prior chat context.
- Keep changes focused and add regression tests for every fix.
- If a change is too large to finish safely, stop and report the exact blocker instead of guessing.
