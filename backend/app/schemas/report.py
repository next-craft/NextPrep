import uuid
from typing import Optional, Literal

from pydantic import BaseModel, Field

ReportReason = Literal[
    "PIRACY", "CONTACT_INFO", "SPAM", "NOT_STUDY_MATERIAL",
    "PROHIBITED", "ABUSIVE", "OTHER",
]


class ReportCreate(BaseModel):
    listing_id: uuid.UUID
    reason: ReportReason
    note: Optional[str] = Field(None, max_length=1000)


class ReportAck(BaseModel):
    # Deliberately minimal — never expose report counts, status, or other reporters.
    received: bool = True
