"""Task collaboration: comments, attachments, and GitHub evidence links
(SRS §3.7–3.9).

All three resources are scoped to a task the actor is allowed to see
(`tasks_service.task_for_user`), so Members can only touch their own tasks.
Deleting is limited to the author/uploader/submitter plus Admins and the
project's Managers. Uploads are validated by MIME type and size before the
bytes reach the storage backend."""

from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.core.storage import Storage
from app.models import ActivityLog, Attachment, Comment, GithubLink, Project, Role, Task, User
from app.repositories import attachments as attachments_repo
from app.repositories import comments as comments_repo
from app.repositories import github_links as github_repo
from app.repositories import tasks as tasks_repo
from app.schemas import AttachmentRead, CommentCreate, CommentRead, GithubLinkCreate, GithubLinkRead
from app.services import permissions
from app.services import tasks as tasks_service

ALLOWED_CONTENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def _safe_name(filename: str | None) -> str:
    name = Path(filename or "file").name.strip() or "file"
    return name[:255]


def _is_moderator(db: Session, task: Task, actor: User) -> bool:
    return permissions.project_role_for_user(db, task.project_id, actor) in (Role.ADMIN.value, Role.MANAGER.value)


def _activity(db: Session, task: Task, actor: User, action: str, details: dict) -> None:
    db.add(ActivityLog(project_id=task.project_id, task_id=task.id, actor_id=actor.id, action=action, details=details))


# --- comments ---------------------------------------------------------------


def _comment_read(comment: Comment, author_name: str | None) -> CommentRead:
    return CommentRead(
        id=comment.id,
        task_id=comment.task_id,
        author_id=comment.author_id,
        author_name=author_name,
        body=comment.body,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


def list_comments(db: Session, actor: User, task_id: UUID) -> list[CommentRead]:
    task, _ = tasks_service.task_for_user(db, task_id, actor)
    comments = comments_repo.list_for_task(db, task.id)
    names = tasks_repo.names(db, {comment.author_id for comment in comments})
    return [_comment_read(comment, names.get(comment.author_id)) for comment in comments]


def create_comment(db: Session, actor: User, task_id: UUID, payload: CommentCreate) -> CommentRead:
    task, _ = tasks_service.task_for_user(db, task_id, actor)
    comment = Comment(task_id=task.id, author_id=actor.id, body=payload.body)
    db.add(comment)
    db.flush()
    _activity(db, task, actor, "comment.added", {"comment_id": str(comment.id)})
    db.commit()
    db.refresh(comment)
    return _comment_read(comment, actor.full_name)


def _comment_for_actor(db: Session, actor: User, task_id: UUID, comment_id: UUID) -> tuple[Comment, Project]:
    task, _ = tasks_service.task_for_user(db, task_id, actor)
    comment = comments_repo.get(db, comment_id)
    if comment is None or comment.task_id != task.id:
        raise NotFoundError("Comment not found")
    if comment.author_id != actor.id and not _is_moderator(db, task, actor):
        raise ForbiddenError("Only the author or a project Manager can change this comment")
    return comment, task


def update_comment(db: Session, actor: User, task_id: UUID, comment_id: UUID, payload: CommentCreate) -> CommentRead:
    comment, task = _comment_for_actor(db, actor, task_id, comment_id)
    comment.body = payload.body
    _activity(db, task, actor, "comment.edited", {"comment_id": str(comment.id)})
    db.commit()
    db.refresh(comment)
    names = tasks_repo.names(db, {comment.author_id})
    return _comment_read(comment, names.get(comment.author_id))


def delete_comment(db: Session, actor: User, task_id: UUID, comment_id: UUID) -> None:
    comment, task = _comment_for_actor(db, actor, task_id, comment_id)
    _activity(db, task, actor, "comment.deleted", {"comment_id": str(comment.id)})
    db.delete(comment)
    db.commit()


# --- attachments ------------------------------------------------------------


def _attachment_read(attachment: Attachment, uploader_name: str | None) -> AttachmentRead:
    return AttachmentRead(
        id=attachment.id,
        task_id=attachment.task_id,
        uploader_id=attachment.uploader_id,
        uploader_name=uploader_name,
        original_name=attachment.original_name,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        created_at=attachment.created_at,
    )


def list_attachments(db: Session, actor: User, task_id: UUID) -> list[AttachmentRead]:
    task, _ = tasks_service.task_for_user(db, task_id, actor)
    attachments = attachments_repo.list_for_task(db, task.id)
    names = tasks_repo.names(db, {attachment.uploader_id for attachment in attachments})
    return [_attachment_read(attachment, names.get(attachment.uploader_id)) for attachment in attachments]


def create_attachment(db: Session, actor: User, task_id: UUID, upload: UploadFile, storage: Storage) -> AttachmentRead:
    task, _ = tasks_service.task_for_user(db, task_id, actor)
    content_type = (upload.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError("Only PNG, JPG, JPEG, PDF, and DOCX files are allowed")
    max_bytes = get_settings().attachment_max_bytes
    data = upload.file.read(max_bytes + 1)
    if not data:
        raise ValidationError("The uploaded file is empty")
    if len(data) > max_bytes:
        raise ValidationError(f"File exceeds the {max_bytes // (1024 * 1024)} MB limit")
    original_name = _safe_name(upload.filename)
    storage_key = storage.save(data, suffix=ALLOWED_CONTENT_TYPES[content_type])
    attachment = Attachment(
        task_id=task.id,
        uploader_id=actor.id,
        original_name=original_name,
        storage_key=storage_key,
        content_type=content_type,
        size_bytes=len(data),
    )
    db.add(attachment)
    db.flush()
    _activity(db, task, actor, "attachment.added", {"original_name": original_name, "size_bytes": len(data)})
    db.commit()
    db.refresh(attachment)
    return _attachment_read(attachment, actor.full_name)


def _attachment_for_actor(db: Session, actor: User, task_id: UUID, attachment_id: UUID) -> tuple[Attachment, Project]:
    task, _ = tasks_service.task_for_user(db, task_id, actor)
    attachment = attachments_repo.get(db, attachment_id)
    if attachment is None or attachment.task_id != task.id:
        raise NotFoundError("Attachment not found")
    return attachment, task


def download_attachment(
    db: Session, actor: User, task_id: UUID, attachment_id: UUID, storage: Storage
) -> tuple[Attachment, bytes]:
    attachment, _ = _attachment_for_actor(db, actor, task_id, attachment_id)
    try:
        data = storage.read(attachment.storage_key)
    except FileNotFoundError:
        raise NotFoundError("Attachment file is missing") from None
    return attachment, data


def delete_attachment(db: Session, actor: User, task_id: UUID, attachment_id: UUID, storage: Storage) -> None:
    attachment, task = _attachment_for_actor(db, actor, task_id, attachment_id)
    if attachment.uploader_id != actor.id and not _is_moderator(db, task, actor):
        raise ForbiddenError("Only the uploader or a project Manager can delete this attachment")
    storage.delete(attachment.storage_key)
    _activity(db, task, actor, "attachment.deleted", {"original_name": attachment.original_name})
    db.delete(attachment)
    db.commit()


# --- GitHub evidence --------------------------------------------------------


def _github_read(link: GithubLink, submitter_name: str | None) -> GithubLinkRead:
    return GithubLinkRead(
        id=link.id,
        task_id=link.task_id,
        submitted_by=link.submitted_by,
        submitter_name=submitter_name,
        url=link.url,
        evidence_type=link.evidence_type,
        created_at=link.created_at,
    )


def list_github_links(db: Session, actor: User, task_id: UUID) -> list[GithubLinkRead]:
    task, _ = tasks_service.task_for_user(db, task_id, actor)
    links = github_repo.list_for_task(db, task.id)
    names = tasks_repo.names(db, {link.submitted_by for link in links})
    return [_github_read(link, names.get(link.submitted_by)) for link in links]


def create_github_link(db: Session, actor: User, task_id: UUID, payload: GithubLinkCreate) -> GithubLinkRead:
    task, _ = tasks_service.task_for_user(db, task_id, actor)
    link = GithubLink(
        task_id=task.id,
        submitted_by=actor.id,
        url=payload.url,
        evidence_type=payload.evidence_type.value,
    )
    db.add(link)
    db.flush()
    _activity(db, task, actor, "evidence.added", {"url": payload.url, "evidence_type": payload.evidence_type.value})
    db.commit()
    db.refresh(link)
    return _github_read(link, actor.full_name)


def delete_github_link(db: Session, actor: User, task_id: UUID, link_id: UUID) -> None:
    task, _ = tasks_service.task_for_user(db, task_id, actor)
    link = github_repo.get(db, link_id)
    if link is None or link.task_id != task.id:
        raise NotFoundError("Evidence link not found")
    if link.submitted_by != actor.id and not _is_moderator(db, task, actor):
        raise ForbiddenError("Only the submitter or a project Manager can delete this link")
    _activity(db, task, actor, "evidence.deleted", {"url": link.url})
    db.delete(link)
    db.commit()
