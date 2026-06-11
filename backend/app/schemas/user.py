import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class UserMe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    city: Optional[str] = None
    avatar_url: Optional[str] = None
    is_verified: bool
    seller_rating: Optional[float] = None
    total_sales: int
    razorpay_account_id: Optional[str] = None
    created_at: datetime


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    city: Optional[str] = None
    avatar_url: Optional[str] = None
    is_verified: bool
    seller_rating: Optional[float] = None
    total_sales: int
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    city: Optional[str] = None
    avatar_url: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        # Runs only when full_name is provided (omitted -> validator skipped, field left
        # untouched by exclude_unset). Rejects explicit null / blank per spec ("Non-empty").
        if v is None or not v.strip():
            raise ValueError("full_name must be non-empty")
        return v.strip()
