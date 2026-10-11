"""C5 regression tests: role changes must not break project access.

Covers the "decouple + reconcile" decision (see
docs/adr/0001-role-changes-and-project-access-c5.md):
- `project_members.role` is the source of truth for project-level authorization.
- Promotion MEMBER -> MANAGER preserves existing memberships (no access loss, no
  automatic manager authority).
- Demotion MANAGER -> MEMBER downgrades MANAGER memberships to MEMBER (no
  privilege escalation) and is audited.

Run from backend/:  python -m pytest tests/test_c5_authorization.py -v
"""

from fastapi.testclient import TestClient

from app.main import app
from app.models import AuditLog, ProjectMember, Role

from support import SessionLocal, auth_headers


def test_promotion_preserves_member_access_to_own_tasks(world):
    member_id = world["member_id"]
    admin_id = world["admin_id"]
    project_id = world["project_id"]
    task_id = world["task_id"]

    client = TestClient(app)
    change = client.patch(f"/api/v1/users/{member_id}/role", headers=auth_headers(admin_id), json={"role": "MANAGER"})
    assert change.status_code == 200, change.text

    headers = auth_headers(member_id)

    tasks = client.get(f"/api/v1/projects/{project_id}/tasks", headers=headers)
    assert tasks.status_code == 200, tasks.text
    assert [t["id"] for t in tasks.json()["items"]] == [str(task_id)]

    started = client.patch(f"/api/v1/tasks/{task_id}/status", headers=headers, json={"status": "IN_PROGRESS"})
    assert started.status_code == 200, started.text
    submitted = client.post(f"/api/v1/tasks/{task_id}/submit-review", headers=headers)
    assert submitted.status_code == 200, submitted.text


def test_promotion_does_not_grant_manager_authority(world):
    member_id = world["member_id"]
    admin_id = world["admin_id"]
    project_id = world["project_id"]

    client = TestClient(app)
    change = client.patch(f"/api/v1/users/{member_id}/role", headers=auth_headers(admin_id), json={"role": "MANAGER"})
    assert change.status_code == 200, change.text

    headers = auth_headers(member_id)

    build = client.post(f"/api/v1/projects/{project_id}/tasks", headers=headers, json={"title": "Should fail"})
    assert build.status_code == 404, build.text
    members = client.get(f"/api/v1/projects/{project_id}/members", headers=headers)
    assert members.status_code == 403, members.text


def test_demotion_reconciles_memberships_and_blocks_escalation(world):
    manager_id = world["manager_id"]
    admin_id = world["admin_id"]
    project_id = world["project_id"]
    task_id = world["task_id"]

    client = TestClient(app)
    change = client.patch(f"/api/v1/users/{manager_id}/role", headers=auth_headers(admin_id), json={"role": "MEMBER"})
    assert change.status_code == 200, change.text

    with SessionLocal() as db:
        membership = db.get(ProjectMember, (project_id, manager_id))
        assert membership is not None
        assert membership.role == Role.MEMBER.value

    headers = auth_headers(manager_id)
    build = client.post(f"/api/v1/projects/{project_id}/tasks", headers=headers, json={"title": "Should fail"})
    assert build.status_code == 404, build.text
    members = client.get(f"/api/v1/projects/{project_id}/members", headers=headers)
    assert members.status_code == 403, members.text
    review = client.post(f"/api/v1/tasks/{task_id}/review", headers=headers, json={"decision": "APPROVED"})
    assert review.status_code == 404, review.text


def test_manager_account_keeps_manager_authority(world):
    manager_id = world["manager_id"]
    project_id = world["project_id"]

    client = TestClient(app)
    headers = auth_headers(manager_id)

    build = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        headers=headers,
        json={"title": "Managed work", "assignee_id": str(world["member_id"])},
    )
    assert build.status_code == 201, build.text
    members = client.get(f"/api/v1/projects/{project_id}/members", headers=headers)
    assert members.status_code == 200, members.text


def test_demotion_is_audit_logged(world):
    manager_id = world["manager_id"]
    admin_id = world["admin_id"]

    client = TestClient(app)
    headers = auth_headers(admin_id)
    resp = client.patch(f"/api/v1/users/{manager_id}/role", headers=headers, json={"role": "MEMBER"})
    assert resp.status_code == 200, resp.text

    with SessionLocal() as db:
        log = db.query(AuditLog).filter_by(action="user.role_changed").order_by(AuditLog.created_at.desc()).first()
        assert log is not None
        assert log.details["new"] == "MEMBER"
        assert log.details["previous"] == "MANAGER"
        assert len(log.details["memberships_downgraded_to_member"]) == 1
