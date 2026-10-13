# HTTP Semantics and Error Policy

This document is the normative reference for status-code usage across the
Invictus Grid API. The generated contract lives in [`docs/openapi.json`](./openapi.json)
(refresh with `npm run backend:openapi`).

## Response envelope

Every error response is a JSON object with a stable shape:

```json
{ "error": { "code": "not_found", "message": "Project not found" } }
```

| Code | HTTP | Meaning |
| --- | --- | --- |
| `validation_error` | 422 | Request body/params failed schema or field validation |
| `authentication_required` | 401 | Missing, malformed, expired, or revoked credentials |
| `forbidden` | 403 | Authenticated, but the capability for this route is not held |
| `not_found` | 404 | Resource missing **or** concealed by object-level authorization |
| `conflict` | 409 | State conflict (invalid transition, duplicate, archived project) |
| `bad_request` | 400 | Semantically invalid self-service action (e.g. wrong current password) |
| `rate_limited` | 429 | Request throttled |
| `internal_error` | 500 | Unhandled server error |
| `service_unavailable` | 503 | Dependency (database) unhealthy |

## Success status codes

- `200 OK` — reads and updates.
- `201 Created` — resource creation (`POST /projects`, `POST /projects/{id}/tasks`,
  comments, attachments, GitHub links, `POST /tasks/{id}/review`).
- `204 No Content` — deletions (`DELETE /projects/{id}`, `DELETE /tasks/{id}`,
  `DELETE /comments/{id}`, `DELETE /attachments/{id}`).

## The 404-vs-403 policy

The rule is deliberate and uniform:

1. **401** when there is no valid authentication.
2. **403** when the caller *can see the resource* but lacks the **capability**
   required by the route (e.g. a project Member submitting a review, or any
   non-Admin calling an Admin-only route).
3. **404** when authorization depends on an **object the caller may not be
   allowed to know exists**. Returning 403 here would let an attacker probe IDs
   (IDOR/BOLA). Concretely: any project, task, comment, attachment, GitHub link,
   activity feed, or notification that is not visible to the caller resolves to
   404, whether it exists or not.

This means the same "not a member" condition is reported differently depending
on whether the resource itself is the target:

| Situation | Result |
| --- | --- |
| Member requests their own project's members list | 403 (capability denied) |
| Manager of an *unrelated* project requests that list | 404 (project concealed) |
| Member requests a task assigned to someone else | 404 (task concealed) |
| Member attempts a manager-only task mutation route | 403 (capability denied) |
| Non-Admin calls `GET /audit-logs` | 403 (capability denied) |
| Non-recipient marks someone else's notification read | 404 (notification concealed) |

Admin-only list/create routes (`/users`, `/projects`, `/audit-logs`) return 403
rather than 404 because the route itself is capability-gated and exposes no
per-object secret.

## Where this is enforced

- `backend/app/api/deps.py` / `backend/app/core/permissions.py` — role gates that
  raise `ForbiddenError` (403).
- `backend/app/services/*` — object resolution helpers that raise `NotFoundError`
  (404) when the caller is neither a member nor a manager of the target project.
- `backend/app/core/errors.py` — maps domain exceptions to the envelope above.

## Where this is tested

- `backend/tests/test_authorization_matrix.py` — full actor × route matrix
  (401/403/404 per endpoint).
- `backend/tests/test_auth_hardening.py` — 401 lifecycle (revoked/expired
  sessions, forced password change).
- `backend/tests/test_notifications_api.py` — 404 concealment of other users'
  notifications.
- `backend/tests/test_activity_audit_api.py` — activity 404s vs. audit 403.
- `backend/tests/test_projects_lifecycle_api.py`,
  `backend/tests/test_task_delete_sort.py` — object-level 404 vs. capability 403.
