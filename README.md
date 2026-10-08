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
# Replace JWT_SECRET_KEY with a unique random secret before starting.
alembic upgrade head
python -m app.bootstrap_admin
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; OpenAPI docs are at `/docs`. The health endpoint is `GET /api/v1/health`.

Set `JWT_SECRET_KEY` to a random secret of at least 32 characters. For split-site production deployments, configure `COOKIE_SECURE=true` and `REFRESH_COOKIE_SAMESITE=none`; local HTTP development uses `false` and `lax`.

### Frontend

Requires Node.js 20.19+ or 22.12+. From `frontend/`:

```powershell
npm install
npm run dev
```

The frontend reads its backend base URL from `VITE_API_BASE_URL` (defaults to `http://localhost:8000/api/v1`).

## Current scope

Implemented slices include authentication, Admin account provisioning and management, project creation and membership management, database migrations, the health endpoint, and frontend sign-in and first-login password-change screens. Admins can search and paginate the People and Projects directories, create accounts and projects, change user roles, manage project assignments, and activate or deactivate accounts.

The frontend keeps access tokens in memory and uses the HttpOnly refresh cookie to renew an expired access token after an authenticated request receives a 401. It retries that request once. Manager/member project views, task workflows, and the non-Admin role dashboards are still planned.

Admin-provisioned accounts must change their initial password through `POST /api/v1/auth/change-password` before using Admin-only operations. Changing a password revokes active sessions, so the user signs in again afterward.
