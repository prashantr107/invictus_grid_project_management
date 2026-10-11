"""Observability tests: request-ID propagation, structured access logging, and
the database-aware health/readiness endpoint.
"""

import logging

from fastapi.testclient import TestClient

from app.main import app

from support import auth_headers


def test_request_id_header_is_echoed(world):
    resp = TestClient(app).get("/api/v1/health/live", headers={"X-Request-ID": "corr-123"})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == "corr-123"


def test_request_id_is_generated_when_absent(world):
    resp = TestClient(app).get("/api/v1/health/live")
    assert resp.headers.get("X-Request-ID")


def test_health_reports_database_connectivity(world):
    resp = TestClient(app).get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


def test_error_response_has_consistent_shape(world):
    resp = TestClient(app).get(
        "/api/v1/tasks/00000000-0000-0000-0000-000000000000", headers=auth_headers(world["member_id"])
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "not_found"
    assert isinstance(body["detail"], str)
    assert body["request_id"] == resp.headers["X-Request-ID"]


def test_access_log_records_request_context(world):
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append  # type: ignore[method-assign]
    logger = logging.getLogger("app.access")
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        TestClient(app).get("/api/v1/health/live", headers={"X-Request-ID": "log-42"})
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)

    match = [record for record in records if getattr(record, "request_id", None) == "log-42"]
    assert match, "expected an access log carrying the request ID"
    record = match[0]
    assert record.method == "GET"
    assert record.path == "/api/v1/health/live"
    assert record.status == 200
    assert record.duration_ms >= 0
