from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models import TaskPriority, TaskStatus, User
from app.schemas import (
    TaskCreate,
    TaskPage,
    TaskRead,
    TaskReviewCreate,
    TaskReviewRead,
    TaskSort,
    TaskStatusUpdate,
    TaskUpdate,
)
from app.services import tasks as tasks_service

router = APIRouter(tags=["tasks"])


@router.post("/projects/{project_id}/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: UUID,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TaskRead:
    return tasks_service.create_task(db, actor, project_id, payload)


@router.get("/projects/{project_id}/tasks", response_model=TaskPage)
def list_project_tasks(
    project_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = None,
    sort: TaskSort | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TaskPage:
    return tasks_service.list_tasks(
        db,
        actor,
        project_id,
        offset=offset,
        limit=limit,
        status=status_filter,
        priority=priority,
        sort=sort,
    )


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: UUID, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> TaskRead:
    return tasks_service.get_task(db, actor, task_id)


@router.get("/tasks/{task_id}/reviews", response_model=list[TaskReviewRead])
def list_task_reviews(
    task_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> list[TaskReviewRead]:
    return tasks_service.list_reviews(db, actor, task_id)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TaskRead:
    return tasks_service.update_task(db, actor, task_id, payload)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> None:
    tasks_service.delete_task(db, actor, task_id)


@router.patch("/tasks/{task_id}/status", response_model=TaskRead)
def update_task_status(
    task_id: UUID,
    payload: TaskStatusUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TaskRead:
    return tasks_service.start_task(db, actor, task_id, payload)


@router.post("/tasks/{task_id}/submit-review", response_model=TaskRead)
def submit_task_for_review(
    task_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TaskRead:
    return tasks_service.submit_for_review(db, actor, task_id)


@router.post("/tasks/{task_id}/review", response_model=TaskReviewRead, status_code=status.HTTP_201_CREATED)
def review_task(
    task_id: UUID,
    payload: TaskReviewCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TaskReviewRead:
    return tasks_service.review_task(db, actor, task_id, payload)
