from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

LeadStage = Literal["new", "qualified", "proposal", "won", "lost"]
SortField = Literal["created_at", "title", "stage", "estimated_value"]
SortDirection = Literal["asc", "desc"]


class CRMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    domain: str | None = Field(default=None, max_length=253)
    phone: str | None = Field(default=None, max_length=40)
    website: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Company name must not be blank.")
        return value

    @field_validator("domain", "phone", "website", "industry")
    @classmethod
    def trim_optional_values(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None


class CompanyResponse(CRMBase):
    id: UUID
    workspace_id: UUID
    name: str
    domain: str | None
    phone: str | None
    website: str | None
    industry: str | None
    created_at: datetime


class CompanyPage(BaseModel):
    items: list[CompanyResponse]
    page: int
    page_size: int
    total: int


class ContactCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    job_title: str | None = Field(default=None, max_length=120)
    company_id: UUID | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def trim_required_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> EmailStr | None:
        return value.strip().casefold() if value is not None else None

    @field_validator("phone", "job_title")
    @classmethod
    def trim_optional_values(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None


class ContactResponse(CRMBase):
    id: UUID
    workspace_id: UUID
    company_id: UUID | None
    first_name: str
    last_name: str
    email: EmailStr | None
    phone: str | None
    job_title: str | None
    created_at: datetime


class ContactPage(BaseModel):
    items: list[ContactResponse]
    page: int
    page_size: int
    total: int


class LeadCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    stage: LeadStage = "new"
    source: str | None = Field(default=None, max_length=80)
    estimated_value: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    company_id: UUID | None = None
    contact_id: UUID | None = None
    assigned_to: UUID | None = None

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Lead title must not be blank.")
        return value

    @field_validator("source")
    @classmethod
    def trim_source(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None


class LeadUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    stage: LeadStage | None = None
    source: str | None = Field(default=None, max_length=80)
    estimated_value: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    company_id: UUID | None = None
    contact_id: UUID | None = None
    assigned_to: UUID | None = None

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Lead title must not be blank.")
        return value

    @field_validator("source")
    @classmethod
    def trim_source(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None


class LeadResponse(CRMBase):
    id: UUID
    workspace_id: UUID
    company_id: UUID | None
    contact_id: UUID | None
    assigned_to: UUID | None
    title: str
    stage: LeadStage
    source: str | None
    estimated_value: Decimal | None
    created_at: datetime
    updated_at: datetime


class LeadPage(BaseModel):
    items: list[LeadResponse]
    page: int
    page_size: int
    total: int


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def trim_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Note must not be blank.")
        return value


class NoteResponse(CRMBase):
    id: UUID
    workspace_id: UUID
    lead_id: UUID | None
    contact_id: UUID | None
    company_id: UUID | None
    author_id: UUID
    body: str
    created_at: datetime


class ActivityResponse(CRMBase):
    id: UUID
    workspace_id: UUID
    lead_id: UUID | None
    contact_id: UUID | None
    company_id: UUID | None
    actor_id: UUID | None
    event_type: str
    summary: str
    from_stage: LeadStage | None
    to_stage: LeadStage | None
    created_at: datetime
