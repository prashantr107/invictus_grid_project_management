"""The audit trail must retain a typed reference to its target.

`audit_logs.target_id` was `String(80)`; migration 0005 retypes it to UUID and
the write paths pass UUID objects (not `str(...)`).
"""

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import AuditLog

from support import SessionLocal, auth_headers


def test_audit_target_id_is_uuid(world):
    client = TestClient(app)
    changed = client.patch(
        f"/api/v1/users/{world['member_id']}/role",
        headers=auth_headers(world["admin_id"]),
        json={"role": "MANAGER"},
    )
    assert changed.status_code == 200, changed.text

    with SessionLocal() as db:
        log = db.scalars(select(AuditLog).where(AuditLog.action == "user.role_changed")).first()
        assert log is not None
        assert isinstance(log.target_id, UUID)
        assert log.target_id == world["member_id"]
