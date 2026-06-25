from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime
import uuid

from app.constants.locations import is_valid_state, is_valid_city

VALID_EXAM_CATEGORIES = {
    "JEE_MAINS", "JEE_ADVANCED", "NEET_UG", "NEET_PG",
    "UPSC_CSE", "UPSC_OTHER",
    "CA_FOUNDATION", "CA_INTERMEDIATE", "CA_FINAL",
    "GATE", "GMAT", "GRE", "IELTS", "CUET",
    "CLASS_9", "CLASS_10", "CLASS_11", "CLASS_12",
    "OTHER",
}
VALID_LISTING_TYPES = {"BOOK", "NOTES", "MODULE", "BUNDLE"}
VALID_CONDITIONS = {"A", "B", "C"}


class ListingCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=1000)
    exam_category: str
    subject: Optional[str] = None
    listing_type: str
    condition: str
    asking_price: int = Field(..., gt=0)
    original_price: Optional[int] = Field(None, gt=0)
    year: Optional[int] = Field(None, ge=2000, le=2026)
    edition: Optional[str] = Field(None, max_length=50)
    state: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)  # district within `state`
    images: list[str] = Field(..., min_length=1, max_length=5)  # at least one image required

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        if not is_valid_state(v):
            raise ValueError("state must be a valid Indian state or union territory")
        return v

    @model_validator(mode="after")
    def validate_city_in_state(self):
        if not is_valid_city(self.state, self.city):
            raise ValueError(f"city must be a district of {self.state}")
        return self

    @field_validator("exam_category")
    @classmethod
    def validate_exam_category(cls, v: str) -> str:
        if v not in VALID_EXAM_CATEGORIES:
            raise ValueError(f"exam_category must be one of: {sorted(VALID_EXAM_CATEGORIES)}")
        return v

    @field_validator("listing_type")
    @classmethod
    def validate_listing_type(cls, v: str) -> str:
        if v not in VALID_LISTING_TYPES:
            raise ValueError("listing_type must be BOOK, NOTES, MODULE, or BUNDLE")
        return v

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, v: str) -> str:
        if v not in VALID_CONDITIONS:
            raise ValueError("condition must be A, B, or C")
        return v

    @field_validator("images")
    @classmethod
    def validate_images(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) > 5:
            raise ValueError("images must have at most 5 URLs")
        return v


class ListingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=1000)
    subject: Optional[str] = None
    condition: Optional[str] = None
    asking_price: Optional[int] = Field(None, gt=0)
    original_price: Optional[int] = Field(None, gt=0)
    year: Optional[int] = Field(None, ge=2000, le=2026)
    edition: Optional[str] = Field(None, max_length=50)
    state: Optional[str] = Field(None, min_length=1)
    city: Optional[str] = Field(None, min_length=1)
    images: Optional[list[str]] = Field(None, max_length=5)
    is_available: Optional[bool] = None

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str | None) -> str | None:
        if v is not None and not is_valid_state(v):
            raise ValueError("state must be a valid Indian state or union territory")
        return v

    @model_validator(mode="after")
    def validate_city_in_state(self):
        # The edit form always submits state + city together; validate the pair when both are present.
        if self.state is not None and self.city is not None and not is_valid_city(self.state, self.city):
            raise ValueError(f"city must be a district of {self.state}")
        return self

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_CONDITIONS:
            raise ValueError("condition must be A, B, or C")
        return v

    @field_validator("images")
    @classmethod
    def validate_images(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) > 5:
            raise ValueError("images must have at most 5 URLs")
        return v


class ListingOut(BaseModel):
    id: uuid.UUID
    seller_id: uuid.UUID
    title: str
    description: Optional[str]
    exam_category: str
    subject: Optional[str]
    listing_type: str
    condition: str
    asking_price: int
    original_price: Optional[int]
    year: Optional[int]
    edition: Optional[str]
    state: Optional[str]
    city: str
    images: Optional[list[str]]
    is_available: bool
    is_sold: bool  # computed: sold_at IS NOT NULL — never expose sold_at itself
    views: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ListingCreateOut(BaseModel):
    listing: ListingOut
    passkey: str  # plaintext, returned once only
