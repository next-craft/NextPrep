import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CollegeBrief(BaseModel):
    """Embedded in listing/user responses for display + linking."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    name: str


class CollegeOut(CollegeBrief):
    model_config = ConfigDict(from_attributes=True)  # inherited from CollegeBrief; declared for visibility
    state: Optional[str] = None
    city: Optional[str] = None
