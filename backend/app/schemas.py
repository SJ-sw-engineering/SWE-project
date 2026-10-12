"""Validate request data and explicitly select safe response fields."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

PostStatus = Literal["RECRUITING", "CLOSED"]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=20, pattern=r"^\S+$")
    password: SecretStr = Field(min_length=1, max_length=128)


class TimestampedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime | None

    @field_validator("created_at")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        # MySQL TIMESTAMP arrives naive; database.py sets the connection to UTC.
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class UserResponse(TimestampedResponse):
    username: str
    name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse


class PostSummary(TimestampedResponse):
    id: int
    author_name: str
    title: str
    category: str
    target_size: int
    current_size: int | None
    status: PostStatus | None


class PostDetail(PostSummary):
    content: str


class PostPage(BaseModel):
    items: list[PostSummary]
    total: int
    page: int
    page_size: int
