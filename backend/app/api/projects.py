from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.db.session import get_db
from app.models import AuditLog, Project, ProjectMember, Role, User, utc_now
from app.schemas import (
    ProjectCreate,
    ProjectMemberRead,
    ProjectMembershipRead,
    ProjectMembershipReplace,
    ProjectPage,
    ProjectRead,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def project_counts(db: Session, project_ids: list[UUID]) -> dict[UUID, dict[str, int]]:
    counts = {project_id: {"MANAGER": 0, "MEMBER": 0} for project_id in project_ids}
    if not project_ids:
        return counts
    rows = db.execute(
        select(ProjectMember.project_id, ProjectMember.role, func.count())
        .where(ProjectMember.project_id.in_(project_ids))
        .group_by(ProjectMember.project_id, ProjectMember.role)
    )
    for project_id, role, count in rows:
        counts[project_id][role] = count
    return counts


def project_read(project: Project, counts: dict[str, int]) -> ProjectRead:
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
    )


def validate_members(db: Session, manager_ids: list[UUID], member_ids: list[UUID]) -> None:
    all_ids = manager_ids + member_ids
    users = list(db.scalars(select(User).where(User.id.in_(all_ids))).all())
    by_id = {user.id: user for user in users}
    if len(by_id) != len(all_ids):
        raise HTTPException(status_code=422, detail="One or more selected users do not exist")
    for user_id in manager_ids:
        user = by_id[user_id]
        if not user.is_active or user.role != Role.MANAGER.value:
            raise HTTPException(status_code=422, detail="Every project Manager must be an active Manager account")
    for user_id in member_ids:
        user = by_id[user_id]
        if not user.is_active or user.role != Role.MEMBER.value:
            raise HTTPException(status_code=422, detail="Every project Member must be an active Member account")


def membership_audit(db: Session, actor: User, project: Project, action: str, details: dict) -> None:
    db.add(
        AuditLog(
            actor_id=actor.id,
            action=action,
            target_type="project",
            target_id=str(project.id),
            details=details,
        )
    )


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> ProjectRead:
    validate_members(db, payload.manager_ids, payload.member_ids)
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
        membership_audit(db, actor, project, "project.created", {"key": project.key, "status": project.status})
        membership_audit(
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
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A project with this key already exists") from None
    db.refresh(project)
    return project_read(project, {"MANAGER": len(payload.manager_ids), "MEMBER": len(payload.member_ids)})


@router.get("", response_model=ProjectPage)
def list_projects(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=180),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> ProjectPage:
    statement = select(Project)
    count_statement = select(func.count()).select_from(Project)
    if actor.role != Role.ADMIN.value:
        statement = statement.join(ProjectMember, ProjectMember.project_id == Project.id).where(
            ProjectMember.user_id == actor.id,
            ProjectMember.role == actor.role,
        )
        count_statement = count_statement.join(ProjectMember, ProjectMember.project_id == Project.id).where(
            ProjectMember.user_id == actor.id,
            ProjectMember.role == actor.role,
        )
    if search and search.strip():
        term = f"%{search.strip()}%"
        criteria = or_(Project.key.ilike(term), Project.name.ilike(term))
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)
    projects = list(db.scalars(statement.order_by(Project.created_at.desc()).offset(offset).limit(limit)).all())
    total = db.scalar(count_statement) or 0
    counts = project_counts(db, [project.id for project in projects])
    return ProjectPage(
        items=[project_read(project, counts[project.id]) for project in projects],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{project_id}/members", response_model=ProjectMembershipRead)
def get_project_members(
    project_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> ProjectMembershipRead:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if actor.role != Role.ADMIN.value:
        membership = db.get(ProjectMember, (project_id, actor.id))
        if actor.role != Role.MANAGER.value or membership is None or membership.role != Role.MANAGER.value:
            raise HTTPException(status_code=403, detail="Only Admins and assigned project Managers can view project membership")
    rows = db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(User.full_name)
    ).all()
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


@router.put("/{project_id}/members", response_model=ProjectMembershipRead)
def replace_project_members(
    project_id: UUID,
    payload: ProjectMembershipReplace,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> ProjectMembershipRead:
    project = db.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    validate_members(db, payload.manager_ids, payload.member_ids)

    current = list(db.scalars(select(ProjectMember).where(ProjectMember.project_id == project_id)).all())
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
        membership_audit(
            db,
            actor,
            project,
            "project.membership_changed",
            {"added": added, "removed": removed, "role_changed": changed},
        )
        db.commit()
    return get_project_members(project_id, db, actor)
