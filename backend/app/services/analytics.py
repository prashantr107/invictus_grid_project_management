"""Project analytics/dashboard aggregation (SRS §3.11).

Visibility follows task visibility: any project member or Admin may read the
aggregates for a project they can access. "Overdue" means a task with a due
date in the past that is not yet completed."""

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import User
from app.repositories import analytics as analytics_repo
from app.repositories import projects as projects_repo
from app.schemas import ContributionRead, ProjectAnalytics, TaskPriorityCounts, TaskStatusCounts
from app.services import tasks as tasks_service


def project_analytics(db: Session, actor: User, project_id: UUID) -> ProjectAnalytics:
    tasks_service.project_for_user(db, project_id, actor)
    by_status = analytics_repo.status_counts(db, project_id)
    by_priority = analytics_repo.priority_counts(db, project_id)
    today = date.today()
    return ProjectAnalytics(
        project_id=project_id,
        progress=projects_repo.progress(db, [project_id])[project_id],
        total_tasks=sum(by_status.values()),
        by_status=TaskStatusCounts(**by_status),
        by_priority=TaskPriorityCounts(**by_priority),
        pending_review=by_status.get("PENDING_REVIEW", 0),
        overdue=analytics_repo.overdue_count(db, project_id, today=today),
        contributions=[ContributionRead(**row) for row in analytics_repo.contributions(db, project_id, today=today)],
    )
