"""Membership replacement: the diff (added/removed/role-changed) is applied and
recorded in the audit log (SRS §3.5, TRD §15).
"""

from fastapi.testclient import TestClient

from app.main import app
from app.models import AuditLog, ProjectMember

from support import SessionLocal, auth_headers


def _latest_membership_audit():
    with SessionLocal() as db:
        return (
            db.query(AuditLog)
            .filter_by(action="project.membership_changed")
            .order_by(AuditLog.created_at.desc())
            .first()
        )


def test_replace_adds_and_removes_members_with_audit(world):
    client = TestClient(app)
    resp = client.put(
        f"/api/v1/projects/{world['project_id']}/members",
        headers=auth_headers(world["admin_id"]),
        json={
            "manager_ids": [str(world["manager_id"])],
            "member_ids": [str(world["member_id"]), str(world["other_member_id"])],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {m["user_id"] for m in body["members"]} == {str(world["member_id"]), str(world["other_member_id"])}
    assert [m["user_id"] for m in body["managers"]] == [str(world["manager_id"])]

    with SessionLocal() as db:
        assert db.get(ProjectMember, (world["project_id"], world["peer_member_id"])) is None
        assert db.get(ProjectMember, (world["project_id"], world["other_member_id"])) is not None

    log = _latest_membership_audit()
    assert str(world["other_member_id"]) in log.details["added"]
    assert str(world["peer_member_id"]) in log.details["removed"]


def test_replace_is_a_noop_when_membership_is_unchanged(world):
    client = TestClient(app)
    # ALPHA currently has manager, member and peer member.
    resp = client.put(
        f"/api/v1/projects/{world['project_id']}/members",
        headers=auth_headers(world["admin_id"]),
        json={
            "manager_ids": [str(world["manager_id"])],
            "member_ids": [str(world["member_id"]), str(world["peer_member_id"])],
        },
    )
    assert resp.status_code == 200, resp.text
    assert _latest_membership_audit() is None
