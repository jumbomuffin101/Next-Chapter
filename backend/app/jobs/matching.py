"""Simple scoring matcher. No embeddings, no ML.

score = role (required, 1-3) + location (required if city known, 1-2)
      + saved skill overlap (up to 0.75 bonus) + salary overlap (+1 bonus)
"""
import re
from html import unescape
from dataclasses import dataclass
from typing import Optional

from ..parsing.rule_parser import US_STATES

# title family -> keywords. Extend with TKH's actual alumni roles.
TITLE_FAMILIES: dict[str, list[str]] = {
    "software": ["software", "developer", "engineer", "swe", "backend", "frontend", "full stack", "fullstack"],
    "data": ["data", "analyst", "analytics", "bi ", "machine learning", "scientist"],
    # not bare "product": that also matched "Account Executive, Product Sales" and "Product Marketing"
    "product": ["product manager", "product owner", "product management", "program manager", "head of product", "product lead"],
    # short keywords start with a space so they match whole words: not "ui" in "Recruiter" or "it " in "Audit "
    "design": ["designer", "design", " ux", " ui"],
    "support": ["support", "customer success", "technical support", "help desk", " it "],
    "ops": ["operations", "coordinator", "associate", "administrator"],
    "sales": ["sales", "account executive", "business development", "sdr", "bdr"],
}


# HR roles that name the team they support ("Engineering Compensation Partner", "Engineering Recruiter")
_HR_TITLE = re.compile(r"\b(compensation|people partners?|recruit\w*)\b", re.I)


def title_family(title: str) -> Optional[str]:
    if _HR_TITLE.search(title):
        return None
    t = f" {title.lower()} "
    for family, kws in TITLE_FAMILIES.items():
        if any(k in t for k in kws):
            return family
    return None


# Words that say "level" or "kind of position", not what the person does. Sharing only these
# ("Course Assistant" vs "Executive Assistant") is not a role match.
GENERIC_TITLE_WORDS = {
    "senior", "junior", "lead", "principal", "staff", "intern", "internship", "assistant",
    "associate", "manager", "director", "head", "vice", "president", "chief", "executive",
    "the", "and", "for", "with",
}


def _tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", title.lower()) if len(w) > 2 and w not in GENERIC_TITLE_WORDS}


# Seniority: 0 intern, 1 junior, 2 unlabeled, 3 senior, 4 lead/manager/staff/principal, 5 director+.
_LEVEL_PATTERNS: list[tuple[int, re.Pattern]] = [
    (0, re.compile(r"\b(intern|internship|co-?op|apprentice|trainee)\b")),
    (1, re.compile(r"\b(junior|jr|entry|associate)\b")),
    (3, re.compile(r"\b(senior|sr)\b")),
    # "Product/Program/Project Manager" is the role itself; "Engineering Manager" is a step up
    (4, re.compile(r"\b(lead|staff|principal)\b|(?<!product )(?<!program )(?<!project )\bmanager\b")),
    (5, re.compile(r"\b(director|vp|vice president|head of|chief)\b")),
]


def seniority(title: str) -> int:
    t = title.lower()
    return max((lvl for lvl, pat in _LEVEL_PATTERNS if pat.search(t)), default=2)


def _level_ok(profile_level: int, job_level: int) -> bool:
    """Not more than one step up (two for interns, whose next step is an unlabeled entry role),
    and not far below the user's level."""
    up = 2 if profile_level == 0 else 1
    return profile_level - 2 <= job_level <= profile_level + up


_US_MARKER = re.compile(
    rf"(?i:\b(?:us|usa|u\.s\.a?\.?|united states|america)\b)|,\s*(?:{US_STATES})\b"
)


def _is_foreign_remote(loc: str) -> bool:
    """'Remote - Argentina' / 'Remote UK' yes; 'Remote', 'Remote - USA', 'Remote, CA' no."""
    if "remote" not in loc.lower():
        return False
    qualifier = re.sub(r"remote|[^A-Za-z]+", "", loc, flags=re.I)
    return bool(qualifier) and not _US_MARKER.search(loc)


@dataclass
class MatchProfile:
    latest_title: str
    city: Optional[str]
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    skills: tuple[str, ...] = ()


# Same labor market: a Newark alumna should see NYC jobs and vice versa.
METRO_GROUPS: list[set[str]] = [
    {"new york", "new york city", "nyc", "newark", "jersey city", "hoboken", "brooklyn", "bronx", "manhattan", "queens", "harlem"},
]


def _metro(city: Optional[str]) -> Optional[set[str]]:
    name = (city or "").lower().split(",")[0].strip()
    return next((g for g in METRO_GROUPS if name in g), None)


def _state(city: Optional[str]) -> Optional[str]:
    if city and "," in city:
        return city.rsplit(",", 1)[1].strip().upper() or None
    return None


def score_job(profile: MatchProfile, job: dict) -> tuple[float, list[str]]:
    """Returns (score, reasons). Score 0 means "do not show".

    Hard requirements: a role signal, and (when we know the user's city) a location signal.
    Salary only adds points; a missing range on either side never excludes a job.
    """
    score, reasons = 0.0, []

    # Seniority: don't show an intern the "Engineering Manager" roles, or a senior the internships
    if not _level_ok(seniority(profile.latest_title), seniority(job["title"])):
        return 0.0, []

    # Remote roles outside the US are no use to TKH alumni
    if _is_foreign_remote(job.get("location") or ""):
        return 0.0, []

    # Role (required). An HR job only matches an HR profile, even if both titles say "Engineering"
    if _HR_TITLE.search(job["title"]) and not _HR_TITLE.search(profile.latest_title):
        return 0.0, []
    pf, jf = title_family(profile.latest_title), title_family(job["title"])
    overlap = _tokens(profile.latest_title) & _tokens(job["title"])
    role = 0.0
    if pf and pf == jf:
        role = 2 + (1 if overlap else 0)
        reasons.append("Similar role")
    elif overlap:
        role = 1
        reasons.append("Related title")
    if role == 0:
        return 0.0, []
    score += role

    # Location (required if the profile has a city; remote always qualifies)
    loc = (job.get("location") or "").lower()
    if "remote" in loc:
        score += 1.5
        reasons.append("Remote")
    elif profile.city:
        city = profile.city.lower().split(",")[0].strip()
        state = _state(profile.city)
        if city and city in loc:
            score += 2
            reasons.append("Same city")
        elif (m := _metro(profile.city)) and any(n in loc for n in m):
            score += 1.5
            reasons.append("Same metro area")
        elif state and re.search(rf"(?:,|\s){state.lower()}(?:\b|$)", loc):
            score += 1
            reasons.append("Same state")
        else:
            return 0.0, []

    # Use saved skills only to order already-eligible jobs. Greenhouse descriptions
    # may contain HTML, so remove tags before looking for whole skill names.
    searchable = re.sub(r"<[^>]*>", " ", unescape(f"{job['title']} {job.get('description') or ''}")).casefold()
    relevant_skills = sorted({skill.strip() for skill in profile.skills if skill and len(skill.strip()) > 1
                              and re.search(rf"(?<!\w){re.escape(skill.strip().casefold())}(?!\w)", searchable)},
                             key=str.casefold)
    if relevant_skills:
        score += min(len(relevant_skills), 3) * 0.25
        reasons.append("Relevant skills: " + ", ".join(relevant_skills[:3]))

    # Salary (bonus only, and only if both sides have a range)
    jmin, jmax = job.get("salary_min"), job.get("salary_max")
    if jmin and jmax and profile.salary_min and profile.salary_max:
        if jmin <= profile.salary_max and jmax >= profile.salary_min:
            score += 1
            reasons.append("Salary in range")

    return score, reasons


def top_matches(profile: MatchProfile, jobs: list[dict], n: int = 10) -> list[dict]:
    scored = []
    for job in jobs:
        s, reasons = score_job(profile, job)
        if s > 0:
            scored.append((s, reasons, job))
    scored.sort(key=lambda x: (-x[0], x[2]["title"].casefold(),
                              x[2]["company"].casefold(), str(x[2]["id"])))
    return [
        {
            "job_id": j["id"],
            "title": j["title"],
            "company": j["company"],
            "location": j["location"],
            # Numeric columns come back as Decimal; keep the response shape (plain ints)
            "salary_min": int(j["salary_min"]) if j.get("salary_min") is not None else None,
            "salary_max": int(j["salary_max"]) if j.get("salary_max") is not None else None,
            "apply_url": j["absolute_url"],
            "updated_at": j.get("updated_at"),  # when the employer last updated the posting (Greenhouse)
            "score": s,
            "why_matched": ", ".join(reasons),
        }
        for s, reasons, j in scored[:n]
    ]
