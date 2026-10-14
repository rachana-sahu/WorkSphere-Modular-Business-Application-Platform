from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ProjectStatusDraftResponse(BaseModel):
    draft: str = Field(min_length=1, max_length=1200)
    provider: Literal["mock"]
    disclaimer: str = (
        "Review and edit this draft before sharing; it may omit context or be inaccurate."
    )

    @field_validator("draft")
    @classmethod
    def trim_draft(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("The generated draft must not be blank.")
        return value
