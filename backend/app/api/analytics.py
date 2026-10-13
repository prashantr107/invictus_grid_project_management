from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import ProjectAnalytics
from app.services import analytics as analytics_service

router = APIRouter(prefix="/projects/{project_id}/analytics", tags=["analytics"])


@router.get("", response_model=ProjectAnalytics)
def project_analytics(
    project_id: UUID, db: Session = Depends(get_db), actor: User = Depends(get_current_user)
) -> ProjectAnalytics:
    return analytics_service.project_analytics(db, actor, project_id)
