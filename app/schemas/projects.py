from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProjectStatus = Literal["active", "on_hold", "completed"]
TaskStatus = Literal["todo", "in_progress", "done"]
TaskPriority = Literal["low", "medium", "high"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name must not be blank.")
        return value

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    status: ProjectStatus | None = None

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Project name must not be null.")
        value = value.strip()
        if not value:
            raise ValueError("Project name must not be blank.")
        return value

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None

    @field_validator("status")
    @classmethod
    def require_status(cls, value: ProjectStatus | None) -> ProjectStatus:
        if value is None:
            raise ValueError("Project status must not be null.")
        return value


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    status: ProjectStatus
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class ProjectPage(BaseModel):
    items: list[ProjectResponse]
    page: int
    page_size: int
    total: int


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    due_date: date | None = None
    assigned_to: UUID | None = None

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Task title must not be blank.")
        return value

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None
    assigned_to: UUID | None = None

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Task title must not be null.")
        value = value.strip()
        if not value:
            raise ValueError("Task title must not be blank.")
        return value

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None

    @field_validator("status")
    @classmethod
    def require_status(cls, value: TaskStatus | None) -> TaskStatus:
        if value is None:
            raise ValueError("Task status must not be null.")
        return value

    @field_validator("priority")
    @classmethod
    def require_priority(cls, value: TaskPriority | None) -> TaskPriority:
        if value is None:
            raise ValueError("Task priority must not be null.")
        return value


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    project_id: UUID
    assigned_to: UUID | None
    created_by: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    created_at: datetime
    updated_at: datetime


class TaskPage(BaseModel):
    items: list[TaskResponse]
    page: int
    page_size: int
    total: int


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def trim_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment must not be blank.")
        return value


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    task_id: UUID
    author_id: UUID
    body: str
    created_at: datetime


class ProjectActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    project_id: UUID
    task_id: UUID | None
    actor_id: UUID | None
    event_type: str
    summary: str
    created_at: datetime


class ProjectMemberResponse(BaseModel):
    id: UUID
    display_name: str
