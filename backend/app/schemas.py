"""Validate request data and explicitly select safe response fields."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator, model_validator

PostStatus = Literal["RECRUITING", "CLOSED"]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=20, pattern=r"^\S+$")
    password: SecretStr = Field(min_length=1, max_length=128)


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=4, max_length=20, pattern=r"^[A-Za-z0-9_-]{4,20}$")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    password: SecretStr = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: SecretStr = Field(min_length=1, max_length=4096)


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
    refresh_token: str
    refresh_expires_in: int
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


Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Content = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]
Category = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
TeamSize = Annotated[int, Field(ge=2, le=100)]


class PostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    content: Content
    category: Category
    target_size: TeamSize


class PostUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title | None = None
    content: Content | None = None
    category: Category | None = None
    target_size: TeamSize | None = None

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("수정할 필드를 한 개 이상 입력하고 null은 사용하지 마세요.")
        return self


class MessageResponse(BaseModel):
    detail: str


class ApplicationContext(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: Literal["PENDING", "APPROVED", "REJECTED"] | None


class PostContext(BaseModel):
    is_owner: bool
    my_application: ApplicationContext | None
