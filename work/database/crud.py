
import uuid
import re
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .database import SessionLocal
from .models import (
    Alumni,
    WorkExperience,
    Education,
    Skill,
    Certification,
    ResumeUpload,
    SalaryRecord,
)


class ProfileNotFoundError(ValueError, LookupError):
    pass


def parse_date(value):
    """Partial dates use January/the first day; full ISO dates retain their day."""
    if value is None or value == "":
        return None

    if isinstance(value, date):
        return value.date() if isinstance(value, datetime) else value

    text = str(value).strip()
    if not re.fullmatch(r"\d{4}(?:-\d{2})?(?:-\d{2})?", text):
        raise ValueError("Dates must use YYYY, YYYY-MM, or YYYY-MM-DD")
    parts = text.split("-")
    try:
        return date(int(parts[0]), int(parts[1]) if len(parts) > 1 else 1,
                    int(parts[2]) if len(parts) > 2 else 1)
    except ValueError:
        raise ValueError("Invalid calendar date") from None


def required_text(value, field, max_length=None):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    value = value.strip()
    if max_length and len(value) > max_length:
        raise ValueError(f"{field} exceeds {max_length} characters")
    return value


def optional_text(value, field, max_length=None):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    return required_text(value, field, max_length) if value.strip() else None


def normalize_list(value, field):
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def role_salary(item: dict):
    """A role's (min, max) salary, or None when it has none; ValueError when only one bound or an impossible range."""
    low, high = item.get("salary_min"), item.get("salary_max")
    if low is None and high is None:
        return None
    if any(type(v) is not int for v in (low, high)) or not 0 < low <= high <= 9_999_999_999:
        raise ValueError("Each role's salary needs a minimum and a maximum, with the minimum no higher than the maximum")
    return low, high


def save_confirmed_resume(
    alumni_id: str,
    parsed_resume: dict,
    file_name: str = "uploaded_resume.pdf",
    *,
    salary_min: int | None = None,
    salary_max: int | None = None,
    replace: bool = False,
):
    """
    Persist a user-confirmed resume.

    - replace=False (resume upload): merge, keeping roles and entries the resume leaves out.
    - replace=True (profile editor, which shows the whole profile): save exactly what was sent,
      so removed roles, schools, skills and certifications are deleted and cleared fields are cleared.

    - Requires an existing alumni profile.
    - Preserves TKH cohort and graduation year.
    - Avoids duplicate career and skill records.
    - Saves all changes in one transaction.
    - Does not persist unconfirmed parser output.
    """

    if not isinstance(parsed_resume, dict):
        raise ValueError("Resume must be a JSON object")

    alumni_uuid = uuid.UUID(str(alumni_id))

    full_name = required_text(
        parsed_resume.get("full_name"), "full_name"
    )
    name_parts = full_name.split(maxsplit=1)
    first_name = required_text(name_parts[0], "first_name", 100)
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    if len(last_name) > 100:
        raise ValueError("last_name exceeds 100 characters")

    email = required_text(
        parsed_resume.get("email"), "email", 255
    ).lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("A valid email is required")

    phone = optional_text(parsed_resume.get("phone"), "phone", 30)
    location = optional_text(parsed_resume.get("location"), "location", 100)
    file_name = required_text(file_name, "file_name", 255)
    has_salary = salary_min is not None or salary_max is not None
    if has_salary:
        if any(type(v) is not int or v < 0 or v > 9_999_999_999 for v in (salary_min, salary_max)):
            raise ValueError("Provide both salary bounds as nonnegative whole annual amounts within database limits")
        if salary_min > salary_max:
            raise ValueError("salary_min cannot exceed salary_max")

    work_items = normalize_list(
        parsed_resume.get("work_experience"),
        "work_experience",
    )
    education_items = normalize_list(
        parsed_resume.get("education"),
        "education",
    )
    skill_items = normalize_list(
        parsed_resume.get("skills"), "skills"
    )
    certification_items = normalize_list(
        parsed_resume.get("certifications"),
        "certifications",
    )

    # Validate all nested data before starting writes.
    normalized_work = []

    for item in work_items:
        if not isinstance(item, dict):
            raise ValueError("Each work experience must be an object")

        start = parse_date(item.get("start_date"))
        end = parse_date(item.get("end_date"))

        if start and end and end < start:
            raise ValueError("Work end_date precedes start_date")
        is_current = item.get("is_current", end is None)
        if not isinstance(is_current, bool):
            raise ValueError("is_current must be a boolean")
        if is_current and end is not None:
            raise ValueError("A current role cannot have an end_date")
        if is_current and start and start > datetime.now(timezone.utc).date():
            raise ValueError("A current role cannot start in the future")

        normalized_work.append({
            "employer": required_text(
                item.get("employer"), "employer", 255
            ),
            "title": required_text(
                item.get("title"), "title", 255
            ),
            "location": optional_text(item.get("location"), "work location", 150),
            "start_date": start,
            "end_date": end,
            "is_current": is_current,
            "description": optional_text(item.get("description"), "description"),
            "salary": role_salary(item),  # saved as a salary entry linked to the role, not a work_experience column
        })

    # Repeated entries in one request have one identity; the last edit wins.
    normalized_work = list({
        (w["employer"].casefold(), w["title"].casefold(), w["start_date"]): w
        for w in normalized_work
    }.values())

    normalized_education = []

    for item in education_items:
        if not isinstance(item, dict):
            raise ValueError("Each education entry must be an object")

        start = parse_date(item.get("start_date"))
        end = parse_date(item.get("end_date"))

        if start and end and end < start:
            raise ValueError("Education end_date precedes start_date")

        normalized_education.append({
            "school": required_text(
                item.get("school"), "school", 255
            ),
            "degree": optional_text(item.get("degree"), "degree", 150),
            "field_of_study": optional_text(item.get("field_of_study"), "field_of_study", 150),
            "start_year": start.year if start else None,
            "graduation_year": end.year if end else None,
        })

    skills = [
        required_text(name, "skill", 100)
        for name in skill_items
    ]

    certifications = [
        required_text(name, "certification", 255)
        for name in certification_items
    ]

    try:
        return _persist_resume(
            alumni_uuid, parsed_resume, file_name, first_name, last_name, email,
            phone, location, normalized_work, normalized_education, skills,
            certifications, salary_min, salary_max, has_salary, replace,
        )
    except IntegrityError:
        # The transaction context has already rolled back. Never leak SQL/PII.
        raise ValueError("Resume conflicts with an existing database record") from None


def _persist_resume(alumni_uuid, parsed_resume, file_name, first_name, last_name,
                    email, phone, location, normalized_work, normalized_education,
                    skills, certifications, salary_min, salary_max, has_salary, replace=False):
    with SessionLocal() as session:
        with session.begin():
            # Serialize confirmations for this alumnus without adding schema constraints.
            alumni = session.scalar(select(Alumni).where(Alumni.id == alumni_uuid).with_for_update())

            if alumni is None:
                raise ProfileNotFoundError("Alumni profile not found")

            # Prevent one profile from claiming another's email.
            other = session.scalar(
                select(Alumni).where(
                    func.lower(func.trim(Alumni.email)) == email,
                    Alumni.id != alumni_uuid,
                )
            )
            if other:
                raise ValueError(
                    "Email belongs to another alumni profile"
                )

            alumni.first_name = first_name
            alumni.last_name = last_name
            alumni.email = email
            # Relationship-only updates must also refresh this timestamp.
            now = datetime.now(timezone.utc)
            alumni.updated_at = now

            if phone is not None or replace:
                alumni.phone = phone

            if location is not None or replace:
                alumni.city = location
            elif not alumni.city:
                roles = sorted(normalized_work, key=lambda w: w["start_date"] or date.min, reverse=True)
                guessed = next((w["location"] for w in roles
                                if w["location"] and w["location"].casefold() != "remote"), None)
                alumni.city = guessed[:100] if guessed else None

            existing_work = session.scalars(
                select(WorkExperience).where(
                    WorkExperience.alumni_id == alumni_uuid
                )
            ).all()

            added_work = 0
            updated_work = 0
            kept_work = set()
            role_jobs = []  # (submitted role, its row), for the per-role salaries below

            for item in normalized_work:
                # Stable job identity: employer, title, start date.
                matching = next(
                    (
                        job for job in existing_work
                        if job.employer.strip().casefold()
                        == item["employer"].casefold()
                        and job.title.strip().casefold()
                        == item["title"].casefold()
                        and job.start_date == item["start_date"]
                    ),
                    None,
                )

                if matching:
                    matching.end_date = item["end_date"]
                    matching.is_current = item["is_current"]
                    if item["location"] is not None or replace:
                        matching.location = item["location"]
                    if item["description"] is not None or replace:
                        matching.description = item["description"]
                    kept_work.add(id(matching))
                    role_jobs.append((item, matching))
                    updated_work += 1
                else:
                    job = WorkExperience(
                        alumni_id=alumni_uuid,
                        source="resume",
                        **{key: value for key, value in item.items() if key != "salary"},
                    )
                    session.add(job)
                    existing_work.append(job)
                    kept_work.add(id(job))
                    role_jobs.append((item, job))
                    added_work += 1

            if replace:
                for job in existing_work:
                    if id(job) not in kept_work:
                        session.delete(job)

            session.flush()  # new roles get their ids; deleted roles' salaries are unlinked by the database
            for item, job in role_jobs:
                _save_role_salary(session, alumni_uuid, job, item["salary"], replace, now)

            if has_salary:
                salary = session.scalar(select(SalaryRecord).where(
                    SalaryRecord.alumni_id == alumni_uuid,
                    SalaryRecord.source == "self_reported",
                    SalaryRecord.effective_date == now.date(),
                ).order_by(SalaryRecord.id).limit(1))
                if salary is None:
                    salary = SalaryRecord(alumni_id=alumni_uuid, source="self_reported",
                                          effective_date=now.date())
                    session.add(salary)
                salary.salary_min = salary_min
                salary.salary_max = salary_max

            existing_education = session.scalars(
                select(Education).where(
                    Education.alumni_id == alumni_uuid
                )
            ).all()

            kept_education = set()
            for item in normalized_education:
                matching = next(
                    (
                        education for education in existing_education
                        if education.school.strip().casefold()
                        == item["school"].casefold()
                        and education.degree == item["degree"]
                        and education.field_of_study
                        == item["field_of_study"]
                    ),
                    None,
                )

                if matching:
                    if item["graduation_year"] is not None or replace:
                        matching.graduation_year = item["graduation_year"]
                    if item["start_year"] is not None or replace:
                        matching.start_year = item["start_year"]
                    kept_education.add(id(matching))
                else:
                    education = Education(
                        alumni_id=alumni_uuid, **item
                    )
                    session.add(education)
                    existing_education.append(education)
                    kept_education.add(id(education))

            if replace:
                for education in existing_education:
                    if id(education) not in kept_education:
                        session.delete(education)

            skill_rows = session.scalars(
                select(Skill).where(Skill.alumni_id == alumni_uuid)
            ).all()
            if replace:
                wanted = {name.casefold() for name in skills}
                for row in skill_rows:
                    if row.name.strip().casefold() not in wanted:
                        session.delete(row)
                skill_rows = [row for row in skill_rows if row.name.strip().casefold() in wanted]
            existing_skills = {skill.name.strip().casefold() for skill in skill_rows}

            for name in skills:
                if name.casefold() not in existing_skills:
                    session.add(Skill(
                        alumni_id=alumni_uuid,
                        name=name,
                    ))
                    existing_skills.add(name.casefold())

            cert_rows = session.scalars(
                select(Certification).where(Certification.alumni_id == alumni_uuid)
            ).all()
            if replace:
                wanted = {name.casefold() for name in certifications}
                for row in cert_rows:
                    if row.name.strip().casefold() not in wanted:
                        session.delete(row)
                cert_rows = [row for row in cert_rows if row.name.strip().casefold() in wanted]
            existing_certs = {cert.name.strip().casefold() for cert in cert_rows}

            for name in certifications:
                if name.casefold() not in existing_certs:
                    session.add(Certification(
                        alumni_id=alumni_uuid,
                        name=name,
                    ))
                    existing_certs.add(name.casefold())

            # Store the confirmed snapshot for provenance.
            # Do not store raw PDF content.
            session.add(ResumeUpload(
                alumni_id=alumni_uuid,
                file_name=file_name,
                parsed_data=parsed_resume,
                confirmed=True,
                uploaded_at=now,
            ))

            session.flush()

            result = {
                "success": True,
                "alumni_id": str(alumni_uuid),
                "work_experience_added": added_work,
                "resume_confirmed": True,
                "work_experience_updated": updated_work,
                "salary_saved": has_salary,
            }

    return result


def _save_role_salary(session, alumni_uuid, job, salary, replace, now):
    """A role's own salary is its earliest linked self-reported entry, dated at the role's start month.
    Later entries linked to the role (raises picked in the salary history) are left alone."""
    month = job.start_date.replace(day=1) if job.start_date else None
    own = session.scalar(select(SalaryRecord).where(
        SalaryRecord.alumni_id == alumni_uuid, SalaryRecord.source == "self_reported",
        SalaryRecord.work_experience_id == job.id,
    ).order_by(SalaryRecord.effective_date).limit(1))
    if salary is None:
        if own is not None and replace:  # the editor shows every role, so "Not set" means remove it
            session.delete(own)
        return
    if own is None and month is not None:
        # reuse an unlinked entry in the role's start month (older data, or one left by renaming the role) instead of a duplicate
        own = session.scalar(select(SalaryRecord).where(
            SalaryRecord.alumni_id == alumni_uuid, SalaryRecord.source == "self_reported",
            SalaryRecord.work_experience_id.is_(None),
            SalaryRecord.effective_date >= month, SalaryRecord.effective_date < _next_month(month),
        ).order_by(SalaryRecord.effective_date).limit(1))
    if own is None:
        own = SalaryRecord(alumni_id=alumni_uuid, source="self_reported")
        session.add(own)
    own.work_experience_id = job.id
    own.salary_min, own.salary_max = salary
    own.effective_date = month or own.effective_date or now.date()


def _next_month(day: date) -> date:
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)
