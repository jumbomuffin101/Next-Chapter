"""Parsed-resume contract. Share this shape with the frontend + DB owners.

If you change a field here, tell the team (it is the shared contract).
"""
from typing import Optional

from pydantic import BaseModel, Field


class Education(BaseModel):
    school: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = Field(None, description="YYYY, YYYY-MM, or YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="YYYY, YYYY-MM, or YYYY-MM-DD; null if ongoing")


class WorkExperience(BaseModel):
    employer: str
    title: str
    location: Optional[str] = None
    start_date: Optional[str] = Field(None, description="YYYY, YYYY-MM, or YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="YYYY, YYYY-MM, or YYYY-MM-DD; null when unknown/ongoing")
    is_current: bool = False
    description: Optional[str] = None
    # What the person earned in this role (whole yearly dollars); both or neither. Shown on the growth chart.
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None


class ParsedResume(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    # Found on the resume (never asked for). Shared with other alumni only if the person joins the network.
    linkedin_url: Optional[str] = None
    education: list[Education] = []
    work_experience: list[WorkExperience] = []
    skills: list[str] = []
    certifications: list[str] = []
    # Added for the rule-based parser: things the review screen should highlight.
    warnings: list[str] = []
