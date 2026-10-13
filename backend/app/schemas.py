from datetime import date, datetime
from enum import Enum
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator, model_validator

from app.models import (
    EvidenceType,
    NotificationType,
    ProjectStatus,
    Role,
    TaskPriority,
    TaskStatus,
    TaskType,
)


def validate_strong_password(value: str) -> str:
    if not any(char.islower() for char in value):
        raise ValueError("Password must include a lowercase letter")
    if not any(char.isupper() for char in value):
        raise ValueError("Password must include an uppercase letter")
    if not any(char.isdigit() for char in value):
        raise ValueError("Password must include a number")
    if not any(not char.isalnum() for char in value):
        raise ValueError("Password must include a symbol")
    return value


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=160)
    role: Role
    initial_password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("full_name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("initial_password")
    @classmethod
    def strong_password(cls, value: SecretStr) -> SecretStr:
        validate_strong_password(value.get_secret_value())
        return value


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserRoleUpdate(BaseModel):
    role: Role


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    must_change_password: bool
    created_at: datetime


class UserPage(BaseModel):
    items: list[UserRead]
    total: int
    offset: int
    limit: int


class ProjectCreate(BaseModel):
    key: str = Field(min_length=2, max_length=10, pattern=r"^[A-Z][A-Z0-9]+$")
    name: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    status: ProjectStatus = ProjectStatus.PLANNED
    due_date: date | None = None
    manager_ids: list[UUID] = Field(min_length=1, max_length=100)
    member_ids: list[UUID] = Field(default_factory=list, max_length=200)

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Project key must be text")
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def unique_disjoint_members(self) -> "ProjectCreate":
        if len(set(self.manager_ids)) != len(self.manager_ids):
            raise ValueError("Manager list contains duplicate users")
        if len(set(self.member_ids)) != len(self.member_ids):
            raise ValueError("Member list contains duplicate users")
        if set(self.manager_ids) & set(self.member_ids):
            raise ValueError("A user cannot be both a Manager and Member on the same project")
        return self


class ProjectMembershipReplace(BaseModel):
    manager_ids: list[UUID] = Field(min_length=1, max_length=100)
    member_ids: list[UUID] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def unique_disjoint_members(self) -> "ProjectMembershipReplace":
        if len(set(self.manager_ids)) != len(self.manager_ids):
            raise ValueError("Manager list contains duplicate users")
        if len(set(self.member_ids)) != len(self.member_ids):
            raise ValueError("Member list contains duplicate users")
        if set(self.manager_ids) & set(self.member_ids):
            raise ValueError("A user cannot be both a Manager and Member on the same project")
        return self


class ProjectRead(BaseModel):
    id: UUID
    key: str
    name: str
    description: str | None
    status: ProjectStatus
    due_date: date | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    manager_count: int
    member_count: int
    progress: int


class ProjectPage(BaseModel):
    items: list[ProjectRead]
    total: int
    offset: int
    limit: int


class ProjectMemberRead(BaseModel):
    user_id: UUID
    full_name: str
    email: EmailStr
    account_role: Role
    project_role: Role
    is_active: bool


class ProjectMembershipRead(BaseModel):
    project_id: UUID
    managers: list[ProjectMemberRead]
    members: list[ProjectMemberRead]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=20000)
    type: TaskType = TaskType.TASK
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: UUID | None = None
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Task title cannot be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_task_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=20000)
    type: TaskType | None = None
    priority: TaskPriority | None = None
    assignee_id: UUID | None = None
    due_date: date | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_required_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            for field_name in ("title", "type", "priority"):
                if field_name in value and value[field_name] is None:
                    raise ValueError(f"{field_name} cannot be null")
        return value

    @field_validator("title")
    @classmethod
    def nonblank_updated_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Task title cannot be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_updated_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskReviewCreate(BaseModel):
    decision: str = Field(pattern=r"^(APPROVED|CHANGES_REQUIRED)$")
    feedback: str | None = Field(default=None, max_length=5000)

    @field_validator("feedback")
    @classmethod
    def normalize_review_feedback(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def require_changes_feedback(self) -> "TaskReviewCreate":
        if self.decision == "CHANGES_REQUIRED" and not self.feedback:
            raise ValueError("Feedback is required when requesting changes")
        return self


class TaskRead(BaseModel):
    id: UUID
    project_id: UUID
    issue_number: int
    issue_key: str
    title: str
    description: str | None
    type: TaskType
    priority: TaskPriority
    status: TaskStatus
    created_by: UUID
    assignee_id: UUID | None
    assignee_name: str | None = None
    due_date: date | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskPage(BaseModel):
    items: list[TaskRead]
    total: int
    offset: int
    limit: int


class TaskReviewRead(BaseModel):
    id: UUID
    task_id: UUID
    reviewer_id: UUID
    reviewer_name: str | None = None
    decision: str
    feedback: str | None
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr


class PasswordChange(BaseModel):
    current_password: SecretStr
    new_password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: SecretStr) -> SecretStr:
        validate_strong_password(value.get_secret_value())
        return value


class PasswordReset(BaseModel):
    new_password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: SecretStr) -> SecretStr:
        validate_strong_password(value.get_secret_value())
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class MessageResponse(BaseModel):
    message: str


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    status: ProjectStatus | None = None
    due_date: date | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_required_fields(cls, value: object) -> object:
        if isinstance(value, dict) and "name" in value and value["name"] is None:
            raise ValueError("name cannot be null")
        return value

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class UserProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)

    @field_validator("full_name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class TaskSort(str, Enum):
    created_desc = "created_desc"
    created_asc = "created_asc"
    due_date_asc = "due_date_asc"
    due_date_desc = "due_date_desc"
    priority_desc = "priority_desc"
    priority_asc = "priority_asc"
    title_asc = "title_asc"


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def nonblank_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment cannot be blank")
        return value


class CommentRead(BaseModel):
    id: UUID
    task_id: UUID
    author_id: UUID
    author_name: str | None = None
    body: str
    created_at: datetime
    updated_at: datetime


class AttachmentRead(BaseModel):
    id: UUID
    task_id: UUID
    uploader_id: UUID
    uploader_name: str | None = None
    original_name: str
    content_type: str
    size_bytes: int
    created_at: datetime


class GithubLinkCreate(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    evidence_type: EvidenceType = EvidenceType.OTHER

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or parsed.hostname not in ("github.com", "www.github.com"):
            raise ValueError("Evidence URL must be a github.com http(s) URL")
        if not parsed.path or parsed.path == "/":
            raise ValueError("Evidence URL must point to a repository resource")
        return value


class GithubLinkRead(BaseModel):
    id: UUID
    task_id: UUID
    submitted_by: UUID
    submitter_name: str | None = None
    url: str
    evidence_type: EvidenceType
    created_at: datetime


class NotificationRead(BaseModel):
    id: UUID
    recipient_id: UUID
    type: NotificationType
    task_id: UUID | None
    project_id: UUID | None
    message: str
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationRead]
    total: int
    unread: int
    offset: int
    limit: int


class ActivityLogRead(BaseModel):
    id: UUID
    project_id: UUID
    task_id: UUID | None
    actor_id: UUID | None
    actor_name: str | None = None
    action: str
    details: dict[str, Any]
    created_at: datetime


class ActivityLogPage(BaseModel):
    items: list[ActivityLogRead]
    total: int
    offset: int
    limit: int


class AuditLogRead(BaseModel):
    id: UUID
    actor_id: UUID | None
    actor_name: str | None = None
    action: str
    target_type: str
    target_id: UUID
    details: dict[str, Any]
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogRead]
    total: int
    offset: int
    limit: int


class TaskStatusCounts(BaseModel):
    TODO: int = 0
    IN_PROGRESS: int = 0
    PENDING_REVIEW: int = 0
    CHANGES_REQUIRED: int = 0
    COMPLETED: int = 0


class TaskPriorityCounts(BaseModel):
    LOW: int = 0
    MEDIUM: int = 0
    HIGH: int = 0
    URGENT: int = 0


class ContributionRead(BaseModel):
    user_id: UUID
    full_name: str
    role: Role
    assigned: int = 0
    completed: int = 0
    pending_review: int = 0
    changes_required: int = 0
    overdue: int = 0


class ProjectAnalytics(BaseModel):
    project_id: UUID
    progress: int
    total_tasks: int
    by_status: TaskStatusCounts
    by_priority: TaskPriorityCounts
    pending_review: int
    overdue: int
    contributions: list[ContributionRead]
