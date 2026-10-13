"""Task workflows: creation, listing, updates, the status state machine,
review submission, and review decisions, including activity/audit writes."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models import (
    ActivityLog,
    AuditLog,
    NotificationType,
    Project,
    Role,
    Task,
    TaskPriority,
    TaskReview,
    TaskStatus,
    User,
    utc_now,
)
from app.repositories import projects as projects_repo
from app.repositories import tasks as tasks_repo
from app.repositories import users as users_repo
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
from app.services import notifications as notifications_service
from app.services import permissions


def _task_read(task: Task, assignee_name: str | None = None) -> TaskRead:
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


def _assignee_name(db: Session, task: Task) -> str | None:
    if task.assignee_id is None:
        return None
    return tasks_repo.names(db, {task.assignee_id}).get(task.assignee_id)


def _activity(db: Session, task: Task, actor: User, action: str, details: dict) -> None:
    db.add(ActivityLog(project_id=task.project_id, task_id=task.id, actor_id=actor.id, action=action, details=details))


def _audit(db: Session, task: Task, actor: User, action: str, details: dict) -> None:
    db.add(AuditLog(actor_id=actor.id, action=action, target_type="task", target_id=task.id, details=details))


def project_for_user(db: Session, project_id: UUID, actor: User, *, managers_only: bool = False) -> Project:
    project = projects_repo.get(db, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    role = permissions.project_role_for_user(db, project_id, actor)
    if role is None or (managers_only and role not in (Role.ADMIN.value, Role.MANAGER.value)):
        raise NotFoundError("Project not found")
    return project


def task_for_user(db: Session, task_id: UUID, actor: User) -> tuple[Task, Project]:
    task = tasks_repo.get(db, task_id)
    if task is None:
        raise NotFoundError("Task not found")
    project = project_for_user(db, task.project_id, actor)
    if (
        permissions.project_role_for_user(db, task.project_id, actor) == Role.MEMBER.value
        and task.assignee_id != actor.id
    ):
        raise NotFoundError("Task not found")
    return task, project


def _validate_assignee(db: Session, project_id: UUID, assignee_id: UUID | None) -> None:
    if assignee_id is None:
        return
    user = users_repo.get(db, assignee_id)
    membership = projects_repo.membership(db, project_id, assignee_id)
    if (
        user is None
        or not user.is_active
        or user.role != Role.MEMBER.value
        or membership is None
        or membership.role != Role.MEMBER.value
    ):
        raise ValidationError("Assignee must be an active Member of this project")


def _manager_can_access_task(db: Session, task: Task, actor: User) -> None:
    if permissions.project_role_for_user(db, task.project_id, actor) not in (Role.ADMIN.value, Role.MANAGER.value):
        raise NotFoundError("Task not found")


def _ensure_project_active(project: Project) -> None:
    if project.status in ("COMPLETED", "ARCHIVED"):
        raise ConflictError(f"Task changes are not allowed in a {project.status.lower()} project")


def create_task(db: Session, actor: User, project_id: UUID, payload: TaskCreate) -> TaskRead:
    project = project_for_user(db, project_id, actor, managers_only=True)
    _ensure_project_active(project)
    _validate_assignee(db, project_id, payload.assignee_id)

    # Locking the project row serializes issue-number allocation for concurrent task creation.
    locked_project = projects_repo.get_for_update(db, project_id)
    next_number = tasks_repo.max_issue_number(db, project_id) + 1
    task = Task(
        project_id=project_id,
        issue_number=next_number,
        issue_key=f"{locked_project.key}-{next_number}",
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
    _activity(db, task, actor, "task.created", {"issue_key": task.issue_key})
    _audit(db, task, actor, "task.created", {"project_id": str(project_id), "issue_key": task.issue_key})
    if task.assignee_id:
        _activity(db, task, actor, "task.assigned", {"assignee_id": str(task.assignee_id)})
        notifications_service.create(
            db,
            recipient_id=task.assignee_id,
            type=NotificationType.TASK_ASSIGNED,
            task_id=task.id,
            project_id=project_id,
        )
    db.commit()
    db.refresh(task)
    return _task_read(task, _assignee_name(db, task))


def list_tasks(
    db: Session,
    actor: User,
    project_id: UUID,
    *,
    offset: int,
    limit: int,
    status: TaskStatus | None,
    priority: TaskPriority | None,
    sort: TaskSort | None = None,
) -> TaskPage:
    project_for_user(db, project_id, actor)
    role = permissions.project_role_for_user(db, project_id, actor)
    assignee_scope = actor.id if role == Role.MEMBER.value else None
    tasks, total = tasks_repo.list_page(
        db,
        project_id=project_id,
        assignee_scope=assignee_scope,
        offset=offset,
        limit=limit,
        status=status.value if status else None,
        priority=priority.value if priority else None,
        sort=sort.value if sort else None,
    )
    assignee_ids = {task.assignee_id for task in tasks if task.assignee_id is not None}
    names = tasks_repo.names(db, assignee_ids)
    return TaskPage(
        items=[_task_read(task, names.get(task.assignee_id)) for task in tasks],
        total=total,
        offset=offset,
        limit=limit,
    )


def get_task(db: Session, actor: User, task_id: UUID) -> TaskRead:
    task, _ = task_for_user(db, task_id, actor)
    return _task_read(task, _assignee_name(db, task))


def list_reviews(db: Session, actor: User, task_id: UUID) -> list[TaskReviewRead]:
    task, _ = task_for_user(db, task_id, actor)
    reviews = tasks_repo.reviews(db, task.id)
    names = tasks_repo.names(db, {review.reviewer_id for review in reviews})
    return [
        TaskReviewRead(
            id=review.id,
            task_id=review.task_id,
            reviewer_id=review.reviewer_id,
            reviewer_name=names.get(review.reviewer_id),
            decision=review.decision,
            feedback=review.feedback,
            created_at=review.created_at,
        )
        for review in reviews
    ]


def update_task(db: Session, actor: User, task_id: UUID, payload: TaskUpdate) -> TaskRead:
    task, project = task_for_user(db, task_id, actor)
    _ensure_project_active(project)
    _manager_can_access_task(db, task, actor)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise ValidationError("At least one task field must be provided")
    old_assignee = task.assignee_id
    if "assignee_id" in changes:
        _validate_assignee(db, task.project_id, changes["assignee_id"])
    for key, value in changes.items():
        setattr(task, key, value.value if hasattr(value, "value") else value)
    _activity(db, task, actor, "task.updated", {"fields": list(changes.keys())})
    if old_assignee != task.assignee_id:
        reassignment = {
            "from": str(old_assignee) if old_assignee else None,
            "to": str(task.assignee_id) if task.assignee_id else None,
        }
        _activity(db, task, actor, "task.reassigned", reassignment)
        _audit(db, task, actor, "task.reassigned", reassignment)
        if task.assignee_id:
            notifications_service.create(
                db,
                recipient_id=task.assignee_id,
                type=NotificationType.TASK_ASSIGNED,
                task_id=task.id,
                project_id=task.project_id,
            )
    db.commit()
    db.refresh(task)
    return _task_read(task, _assignee_name(db, task))


def start_task(db: Session, actor: User, task_id: UUID, payload: TaskStatusUpdate) -> TaskRead:
    task, _ = task_for_user(db, task_id, actor)
    if (
        permissions.project_role_for_user(db, task.project_id, actor) != Role.MEMBER.value
        or task.assignee_id != actor.id
    ):
        raise ForbiddenError("Only the assigned Member can start or resume this task")
    if payload.status != TaskStatus.IN_PROGRESS or task.status not in (
        TaskStatus.TODO.value,
        TaskStatus.CHANGES_REQUIRED.value,
    ):
        raise ConflictError(f"Cannot transition task from {task.status} to {payload.status.value}")
    previous = task.status
    task.status = TaskStatus.IN_PROGRESS.value
    task.completed_at = None
    _activity(db, task, actor, "task.status_changed", {"from": previous, "to": task.status})
    db.commit()
    db.refresh(task)
    return _task_read(task, _assignee_name(db, task))


def submit_for_review(db: Session, actor: User, task_id: UUID) -> TaskRead:
    task, _ = task_for_user(db, task_id, actor)
    if (
        permissions.project_role_for_user(db, task.project_id, actor) != Role.MEMBER.value
        or task.assignee_id != actor.id
    ):
        raise ForbiddenError("Only the assigned Member can submit this task")
    if task.status != TaskStatus.IN_PROGRESS.value:
        raise ConflictError("Only an in-progress task can be submitted for review")
    task.status = TaskStatus.PENDING_REVIEW.value
    _activity(db, task, actor, "task.submitted_for_review", {})
    notifications_service.notify_project_managers(
        db,
        project_id=task.project_id,
        type=NotificationType.REVIEW_REQUESTED,
        task_id=task.id,
        exclude_id=actor.id,
    )
    db.commit()
    db.refresh(task)
    return _task_read(task, _assignee_name(db, task))


def review_task(db: Session, actor: User, task_id: UUID, payload: TaskReviewCreate) -> TaskReviewRead:
    task, project = task_for_user(db, task_id, actor)
    _ensure_project_active(project)
    _manager_can_access_task(db, task, actor)
    if task.status != TaskStatus.PENDING_REVIEW.value:
        raise ConflictError("Only a task pending review can be reviewed")
    decision = payload.decision
    review = TaskReview(task_id=task.id, reviewer_id=actor.id, decision=decision, feedback=payload.feedback)
    previous = task.status
    task.status = TaskStatus.COMPLETED.value if decision == "APPROVED" else TaskStatus.CHANGES_REQUIRED.value
    task.completed_at = utc_now() if decision == "APPROVED" else None
    db.add(review)
    _activity(db, task, actor, "task.reviewed", {"from": previous, "to": task.status, "feedback": payload.feedback})
    _audit(db, task, actor, "task.reviewed", {"decision": decision, "feedback": payload.feedback})
    if task.assignee_id:
        notifications_service.create(
            db,
            recipient_id=task.assignee_id,
            type=NotificationType.TASK_APPROVED if decision == "APPROVED" else NotificationType.CHANGES_REQUIRED,
            task_id=task.id,
            project_id=task.project_id,
        )
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


def delete_task(db: Session, actor: User, task_id: UUID) -> None:
    task, project = task_for_user(db, task_id, actor)
    _manager_can_access_task(db, task, actor)
    _ensure_project_active(project)
    _audit(db, task, actor, "task.deleted", {"project_id": str(task.project_id), "issue_key": task.issue_key})
    db.delete(task)
    db.commit()
