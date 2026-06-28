import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.constants.locations import is_valid_state, is_valid_city
from app.schemas.college import CollegeBrief


class UserMe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    state: Optional[str] = None
    city: Optional[str] = None
    college: Optional[CollegeBrief] = None  # canonical campus brief; raw college_id never exposed
    college_other: Optional[str] = None  # un-promoted free-text campus, display-only
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
    state: Optional[str] = None
    city: Optional[str] = None
    college: Optional[CollegeBrief] = None  # canonical campus brief; raw college_id never exposed
    college_other: Optional[str] = None  # un-promoted free-text campus, display-only
    avatar_url: Optional[str] = None
    is_verified: bool  # verification badge — earned at 10 verified sales
    seller_rating: Optional[float] = None
    books_sold: int
    books_bought: int
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    college_id: Optional[uuid.UUID] = None
    college_other: Optional[str] = Field(None, max_length=120)
    avatar_url: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        # Runs only when full_name is provided (omitted -> validator skipped, field left
        # untouched by exclude_unset). Rejects explicit null / blank per spec ("Non-empty").
        if v is None or not v.strip():
            raise ValueError("full_name must be non-empty")
        return v.strip()

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: Optional[str]) -> Optional[str]:
        # "" / None mean "not set" — allowed. A non-empty value must be a real state.
        if v and not is_valid_state(v):
            raise ValueError("state must be a valid Indian state or union territory")
        return v

    @model_validator(mode="after")
    def validate_city_in_state(self):
        # Settings submits state + city together. Validate the pair only when both are set.
        if self.state and self.city and not is_valid_city(self.state, self.city):
            raise ValueError(f"city must be a district of {self.state}")
        return self

    @field_validator("college_other")
    @classmethod
    def clean_college_other(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def one_college_source(self):
        if self.college_id is not None and self.college_other:
            raise ValueError("Provide either college_id or college_other, not both.")
        return self
