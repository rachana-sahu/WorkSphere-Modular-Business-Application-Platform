# Development log

## Milestone 1 — repository and runnable foundation

- Established the frontend/backend/PostgreSQL modular-monolith layout.
- Added a React/Vite client, FastAPI liveness and readiness routes, and
  SQLAlchemy PostgreSQL connectivity.
- Added local PostgreSQL Compose configuration, a safe-to-copy development
  environment example, and setup/dependency documentation.
- Fixed pytest's backend import path with a local configuration after the
  initial collection attempt could not import `app`.
- Validation:
  - `npm install` — completed; audit reported 0 vulnerabilities.
  - `npm run build` — passed TypeScript checking and Vite production build
    (29 modules transformed).
  - `.venv/bin/python -m pytest -q backend/tests` — 3 passed; one upstream
    Starlette deprecation warning remains for its HTTPX-backed test client.
- Known environment constraint: Docker Compose and PostgreSQL command-line
  tools are unavailable here, so the database container and live PostgreSQL
  connection could not be exercised.

## Milestone 2 — relational foundation and migrations

- Added normalized `workspaces`, `users`, and `workspace_memberships`
  SQLAlchemy models with UUID primary keys, unique email/slug constraints,
  role validation, cascading foreign keys, and membership lookup indexing.
- Added Alembic configuration and an initial reversible schema migration.
- Added a reusable SQLAlchemy session factory and request dependency; kept
  database readiness separate from API liveness.
- Added SQLite-backed tests for foreign keys, uniqueness, role constraints,
  and migration upgrade/downgrade, alongside the existing health tests.
- Fixed the downgrade test to account for Alembic's retained version table and
  aligned the role constraint name with the metadata naming convention.
- Validation:
  - `.venv/bin/python -m pytest -q backend/tests` — 11 passed; one upstream
    Starlette test-client deprecation warning.
  - `cd backend && ../.venv/bin/alembic upgrade head --sql` — generated
    PostgreSQL migration SQL successfully.
  - `cd frontend && npm run build` — passed TypeScript checking and Vite
    production build.
- Limitation: migrations were exercised on SQLite and SQL generation was
  checked for PostgreSQL, but no live PostgreSQL server was available.
- Decision: persist the workspace/user relationship now, while deferring
  password hashing, registration/login, and authorization enforcement to
  Milestone 3.

## Milestone 3 — authentication and authorization

- Added registration with email normalization, Argon2id password hashing,
  generated workspace slugs, atomic owner-membership creation, and explicit
  conflict responses for duplicate accounts or workspace slugs.
- Added JSON login, short-lived signed bearer tokens with issuer/audience/
  expiry validation, current-user access, and workspace-scoped APIs.
- Added database-backed owner/admin/member access checks and guarded role
  changes; owner role changes are blocked to avoid accidental workspace
  lockout. Unknown-email login attempts use a dummy Argon2 verification to
  reduce credential-enumeration timing differences.
- Added a validation-error handler that omits raw request values, so invalid
  password submissions are not echoed in 422 responses.
- Added a responsive register/login UI and a protected workspace screen;
  bearer tokens are stored in tab-scoped `sessionStorage`.
- Added backend authentication/authorization tests and frontend interaction
  tests. Initial fixtures exposed Pydantic EmailStr's rejection of the
  reserved `.test` TLD; fixtures now use valid `.com` domains. UI testing
  also caught password helper copy being included in the input's accessible
  label; the help text now uses `aria-describedby`.
- Validation:
  - `.venv/bin/python -m pytest -q backend/tests` — 27 passed; one upstream
    Starlette test-client deprecation warning.
  - `npm test` — 5 passed, including registration, sign-in error handling,
    and protected workspace access.
  - `npm run build` — TypeScript check and production build passed.
  - `.venv/bin/python -m pip check` — no broken requirements found.
  - Pylance Python syntax checks passed for the new auth modules and tests.
  - npm install/audit — 0 vulnerabilities reported.
- Security limitations: no refresh/revocation, rate limiting, email
  verification, invitation flow, password reset, or CSRF-protected
  HttpOnly-cookie session yet. The default Pylance workspace interpreter was
  not the project's `.venv`, so workspace-wide type diagnostics were not used
  as a validation signal; backend runtime and API tests ran in the `.venv`.

## Milestone 4 — CRM vertical slice

- Added workspace-scoped company, contact, lead, note, and activity models and
  the reversible `0002_crm` Alembic migration. The schema includes
  case-insensitive workspace uniqueness, stage/value constraints, activity
  history indexes, and a check that each note/activity targets exactly one
  CRM record.
- Added company/contact/lead list and create endpoints with validated inputs,
  literal case-insensitive search, pagination, lead stage filtering and
  sorting, workspace-checked relationships, duplicate conflicts, lead
  updates, note creation, and activity history. Stage updates and their audit
  event are committed together.
- Added the authenticated CRM page with lead/company/contact tabs, create
  forms, search, lead-stage selection, pagination, lead notes, activity
  history, and request loading/error/empty states.
- A backend integration run first exposed that the CRM router was not mounted;
  registered it in the FastAPI application. The next run exposed low timestamp
  precision in SQLite causing ambiguous event ordering; CRM note/activity
  timestamps now use precise UTC application defaults while retaining database
  defaults. SQLAlchemy UUID assertions use UUID values rather than strings.
- Frontend tests caught incorrect request mocks for paginated URLs and an
  assertion against a `Headers` instance as if it were a plain object; tests
  now inspect the serialized request and verify the bearer header.
- Validation:
  - `.venv/bin/python -m pytest -q backend/tests` — 35 passed; one upstream
    Starlette test-client deprecation warning. Includes CRM API integration
    tests and SQLite Alembic upgrade/downgrade checks for both revisions.
  - `cd frontend && npm test -- --run` — 8 passed across 2 test files.
  - `cd frontend && npm run build` — TypeScript check and Vite production
    build passed.
- Limitations: no live PostgreSQL or Docker Compose executable is available
  in this environment. API integration tests and migration upgrade/downgrade
  run on SQLite; live PostgreSQL behavior remains unverified.

## Milestone 5 — project management vertical slice

- Added projects, tasks, task comments, and project activity models plus the
  reversible `0003_projects` Alembic migration. Projects and tasks have
  constrained statuses; tasks also have constrained priorities, optional due
  dates and workspace-validated assignees.
- Added authenticated workspace-scoped APIs for project creation/search/
  pagination/status changes, member display-name choices, task creation and
  filtering/pagination, task updates, comments, and project activity history.
  Project/task updates and comments record activity in the same database
  transaction as the change.
- Added the responsive Projects workspace with project/task search and
  filters, assignment, priorities, deadlines, status changes, comments, and
  recent activity. The signed-in workspace now links to both CRM and Projects.
- Added backend integration coverage for pagination/search, task filtering,
  assignment validation, workspace isolation, authentication, status updates,
  comments, and activity. Added frontend tests for project selection, task
  filters, assigned task creation, task discussions, and API error feedback.
- Initial checks found SQLite migration constraint names were double-prefixed
  when the migration supplied already-prefixed names; changed migration
  constraint identifiers to follow the repository's SQLAlchemy naming
  convention. UI test failures came from mocks that did not account for query
  strings and tests that had not selected a project before requesting its
  tasks. These were corrected and the focused suites then passed. Final review
  extended the activity log to include project/task metadata changes, not only
  status transitions and comments.
- Validation:
  - `.venv/bin/python -m pytest -q backend/tests` — 38 passed; one upstream
    Starlette test-client deprecation warning. Includes full SQLite migration
    upgrade/downgrade coverage.
  - `cd frontend && npm test -- --run` — 12 passed across 3 test files.
  - `cd frontend && npm run build` — TypeScript check and Vite production
    build passed.
  - `.venv/bin/python -m pip check` — no broken requirements found.
- Limitations: live PostgreSQL is still unavailable; SQLite exercised
  migration up/down and API integration behavior. Comments are plain text
  and the first project-management slice does not yet include task
  dependencies, attachments, notifications, or delete/archive flows.

## Milestone 6 — communication, HR, and applicant tracking

- Added channel/message, department/employee/leave-request, and job/candidate/
  application/history models, Pydantic schemas, workspace-scoped API routers,
  and the reversible `0004_people_communication_ats` migration.
- Applied backend authorization at the API boundary: channel communication
  and ATS are workspace-member features; HR routes require owner/admin roles.
  Leave approvals only update pending requests, and application stage changes
  write status history.
- Added an authenticated Team page with Communication, People, and Hiring
  tabs. Communication polls the selected channel every five seconds; HR
  supports department/employee setup and leave review; Hiring supports job
  creation, candidate applications, stage changes, and history.
- Added loading/empty/error feedback, responsive styling, accessible form
  labels, and explicit handling for HR permission errors. Documented the
  endpoint surfaces, current role policy, scope, and limitations in README.
- Validation:
  - `.venv/bin/python -m pytest -q backend/tests` — 38 passed; one upstream
    Starlette test-client deprecation warning. This confirms the prior suite
    remains green and runs its migration coverage, but does not include
    dedicated API integration tests for the new M6 routes.
  - `cd frontend && npm test -- --run` — 16 passed across 4 test files,
    including workspace-to-Team navigation, communication posting, HR access
    feedback, and job creation.
  - `cd frontend && npm run build` — TypeScript check and Vite production
    build passed.
- Remaining verification: add dedicated backend API integration tests for
  communication, HR, and ATS; inspect migration constraints/indexes directly;
  and run the migration against PostgreSQL when that service is available.
  Live PostgreSQL and Docker Compose were unavailable in this environment.

## Milestone 7 — bounded project status assistant

- Added a `ProjectSummaryProvider` interface and a deterministic mock
  implementation. The default feature requires no API key, network access,
  third-party provider, new package, or migration.
- Added an explicitly triggered, authenticated project status-draft endpoint.
  It verifies the project belongs to the authorized workspace and gives the
  provider only that project's description, task-status counts, and up to
  five recent activity summaries.
- Validated provider output as nonblank and at most 1,200 characters. Provider
  unavailability and invalid output return explicit API errors; the draft
  response discloses that it may omit context or be inaccurate.
- Added a project-page action that requests a draft only on user click and
  presents it as editable text; the draft is neither saved nor shared
  automatically. Documented the API, privacy behavior, mock limitations, and
  provider boundary in README.
- Validation:
  - `.venv/bin/python -m pytest -q backend/tests` — 41 passed; one upstream
    Starlette test-client deprecation warning. New tests cover scoped context
    generation, foreign-project and unauthenticated access, invalid output,
    and provider failure.
  - `cd frontend && npm test -- --run` — 18 passed across 4 test files,
    including explicit generation, editable output, error feedback, and no
    request before the user action.
  - `cd frontend && npm run build` — TypeScript check and Vite production
    build passed.
  - `.venv/bin/python -m pip check` — no broken requirements found.
- Limitation: the mock is a deterministic template, not a language model.
  Real provider integration requires a separate privacy/configuration review
  and explicit opt-in before any private workspace records can leave the
  application.

## Milestone 8 — quality gates, observability, and security review

- Added GitHub Actions CI for Python linting, compilation, backend tests,
  dependency consistency, offline PostgreSQL migration SQL generation, and
  frontend tests/build/type-checking. CI uses a fixed non-production signing
  key only for tests.
- Added request IDs with safe caller-ID validation, response correlation
  headers, structured JSON HTTP logs (method, path, status, duration), and a
  generic 500 response. Unexpected exceptions are logged with the request ID;
  exception details are not returned to API clients.
- Added reproducible synthetic SQLite API read-benchmark harness for project
  and task list routes. It reports measurements only and explicitly makes no
  PostgreSQL or production performance claim.
- Added API integration tests for communication, HR role restrictions and
  leave approval state transitions, ATS application history, plus validation,
  duplicate, workspace-isolation, and request-observability cases. Extended
  migration tests through revision 0004 to assert tables, constraints,
  indexes, and downgrade behavior.
- Security review: no vulnerabilities were reported in the reviewed codebase.
  This is a source review, not a penetration test or deployment certification.
- Validation:
  - `.venv/bin/python -m pytest -q backend/tests` — 47 passed; one upstream
    Starlette test-client deprecation warning.
  - `cd backend && ../.venv/bin/ruff check --select E4,E7,E9,F app tests benchmarks`
    — passed.
  - `.venv/bin/python -m compileall -q backend/app backend/tests backend/benchmarks`
    — passed.
  - `.venv/bin/python -m pip check` — no broken requirements found.
  - `cd frontend && npm test -- --run` — 18 passed across 4 files.
  - `cd frontend && npm run build` — TypeScript check and production build
    passed.
  - `JWT_SECRET_KEY=ci-only-signing-key-for-worksphere-tests-1234567890
    ../.venv/bin/python -m alembic upgrade head --sql` from `backend/` —
    PostgreSQL dialect migration SQL generated successfully; no live
    PostgreSQL server was used.
  - `cd backend && JWT_SECRET_KEY=benchmark-only-key-for-local-measurement
    ../.venv/bin/python -m benchmarks.api_read_benchmark --iterations 5
    --tasks 10` — benchmark smoke run completed with synthetic SQLite data.
- Limitations: the hosted GitHub Actions workflow has not run in this
  environment. The benchmark is a local repeatability harness, not a
  performance result. No live PostgreSQL, production deployment, or external
  AI provider was exercised.

## Milestone 9 — release documentation and local verification

- Corrected the README's implemented-milestone scope, removed a duplicated
  assistant feature description, refreshed its repository tree, consolidated
  test/build instructions, added a Team/HR/ATS ER diagram, and documented the
  currently implemented API and local-only demo workflow.
- Added `backend/scripts/seed_demo.py`, an opt-in, idempotent synthetic-data
  seed covering CRM, Projects, Communication, HR, and ATS. It requires a
  caller-supplied password, rejects non-loopback database hosts, preserves
  existing credentials, and refuses partially existing or differently owned
  demo-account/workspace pairs. Added tests for idempotency, password use, and
  remote-host rejection.
- Captured `screenshots/crm.png` from the running responsive app using the
  seeded demo data. The screenshot is a genuine local browser capture, not a
  mockup.
- Extended CI's Python lint and compilation steps to include the seed script.
- Validation:
  - `.venv/bin/python -m pytest -q backend/tests` — 49 passed; one upstream
    Starlette test-client deprecation warning.
  - `cd backend && ../.venv/bin/ruff check --select E4,E7,E9,F app tests benchmarks scripts`
    — passed.
  - `cd frontend && npm ci` — completed; npm reported 0 vulnerabilities.
  - `cd frontend && npm test -- --run` — 18 passed across 4 files.
  - `cd frontend && npm run build` — TypeScript check and Vite production
    build passed.
  - `cd backend && ../.venv/bin/python -m compileall -q app tests benchmarks scripts`
    — passed; `pip check` — no broken requirements found.
  - `JWT_SECRET_KEY=ci-only-signing-key-for-worksphere-tests-1234567890
    ../.venv/bin/python -m alembic upgrade head --sql` from `backend/` —
    PostgreSQL dialect migration SQL generated successfully.
  - On a fresh temporary SQLite database, `alembic upgrade head` and
    `python -m scripts.seed_demo` both completed; the migrated schema
    contained 22 tables.
  - Started the API and Vite locally against synthetic SQLite data; health
    endpoint and frontend returned HTTP 200, and the demo account reached the
    authenticated workspace and CRM.
- Limitations: Docker and `psql` are not installed here, so live PostgreSQL
  migration/runtime and Docker Compose setup could not be tested. The hosted
  Actions workflow has not run. The screenshot covers CRM only; the AI
  provider remains a local mock. This remains a portfolio application, not a
  production-readiness or scale certification.

## Post-milestone hardening — Python version support

- Corrected the setup guide's minimum Python version from 3.10 to 3.11 after
  confirming the backend imports `datetime.UTC`, which is not available in
  Python 3.10.
- Expanded the backend CI matrix to test Python 3.11 and 3.12 rather than
  testing only 3.12. Local validation uses the configured Python 3.12
  environment; the Python 3.11 CI job has not run from this workspace.
- Validation:
  - `.venv/bin/python -m pytest -q backend/tests` — 49 passed; one upstream
    Starlette test-client deprecation warning.
  - Ruby Psych parsed `.github/workflows/ci.yml` successfully.

## Post-milestone hardening — browser authentication and CSRF

- Replaced browser `sessionStorage` bearer-token handling with a short-lived
  `HttpOnly`, `SameSite=Lax` session cookie and a session-bound CSRF cookie.
  Unsafe cookie-authenticated requests require the matching
  `X-CSRF-Token` header; the shared frontend request helper supplies it.
- Added `/api/auth/logout` to clear browser cookies and `/api/auth/token` for
  non-browser API clients that explicitly need a bearer token. Registration
  and login no longer expose the session JWT in their response bodies.
- Kept bearer authentication available for API clients and exempted explicit
  bearer-authenticated calls from cookie CSRF checks. The default cookie
  `Secure` setting is true; `.env.example` disables it only for local HTTP.
- Updated auth/security documentation and clarified that browser sign-out
  cannot revoke already-issued bearer tokens, while CSRF protection does not
  mitigate same-origin XSS.
- Validation:
  - `.venv/bin/python -m pytest -q backend/tests` — 52 passed; one upstream
    Starlette test-client deprecation warning.
  - `cd backend && ../.venv/bin/ruff check --select E4,E7,E9,F app tests benchmarks scripts`
    — passed; compileall passed; `pip check` reported no broken requirements.
  - `cd frontend && npm test -- --run` — 18 passed across 4 files.
  - `cd frontend && npm run build` — TypeScript check and Vite production
    build passed.
- Limitations: hosted CI and live PostgreSQL/deployment behavior were not
  exercised. Python 3.11 support is configured in CI, but the hosted 3.11 job
  has not run from this workspace.
