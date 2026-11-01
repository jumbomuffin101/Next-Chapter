"""Generate one digest from a single enforced read-only PostgreSQL snapshot."""
from datetime import date, datetime, timezone
from uuid import UUID

from .content import CohortCounts, Profile, compose
from .render import Newsletter, render


def _catalog_and_counts(session, profile: Profile, matching):
    """Read public listings and a suppressed cohort aggregate, never peer profiles."""
    from sqlalchemy import select
    from work.database.models import Job
    from ..analytics.router import _aggregates, _population

    jobs = [dict(row) for row in session.execute(select(Job.__table__)).mappings()] if matching else []
    counts = None
    if (cohort := (profile.cohort or "").strip()):
        population = _population(include_demo=True)
        totals = session.execute(select(*_aggregates(population)).where(
            population.c.cohort == cohort, population.c.is_demo.is_(profile.is_demo),
        )).mappings().one()
        counts = CohortCounts(totals["total_alumni"], totals["alumni_with_current_roles"],
                              totals["alumni_with_confirmed_resumes"])
    return jobs, counts


def generate_newsletter(profile_id: UUID | str, *, app_url: str, events_after: date | None = None,
                        demo_only: bool = False) -> Newsletter:
    """Internal service only. Caller must authorize access before exposing this result.

    Does not send, persist, refresh jobs, or log personal content. A missing profile
    raises LookupError. Configuration/connection errors propagate to the caller.
    """
    # Lazy database imports keep the synthetic preview entirely configuration-free.
    from sqlalchemy import case, select
    from work.database.database import readonly_session
    from work.database.models import Alumni, SalaryRecord, Skill, WorkExperience
    from ..jobs.matching import MatchProfile, title_family
    from .content import application_url

    application_url(app_url)  # Reject unsafe links before accessing personal data.
    identifier = UUID(str(profile_id))
    today = datetime.now(timezone.utc).date()
    with readonly_session() as session:
        person = session.execute(select(Alumni.first_name, Alumni.city, Alumni.cohort, Alumni.is_demo)
                                 .where(Alumni.id == identifier)).mappings().one_or_none()
        if person is None:
            raise LookupError("Alumni profile not found")
        if demo_only and not person["is_demo"]:
            raise PermissionError("Interactive newsletters are available for synthetic demo accounts only")
        profile = Profile(**person)
        current_rank = case((WorkExperience.is_current.is_(True) & WorkExperience.end_date.is_(None), 0), else_=1)
        titles = session.scalars(select(WorkExperience.title).where(
            WorkExperience.alumni_id == identifier,
            WorkExperience.start_date.is_(None) | (WorkExperience.start_date <= today),
        ).order_by(current_rank, WorkExperience.start_date.desc().nulls_last(), WorkExperience.id)).all()
        salary = session.execute(select(SalaryRecord.salary_min, SalaryRecord.salary_max).where(
            SalaryRecord.alumni_id == identifier,
        ).order_by(SalaryRecord.effective_date.desc().nulls_last(), SalaryRecord.id).limit(1)).first()
        skills = tuple(session.scalars(select(Skill.name).where(
            Skill.alumni_id == identifier,
        ).order_by(Skill.name, Skill.id)))
        # Same latest-classifiable-title policy as the existing matching endpoint.
        matching = MatchProfile(next((t for t in titles if title_family(t)), titles[0]), profile.city,
                                salary.salary_min if salary else None, salary.salary_max if salary else None,
                                skills) if titles else None
        jobs, counts = _catalog_and_counts(session, profile, matching)
    return render(compose(profile, matching, jobs, counts, app_url=app_url, today=today, events_after=events_after))


def generate_demo_newsletter(profile: Profile, matching, *, app_url: str) -> Newsletter:
    """Compute from caller-supplied synthetic fields; never retrieve an alumnus by ID."""
    if not profile.is_demo:
        raise ValueError("Synthetic demo profile required")
    from work.database.database import readonly_session
    from .content import application_url

    application_url(app_url)
    today = datetime.now(timezone.utc).date()
    with readonly_session() as session:
        jobs, counts = _catalog_and_counts(session, profile, matching)
    return render(compose(profile, matching, jobs, counts, app_url=app_url, today=today))
