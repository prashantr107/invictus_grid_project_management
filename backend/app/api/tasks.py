from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models import (
    ActivityLog,
    AuditLog,
    Project,
    ProjectMember,
    Role,
    Task,
    TaskPriority,
    TaskReview,
    TaskStatus,
    TaskType,
    User,
    utc_now,
)
from app.schemas import TaskCreate, TaskPage, TaskRead, TaskReviewCreate, TaskReviewRead, TaskStatusUpdate, TaskUpdate

router = APIRouter(tags=["tasks"])


def project_for_user(db: Session, project_id: UUID, actor: User, *, managers_only: bool = False) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if actor.role == Role.ADMIN.value:
        return project
    membership = db.get(ProjectMember, (project_id, actor.id))
    if membership is None or membership.role != actor.role or (managers_only and membership.role != Role.MANAGER.value):
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def task_for_user(db: Session, task_id: UUID, actor: User) -> tuple[Task, Project]:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    project = project_for_user(db, task.project_id, actor)
    if actor.role == Role.MEMBER.value and task.assignee_id != actor.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task, project


def task_read(task: Task, assignee_name: str | None = None) -> TaskRead:
    return TaskRead(
        id=task.id,
        project_id=task.project_id,
        issue_number=task.issue_number,
        issue_key=task.issue_key,
        title=task.title,
        description=task.description,
        type=task.type,
        priority=task.priority,
        status=task.status,
        created_by=task.created_by,
        assignee_id=task.assignee_id,
        assignee_name=assignee_name,
        due_date=task.due_date,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def activity(db: Session, task: Task, actor: User, action: str, details: dict) -> None:
    db.add(ActivityLog(project_id=task.project_id, task_id=task.id, actor_id=actor.id, action=action, details=details))


def audit(db: Session, task: Task, actor: User, action: str, details: dict) -> None:
    db.add(AuditLog(actor_id=actor.id, action=action, target_type="task", target_id=str(task.id), details=details))


def validate_assignee(db: Session, project_id: UUID, assignee_id: UUID | None) -> User | None:
    if assignee_id is None:
        return None
    user = db.get(User, assignee_id)
    membership = db.get(ProjectMember, (project_id, assignee_id))
    if user is None or not user.is_active or user.role != Role.MEMBER.value or membership is None or membership.role != Role.MEMBER.value:
        raise HTTPException(status_code=422, detail="Assignee must be an active Member of this project")
    return user


def manager_can_access_task(db: Session, task: Task, actor: User) -> None:
    if actor.role == Role.ADMIN.value:
        return
    membership = db.get(ProjectMember, (task.project_id, actor.id))
    if actor.role != Role.MANAGER.value or membership is None or membership.role != Role.MANAGER.value:
        raise HTTPException(status_code=404, detail="Task not found")


@router.post("/projects/{project_id}/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: UUID,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TaskRead:
    project = project_for_user(db, project_id, actor, managers_only=True)
    if actor.role not in (Role.ADMIN.value, Role.MANAGER.value):
        raise HTTPException(status_code=403, detail="Only Admins and project Managers can create tasks")
    if project.status in ("COMPLETED", "ARCHIVED"):
        raise HTTPException(status_code=409, detail="Tasks cannot be created in a completed or archived project")
    validate_assignee(db, project_id, payload.assignee_id)

    # Locking the project row serializes issue-number allocation for concurrent task creation.
    project = db.scalar(select(Project).where(Project.id == project_id).with_for_update())
    next_number = (db.scalar(select(func.max(Task.issue_number)).where(Task.project_id == project_id)) or 0) + 1
    task = Task(
        project_id=project_id,
        issue_number=next_number,
        issue_key=f"{project.key}-{next_number}",
        title=payload.title,
        description=payload.description,
        type=payload.type.value,
        priority=payload.priority.value,
        status=TaskStatus.TODO.value,
        created_by=actor.id,
        assignee_id=payload.assignee_id,
        due_date=payload.due_date,
    )
    db.add(task)
    db.flush()
    activity(db, task, actor, "task.created", {"issue_key": task.issue_key})
    audit(db, task, actor, "task.created", {"project_id": str(project_id), "issue_key": task.issue_key})
    if task.assignee_id:
        activity(db, task, actor, "task.assigned", {"assignee_id": str(task.assignee_id)})
    db.commit()
    db.refresh(task)
    assignee_name = db.scalar(select(User.full_name).where(User.id == task.assignee_id)) if task.assignee_id else None
    return task_read(task, assignee_name)


@router.get("/projects/{project_id}/tasks", response_model=TaskPage)
def list_project_tasks(
    project_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TaskPage:
    project_for_user(db, project_id, actor)
    statement = select(Task).where(Task.project_id == project_id)
    count_statement = select(func.count()).select_from(Task).where(Task.project_id == project_id)
    if actor.role == Role.MEMBER.value:
        statement = statement.where(Task.assignee_id == actor.id)
        count_statement = count_statement.where(Task.assignee_id == actor.id)
    if status_filter:
        statement = statement.where(Task.status == status_filter.value)
        count_statement = count_statement.where(Task.status == status_filter.value)
    if priority:
        statement = statement.where(Task.priority == priority.value)
        count_statement = count_statement.where(Task.priority == priority.value)
    tasks = list(db.scalars(statement.order_by(Task.created_at.desc()).offset(offset).limit(limit)).all())
    total = db.scalar(count_statement) or 0
    assignee_ids = {task.assignee_id for task in tasks if task.assignee_id is not None}
    names = dict(db.execute(select(User.id, User.full_name).where(User.id.in_(assignee_ids))).all()) if assignee_ids else {}
    return TaskPage(items=[task_read(task, names.get(task.assignee_id)) for task in tasks], total=total, offset=offset, limit=limit)


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: UUID, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> TaskRead:
    task, _ = task_for_user(db, task_id, actor)
    assignee_name = db.scalar(select(User.full_name).where(User.id == task.assignee_id)) if task.assignee_id else None
    return task_read(task, assignee_name)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TaskRead:
    task, _ = task_for_user(db, task_id, actor)
    manager_can_access_task(db, task, actor)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one task field must be provided")
    old_assignee = task.assignee_id
    if "assignee_id" in changes:
        validate_assignee(db, task.project_id, changes["assignee_id"])
    before = {key: str(getattr(task, key)) if getattr(task, key) is not None else None for key in changes}
    for key, value in changes.items():
        setattr(task, key, value.value if hasattr(value, "value") else value)
    activity(db, task, actor, "task.updated", {"fields": list(changes.keys())})
    if old_assignee != task.assignee_id:
        activity(db, task, actor, "task.reassigned", {"from": str(old_assignee) if old_assignee else None, "to": str(task.assignee_id) if task.assignee_id else None})
        audit(db, task, actor, "task.reassigned", {"from": str(old_assignee) if old_assignee else None, "to": str(task.assignee_id) if task.assignee_id else None})
    db.commit()
    db.refresh(task)
    assignee_name = db.scalar(select(User.full_name).where(User.id == task.assignee_id)) if task.assignee_id else None
    return task_read(task, assignee_name)


@router.patch("/tasks/{task_id}/status", response_model=TaskRead)
def update_task_status(
    task_id: UUID,
    payload: TaskStatusUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TaskRead:
    task, _ = task_for_user(db, task_id, actor)
    if actor.role != Role.MEMBER.value or task.assignee_id != actor.id:
        raise HTTPException(status_code=403, detail="Only the assigned Member can start or resume this task")
    if payload.status != TaskStatus.IN_PROGRESS or task.status not in (TaskStatus.TODO.value, TaskStatus.CHANGES_REQUIRED.value):
        raise HTTPException(status_code=409, detail=f"Cannot transition task from {task.status} to {payload.status.value}")
    previous = task.status
    task.status = TaskStatus.IN_PROGRESS.value
    task.completed_at = None
    activity(db, task, actor, "task.status_changed", {"from": previous, "to": task.status})
    db.commit()
    db.refresh(task)
    assignee_name = db.scalar(select(User.full_name).where(User.id == task.assignee_id)) if task.assignee_id else None
    return task_read(task, assignee_name)


@router.post("/tasks/{task_id}/submit-review", response_model=TaskRead)
def submit_task_for_review(
    task_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TaskRead:
    task, _ = task_for_user(db, task_id, actor)
    if actor.role != Role.MEMBER.value or task.assignee_id != actor.id:
        raise HTTPException(status_code=403, detail="Only the assigned Member can submit this task")
    if task.status != TaskStatus.IN_PROGRESS.value:
        raise HTTPException(status_code=409, detail="Only an in-progress task can be submitted for review")
    task.status = TaskStatus.PENDING_REVIEW.value
    activity(db, task, actor, "task.submitted_for_review", {})
    db.commit()
    db.refresh(task)
    assignee_name = db.scalar(select(User.full_name).where(User.id == task.assignee_id)) if task.assignee_id else None
    return task_read(task, assignee_name)


@router.post("/tasks/{task_id}/review", response_model=TaskReviewRead, status_code=status.HTTP_201_CREATED)
def review_task(
    task_id: UUID,
    payload: TaskReviewCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TaskReviewRead:
    task, _ = task_for_user(db, task_id, actor)
    manager_can_access_task(db, task, actor)
    if task.status != TaskStatus.PENDING_REVIEW.value:
        raise HTTPException(status_code=409, detail="Only a task pending review can be reviewed")
    decision = payload.decision
    review = TaskReview(task_id=task.id, reviewer_id=actor.id, decision=decision, feedback=payload.feedback)
    previous = task.status
    task.status = TaskStatus.COMPLETED.value if decision == "APPROVED" else TaskStatus.CHANGES_REQUIRED.value
    task.completed_at = utc_now() if decision == "APPROVED" else None
    db.add(review)
    activity(db, task, actor, "task.reviewed", {"from": previous, "to": task.status, "feedback": payload.feedback})
    audit(db, task, actor, "task.reviewed", {"decision": decision, "feedback": payload.feedback})
    db.commit()
    db.refresh(review)
    return TaskReviewRead(
        id=review.id,
        task_id=review.task_id,
        reviewer_id=review.reviewer_id,
        decision=review.decision,
        feedback=review.feedback,
        created_at=review.created_at,
    )
