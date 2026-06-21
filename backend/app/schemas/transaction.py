import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VerifyPasskeyRequest(BaseModel):
    listing_id: uuid.UUID
    # Exactly 8 digits. Rejecting malformed input with 422 before any HMAC work avoids
    # CPU-amplification from oversized payloads and treats junk as a bad request, not a
    # wasted passkey attempt.
    passkey: str = Field(..., min_length=8, max_length=8, pattern=r"^\d{8}$")


class CompleteTransactionResponse(BaseModel):
    """Returned when the buyer enters a correct passkey — the listing is now SOLD.
    Carries what the buyer needs to be prompted to rate the seller."""
    transaction_id: uuid.UUID
    seller_id: uuid.UUID
    seller_name: str
    listing_title: str


class TransactionListItem(BaseModel):
    id: uuid.UUID
    role: str  # "buyer" | "seller" — relative to the requesting user
    listing_title: Optional[str] = None  # NULL if the listing was deleted (FK SET NULL)
    created_at: datetime
    seller_id: uuid.UUID
    seller_name: Optional[str] = None
    # Only buyers can rate, and only once. True when this requester (a buyer) has not
    # yet rated this transaction. Always False for seller-side rows.
    can_rate: bool = False


class RatingCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = Field(None, max_length=1000)


class RatingResponse(BaseModel):
    transaction_id: uuid.UUID
    rating: int
    review: Optional[str] = None
    seller_rating: Optional[float] = None  # the seller's recomputed average
