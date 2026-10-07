from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from app.models import Role


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
