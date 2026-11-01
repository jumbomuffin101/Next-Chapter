"""Pure content selection shared by database generation and the offline preview."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

from ..jobs.matching import MatchProfile, title_family, top_matches
from ..network.events import events_for

TITLE = "Your Monthly Career & Community Digest"
MIN_COHORT_SIZE = 5


def safe_url(value: str) -> str | None:
    """Allow absolute web links only, without embedded credentials/control characters."""
    if not isinstance(value, str) or any(ord(c) < 33 or ord(c) == 127 for c in value):
        return None
    try:
        parts = urlsplit(value)
        parts.port  # Validate malformed port numbers too.
        if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username or parts.password:
            return None
    except ValueError:
        return None
    return value


def application_url(value: str) -> str:
    if not safe_url(value) or urlsplit(value).query or urlsplit(value).fragment:
        raise ValueError("Application URL must be an absolute HTTP(S) URL without credentials, query, or fragment")
    return value.rstrip("/") + "/"


@dataclass(frozen=True)
class Profile:
    first_name: str = ""
    city: str | None = None
    cohort: str | None = None
    is_demo: bool = False


@dataclass(frozen=True)
class CohortCounts:
    total: int
    with_current_roles: int
    with_confirmed_resumes: int


@dataclass(frozen=True)
class Opportunity:
    title: str
    company: str
    location: str
    apply_url: str
    why_matched: str
    updated_on: date | None
    example: bool = False


@dataclass(frozen=True)
class Event:
    title: str
    date: date
    location: str
    details: str
    example: bool


@dataclass(frozen=True)
class Content:
    first_name: str
    generated_on: date
    app_url: str
    jobs: tuple[Opportunity, ...]
    events: tuple[Event, ...]
    cohort_message: str
    is_demo: bool
    title: str = TITLE


def _updated(value) -> datetime | None:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def select_jobs(profile: MatchProfile | None, jobs: list[dict], *, examples: bool = False) -> tuple[Opportunity, ...]:
    if profile is None:
        return ()
    candidates = [j for j in jobs if safe_url(j.get("absolute_url"))]
    # Reuse eligibility, seniority, location, salary scoring, and deterministic ties.
    matches = top_matches(profile, candidates, n=len(candidates))
    dates = {str(j["id"]): _updated(j.get("updated_at")) for j in candidates}
    # Greenhouse provides employer update dates, not a reliable original posting date.
    matches.sort(key=lambda m: (-m["score"], -(dates[str(m["job_id"])].timestamp()
                                             if dates[str(m["job_id"])] else float("-inf"))))
    unique_matches = []
    seen_urls = set()
    for match in matches:
        if match["apply_url"] in seen_urls:
            continue
        seen_urls.add(match["apply_url"])
        unique_matches.append(match)
        if len(unique_matches) == 5:
            break
    return tuple(Opportunity(
        title=m["title"], company=m["company"], location=m["location"] or "Location not listed",
        apply_url=m["apply_url"], why_matched=m["why_matched"],
        updated_on=dates[str(m["job_id"])].date() if dates[str(m["job_id"])] else None,
        example=examples,
    ) for m in unique_matches)


def select_events(profile: Profile, matching: MatchProfile | None, today: date) -> tuple[Event, ...]:
    family = (title_family(matching.latest_title) if matching else None) or "other"
    data = events_for(profile.city, family, today)
    candidates = []
    for entry in [*data.get("local", []), *data.get("online", [])]:
        try:
            when = date.fromisoformat(entry["date"])
        except (KeyError, ValueError, TypeError):
            continue
        if when > today:
            candidates.append((entry, when))
    candidates.sort(key=lambda pair: (not pair[0].get("for_you", False),
                                      pair[0].get("virtual", False), pair[1], pair[0]["id"]))
    return tuple(Event(e["title"], when, e["where"], f"{e['kind']} · {e['time']} · Hosted by {e['host']}",
                       bool(e.get("sample", False))) for e, when in candidates[:3])


def compose(profile: Profile, matching: MatchProfile | None, jobs: list[dict],
            cohort_counts: CohortCounts | None, *, app_url: str, today: date,
            example_jobs: bool = False, events_after: date | None = None) -> Content:
    url = application_url(app_url)
    cohort = (profile.cohort or "").strip()
    if not cohort:
        message = "Add your TKH cohort to your profile to see a community summary here."
    elif cohort_counts is None or cohort_counts.total < MIN_COHORT_SIZE:
        message = f"Cohort {cohort}: there is not enough shareable data for an aggregate summary yet."
    else:
        label = "Synthetic demo records only" if profile.is_demo else "Real records only; synthetic demo records excluded"
        message = (f"Cohort {cohort} — {label}: {cohort_counts.total} alumni on record; "
                   f"{cohort_counts.with_current_roles} have recorded current roles; "
                   f"{cohort_counts.with_confirmed_resumes} have confirmed resumes. "
                   "These are current totals, not changes this month or verified employment outcomes.")
    return Content(profile.first_name.strip() or "there", today, url,
                   select_jobs(matching, jobs, examples=example_jobs), select_events(profile, matching, max(today, events_after or today)),
                   message, profile.is_demo)
