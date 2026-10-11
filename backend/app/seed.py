"""Seed the local database with demo data for development.

Idempotency: refuses to run when any account already exists, so it is intended
for a fresh database (either instead of `app.bootstrap_admin`, or after
`alembic upgrade head` on an empty DB).

Run from backend/:  python -m app.seed
The demo password can be overridden with the SEED_DEMO_PASSWORD env var.
"""

from datetime import date, timedelta
import os

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models import (
    ActivityLog,
    Attachment,
    AuditLog,
    Comment,
    GithubLink,
    Notification,
    NotificationType,
    Project,
    ProjectMember,
    ProjectStatus,
    Role,
    Task,
    TaskPriority,
    TaskStatus,
    TaskType,
    User,
    utc_now,
)
from app.schemas import validate_strong_password

SEED_DEMO_PASSWORD_ENV = "SEED_DEMO_PASSWORD"
DEFAULT_DEMO_PASSWORD = "DemoPassw0rd!"


def seed(db: Session, password: str = DEFAULT_DEMO_PASSWORD) -> dict:
    validate_strong_password(password)
    if (db.scalar(select(func.count()).select_from(User)) or 0) > 0:
        raise RuntimeError("Seed refused: accounts already exist. Run against a fresh database.")

    password_hash = hash_password(password)
    admin = User(
        email="admin@invictusgrid.com",
        full_name="Ada Admin",
        role=Role.ADMIN.value,
        password_hash=password_hash,
        is_active=True,
        must_change_password=False,
    )
    manager = User(
        email="manager@invictusgrid.com",
        full_name="Morgan Manager",
        role=Role.MANAGER.value,
        password_hash=password_hash,
        is_active=True,
        must_change_password=False,
    )
    member = User(
        email="member@invictusgrid.com",
        full_name="Mia Member",
        role=Role.MEMBER.value,
        password_hash=password_hash,
        is_active=True,
        must_change_password=False,
    )
    member_two = User(
        email="dev@invictusgrid.com",
        full_name="Dev Member",
        role=Role.MEMBER.value,
        password_hash=password_hash,
        is_active=True,
        must_change_password=False,
    )
    db.add_all([admin, manager, member, member_two])
    db.flush()

    project = Project(
        key="ALPHA",
        name="Alpha Launch",
        description="First demo project seeded for local development.",
        status=ProjectStatus.ACTIVE.value,
        due_date=date.today() + timedelta(days=30),
        created_by=admin.id,
    )
    db.add(project)
    db.flush()
    db.add_all(
        [
            ProjectMember(project_id=project.id, user_id=manager.id, role=Role.MANAGER.value, added_by=admin.id),
            ProjectMember(project_id=project.id, user_id=member.id, role=Role.MEMBER.value, added_by=admin.id),
            ProjectMember(project_id=project.id, user_id=member_two.id, role=Role.MEMBER.value, added_by=admin.id),
        ]
    )

    task_specs = [
        ("Draft the launch checklist", TaskStatus.TODO, TaskPriority.HIGH, member.id, 1),
        ("Wire up the CI pipeline", TaskStatus.IN_PROGRESS, TaskPriority.MEDIUM, member_two.id, 2),
        ("Write the release notes", TaskStatus.PENDING_REVIEW, TaskPriority.MEDIUM, member.id, 3),
        ("Design the landing page", TaskStatus.COMPLETED, TaskPriority.HIGH, member_two.id, 4),
        ("Set up analytics", TaskStatus.COMPLETED, TaskPriority.LOW, member.id, 5),
    ]
    tasks: list[Task] = []
    for title, task_status, priority, assignee_id, number in task_specs:
        task = Task(
            project_id=project.id,
            issue_number=number,
            issue_key=f"{project.key}-{number}",
            title=title,
            description=f"{title} (seeded demo task).",
            type=TaskType.TASK.value,
            priority=priority.value,
            status=task_status.value,
            created_by=manager.id,
            assignee_id=assignee_id,
            completed_at=utc_now() if task_status == TaskStatus.COMPLETED else None,
        )
        db.add(task)
        tasks.append(task)
    db.flush()

    db.add(Comment(task_id=tasks[0].id, author_id=member.id, body="Starting on the checklist today."))
    db.add(
        GithubLink(
            task_id=tasks[1].id,
            submitted_by=member_two.id,
            url="https://github.com/invictusgrid/workspace/pull/42",
            evidence_type="PULL_REQUEST",
        )
    )
    db.add(
        Attachment(
            task_id=tasks[1].id,
            uploader_id=member_two.id,
            original_name="pipeline.png",
            storage_key="seed-attachment-pipeline",
            content_type="image/png",
            size_bytes=20480,
        )
    )
    db.add_all(
        [
            Notification(
                recipient_id=member.id,
                type=NotificationType.TASK_ASSIGNED.value,
                task_id=tasks[0].id,
                project_id=project.id,
            ),
            Notification(
                recipient_id=member_two.id,
                type=NotificationType.TASK_ASSIGNED.value,
                task_id=tasks[1].id,
                project_id=project.id,
            ),
        ]
    )
    db.add(
        ActivityLog(
            project_id=project.id,
            task_id=tasks[0].id,
            actor_id=manager.id,
            action="task.created",
            details={"issue_key": tasks[0].issue_key},
        )
    )
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="project.created",
            target_type="project",
            target_id=project.id,
            details={"key": project.key, "source": "seed"},
        )
    )
    db.commit()

    completed = sum(1 for task in tasks if task.status == TaskStatus.COMPLETED.value)
    return {
        "users": 4,
        "project_key": project.key,
        "tasks": len(tasks),
        "completed_tasks": completed,
        "progress": round(completed / len(tasks) * 100),
    }


def main() -> None:
    password = os.getenv(SEED_DEMO_PASSWORD_ENV, DEFAULT_DEMO_PASSWORD)
    with get_session_factory()() as db:
        summary = seed(db, password)
    print(
        f"Seeded demo data: {summary['users']} users, project {summary['project_key']} "
        f"with {summary['tasks']} tasks ({summary['progress']}% complete)."
    )
    print(
        "Demo accounts (password from SEED_DEMO_PASSWORD): "
        "admin@invictusgrid.com, manager@invictusgrid.com, member@invictusgrid.com, dev@invictusgrid.com"
    )


if __name__ == "__main__":
    main()
