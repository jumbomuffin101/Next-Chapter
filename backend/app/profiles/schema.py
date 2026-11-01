"""Response contracts for the read-only alumni collection."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel


class CurrentRole(BaseModel):
    title: str
    employer: str
    start_date: date | None


class ProfileSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    city: str | None
    cohort: str | None
    graduation_year: int | None
    is_demo: bool
    last_updated_at: datetime
    current_role: CurrentRole | None


class ProfileList(BaseModel):
    items: list[ProfileSummary]
    total: int
    limit: int
    offset: int
