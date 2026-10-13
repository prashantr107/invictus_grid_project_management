"""Project workflows: creation, listing, membership views and replacement,
including progress and audit writes."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models import AuditLog, NotificationType, Project, ProjectMember, Role, User, utc_now
from app.repositories import projects as projects_repo
from app.repositories import users as users_repo
from app.schemas import (
    ProjectCreate,
    ProjectMemberRead,
    ProjectMembershipRead,
    ProjectMembershipReplace,
    ProjectPage,
    ProjectRead,
    ProjectUpdate,
)
from app.services import notifications as notifications_service
from app.services import permissions


_PROJECT_TRANSITIONS = {
    "PLANNED": {"ACTIVE"},
    "ACTIVE": {"COMPLETED"},
    "COMPLETED": {"ARCHIVED"},
    "ARCHIVED": set(),
}


def _project_read(project: Project, counts: dict[str, int], progress: int = 0) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        key=project.key,
        name=project.name,
        description=project.description,
        status=project.status,
        due_date=project.due_date,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        manager_count=counts["MANAGER"],
        member_count=counts["MEMBER"],
        progress=progress,
    )


def _validate_members(db: Session, manager_ids: list[UUID], member_ids: list[UUID]) -> None:
    all_ids = manager_ids + member_ids
    by_id = users_repo.get_many(db, all_ids)
    if len(by_id) != len(all_ids):
        raise ValidationError("One or more selected users do not exist")
    for user_id in manager_ids:
        user = by_id[user_id]
        if not user.is_active or user.role != Role.MANAGER.value:
            raise ValidationError("Every project Manager must be an active Manager account")
    for user_id in member_ids:
        user = by_id[user_id]
        if not user.is_active or user.role != Role.MEMBER.value:
            raise ValidationError("Every project Member must be an active Member account")


def _membership_audit(db: Session, actor: User, project: Project, action: str, details: dict) -> None:
    db.add(AuditLog(actor_id=actor.id, action=action, target_type="project", target_id=project.id, details=details))


def create_project(db: Session, actor: User, payload: ProjectCreate) -> ProjectRead:
    _validate_members(db, payload.manager_ids, payload.member_ids)
    project = Project(
        key=payload.key,
        name=payload.name,
        description=payload.description,
        status=payload.status.value,
        due_date=payload.due_date,
        created_by=actor.id,
    )
    db.add(project)
    try:
        db.flush()
        for user_id in payload.manager_ids:
            db.add(ProjectMember(project_id=project.id, user_id=user_id, role=Role.MANAGER.value, added_by=actor.id))
        for user_id in payload.member_ids:
            db.add(ProjectMember(project_id=project.id, user_id=user_id, role=Role.MEMBER.value, added_by=actor.id))
        _membership_audit(db, actor, project, "project.created", {"key": project.key, "status": project.status})
        _membership_audit(
            db,
            actor,
            project,
            "project.membership_changed",
            {
                "added": {
                    "managers": [str(user_id) for user_id in payload.manager_ids],
                    "members": [str(user_id) for user_id in payload.member_ids],
                },
                "removed": {"managers": [], "members": []},
            },
        )
        for user_id in payload.manager_ids + payload.member_ids:
            notifications_service.create(
                db, recipient_id=user_id, type=NotificationType.PROJECT_ADDED, project_id=project.id
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("A project with this key already exists") from None
    db.refresh(project)
    return _project_read(project, {"MANAGER": len(payload.manager_ids), "MEMBER": len(payload.member_ids)})


def list_projects(db: Session, actor: User, *, offset: int, limit: int, search: str | None) -> ProjectPage:
    projects, total = projects_repo.list_page(
        db,
        actor_id=actor.id,
        is_admin=actor.role == Role.ADMIN.value,
        offset=offset,
        limit=limit,
        search=search,
    )
    project_ids = [project.id for project in projects]
    counts = projects_repo.member_counts(db, project_ids)
    progress = projects_repo.progress(db, project_ids)
    return ProjectPage(
        items=[_project_read(project, counts[project.id], progress[project.id]) for project in projects],
        total=total,
        offset=offset,
        limit=limit,
    )


def get_project(db: Session, actor: User, project_id: UUID) -> ProjectRead:
    project = projects_repo.get(db, project_id)
    if project is None or permissions.project_role_for_user(db, project_id, actor) is None:
        raise NotFoundError("Project not found")
    counts = projects_repo.member_counts(db, [project_id])[project_id]
    progress = projects_repo.progress(db, [project_id])[project_id]
    return _project_read(project, counts, progress)


def update_project(db: Session, actor: User, project_id: UUID, payload: ProjectUpdate) -> ProjectRead:
    project = projects_repo.get_for_update(db, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise ValidationError("At least one project field must be provided")

    new_status = changes.get("status")
    if new_status is not None:
        new_status = new_status.value if hasattr(new_status, "value") else new_status
        if new_status != project.status:
            if new_status not in _PROJECT_TRANSITIONS.get(project.status, set()):
                raise ConflictError(f"Cannot move a project from {project.status} to {new_status}")
            _membership_audit(
                db,
                actor,
                project,
                "project.status_changed",
                {"from": project.status, "to": new_status},
            )
            project.status = new_status

    for field in ("name", "description", "due_date"):
        if field in changes:
            setattr(project, field, changes[field])

    _membership_audit(db, actor, project, "project.updated", {"fields": sorted(changes.keys())})
    db.commit()
    db.refresh(project)
    counts = projects_repo.member_counts(db, [project_id])[project_id]
    progress = projects_repo.progress(db, [project_id])[project_id]
    return _project_read(project, counts, progress)


def delete_project(db: Session, actor: User, project_id: UUID) -> None:
    project = projects_repo.get_for_update(db, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    _membership_audit(db, actor, project, "project.deleted", {"key": project.key, "name": project.name})
    db.delete(project)
    db.commit()


def get_members(db: Session, actor: User, project_id: UUID) -> ProjectMembershipRead:
    if projects_repo.get(db, project_id) is None:
        raise NotFoundError("Project not found")
    project_role = permissions.project_role_for_user(db, project_id, actor)
    if project_role is None and actor.role != Role.ADMIN.value:
        # Object-level concealment: callers who cannot see the project must not
        # be able to tell it exists (uniform 404 policy, see docs/http-semantics.md).
        raise NotFoundError("Project not found")
    if actor.role != Role.ADMIN.value and project_role != Role.MANAGER.value:
        raise ForbiddenError("Only Admins and assigned project Managers can view project membership")
    rows = projects_repo.members_with_users(db, project_id)
    managers: list[ProjectMemberRead] = []
    members: list[ProjectMemberRead] = []
    for membership, user in rows:
        item = ProjectMemberRead(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            account_role=user.role,
            project_role=membership.role,
            is_active=user.is_active,
        )
        (managers if membership.role == Role.MANAGER.value else members).append(item)
    return ProjectMembershipRead(project_id=project_id, managers=managers, members=members)


def replace_members(
    db: Session, actor: User, project_id: UUID, payload: ProjectMembershipReplace
) -> ProjectMembershipRead:
    project = projects_repo.get_for_update(db, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    _validate_members(db, payload.manager_ids, payload.member_ids)

    current = projects_repo.memberships(db, project_id)
    current_roles = {membership.user_id: membership.role for membership in current}
    next_roles = {user_id: Role.MANAGER.value for user_id in payload.manager_ids}
    next_roles.update({user_id: Role.MEMBER.value for user_id in payload.member_ids})
    added = {str(user_id): role for user_id, role in next_roles.items() if user_id not in current_roles}
    removed = {str(user_id): role for user_id, role in current_roles.items() if user_id not in next_roles}
    changed = {
        str(user_id): {"from": current_roles[user_id], "to": role}
        for user_id, role in next_roles.items()
        if user_id in current_roles and current_roles[user_id] != role
    }

    if added or removed or changed:
        for membership in current:
            next_role = next_roles.get(membership.user_id)
            if next_role is None:
                db.delete(membership)
            elif next_role != membership.role:
                membership.role = next_role
                membership.added_by = actor.id
                membership.added_at = utc_now()
        for user_id, role in next_roles.items():
            if user_id not in current_roles:
                db.add(ProjectMember(project_id=project_id, user_id=user_id, role=role, added_by=actor.id))
        _membership_audit(
            db,
            actor,
            project,
            "project.membership_changed",
            {"added": added, "removed": removed, "role_changed": changed},
        )
        for user_id in next_roles:
            if user_id not in current_roles:
                notifications_service.create(
                    db, recipient_id=user_id, type=NotificationType.PROJECT_ADDED, project_id=project_id
                )
        db.commit()
    return get_members(db, actor, project_id)
