import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


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
