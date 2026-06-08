import uuid
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
