# Project Development Checklist

> **Purpose:** Master checklist for tracking Invictus Grid Workspace from its current state to a production-ready state.
> **Rules:** Only `[x]` when verified in the actual code. Partial work stays `[ ]` with a `(partially implemented: …)` note. Never delete completed tasks — only flip `[ ]` → `[x]`. Append to the Change Log on every update.

---

## Project Overview

- **Project name:** Invictus Grid Workspace (IGW)
- **Purpose:** Secure internal project-management and issue-tracking platform for a single college club (~120–150 members). Roles: `ADMIN` (full access), `MANAGER` (assigned projects only), `MEMBER` (own assigned tasks only). No public registration. Source of truth: `Invictus_Grid_Workspace_PRD/SRS/TRD.txt` v1.0.
- **Current technology stack:**
  - **Frontend:** React 18, TypeScript (~5.6, `strict`), Vite 8, Tailwind CSS 4 (installed but unused — styling is custom CSS), no router, no data-fetching library.
  - **Backend:** FastAPI, Pydantic v2, SQLAlchemy 2.0 (ORM), Alembic, Argon2id (`argon2-cffi`), PyJWT (HS256), slowapi rate limiting, psycopg 3.
  - **Database:** PostgreSQL (UUID PKs, FK/CHECK/UNIQUE constraints, indexed lookups).
  - **Auth design:** in-memory access token (15 min JWT) + rotating HttpOnly refresh cookie scoped to `/api/v1/auth`; server-side `auth_sessions` revocation.
- **Current project status:** MVP slice 1 delivered (auth, Admin user provisioning, projects + membership, task creation/assignment, task review workflow, health endpoint). Verified this session: frontend `tsc --noEmit` passes; backend dependencies are **not installed** (no `.venv`, no `.env`, no local PostgreSQL) so the API cannot run as-is. No tests, no CI, no deployment config. Several SRS-mandatory features are entirely absent (comments, attachments, GitHub evidence, notifications, dashboards).

---

## Phase 0 — Existing Project Analysis

### Phase Goal
Build a verified, evidence-based understanding of what exists today so every later phase and every `[x]` in this file rests on inspected code rather than assumption.

### Checklist

#### Documentation & baseline
- [ ] Read and reconcile `Invictus_Grid_Workspace_PRD.txt` (product scope, role matrix, acceptance criteria 1–27)
- [ ] Read and reconcile `Invictus_Grid_Workspace_SRS.txt` (FR-AUTH/RBAC/PROJ/TASK/REVIEW/GH requirements, §3.7–3.11 features)
- [ ] Read and reconcile `Invictus_Grid_Workspace_TRD.txt` (stack, layered architecture, testing/CI/deployment rules)
- [ ] Confirm README run instructions match the actual repository layout

#### Repository & structure
- [ ] Inventory folder/file structure (`backend/`, `frontend/`, docs, migrations)
- [ ] Review git history and confirm working tree state (`git status`, `git log`)
- [ ] Confirm `.gitignore` excludes secrets, `node_modules`, `dist`, `__pycache__`

#### Backend analysis
- [ ] Inspect `app/main.py` (app, CORS, limiter, router mounting)
- [ ] Inspect `app/models.py` (all tables, enums, constraints, relationships)
- [ ] Inspect `app/schemas.py` (request/response contracts, validation rules)
- [ ] Inspect `app/core/config.py` and `app/core/security.py`
- [ ] Inspect `app/db/session.py` and `app/api/dependencies.py`
- [ ] Inspect all routers: `auth.py`, `users.py`, `projects.py`, `tasks.py`, `health.py`
- [ ] Inspect Alembic migrations `0001` → `0002` → `0003`

#### Frontend analysis
- [ ] Inspect `src/api.ts` (request client, token store, 401→refresh→retry)
- [ ] Inspect `src/App.tsx` (session restore, login, forced password change, view switching)
- [ ] Inspect `AdminUsers.tsx`, `AdminProjects.tsx`, `TasksWorkspace.tsx`
- [ ] Inspect `styles.css`, `vite.config.ts`, `tsconfig.json`, `package.json`
- [ ] Run frontend typecheck (`tsc --noEmit`) and record result

#### Environment analysis
- [ ] Confirm Python version, backend virtualenv presence, installed backend dependencies
- [ ] Confirm Node version and `node_modules` state
- [ ] Confirm local PostgreSQL availability and whether `.env` files exist
- [ ] Record all known defects, gaps and spec deviations into this checklist

### Dependencies
None.

### Completion Criteria
Every checkbox above is `[x]` with notes captured in the Change Log; a gap list derived from PRD/SRS/TRD exists and is reflected in Phases 2–16 of this file.

### Current Status
- **NOT STARTED** (this session performed a full analysis and authored this checklist, but the analysis is intentionally left unchecked so it can be independently re-verified and re-run after each major phase.)

---

## Phase 1 — Environment & Project Setup

### Phase Goal
Make the project runnable and consistent for any developer: reproducible backend/frontend setup, environment configuration, and basic tooling.

### Checklist

#### Repository bootstrap
- [x] Monorepo layout with `backend/` and `frontend/` separated
- [x] Root `README.md` with backend and frontend local-run instructions
- [x] Root `.gitignore` covering Python, Node, `dist`, `.env*` (with `!.env.example` negation)
- [x] `backend/.env.example` documenting all 11 settings keys
- [x] `frontend/.env.example` documenting `VITE_API_BASE_URL`
- [x] Frontend `node_modules` installed; `npm run dev` / `npm run build` scripts defined in `package.json`

#### Environment (not runnable today)
- [ ] Create `backend/.venv` and install `requirements.txt` *(partially implemented: no virtualenv exists; `sqlalchemy`, `alembic`, `psycopg`, `PyJWT`, `argon2`, `slowapi` are not installed in the interpreter)*
- [ ] Create `backend/.env` from `.env.example` with a real `JWT_SECRET_KEY` (≥32 chars) and working `DATABASE_URL`
- [ ] Install/start a local PostgreSQL instance and create the `invictus_grid` database
- [ ] Verify `alembic upgrade head` runs end-to-end *(partially implemented: `migrations/env.py:14` eagerly evaluates `get_settings()`, so migrations fail unless a full `.env` exists — see Phase 2)*
- [ ] Verify `python -m app.bootstrap_admin` bootstraps the first Admin
- [ ] Verify `uvicorn app.main:app --reload` starts and `GET /api/v1/health` responds
- [ ] Verify `npm run dev` serves the SPA at `http://localhost:5173`

#### Tooling
- [ ] Add Python linter/formatter config (`ruff` or equivalent) + make target/script
- [ ] Add frontend linting (`eslint`) and formatting (`prettier`) config
- [ ] Add a root-level script/task runner (e.g. `Makefile`, `justfile`, or npm workspaces) for common commands
- [ ] Pin backend dependency versions or add a lock strategy (currently loose ranges only)
- [ ] Add pre-commit hooks (optional but recommended)

### Dependencies
Phase 0.

### Completion Criteria
A fresh clone can be brought up with documented commands only; backend, frontend and database all run locally; lint/typecheck commands exist and pass.

### Current Status
- **PARTIALLY COMPLETED** — structure, docs and config examples exist; the backend is not installable/runnable in the current environment and no tooling config exists.

---

## Phase 2 — Critical Defect Fixes

### Phase Goal
Resolve verified, user-visible/blocking defects before any new feature work, so later phases are built on a correct base.

### Checklist

#### Confirmed defects (verified against code this session)
- [ ] **C1 — CORS blocks the only `PUT` endpoint.** `backend/app/main.py:22` allows only `GET, POST, PATCH, DELETE`; `PUT /projects/{id}/members` fails preflight with `400 Disallowed CORS method`, so "Save membership" breaks cross-origin (Starlette `CORSMiddleware.preflight_response` verified). Add `PUT` to `allow_methods`.
- [ ] **C2 — Review feedback is write-only.** `POST /tasks/{id}/review` stores `TaskReview.feedback`, but no `GET` endpoint and no UI exist to read it, so a Member told `CHANGES_REQUIRED` never learns what to fix (SRS FR-REVIEW-005 / PRD acceptance 20–21). Add a reviews read endpoint + surface feedback in the task list.
- [ ] **C3 — Disabled assignee `<select>` submits literal `"null"`.** `TasksWorkspace.tsx:130` builds `assignee_id` via `String(form.get("task-assignee"))`; when the select is `disabled` (`members.length === 0`) the field is absent from `FormData`, so `String(null)` → `"null"` → 422 "Input should be a valid UUID". Use the raw value (`form.get(...) ?? ""`).
- [ ] **C4 — Alembic requires a JWT secret.** `migrations/env.py:14` uses `os.getenv("DATABASE_URL", get_settings().database_url)`; the default argument evaluates eagerly, so `alembic upgrade head` fails whenever `.env` lacks `JWT_SECRET_KEY`. Guard the fallback.

#### Design defect needing an explicit decision
- [ ] **C5 — Role changes break project access.** `PATCH /users/{id}/role` (`users.py:80-92`) never reconciles `project_members`, while access checks require `project_members.role == users.role` (`projects.py:135-143`, `tasks.py:35`). Promoting MEMBER→MANAGER makes the user lose *all* projects and their own assigned tasks (404s); demotion orphans assigned tasks. Decide and implement: cascade membership updates **or** decouple authorization from the duplicated role column.
- [ ] Document the chosen C5 decision (rationale + migration/backfill plan) in the repo

#### Secondary defects
- [ ] Remove unreachable/dead code: unused `before` dict in `update_task` (`tasks.py:190`); unreachable role check in `create_task` (`tasks.py:105`)
- [ ] Make `update_task` / `review_task` respect `COMPLETED`/`ARCHIVED` projects consistently with `create_task` (`tasks.py:107`)
- [ ] Fix duplicated frontend helpers (`errorMessage`, `passwordIsStrong`, `formatDate` in 3 files)

### Dependencies
Phase 0 (findings). Phase 1 recommended first for a runnable environment (needed to reproduce/verify fixes).

### Completion Criteria
Each defect has a fix, is reproduced-then-verified locally, and is covered by at least one regression test (or a note pointing at the Phase 11 test that covers it).

### Current Status
- **NOT STARTED**

---

## Phase 3 — Database & Migrations

### Phase Goal
A complete, drift-free schema that supports every PRD/SRS entity, with integrity constraints, correct indexes, and repeatable migrations.

### Checklist

#### Delivered schema (verified)
- [x] `users` table — email (unique), full_name, role, password_hash, `is_active`, `must_change_password`, timestamps (`0001`)
- [x] `auth_sessions` table — `refresh_token_hash` (unique), expiry, `revoked_at`, user FK CASCADE (`0001`)
- [x] `audit_logs` table — actor FK SET NULL, action/target/details JSON (`0001`)
- [x] `projects` table — unique `key`, status CHECK, `created_by` FK RESTRICT (`0002`)
- [x] `project_members` composite PK `(project_id, user_id)` with role CHECK (`0002`)
- [x] `tasks` table — unique `(project_id, issue_number)` and `(project_id, issue_key)`, type/priority/status CHECKs (`0003`)
- [x] `task_reviews` table — decision CHECK, reviewer FK (`0003`)
- [x] `activity_logs` table — project/task/actor FKs with JSON details (`0003`)
- [x] Indexes on all lookup columns (email, project key, `project_id`, `user_id`, `assignee_id`, `created_by`, `refresh_token_hash`)
- [x] UUID primary keys throughout; UTC `DateTime(timezone=True)` timestamps
- [x] Alembic wired via `migrations/env.py` with `target_metadata = Base.metadata`
- [x] SQLAlchemy models and migrations are structurally consistent for tables/rows/constraints

#### Known schema issues
- [ ] Fix model ↔ migration drift on unique *indexes*: models declare `unique=True, index=True` for `users.email` and `projects.key` (unique index) while migrations create a unique **constraint** + a **non-unique** index → redundant duplicate indexes and permanent `alembic autogenerate` diffs (`models.py:33,73`; `0001:31`, `0002:32`)
- [ ] Add `alembic check` (or `autogenerate --diff`) to the workflow so drift is caught automatically
- [ ] Remove hardcoded `postgres:postgres` default URL from `alembic.ini:4` and `config.py:12`

#### Missing SRS tables (§4.1)
- [ ] `comments` table (task FK, author FK, body, timestamps)
- [ ] `attachments` table (metadata: original name, safe storage key, MIME, size, uploader, task FK)
- [ ] `github_links` table (URL, evidence type, task FK, submitting user, timestamp)
- [ ] `notifications` table (recipient FK, type, related entity, read state, timestamp)
- [ ] Add matching CHECK constraints, FKs, indexes and Alembic migration(s) for the above

#### Data & lifecycle
- [ ] Seed script / fixtures for local demo data (roles, a sample project, tasks)
- [ ] Server-side project progress storage or computed view (SRS §3.11: completed active / total active × 100, 0 when empty)
- [ ] Decide retention/archiving policy for `audit_logs` and `activity_logs` (currently unbounded append-only)
- [ ] Type `audit_logs.target_id` as UUID instead of `String(80)` (`models.py:61`)
- [ ] Add index on `tasks.status` (and `due_date` if filters are added)
- [ ] Document schema/ERD (or generate from models)

### Dependencies
Phase 0, Phase 1. New tables depend on Phase 2 (C4) so migrations can run.

### Completion Criteria
`alembic upgrade head` and `downgrade` run cleanly on a fresh database; `alembic check` reports no drift; every SRS §4.1 entity exists with constraints and indexes.

### Current Status
- **PARTIALLY COMPLETED** — 9 tables + 3 migrations verified working in design; 4 SRS tables missing; known unique-index drift; migrations not yet executed in this environment.

---

## Phase 4 — Backend Architecture

### Phase Goal
Meet the TRD §3 layered architecture: thin routers, a service layer owning business rules and authorization-sensitive operations, a data-access layer, and cross-cutting config/security/logging/error modules.

### Checklist

#### Delivered (verified)
- [x] `app/core/config.py` — pydantic-settings, env-driven, `cors_origins` property, cookie-safety validation (rejects `SAMESITE=none` without `COOKIE_SECURE`, and insecure production)
- [x] `app/core/security.py` — Argon2 hash/verify, refresh token generation + SHA-256 hashing, JWT create/decode
- [x] `app/db/session.py` — declarative `Base`, engine with `pool_pre_ping`, request-scoped `get_db()` generator
- [x] `app/api/dependencies.py` — composable auth dependencies (`get_authenticated_user` → `get_current_user` → `require_admin`)
- [x] `app/schemas.py` — centralized Pydantic contracts with custom validators
- [x] `app/bootstrap_admin.py` — guarded one-shot Admin creation (refuses if users exist)
- [x] `app/main.py` — app factory wiring, limiter state, router mounting under `/api/v1`

#### Missing / required by TRD §3
- [ ] Service layer: `app/services/{auth,users,projects,tasks}.py` owning state transitions and audit writes
- [ ] Data-access/repository layer isolating query construction
- [ ] Move all business rules out of route handlers (currently every router contains validation + state machine + audit logic)
- [ ] Centralized exception mapping to a consistent API error response
- [ ] Structured application logging (severity, timestamp, request ID, actor, route, status, duration) — **no `logging` usage exists anywhere in the backend today**
- [ ] Request-ID middleware / correlation IDs
- [ ] Health endpoint that actually checks database connectivity (`health.py` returns a static dict)
- [ ] Lifespan/startup-shutdown hooks (engine disposal, readiness state)
- [ ] Ensure modules remain independently testable (TRD §3)

### Dependencies
Phase 0; Phase 2 recommended first (refactor after critical fixes to avoid churn).

### Completion Criteria
No authorization or state-transition logic lives in a router; `app/services/` exists and is used by all mutating endpoints; logs are emitted with request IDs; `/health` reports DB status without leaking secrets.

### Current Status
- **PARTIALLY COMPLETED** — solid core/db/config/dependencies modules exist, but the service and repository layers do not, and there is no logging or centralized error handling.

---

## Phase 5 — Authentication & Authorization

### Phase Goal
Fully satisfy SRS §3.1 and §3.2: secure login/session lifecycle, brute-force protection, and server-side RBAC plus object-level authorization on every endpoint.

### Checklist

#### Delivered (verified in code)
- [x] `POST /api/v1/auth/login` with generic failure message (never reveals account existence)
- [x] Constant-ish-time login: dummy Argon2 hash verified when the user does not exist (`auth.py:19,53-54`)
- [x] Argon2id password hashing, never plaintext (`security.py:16-25`)
- [x] Strong-password policy (12–128 chars, upper/lower/digit/symbol) enforced server-side on create and change
- [x] Access tokens are short-lived JWTs (15 min) carrying `sub` + `sid` + `type=access`
- [x] `POST /auth/refresh` rotates the refresh token and revokes the previous session (`auth.py:88-89`)
- [x] Refresh token is random 48-byte urlsafe; only its SHA-256 hash is stored; DB column is `unique`
- [x] Refresh cookie is `HttpOnly`, `path=/api/v1/auth`, configurable `secure`/`samesite`, correct `max_age`
- [x] `POST /auth/logout` revokes the session and clears the cookie
- [x] `GET /auth/me` returns the authenticated profile
- [x] `POST /auth/change-password` verifies current password, blocks reuse of the same password, revokes **all** active sessions
- [x] Forced first-login password change: `must_change_password` gates every non-auth endpoint with 403 (`dependencies.py:45-48`)
- [x] No public registration — user creation is Admin-only
- [x] Every request re-validates session revocation/expiry **and** `users.is_active` → deactivation takes effect immediately on outstanding tokens
- [x] Deactivation revokes all of the user's sessions (`users.py:68-73`)
- [x] Self-deactivation and self-demotion blocked for Admins (`users.py:64-65,85-86`)
- [x] Browser Origin check on the cookie-authenticated `refresh`/`logout` POSTs (CSRF defense, `auth.py:30-33`)
- [x] Login rate limiting: `5/minute` via slowapi with `RateLimitExceeded` → 429 handler
- [x] Role constants enforced by DB CHECK constraints, not only application code
- [x] RBAC dependencies: `require_admin` for user/project-admin routes; `get_current_user` otherwise
- [x] Object-level authorization: project access resolved via `project_members`; Members restricted to `assignee_id == actor.id`; unauthorized access returns **404** to avoid ID probing (`tasks.py:28-47`)
- [x] Managers cannot approve their own work by construction (assignees must hold the `MEMBER` account role, `tasks.py:79-86`)

#### Gaps
- [ ] Rate limit `/auth/refresh` and `/auth/change-password` (current-password brute force is unlimited)
- [ ] Make the rate limiter proxy-aware (trusted `X-Forwarded-For`); today `get_remote_address` keys on the socket peer, so behind Render every user shares **one** 5/min login bucket
- [ ] Per-account lockout / failed-attempt counters
- [ ] Refresh-token **reuse detection** (family invalidation when a revoked token is replayed)
- [ ] Admin-initiated password reset for another user
- [ ] Origin check on `POST /auth/login` (login-CSRF)
- [ ] Explicit authorization test matrix documented (role × endpoint) — see Phase 11
- [ ] Confirm `Password change required` 403 is handled gracefully in the UI for all routes

### Dependencies
Phase 0, Phase 2 (C5 role/membership reconciliation affects authorization semantics).

### Completion Criteria
SRS FR-AUTH-001…009 and FR-RBAC-001…007 all hold; brute-force controls work behind a proxy; the role×endpoint matrix is documented and covered by tests.

### Current Status
- **PARTIALLY COMPLETED (strong)** — the core auth design is implemented and verified; rate-limit scope, lockout, reuse detection and admin reset remain.

---

## Phase 6 — API Development

### Phase Goal
Deliver the full REST surface required by SRS §5.2 / TRD §12 under `/api/v1`, with consistent semantics, pagination, and OpenAPI documentation.

### Checklist

#### Endpoints verified as implemented
- [x] `GET /api/v1/health`
- [x] `POST /auth/login` · `POST /auth/refresh` · `POST /auth/logout` · `GET /auth/me` · `POST /auth/change-password`
- [x] `POST /users` (Admin, 201, duplicate → 409)
- [x] `GET /users` (Admin, `offset`/`limit`/`search`, returns `{items,total,offset,limit}`)
- [x] `PATCH /users/{id}/status` (Admin, revokes sessions on deactivate, audited)
- [x] `PATCH /users/{id}/role` (Admin, audited)
- [x] `POST /projects` (Admin, 201, membership validation, duplicate key → 409, audited)
- [x] `GET /projects` (role-scoped listing, search, pagination, batched member counts)
- [x] `GET /projects/{id}/members` (Admin or project Manager only)
- [x] `PUT /projects/{id}/members` (Admin, diff-based replace, audited)
- [x] `POST /projects/{id}/tasks` (Admin/project Manager, serialized issue-number allocation under row lock, audited)
- [x] `GET /projects/{id}/tasks` (role-scoped, `status`/`priority` filters, pagination, batched assignee names)
- [x] `GET /tasks/{task_id}` (role + assignee scoped)
- [x] `PATCH /tasks/{task_id}` (Manager/Admin only, reassignment audited)
- [x] `PATCH /tasks/{task_id}/status` (assignee Member only, strict transition guard)
- [x] `POST /tasks/{task_id}/submit-review` (assignee Member only, `IN_PROGRESS` → `PENDING_REVIEW`)
- [x] `POST /tasks/{task_id}/review` (Manager/Admin, creates `TaskReview`, APPROVED/CHANGES_REQUIRED transitions)
- [x] OpenAPI/Swagger auto-generated at `/docs`

#### Missing endpoints (SRS/TRD)
- [ ] `GET /tasks/{id}/reviews` (read review history + feedback — see Phase 2 / C2)
- [ ] `GET /projects/{id}` (project detail)
- [ ] `PATCH /projects/{id}` (status lifecycle PLANNED→ACTIVE→COMPLETED→ARCHIVED, name/description/due date)
- [ ] `DELETE /projects/{id}` (or archive-only policy) — TRD §13 expects audited project deletion
- [ ] `DELETE /tasks/{id}` (or documented soft-delete policy)
- [ ] Comments API: `GET/POST /tasks/{id}/comments` (+ edit/delete policy)
- [ ] Attachments API: `POST /tasks/{id}/attachments` (multipart), `GET` download, `DELETE` — with authorization
- [ ] GitHub evidence API: `GET/POST /tasks/{id}/github-links`, `DELETE`
- [ ] Notifications API: `GET /notifications`, `PATCH /notifications/{id}/read`
- [ ] Activity API: `GET /projects/{id}/activity`, `GET /tasks/{id}/activity`
- [ ] Audit API: `GET /audit-logs` (Admin) — today `audit_logs` are written but never readable
- [ ] Analytics/dashboards API: project progress %, task counts by status/priority, pending review, overdue, contribution metrics (SRS §3.11)
- [ ] Expose task `status`/`priority` filters and sort options the frontend can consume
- [ ] Admin user detail endpoint (`GET /users/{id}`) and profile update (`PATCH /users/me`)
- [ ] Consistent HTTP semantics audit: confirm 2xx/4xx/5xx usage and 404-vs-403 policy across all routes
- [ ] Document the API contract (or generate from OpenAPI) as a stable artifact

### Dependencies
Phase 0, Phase 2, Phase 4 (endpoints should delegate to services).

### Completion Criteria
Every SRS §3 and §12 endpoint exists, is authorization-checked, paginated where it is a collection, and appears in `/docs`; no write-only data (audit, activity, reviews) remains unreadable.

### Current Status
- **PARTIALLY COMPLETED** — ~15 resource endpoints verified; all comment/attachment/evidence/notification/activity/audit/analytics and project-lifecycle endpoints are missing.

---

## Phase 7 — Frontend

### Phase Goal
A complete, accessible, role-aware SPA covering every PRD §19 main screen with strict TypeScript and maintainable structure.

### Checklist

#### Delivered (verified; `tsc --noEmit` passes with `strict`, `noUnusedLocals`, `noUnusedParameters`)
- [x] `main.tsx` mounts under `StrictMode`; `styles.css` global import
- [x] `App.tsx` — session restore on load (guard against StrictMode double-invoke), login screen, forced password-change screen (with client-side strength check + confirmation match), sign-out, Admin view switching
- [x] `api.ts` — typed API surface mirroring backend schemas; in-memory access token; automatic single-flight refresh + one retry on 401; typed `ApiError` with user-facing messages; 429/network error messaging
- [x] `AdminUsers.tsx` — create account, search, pagination, role selector (self protected), activate/deactivate, notices, refresh-after-create
- [x] `AdminProjects.tsx` — create project with key/name/status/due date/description + Manager/Member pickers, search, pagination, membership editor with inactive/role-changed assignment warning
- [x] `TasksWorkspace.tsx` — project selector, task list with status/priority/type metadata, create-task form (Manager/Admin), Start/Resume, Submit for review, Approve/Request-changes with feedback textarea (Manager/Admin), pagination
- [x] Accessibility basics: semantic elements, `aria-current`, `aria-live`/`role=status|alert`, `visually-hidden` labels, `:focus-visible` outlines, `prefers-reduced-motion`, one responsive breakpoint (`max-width: 680px`)
- [x] Loading/disabled/busy states and error/notice banners on all interactive flows
- [x] `tsconfig.json` strict mode; `vite.config.ts` with React + Tailwind plugins; `index.html` title/meta

#### Missing / required by SRS §5.1 and TRD §4
- [ ] Client-side router with real routes and deep links (currently prop-driven view state; `href="#workspace"` anchors only)
- [ ] Task **detail page** (full description, reviews/feedback, comments, attachments, evidence, activity)
- [ ] Review feedback visible to the Member (blocked on Phase 2 / C2)
- [ ] **Kanban board** with drag/drop wired to validated transition APIs (TRD §4)
- [ ] Project overview/dashboard screen (progress %, counts, overdue, recent activity)
- [ ] Comments UI, attachments UI (upload/download), GitHub evidence UI
- [ ] Notifications panel (list + mark read)
- [ ] Admin audit-log viewer; activity history view
- [ ] Task search/status/priority filters + sort controls in the UI
- [ ] Adopt TanStack Query for server state (TRD §4) instead of hand-rolled fetch/loading/stale logic
- [ ] Error boundary (a render error currently white-screens the app)
- [ ] Reusable form/UI primitives (`FormField`, `Banner`, `Pagination`, `Modal`) to remove duplication across the three screens
- [ ] Extract duplicated helpers (`errorMessage`, `passwordIsStrong`, `formatDate`)
- [ ] Resolve Tailwind: either adopt utility classes or remove the dependency (currently `@import "tailwindcss"` with **zero** utility classes used; all styling is custom CSS)
- [ ] Loading skeleton/empty states for every collection
- [ ] Session-expiry UX (prompt or redirect on 401 after failed refresh)
- [ ] Mobile/responsive verification beyond the single breakpoint

### Dependencies
Phase 0. Feature UI depends on Phase 6 endpoints.

### Completion Criteria
Every PRD §19 screen exists and is reachable by URL; no duplicated helpers; `tsc --noEmit`, lint and build all pass; an error boundary prevents white screens.

### Current Status
- **PARTIALLY COMPLETED** — 4 screens + API client verified and type-safe; router, task detail, Kanban, dashboards, notifications, comments/attachments/evidence UI not started.

---

## Phase 8 — Frontend ↔ Backend Integration

### Phase Goal
Seamless, correct communication between SPA and API: authentication handshake, CORS, error propagation, and state synchronization.

### Checklist

#### Delivered (verified)
- [x] Base URL from `VITE_API_BASE_URL` with localhost fallback (`api.ts:1`)
- [x] `credentials: "include"` on all requests so the refresh cookie flows
- [x] Bearer header attached only to authenticated requests
- [x] 401 → single-flight refresh (`refreshInFlight` dedupe) → one retry, then typed "session expired" error
- [x] Backend `Content-Type`/`Accept` headers and JSON encoding on both sides
- [x] Backend error `detail` strings surfaced as user-facing messages; 429 mapped to a friendly notice
- [x] CORS middleware configured with explicit origins from `FRONTEND_ORIGINS` and `allow_credentials=True`
- [x] Cookie `path` scoping limits refresh cookie exposure to auth routes
- [x] Post-create/post-mutation list refresh in People/Projects/Tasks screens

#### Gaps
- [ ] **Add `PUT` to CORS `allow_methods`** — membership replacement is blocked cross-origin today (Phase 2 / C1)
- [ ] Verify CORS end-to-end from the real frontend origin (dev `5173` and deployed domain) with a preflight test
- [ ] Handle backend 403 `Password change required` consistently across all screens
- [ ] Abort/cancel in-flight requests on unmount/navigation (partially handled via `current` flags)
- [ ] Consistent loading/error state strategy once TanStack Query is adopted
- [ ] Timezone/date serialization audit (backend returns ISO 8601 UTC; frontend formats with local `Date`)
- [ ] End-to-end smoke pass: login → admin creates user/project → manager creates task → member submits → manager reviews

### Dependencies
Phase 2 (C1), Phase 6.

### Completion Criteria
All cross-origin requests succeed from a browser (including the `PUT`), the full happy path works without console/CORS errors, and session expiry is handled without data loss.

### Current Status
- **PARTIALLY COMPLETED** — the auth/refresh integration is solid; CORS configuration has a verified defect that breaks membership editing.

---

## Phase 9 — Core Features & SRS Parity

### Phase Goal
Close the gap between what is shipped and what PRD/SRS declare as MVP acceptance criteria.

### Checklist

#### Verified as implemented
- [x] Three-role model with hard server-side restrictions (Admin creates users/projects; Manager within assigned projects; Member own tasks only)
- [x] Admin account provisioning with initial password + forced change at first sign-in
- [x] Admin activate/deactivate and role change, both audit-logged
- [x] Project creation with unique key and required ≥1 Manager; membership add/remove/role-change with audit
- [x] Project-scoped task creation with unique issue key (`KEY-N`) and assignment to active project Members
- [x] Task state machine enforced server-side: `TODO → IN_PROGRESS → PENDING_REVIEW → COMPLETED` and `PENDING_REVIEW → CHANGES_REQUIRED → IN_PROGRESS`
- [x] Only the assigned Member can start/resume/submit; only Admin/project Manager can create/edit/review
- [x] `CHANGES_REQUIRED` requires feedback (schema-level); task stays assigned to the same Member
- [x] Review creates a `TaskReview` record with reviewer, decision, feedback, timestamp (SRS FR-REVIEW-004/005)
- [x] `activity_logs` and `audit_logs` written for creation, assignment, status changes, reassignment, review, and all admin actions
- [x] Login, provisioning, project, membership and task workflows reachable in the UI

#### Not started (SRS/PRD acceptance criteria still open)
- [ ] Comments on tasks with author/timestamps, permission-checked and activity-logged (SRS §3.8; AC 18)
- [ ] Attachments: PNG/JPG/JPEG/PDF/DOCX only, size limit, safe server-generated storage keys, authorized download, storage behind an interface (SRS §3.9; AC 25)
- [ ] GitHub evidence URLs: format validation, stored records, **no** auto-completion (SRS §3.7; AC 22)
- [ ] In-app notifications for assignment / review-request / changes-required / approval, list + mark-read (SRS §3.10; AC 24)
- [ ] Project dashboard + server-side progress formula `completed/total×100`, 0 when empty (SRS §3.11; AC 11)
- [ ] Contribution analytics (assigned, completed, pending, changes, overdue, completion rate) respecting role visibility
- [ ] Activity history visible to users; audit log visible to Admins (SRS §3.12; AC 26)
- [ ] Review feedback readable by the Member (Phase 2 / C2)
- [ ] Kanban board (PRD §19)
- [ ] Task detail page (SRS §5.1)
- [ ] Evidence/attachments/comments cannot complete a task — only explicit submission does (SRS FR-GH-004)
- [ ] Overdue detection and surfacing
- [ ] Admin project status lifecycle updates

### Dependencies
Phases 2, 3 (new tables), 6 (endpoints), 7 (UI).

### Completion Criteria
PRD acceptance criteria 1–27 and SRS §7 acceptance criteria 1–14 are each demonstrable end-to-end.

### Current Status
- **PARTIALLY COMPLETED** — the account/project/task/review core is done and verified; comments, attachments, evidence, notifications, dashboards, analytics, activity/audit visibility and Kanban are not started.

---

## Phase 10 — Validation & Error Handling

### Phase Goal
Consistent, safe input validation and predictable error responses across the whole API (TRD §11).

### Checklist

#### Delivered (verified)
- [x] Pydantic request models for every endpoint with length bounds (`Field(min_length/max_length)`)
- [x] Custom validators: non-blank name/title/description, project key normalization (trim + uppercase), password strength
- [x] Cross-field validators: duplicate/disjoint Manager/Member lists, feedback required on `CHANGES_REQUIRED`
- [x] `reject_null_required_fields` guard on `TaskUpdate` so required fields cannot be nulled
- [x] DB CHECK constraints mirror every enum (defense in depth)
- [x] Query param validation (`offset ≥ 0`, `1 ≤ limit ≤ 100`, `max_length` on search)
- [x] IntegrityError → 409 mapping for duplicate email and duplicate project key
- [x] Meaningful status codes: 401 auth, 403 role/forced-change, 404 concealed authorization failures, 409 state conflicts, 422 validation, 429 rate limit
- [x] State-transition guards return 409 with a descriptive message

#### Gaps
- [ ] Global exception handlers (unhandled exceptions currently fall through to FastAPI's default 500 with a generic body)
- [ ] Unified error envelope per TRD §11 (`code`, `message`, `details`, `request_id`) instead of ad-hoc `{"detail": ...}`
- [ ] Never leak stack traces/internals in production (verify `debug=False` behavior and custom handlers)
- [ ] Uniform 404-vs-403 policy documented and tested
- [ ] Cross-field validation for project status transitions and archived-project mutations (Phase 2 secondary defects)
- [ ] Sanitize/validate `search` input semantics (currently raw `ilike` — safe, but behavior undocumented)
- [ ] File-upload validation rules defined (Phase 9 attachments): extension, MIME sniff, size cap
- [ ] URL validation rules defined for GitHub evidence

### Dependencies
Phase 0; benefits from Phase 4 (central error mapping belongs with services).

### Completion Criteria
Every error response follows one documented shape with a request ID; no endpoint can return an unhandled traceback; validation and authorization errors are distinguishable and tested.

### Current Status
- **PARTIALLY COMPLETED** — per-endpoint Pydantic validation is strong; centralized error handling/envelope is absent.

---

## Phase 11 — Testing

### Phase Goal
Automated confidence for authorization, workflow and regression safety (TRD §15, SRS §8).

### Checklist

#### Infrastructure
- [ ] Python test framework configured (`pytest` + `pytest-asyncio` if needed) with a `tests/` layout
- [ ] Test database strategy (fixtures creating/dropping schema per run, or transaction rollback)
- [ ] Backend test dependencies added to a dev requirements file
- [ ] Frontend test runner configured (Vitest) + `@testing-library/react`
- [ ] Coverage reporting configured
- [ ] Tests wired into a local command and into CI (Phase 14)

#### Backend unit tests
- [ ] Password hashing/verification, refresh token hashing, JWT create/decode claims
- [ ] Settings validation (cookie security rules, CORS parsing)
- [ ] Schema validators: password strength, key normalization, disjoint membership, required review feedback
- [ ] Service-level state machine: every allowed transition passes, every disallowed transition fails
- [ ] Project progress calculation (including the zero-task case)

#### API / integration tests
- [ ] Auth: login success/failure, rate limiting, refresh rotation, logout revocation, expired/revoked session rejection, inactive user rejection
- [ ] Forced password change blocks other endpoints and is cleared after change
- [ ] Role matrix for **every** endpoint (Admin / Manager / Member / anonymous)
- [ ] **IDOR/BOLA:** Member cannot read another Member's task by ID; Manager cannot touch an unassigned project; cross-project access returns 404
- [ ] Admin-only enforcement on user and project creation
- [ ] Membership replace diffing and audit records
- [ ] Issue-number uniqueness under concurrent task creation
- [ ] Audit/activity rows written for each privileged action (and contain no secrets)

#### Frontend tests
- [ ] Login form validation and error display
- [ ] Forced password-change flow (strength + confirmation)
- [ ] Role-gated rendering (Admin nav, Member action buttons)
- [ ] API client: 401 → refresh → retry, refresh failure → session-expired error
- [ ] Create forms wire correct payloads (regression test for the `"null"` assignee bug)

#### End-to-end
- [ ] Full journey: bootstrap admin → create users → create project → assign → create task → start → submit → approve
- [ ] Changes-required journey: reject with feedback → feedback visible to Member → resume → resubmit → approve
- [ ] Deactivation mid-session cannot continue using issued tokens

#### Security tests (SRS §8.2)
- [ ] Direct-object access with foreign IDs
- [ ] Role escalation via crafted payloads
- [ ] Access after deactivation
- [ ] Brute-force/rate-limit behavior
- [ ] No secrets returned in errors or logs

### Dependencies
Phase 2 (fixes must be covered), Phase 4 (services make unit testing feasible), Phase 6.

### Completion Criteria
A single command runs the suite green; the role×endpoint matrix and task state machine are fully covered; CI blocks merges on failure.

### Current Status
- **NOT STARTED** — zero test files, no test runner configuration, no CI.

---

## Phase 12 — Security

### Phase Goal
Meet SRS §6.1 and TRD §13 hardening requirements end-to-end.

### Checklist

#### Delivered (verified)
- [x] Argon2id password hashing; no plaintext passwords stored or logged
- [x] Secrets sourced from environment (`pydantic-settings`); `.env` git-ignored; no committed secrets found
- [x] `JWT_SECRET_KEY` enforced with `min_length=32` at startup
- [x] HttpOnly + SameSite refresh cookie with production `COOKIE_SECURE` enforcement at config-validation time
- [x] Login rate limiting + generic auth failure messages
- [x] Server-side authorization on every protected endpoint (no reliance on UI gating)
- [x] IDOR/BOLA resistance via 404-based object resolution
- [x] Parameterized queries/ORM only — no string-built SQL from user input
- [x] Strict input validation via Pydantic on all payloads
- [x] CORS restricted to configured origins with credentials enabled
- [x] Origin check on cookie-authenticated endpoints (refresh/logout)
- [x] Session revocation on deactivation and password change
- [x] Bootstrap script refuses to run when users already exist (prevents accidental re-seed)

#### Gaps
- [ ] Security headers: HSTS, `X-Content-Type-Options`, `X-Frame-Options`/`frame-ancestors`, CSP, Referrer-Policy (none configured)
- [ ] HTTPS enforcement in production (deployment-level; not yet defined)
- [ ] Rate limiting made proxy-aware and applied to `refresh` + `change-password` (Phase 5)
- [ ] Dependency vulnerability scanning (`pip-audit`/`npm audit`) in CI
- [ ] Static analysis / secret scanning in CI
- [ ] Formal endpoint authorization review (document every route's required role)
- [ ] Audit log coverage review vs TRD §13 list (project deletion, privileged task actions)
- [ ] Ensure error responses and logs never contain tokens/passwords (verify under failure conditions)
- [ ] Upload security controls defined before attachments ship (Phase 9): path traversal, MIME spoofing, executables, size caps, safe storage names
- [ ] Threat-model note for refresh-token theft/reuse (Phase 5 reuse detection)

### Dependencies
Phase 5, Phase 12 tests depend on Phase 11.

### Completion Criteria
SRS §6.1 checklist fully satisfied; security headers present; scanners run clean in CI; the SRS §8.2 security test list passes.

### Current Status
- **PARTIALLY COMPLETED** — authentication and authorization hygiene is strong; headers, scanning, HTTPS, proxy-aware limits and upload controls are outstanding.

---

## Phase 13 — Performance & Optimization

### Phase Goal
Responsive experience at 120–150 members without architectural redesign (TRD §18).

### Checklist

#### Delivered (verified)
- [x] Pagination on users, projects and tasks endpoints (`offset`/`limit` with `total`)
- [x] No N+1 queries: `project_counts()` aggregates membership counts in one grouped query; task pages batch assignee name lookups
- [x] Count queries issued separately and only once per request
- [x] Indexes on all join/filter columns (`project_id`, `user_id`, `assignee_id`, `created_by`, `refresh_token_hash`, email, key)
- [x] `pool_pre_ping=True` on the engine for resilient connections
- [x] Row-level `SELECT ... FOR UPDATE` only where needed (issue-number allocation, membership replace, refresh rotation)

#### Gaps
- [ ] Query-count/latency instrumentation (no metrics exist)
- [ ] Add `tasks.status` / `due_date` indexes once filters ship
- [ ] Avoid full list fan-out in the frontend (`listAllUsers`, project loader page through all pages) — dedicated "fetch all" or server-side select options
- [ ] Connection pool sizing documented for production
- [ ] Caching evaluation (TRD says do not add Redis prematurely — document the decision)
- [ ] Load/concurrency check for the target scale
- [ ] Audit unbounded tables (`audit_logs`, `activity_logs`) for long-term query cost
- [ ] Frontend bundle review (currently single bundle; code-split by route once a router exists)

### Dependencies
Phase 6, Phase 7.

### Completion Criteria
Representative list/dashboard requests respond quickly at target scale with bounded query counts; indexes match actual filter usage; instrumentation exists to prove it.

### Current Status
- **PARTIALLY COMPLETED** — core query patterns are already efficient and verified; instrumentation, tuning and load validation are not started.

---

## Phase 14 — Deployment

### Phase Goal
Repeatable, environment-separated deployment of frontend, backend and database per TRD §16/§17 (Vercel + Render + managed PostgreSQL).

### Checklist

#### Documented (verified)
- [x] README documents local backend startup sequence (venv → deps → `.env` → alembic → bootstrap → uvicorn)
- [x] README documents frontend startup and `VITE_API_BASE_URL`
- [x] README documents production cookie settings (`COOKIE_SECURE=true`, `REFRESH_COOKIE_SAMESITE=none`)

#### Not started
- [ ] Frontend production build verified (`npm run build` output deployed and smoke-tested)
- [ ] `vercel.json` (or equivalent) for SPA routing/rewrites
- [ ] `render.yaml` / service definition for the API (or documented Render setup)
- [ ] Dockerfile(s) or documented alternative for the backend
- [ ] Production `DATABASE_URL` (managed Postgres) with TLS
- [ ] Environment separation: development / staging / production variable sets documented
- [ ] Migration step integrated into the deploy pipeline (run `alembic upgrade head` as a controlled release step)
- [ ] Seed/bootstrap procedure documented for first production deploy
- [ ] Domain + HTTPS configured; cookie `secure`/`samesite` validated against the real split-site topology
- [ ] Database backups enabled and a restore procedure documented (TRD §17)
- [ ] Persistent-disk strategy documented for future attachments
- [ ] Rollback procedure documented (app + migration)
- [ ] Health/readiness endpoint used by the platform for uptime checks
- [ ] CI/CD pipeline: install → lint → typecheck → tests → build → migrate → deploy only on green (TRD §16)
- [ ] Protected `main` branch / PR-based workflow enabled

### Dependencies
Phases 1, 11 (tests gate deploys), 12 (security headers/HTTPS).

### Completion Criteria
A clean deploy from a fresh repository succeeds on the target platforms; migrations run as a deploy step; backups and rollback are documented and tested.

### Current Status
- **PARTIALLY COMPLETED** — local run documentation only; no pipeline, no IaC/manifests, no backups.

---

## Phase 15 — Documentation

### Phase Goal
Documentation sufficient for a new developer, an operator and a reviewer (TRD §19/§20).

### Checklist

#### Delivered (verified)
- [x] `README.md` — repository layout, backend/frontend setup, current scope summary, auth/session behavior notes
- [x] `backend/.env.example` and `frontend/.env.example` listing every variable
- [x] PRD / SRS / TRD baseline documents checked into the repo
- [x] FastAPI auto-generated OpenAPI at `/docs` with route summaries/tags

#### Not started
- [ ] Architecture overview document (layers, request flow, auth flow, data model diagram)
- [ ] API contract artifact (generated OpenAPI JSON committed, or a written contract doc)
- [ ] Deployment/operations runbook (env vars, deploy, migrate, backup, restore, rollback)
- [ ] Decision records (ADR) for: auth design, 404-based authorization policy, C5 role/membership decision, storage abstraction
- [ ] Contribution guide: commands, style, PR expectations, branch policy
- [ ] Data model / ERD reference
- [ ] Security notes (threat model, secrets handling, incident basics)
- [ ] Update README "Current scope" section as Phases 6/9 land (it currently reflects slice 1 only)
- [ ] Changelog / release notes process

### Dependencies
Phases 4–14 (document what actually exists).

### Completion Criteria
A newcomer can set up, run, test and deploy using only repo documentation; every architecture decision is recorded.

### Current Status
- **PARTIALLY COMPLETED** — baseline docs and env examples exist; architecture, ops, ADR and contribution docs do not.

---

## Phase 16 — Production Readiness

### Phase Goal
Final validation that the system is secure, observable, performant and supportable in production.

### Checklist

#### Release validation
- [ ] Full regression pass of PRD acceptance criteria 1–27 in a staging environment
- [ ] All Phase 11 test suites green in CI
- [ ] All Phase 12 security checks and headers verified in the deployed environment
- [ ] Cross-origin smoke test from the real deployed frontend origin (including `PUT /projects/{id}/members`)
- [ ] Accessibility review (keyboard navigation, contrast, screen-reader labels) across all screens
- [ ] Browser/device matrix check (desktop + mobile)
- [ ] Error/empty/loading state review across every screen

#### Observability & operations
- [ ] Structured logs shipped and queryable (with request IDs)
- [ ] Alerting/uptime checks on the health endpoint
- [ ] Metrics baseline: request latency, error rate, login failures (even if manual at first)
- [ ] Backup + restore drill executed and recorded
- [ ] Data retention policy applied to audit/activity logs

#### Governance
- [ ] Secret inventory reviewed (no secrets in repo, images, or logs)
- [ ] Dependency versions current and vulnerability scan clean
- [ ] `PROJECT_CHECKLIST.md` fully reconciled with reality; no stale `[x]`
- [ ] Known issues / deferred items documented with owners
- [ ] Sign-off against TRD §20 "Definition of Technical Done"

### Dependencies
All previous phases.

### Completion Criteria
Every checkbox in Phases 0–15 is `[x]`, staging matches production configuration, and TRD §20 is signed off.

### Current Status
- **NOT STARTED**

---

# Overall Progress

| Metric | Value |
|---|---|
| **Total phases** | 17 (Phase 0 → Phase 16) |
| **Completed phases** | 0 |
| **In-progress phases** | 0 formally; Phases 0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15 are all **PARTIALLY COMPLETED** |
| **Not started phases** | 2 (Critical Defect Fixes), 11 (Testing), 16 (Production Readiness) — plus Phase 0 awaiting independent verification |
| **Remaining phases** | 17 of 17 |

**Checklist items: 129 of 356 verified complete → 36%**
*(Backend/DB/auth core of slice 1 is verified complete; environment setup, testing, CI, deployment, security hardening and ~half of the SRS feature set remain. Recalculated on every Change Log entry.)*

**Verified-complete highlights:** auth + session lifecycle, RBAC/IDOR guards, user provisioning, projects + memberships, task lifecycle + review workflow, audit/activity writes, 3 migrations, pagination and batched queries, full Admin/Member/Manager UIs for those flows, strict-TS frontend that typechecks clean.

**Largest outstanding bodies of work:** runnable environment (Phase 1), critical fixes (Phase 2), tests + CI (Phase 11), service-layer refactor (Phase 4), SRS feature parity (Phase 9), deployment (Phase 14).

---

# Current Priority

Ordered by priority — complete top-down:

1. **C1 — Add `PUT` to CORS `allow_methods`** (`backend/app/main.py:22`). One-line fix; project membership editing is currently broken in any browser. *(Critical)*
2. **C2 — Expose review feedback** (`GET /tasks/{id}/reviews` + surface it in `TasksWorkspace.tsx`). Without this, Members cannot act on `CHANGES_REQUIRED`. *(Critical)*
3. **C3 — Fix the `"null"` assignee payload** (`TasksWorkspace.tsx:130`). *(Critical)*
4. **C4 — Uncouple Alembic from `JWT_SECRET_KEY`** (`migrations/env.py:14`). *(Critical)*
5. **Phase 1 — Make the backend runnable**: `.venv`, `.env`, local PostgreSQL, verify migrations/bootstrap/uvicorn, then verify frontend dev + build. *(Critical — everything else needs a running system)*
6. **Phase 11 bootstrap — add pytest + a test harness** and cover the auth/IDOR/state-machine paths before refactoring. *(High)*
7. **Phase 4 — extract the service layer** so business rules are testable (TRD §3). *(High)*
8. **C5 — decide and implement role/membership reconciliation** so role changes stop breaking project access. *(High)*
9. **Phase 10 — centralized error envelope + global exception handlers.** *(Medium)*
10. **Phase 5 — proxy-aware rate limiting, limits on `refresh`/`change-password`, failed-login lockout.** *(Medium)*
11. **Phase 6/9 slice — review-feedback read path, project lifecycle endpoints, then comments → GitHub evidence → attachments → notifications → dashboards.** *(Medium, delivers SRS acceptance criteria)*
12. **Phase 12 — security headers + CI scanning.** *(Medium)*
13. **Phase 14 — deployment manifests + CI/CD pipeline.** *(Medium)*
14. **Phase 7 — router, task detail page, Kanban, TanStack Query, error boundary.** *(Medium)*
15. **Phase 15/16 — architecture & ops docs, full production-readiness pass.** *(Low at this stage)*

---

# Change Log

| Date | What was completed | What changed | What should be done next |
|---|---|---|---|
| 2026-10-08 | Full repository analysis performed (backend, frontend, migrations, docs, git history, frontend typecheck run). | Created `PROJECT_CHECKLIST.md` with 17 phases and 356 checklist items (129 `[x]` verified, 227 `[ ]`); recorded verified-complete items as `[x]` and partial work as `[ ]` with notes. Phase 0 intentionally left unchecked for independent re-verification. No source files modified. | Execute Current Priority items 1–5 (CORS fix, review-feedback read path, assignee fix, Alembic fix, runnable environment). |
