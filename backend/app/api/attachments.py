from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.storage import Storage, get_storage
from app.db.session import get_db
from app.models import User
from app.schemas import AttachmentRead
from app.services import collaboration as collaboration_service

router = APIRouter(prefix="/tasks/{task_id}/attachments", tags=["attachments"])


@router.get("", response_model=list[AttachmentRead])
def list_attachments(
    task_id: UUID, db: Session = Depends(get_db), actor: User = Depends(get_current_user)
) -> list[AttachmentRead]:
    return collaboration_service.list_attachments(db, actor, task_id)


@router.post("", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
def upload_attachment(
    task_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    storage: Storage = Depends(get_storage),
) -> AttachmentRead:
    return collaboration_service.create_attachment(db, actor, task_id, file, storage)


@router.get("/{attachment_id}")
def download_attachment(
    task_id: UUID,
    attachment_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    storage: Storage = Depends(get_storage),
) -> Response:
    attachment, data = collaboration_service.download_attachment(db, actor, task_id, attachment_id, storage)
    disposition = f"attachment; filename*=UTF-8''{quote(attachment.original_name)}"
    return Response(
        content=data,
        media_type=attachment.content_type,
        headers={"Content-Disposition": disposition},
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    task_id: UUID,
    attachment_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    storage: Storage = Depends(get_storage),
) -> None:
    collaboration_service.delete_attachment(db, actor, task_id, attachment_id, storage)
