# ADR-0001: Role changes and project access (C5)

- **Status:** Accepted
- **Date:** 2026-10-11
- **Relates to:** `PROJECT_CHECKLIST.md` Phase 2 defect C5, SRS §3.2 (FR-RBAC) / §3.4 (FR-PROJ)
- **Source-of-truth guard:** PRD §24 / TRD §22 — the task lifecycle, roles, and access rules are changed only with an explicit product decision; this ADR records that decision.

## Context

`PATCH /api/v1/users/{id}/role` (`backend/app/api/users.py`) updated only `users.role`. Authorization checks in `backend/app/api/projects.py` (`list_projects`, `get_project_members`) and `backend/app/api/tasks.py` (`project_for_user`, `task_for_user`, `manager_can_access_task`) compared `project_members.role == users.role` and required them to be identical.

Because the two columns were forced to match manually, a role change without an identical membership change broke the system:

- **Promotion MEMBER → MANAGER:** the user's `project_members` rows still had `role = MEMBER`, so `membership.role != users.role` made every project (and the user's own assigned tasks) 404.
- **Demotion MANAGER → MEMBER:** `project_members` rows still had `role = MANAGER`, so the user retained stale manager membership — an access-control ambiguity and a latent privilege-escalation risk.

## Decision

Decouple project access from the duplicated role comparison. **`project_members.role` is the single source of truth for a user's role inside a project.** `users.role` has only two effects:

1. **ADMIN** grants global access (no membership required).
2. It acts as a **capability cap**, so a demoted account can never act above its account role.

Effective project role (`backend/app/api/authorization.py`:

| Account role (`users.role`) | Membership role (`project_members.role`) | Effective project role |
|---|---|---|
| ADMIN | — | ADMIN (global) |
| MANAGER | MANAGER | MANAGER |
| MANAGER | MEMBER | MEMBER |
| MEMBER | MEMBER | MEMBER |
| MEMBER | MANAGER | MEMBER (cap applies; stale row is neutralized) |
| any | none | no access |

Reconciliation performed in `update_user_role` in the same transaction as the role change, and audit-logged:

- **Demotion to MEMBER:** every `project_members` row with `role = MANAGER` is downgraded to `MEMBER` (so stale manager authority is truly removed, not just ignored).
- **Promotion to MANAGER:** memberships are left untouched. Promoting the account role does **not** grant manager authority on any project; an Admin grants per-project manager authority explicitly via `PUT /projects/{id}/members`.

## Consequences

- **Promotion no longer breaks access** — existing memberships and assigned tasks remain visible and actionable (the user keeps acting as the project role their membership grants, i.e. MEMBER).
- **Promotion grants no silent privileges** — a promoted user cannot create tasks, review, or view membership until an Admin changes the per-project membership role.
- **Demotion takes effect immediately** — the manager's memberships are rewritten to MEMBER, so manager powers are gone even where stale rows could have remained.
- **No schema change.** Behavior only.
- **Assignee constraint unchanged:** `validate_assignee` still requires the account role `MEMBER`, so a promoted (now MANAGER-account) user can finish their previously assigned tasks but cannot be assigned new ones until explicitly reassigned.
- Authorization helpers are centralized (`app/api/authorization.py`) so routers stay thin and the rule is testable.

## Implementation summary

- `backend/app/api/authorization.py` (new): `effective_project_role()` (pure) + `project_role_for_user()` (DB-backed).
- `backend/app/api/projects.py`: `list_projects` scopes by membership existence only; `get_project_members` uses the effective role.
- `backend/app/api/tasks.py`: `project_for_user`, `task_for_user`, `list_project_tasks`, `update_task_status`, `submit_task_for_review`, `manager_can_access_task` all use the effective role; the executor guards allow an effective MEMBER assignee to work their own tasks.
- `backend/app/api/users.py`: `update_user_role` reconciles MANAGER memberships on demotion and records them in the audit `details`.
- `backend/tests/test_c5_authorization.py`: 5 regression tests (promotion preserves access, promotion grants no manager authority, demotion reconciles + blocks escalation, manager authority preserved, demotion audited). `python -m pytest tests/test_c5_authorization.py` → 5 passed.

## Migration / backfill plan

No schema migration is required. A one-time data backfill is recommended for any legacy rows where a MEMBER account still holds a MANAGER membership (e.g. left over from pre-decouple demotions):

```sql
UPDATE project_members AS pm
SET role = 'MEMBER'
FROM users AS u
WHERE u.id = pm.user_id
  AND u.role = 'MEMBER'
  AND pm.role = 'MANAGER';
```

Run against the target database as a controlled release step; add it as an Alembic data migration only if the affected set is expected to be non-empty.

## Alternatives considered

**Cascade membership roles** (rewrite all `project_members` rows to the new account role on every change) was rejected: promoting MEMBER → MANAGER would silently make the user a Manager on *every* project they belong to, and demoting could orphan assignments — worse than the original defect.
