"""Schema + integrity tests for the collaboration tables (comments, attachments,
GitHub evidence, notifications) added in migration 0004.

Run from backend/:  python -m pytest tests/test_collaboration_schema.py -v
"""

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models import Attachment, Comment, GithubLink, Notification
from support import SessionLocal, TEST_DB

COLLABORATION_TABLES = {"comments", "attachments", "github_links", "notifications"}


def test_collaboration_tables_exist():
    assert COLLABORATION_TABLES <= set(inspect(TEST_DB).get_table_names())


def test_attachment_storage_key_has_unique_index():
    index = next(i for i in inspect(TEST_DB).get_indexes("attachments") if i["name"] == "ix_attachments_storage_key")
    assert index["unique"]


def test_comment_persists_with_author_and_timestamp(world):
    with SessionLocal() as db:
        comment = Comment(task_id=world["task_id"], author_id=world["member_id"], body="Looks good")
        db.add(comment)
        db.commit()
        db.refresh(comment)
        assert comment.created_at is not None
        assert comment.body == "Looks good"


def test_notification_defaults_to_unread(world):
    with SessionLocal() as db:
        note = Notification(recipient_id=world["member_id"], type="TASK_ASSIGNED", task_id=world["task_id"])
        db.add(note)
        db.commit()
        db.refresh(note)
        assert note.is_read is False
        assert note.read_at is None


def test_notification_rejects_unknown_type(world):
    with SessionLocal() as db:
        db.add(Notification(recipient_id=world["member_id"], type="NOT_A_REAL_TYPE"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_attachment_rejects_non_unique_storage_key(world):
    with SessionLocal() as db:
        db.add(
            Attachment(
                task_id=world["task_id"],
                uploader_id=world["member_id"],
                original_name="a.png",
                storage_key="att-1",
                content_type="image/png",
                size_bytes=10,
            )
        )
        db.commit()

    with SessionLocal() as db:
        db.add(
            Attachment(
                task_id=world["task_id"],
                uploader_id=world["member_id"],
                original_name="b.png",
                storage_key="att-1",
                content_type="image/png",
                size_bytes=20,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_attachment_rejects_unsupported_content_type(world):
    with SessionLocal() as db:
        db.add(
            Attachment(
                task_id=world["task_id"],
                uploader_id=world["member_id"],
                original_name="run.exe",
                storage_key="att-exe",
                content_type="application/x-msdownload",
                size_bytes=10,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_github_link_rejects_non_http_url(world):
    with SessionLocal() as db:
        db.add(
            GithubLink(
                task_id=world["task_id"],
                submitted_by=world["member_id"],
                url="ftp://example.com/repo",
                evidence_type="REPOSITORY",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_github_link_accepts_well_formed_https_url(world):
    with SessionLocal() as db:
        link = GithubLink(
            task_id=world["task_id"],
            submitted_by=world["member_id"],
            url="https://github.com/invictusgrid/workspace/pull/1",
            evidence_type="PULL_REQUEST",
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        assert link.created_at is not None
