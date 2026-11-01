"""Step 3: cheap sanity checks / cleanup before showing the user the review screen."""
import re
from datetime import date

from .schema import ParsedResume

_DATE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2]))?(-\d{2})?$")


def _clean_date(value):
    if value is None:
        return None
    value = value.strip()
    if not _DATE.fullmatch(value):
        return None
    try:
        date.fromisoformat(value + ("-01-01" if len(value) == 4 else "-01" if len(value) == 7 else ""))
    except ValueError:
        return None
    return value


def normalize(resume: ParsedResume) -> ParsedResume:
    for job in resume.work_experience:
        original_end = job.end_date
        job.start_date = _clean_date(job.start_date)
        job.end_date = _clean_date(job.end_date)
        if original_end and job.end_date is None:
            job.is_current = False
            warning = "A role has an invalid end date; please correct it and confirm whether it is current."
            if warning not in resume.warnings:
                resume.warnings.append(warning)
        elif job.end_date is not None:
            job.is_current = False
    resume.skills = sorted({s.strip() for s in resume.skills if s.strip()})
    resume.certifications = [c.strip() for c in resume.certifications if c.strip()]
    # Most recent first, so work_experience[0] is the "current/latest" role
    resume.work_experience.sort(key=lambda j: j.start_date or "", reverse=True)
    return resume
