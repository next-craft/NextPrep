import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class VerifyPasskeyRequest(BaseModel):
    listing_id: uuid.UUID
    passkey: str


class VerifyPasskeyResponse(BaseModel):
    payment_link_url: str


class OnboardResponse(BaseModel):
    message: Optional[str] = None
    onboarding_url: Optional[str] = None
    razorpay_account_id: Optional[str] = None


class OnboardCompleteRequest(BaseModel):
    razorpay_account_id: str


class OnboardCompleteResponse(BaseModel):
    status: str


class TransactionStatusResponse(BaseModel):
    status: str
    amount_rupees: int


class TransactionListItem(BaseModel):
    id: uuid.UUID
    role: str  # "buyer" | "seller" — relative to the requesting user
    listing_title: Optional[str] = None  # NULL if the listing was deleted (FK SET NULL)
    amount_rupees: int
    status: str
    created_at: datetime
