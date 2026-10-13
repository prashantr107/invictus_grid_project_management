"""Comments, attachments, and GitHub evidence endpoints (SRS §3.7-3.9)."""

import pytest
from fastapi.testclient import TestClient

from app.core.storage import LocalStorage, get_storage
from app.main import app

from support import auth_headers


@pytest.fixture
def storage(tmp_path):
    store = LocalStorage(tmp_path)
    app.dependency_overrides[get_storage] = lambda: store
    yield store
    app.dependency_overrides.pop(get_storage, None)


def _client():
    return TestClient(app)


# --- comments ---------------------------------------------------------------


def test_member_can_comment_on_own_task(world):
    client = _client()
    created = client.post(
        f"/api/v1/tasks/{world['task_id']}/comments",
        headers=auth_headers(world["member_id"]),
        json={"body": "Working on it"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["body"] == "Working on it"
    assert body["author_id"] == str(world["member_id"])

    listing = client.get(f"/api/v1/tasks/{world['task_id']}/comments", headers=auth_headers(world["member_id"]))
    assert listing.status_code == 200
    assert [c["body"] for c in listing.json()] == ["Working on it"]


def test_peer_member_cannot_comment_on_another_users_task(world):
    resp = _client().post(
        f"/api/v1/tasks/{world['task_id']}/comments",
        headers=auth_headers(world["peer_member_id"]),
        json={"body": "Sneaky"},
    )
    assert resp.status_code == 404, resp.text


def test_comment_edit_and_delete_rules(world):
    client = _client()
    comment_id = client.post(
        f"/api/v1/tasks/{world['task_id']}/comments",
        headers=auth_headers(world["member_id"]),
        json={"body": "first"},
    ).json()["id"]

    manager_edit = client.patch(
        f"/api/v1/tasks/{world['task_id']}/comments/{comment_id}",
        headers=auth_headers(world["manager_id"]),
        json={"body": "manager edit"},
    )
    assert manager_edit.status_code == 200, manager_edit.text

    peer_edit = client.patch(
        f"/api/v1/tasks/{world['task_id']}/comments/{comment_id}",
        headers=auth_headers(world["peer_member_id"]),
        json={"body": "peer edit"},
    )
    assert peer_edit.status_code == 404, peer_edit.text

    deleted = client.delete(
        f"/api/v1/tasks/{world['task_id']}/comments/{comment_id}", headers=auth_headers(world["member_id"])
    )
    assert deleted.status_code == 204, deleted.text
    assert (
        client.get(f"/api/v1/tasks/{world['task_id']}/comments", headers=auth_headers(world["member_id"])).json() == []
    )


def test_blank_comment_rejected(world):
    resp = _client().post(
        f"/api/v1/tasks/{world['task_id']}/comments",
        headers=auth_headers(world["member_id"]),
        json={"body": "   "},
    )
    assert resp.status_code == 422, resp.text


# --- attachments ------------------------------------------------------------


def test_attachment_upload_list_download_delete(world, storage):
    client = _client()
    upload = client.post(
        f"/api/v1/tasks/{world['task_id']}/attachments",
        headers=auth_headers(world["member_id"]),
        files={"file": ("report.pdf", b"%PDF-1.4 hello", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    attachment = upload.json()
    assert attachment["original_name"] == "report.pdf"
    assert attachment["size_bytes"] == 14

    listing = client.get(f"/api/v1/tasks/{world['task_id']}/attachments", headers=auth_headers(world["member_id"]))
    assert [a["id"] for a in listing.json()] == [attachment["id"]]

    download = client.get(
        f"/api/v1/tasks/{world['task_id']}/attachments/{attachment['id']}",
        headers=auth_headers(world["member_id"]),
    )
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4 hello"
    assert download.headers["content-type"].startswith("application/pdf")

    deleted = client.delete(
        f"/api/v1/tasks/{world['task_id']}/attachments/{attachment['id']}",
        headers=auth_headers(world["member_id"]),
    )
    assert deleted.status_code == 204, deleted.text


def test_attachment_rejects_disallowed_type(world, storage):
    resp = _client().post(
        f"/api/v1/tasks/{world['task_id']}/attachments",
        headers=auth_headers(world["member_id"]),
        files={"file": ("run.exe", b"MZ", "application/x-msdownload")},
    )
    assert resp.status_code == 422, resp.text


def test_attachment_rejects_oversize(world, storage, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "attachment_max_bytes", 4)
    resp = _client().post(
        f"/api/v1/tasks/{world['task_id']}/attachments",
        headers=auth_headers(world["member_id"]),
        files={"file": ("big.pdf", b"%PDF-1.4 too big", "application/pdf")},
    )
    assert resp.status_code == 422, resp.text


def test_peer_member_cannot_touch_another_users_attachment(world, storage):
    client = _client()
    attachment_id = client.post(
        f"/api/v1/tasks/{world['task_id']}/attachments",
        headers=auth_headers(world["member_id"]),
        files={"file": ("a.pdf", b"%PDF", "application/pdf")},
    ).json()["id"]
    resp = client.delete(
        f"/api/v1/tasks/{world['task_id']}/attachments/{attachment_id}",
        headers=auth_headers(world["peer_member_id"]),
    )
    assert resp.status_code == 404, resp.text


# --- GitHub evidence --------------------------------------------------------


def test_github_evidence_create_list_delete(world):
    client = _client()
    created = client.post(
        f"/api/v1/tasks/{world['task_id']}/github-links",
        headers=auth_headers(world["member_id"]),
        json={"url": "https://github.com/invictus/repo/pull/1", "evidence_type": "PULL_REQUEST"},
    )
    assert created.status_code == 201, created.text
    link = created.json()
    assert link["evidence_type"] == "PULL_REQUEST"

    listing = client.get(f"/api/v1/tasks/{world['task_id']}/github-links", headers=auth_headers(world["manager_id"]))
    assert [item["id"] for item in listing.json()] == [link["id"]]

    manager_delete = client.delete(
        f"/api/v1/tasks/{world['task_id']}/github-links/{link['id']}", headers=auth_headers(world["manager_id"])
    )
    assert manager_delete.status_code == 204, manager_delete.text


def test_github_evidence_rejects_bad_url(world):
    client = _client()
    for bad_url in ("ftp://example.com/x", "https://example.com/x", "https://github.com"):
        resp = client.post(
            f"/api/v1/tasks/{world['task_id']}/github-links",
            headers=auth_headers(world["member_id"]),
            json={"url": bad_url},
        )
        assert resp.status_code == 422, (bad_url, resp.text)


def test_peer_member_cannot_read_evidence(world):
    resp = _client().get(
        f"/api/v1/tasks/{world['task_id']}/github-links", headers=auth_headers(world["peer_member_id"])
    )
    assert resp.status_code == 404, resp.text
