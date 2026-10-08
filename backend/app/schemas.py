from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator, model_validator

from app.models import ProjectStatus, Role, TaskPriority, TaskStatus, TaskType


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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class MessageResponse(BaseModel):
    message: str
