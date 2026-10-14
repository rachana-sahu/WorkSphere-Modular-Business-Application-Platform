from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

LeaveStatus = Literal["pending", "approved", "rejected"]


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Department name must not be blank.")
        return value


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str


class EmployeeCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    job_title: str | None = Field(default=None, max_length=120)
    department_id: UUID | None = None
    start_date: date | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Employee name must not be blank.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> EmailStr:
        return value.strip().casefold()


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    user_id: UUID | None
    department_id: UUID | None
    first_name: str
    last_name: str
    email: EmailStr
    job_title: str | None
    start_date: date | None


class LeaveCreate(BaseModel):
    employee_id: UUID
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("end_date")
    @classmethod
    def date_range_is_ordered(cls, value: date, info) -> date:
        start_date = info.data.get("start_date")
        if start_date is not None and value < start_date:
            raise ValueError("Leave end date must not be before the start date.")
        return value


class LeaveReview(BaseModel):
    status: Literal["approved", "rejected"]


class LeaveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    employee_id: UUID
    reviewed_by: UUID | None
    start_date: date
    end_date: date
    reason: str | None
    status: LeaveStatus
    created_at: datetime
