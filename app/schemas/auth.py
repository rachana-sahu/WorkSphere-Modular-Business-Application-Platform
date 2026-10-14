from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    workspace_name: str = Field(min_length=2, max_length=120)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().casefold()

    @field_validator("display_name", "workspace_name")
    @classmethod
    def trim_names(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field must not be blank.")
        return normalized


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().casefold()


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str


class SessionResponse(BaseModel):
    expires_in: int


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class WorkspaceResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    role: str


class WorkspaceMemberResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    display_name: str
    role: str


class MembershipRoleUpdate(BaseModel):
    role: str = Field(pattern="^(admin|member)$")
