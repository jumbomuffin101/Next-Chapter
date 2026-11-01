"""Dashboard aggregates over distinct alumni, with explicit demo/real splits."""
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Integer, cast, exists, func, select

from work.database.database import readonly_session
from work.database.models import Alumni, ResumeUpload, WorkExperience

router = APIRouter(prefix="/analytics", tags=["analytics"])


class Metrics(BaseModel):
    total_alumni: int
    alumni_with_current_roles: int
    alumni_with_confirmed_resumes: int
    total_career_history_records: int


class SegmentedMetrics(Metrics):
    demo: Metrics
    real: Metrics


class CohortMetrics(SegmentedMetrics):
    cohort: str | None


class CityMetrics(SegmentedMetrics):
    city: str | None


class Summary(SegmentedMetrics):
    by_cohort: list[CohortMetrics]
    by_city: list[CityMetrics]
    data_note: str


def _population(include_demo):
    current = exists(select(WorkExperience.id).where(
        WorkExperience.alumni_id == Alumni.id,
        WorkExperience.is_current.is_(True),
        WorkExperience.end_date.is_(None),
        (WorkExperience.start_date.is_(None) | (WorkExperience.start_date <= func.current_date())),
    ))
    confirmed = exists(select(ResumeUpload.id).where(
        ResumeUpload.alumni_id == Alumni.id, ResumeUpload.confirmed.is_(True),
    ))
    careers = select(func.count(WorkExperience.id)).where(
        WorkExperience.alumni_id == Alumni.id,
    ).correlate(Alumni).scalar_subquery()
    query = select(
        Alumni.id, Alumni.is_demo,
        func.nullif(func.trim(Alumni.cohort), "").label("cohort"),
        func.nullif(func.trim(Alumni.city), "").label("city"),
        cast(current, Integer).label("has_current"),
        cast(confirmed, Integer).label("has_confirmed"),
        careers.label("careers"),
    )
    if not include_demo:
        query = query.where(Alumni.is_demo.is_(False))
    return query.subquery()


def _aggregates(population):
    columns = []
    values = {
        "total_alumni": func.count(population.c.id),
        "alumni_with_current_roles": func.sum(population.c.has_current),
        "alumni_with_confirmed_resumes": func.sum(population.c.has_confirmed),
        "total_career_history_records": func.sum(population.c.careers),
    }
    for prefix, condition in (("", None), ("demo_", population.c.is_demo.is_(True)),
                              ("real_", population.c.is_demo.is_(False))):
        for name, aggregate in values.items():
            expression = aggregate if condition is None else aggregate.filter(condition)
            columns.append(func.coalesce(expression, 0).label(prefix + name))
    return columns


def _metrics(row):
    result = {name: row[name] for name in Metrics.model_fields}
    for group in ("demo", "real"):
        result[group] = {name: row[f"{group}_{name}"] for name in Metrics.model_fields}
    return result


@router.get("/summary", response_model=Summary)
def summary(include_demo: bool = True):
    """Counts describe recorded data, not independently verified employment outcomes."""
    population = _population(include_demo)
    columns = _aggregates(population)
    with readonly_session() as session:
        total = session.execute(select(*columns).select_from(population)).mappings().one()
        breakdowns = {}
        for field in ("cohort", "city"):
            group = population.c[field]
            rows = session.execute(
                select(group, *columns).select_from(population)
                .group_by(group).order_by(group.asc().nulls_last())
            ).mappings()
            breakdowns[f"by_{field}"] = [{field: row[field], **_metrics(row)} for row in rows]
    return Summary(
        **_metrics(total), **breakdowns,
        data_note="Demo records are synthetic. Recorded current roles and confirmed resumes do not establish verified employment outcomes.",
    )
