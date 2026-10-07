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

Requires Node.js 20+. From `frontend/`:

```powershell
npm install
npm run dev
```

The frontend reads its backend base URL from `VITE_API_BASE_URL` (defaults to `http://localhost:8000/api/v1`).

## Current scope

The foundation includes authentication, Admin account provisioning, initial database migrations, and the health endpoint. Project/task workflows, frontend sign-in screens, and the remaining product modules are planned for later implementation slices.

Admin-provisioned accounts must change their initial password through `POST /api/v1/auth/change-password` before using Admin-only operations. Changing a password revokes active sessions, so the user signs in again afterward.
