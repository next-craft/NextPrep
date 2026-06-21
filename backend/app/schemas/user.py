import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserMe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    city: Optional[str] = None
    avatar_url: Optional[str] = None
    is_verified: bool  # verification badge — earned at 10 verified sales
    seller_rating: Optional[float] = None
    books_sold: int
    books_bought: int
    created_at: datetime


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    city: Optional[str] = None
    avatar_url: Optional[str] = None
    is_verified: bool  # verification badge — earned at 10 verified sales
    seller_rating: Optional[float] = None
    books_sold: int
    books_bought: int
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=80)
    city: Optional[str] = Field(None, max_length=80)
    avatar_url: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        # Runs only when full_name is provided (omitted -> validator skipped, field left
        # untouched by exclude_unset). Rejects explicit null / blank per spec ("Non-empty").
        if v is None or not v.strip():
            raise ValueError("full_name must be non-empty")
        return v.strip()

    @field_validator("avatar_url")
    @classmethod
    def avatar_url_safe(cls, v: Optional[str]) -> Optional[str]:
        # Server-side boundary (the client regex is not one): https only, so a stored
        # javascript:/data: scheme can never reach an <img src>/href, and plaintext http
        # (which the frontend CSP blocks from rendering anyway) is rejected at the source.
        # Bounded length to avoid absurd payloads.
        if v is None or v == "":
            return v
        v = v.strip()
        if not v.startswith("https://") or len(v) > 2048:
            raise ValueError("avatar_url must be an https URL under 2048 characters")
        return v
