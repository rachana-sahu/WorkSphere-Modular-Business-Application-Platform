from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

JobStatus = Literal["open", "paused", "closed"]
ApplicationStatus = Literal[
    "applied", "screening", "interview", "offer", "hired", "rejected"
]


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    department: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Job title must not be blank.")
        return value


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    created_by: UUID
    title: str
    department: str | None
    description: str | None
    status: JobStatus
    created_at: datetime


class CandidateCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    job_id: UUID

    @field_validator("first_name", "last_name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Candidate name must not be blank.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> EmailStr:
        return value.strip().casefold()


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None
    created_at: datetime


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    candidate_id: UUID
    job_id: UUID
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus


class ApplicationHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    application_id: UUID
    actor_id: UUID | None
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    created_at: datetime
