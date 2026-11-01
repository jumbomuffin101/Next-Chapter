"""HTTP adapter for the single authoritative confirmed-resume transaction."""
import uuid
from typing import Optional

from pydantic import BaseModel, Field

from work.database.crud import parse_date, save_confirmed_resume
from .schema import ParsedResume


class ConfirmPayload(BaseModel):
    resume: ParsedResume
    salary_min: Optional[int] = Field(None, ge=0, le=9_999_999_999, strict=True)
    salary_max: Optional[int] = Field(None, ge=0, le=9_999_999_999, strict=True)
    file_name: str = Field("uploaded_resume.pdf", min_length=1, max_length=255)
    # True from the profile editor: the form is the whole profile, so anything left out is removed
    replace: bool = False


def to_date(value: Optional[str]):
    """Compatibility helper; all callers use the authoritative date conversion."""
    return parse_date(value)


def save_resume(profile_id: uuid.UUID, payload: ConfirmPayload) -> dict:
    result = save_confirmed_resume(
        alumni_id=str(profile_id),
        parsed_resume=payload.resume.model_dump(mode="json"),
        file_name=payload.file_name,
        salary_min=payload.salary_min,
        salary_max=payload.salary_max,
        replace=payload.replace,
    )
    return {
        "profile_id": result["alumni_id"],
        "roles_added": result["work_experience_added"],
        "roles_updated": result["work_experience_updated"],
        "salary_saved": result["salary_saved"],
    }
