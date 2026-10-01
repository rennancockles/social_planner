from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class PostStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Platform(StrEnum):
    instagram = "instagram"
    linkedin = "linkedin"
    twitter = "twitter"


class Tone(StrEnum):
    casual = "casual"
    professional = "professional"
    inspirational = "inspirational"
    educational = "educational"


class Post(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content: str
    platform: Platform
    topic: str | None = None
    status: PostStatus = PostStatus.pending
    image_path: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Profile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    niche: str
    tone: Tone
    platform: Platform
    audience_description: str
