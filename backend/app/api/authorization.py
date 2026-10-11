"""Project-level authorization.

`project_members.role` is the source of truth for a user's role inside a
project. The account role (`users.role`) is only a capability cap:

* ADMIN accounts have global authority and need no membership.
* MANAGER accounts hold whatever role their membership row grants, so they can
  be a Manager of one project and a Member of another.
* MEMBER accounts are always treated as project Members even if a stale
  MANAGER membership row still exists, so demotions take effect immediately
  without granting manager authority.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ProjectMember, Role, User


def effective_project_role(account_role: str, membership_role: str | None) -> str | None:
    if account_role == Role.ADMIN.value:
        return Role.ADMIN.value
    if membership_role is None:
        return None
    if account_role == Role.MEMBER.value:
        return Role.MEMBER.value
    return membership_role


def project_role_for_user(db: Session, project_id: UUID, actor: User) -> str | None:
    if actor.role == Role.ADMIN.value:
        return Role.ADMIN.value
    membership = db.get(ProjectMember, (project_id, actor.id))
    return effective_project_role(actor.role, membership.role if membership else None)
