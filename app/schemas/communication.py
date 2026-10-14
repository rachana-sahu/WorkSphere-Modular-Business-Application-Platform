from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=240)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Channel name must not be blank.")
        return value


class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    created_by: UUID
    created_at: datetime


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def trim_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message must not be blank.")
        return value


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    channel_id: UUID
    author_id: UUID
    body: str
    created_at: datetime
