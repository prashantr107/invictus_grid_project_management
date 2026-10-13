# Invictus Grid Workspace

MVP foundation for the Invictus Grid club project-management workspace. Product behavior and security boundaries are defined in the accompanying PRD, SRS, and TRD; this repository is being built to those documents.

## Repository layout

- `frontend/` — React, TypeScript, Vite, and Tailwind CSS client.
- `backend/` — FastAPI application, configuration, and PostgreSQL access layer.
- `Invictus_Grid_Workspace_*.txt` — approved v1.0 product and technical baseline.

## Local development

### Backend

Requires Python 3.11+ and PostgreSQL. From `backend/`:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Set DATABASE_URL to your local PostgreSQL credentials and JWT_SECRET_KEY to a unique random secret.
alembic upgrade head
python -m app.bootstrap_admin
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; OpenAPI docs are at `/docs`. `GET /api/v1/health` is the readiness probe (it checks database connectivity and returns `503` when it is unavailable); `GET /api/v1/health/live` is the static liveness probe. Every response carries an `X-Request-ID` header and every error uses the shape `{detail, code, details, request_id}`. Requests are logged as one JSON line each (`LOG_LEVEL`, default `INFO`).

Instead of `python -m app.bootstrap_admin`, you can load a full demo dataset into an empty database with `python -m app.seed` (or `npm run backend:seed` from the root). It creates four accounts (`admin@invictusgrid.com`, `manager@invictusgrid.com`, `member@invictusgrid.com`, `dev@invictusgrid.com`) and the `ALPHA` project with tasks; all share the password `DemoPassw0rd!` unless overridden with `SEED_DEMO_PASSWORD`.

Set `JWT_SECRET_KEY` to a random secret of at least 32 characters. For split-site production deployments, configure `COOKIE_SECURE=true` and `REFRESH_COOKIE_SAMESITE=none`; local HTTP development uses `false` and `lax`.

### Frontend

Requires Node.js 20.19+ or 22.12+. From `frontend/`:

```powershell
npm install
npm run dev
```

The frontend reads its backend base URL from `VITE_API_BASE_URL` (defaults to `http://localhost:8000/api/v1`).

### Tooling & quality

From the repository root, `npm run <task>` drives every common command:

| Task | What it runs |
|---|---|
| `npm run setup` | install backend (`requirements.txt`) + frontend deps |
| `npm run db:up` / `db:down` | start / stop the local Postgres container (`igw-postgres`) |
| `npm run backend:dev` / `frontend:dev` | uvicorn with reload / Vite dev server |
| `npm run backend:migrate` | `alembic upgrade head` |
| `npm run backend:migrate:check` | `alembic check` — fails if the models and the database schema have drifted |
| `npm run backend:seed` | load demo data (4 accounts, the `ALPHA` project, 5 tasks) into an empty database |
| `npm run backend:install-dev` | install dev deps (ruff, pre-commit, pytest, pytest-cov) into `backend/.venv` |
| `npm run test` / `backend:test` | run the backend pytest suite (in-memory SQLite, no Postgres needed) |
| `npm run backend:test:cov` | run the suite with coverage (`--cov=app`); currently ~92% |
| `npm run lint` | `ruff check` (backend) + `eslint` (frontend) |
| `npm run typecheck` | `tsc --noEmit` (frontend) |
| `npm run format` / `format:check` | `ruff format` + `prettier --write`, or the check-only variants |

Backend dependency versions are pinned in `backend/requirements.lock` (generated from `pip freeze` of a known-good venv); `requirements.txt` stays the loose, human-edited input. Pre-commit hooks run the lint/format checks before each commit — set them up once with `backend\.venv\Scripts\pre-commit.exe install`.

## Current scope

Implemented slices include authentication, Admin account provisioning and management, project creation and membership management, project-scoped task creation and assignment, task status and review workflows, database migrations, and the health endpoint. Admins can search and paginate the People and Projects directories, create accounts and projects, change user roles, manage project assignments, activate or deactivate accounts, and manage tasks. Managers see their assigned projects, create and assign project tasks, and review submissions. Members see only their assigned tasks, start or resume work, and submit tasks for review.

The backend API now also exposes the full Phase 6 surface under `/api/v1`: project detail/lifecycle (status transitions, update, delete), task deletion and list sorting, task comments, file attachments (multipart upload/download), GitHub evidence links, in-app notifications (list + mark-read), project/task activity feeds, Admin audit-log reads, per-project analytics (progress, counts by status/priority, overdue, contributions), and self-service profile updates. The generated API contract is committed at [`docs/openapi.json`](./docs/openapi.json) and the status-code policy is documented in [`docs/http-semantics.md`](./docs/http-semantics.md).

The frontend keeps access tokens in memory and uses the HttpOnly refresh cookie to renew an expired access token after an authenticated request receives a 401. It retries that request once. The frontend UI for comments, GitHub evidence, attachments, notifications, and project analytics remains planned (Phase 7).

Admin-provisioned accounts must change their initial password through `POST /api/v1/auth/change-password` before using Admin-only operations. Changing a password revokes active sessions, so the user signs in again afterward.
