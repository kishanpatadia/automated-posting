"""Request and response models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.validators import MAX_MESSAGE_LENGTH, find_links, validate_message


class PostingRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "Check out our latest business platform and grow your online "
                    "visibility. https://example.com"
                }
            ]
        }
    )

    message: str = Field(
        description=f"Text to publish (max {MAX_MESSAGE_LENGTH} characters) with exactly one http(s) link."
    )

    @field_validator("message")
    @classmethod
    def check_message(cls, value: str) -> str:
        cleaned, _ = validate_message(value)
        return cleaned

    @property
    def cta_url(self) -> str:
        return find_links(self.message)[0]


class PlatformResult(BaseModel):
    platform: str
    status: Literal["success", "failed"]
    posted_url: str | None = None
    public_access: bool = False
    date: str | None = Field(default=None, description="Posting date, YYYY-MM-DD")
    time: str | None = Field(default=None, description="Posting time, HH:MM:SS")
    error: str | None = None


class PostingResponse(BaseModel):
    success: bool = Field(description="True when at least one platform published the message.")
    results: list[PlatformResult]


class ValidationErrorItem(BaseModel):
    field: str
    error: str


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    errors: list[ValidationErrorItem]
