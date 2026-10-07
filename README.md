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
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; OpenAPI docs are at `/docs`. The health endpoint is `GET /api/v1/health`.

### Frontend

Requires Node.js 20+. From `frontend/`:

```powershell
npm install
npm run dev
```

The frontend reads its backend base URL from `VITE_API_BASE_URL` (defaults to `http://localhost:8000/api/v1`).

## Current scope

This is the application foundation only. Authentication, domain models, migrations, and product workflows will be added in subsequent implementation slices, following the approved requirements.
