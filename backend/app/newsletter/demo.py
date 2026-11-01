"""Bounded, stateless synthetic-profile calculation; no alumni record lookup."""
from collections import deque
from dataclasses import asdict
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Annotated, Literal

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, StringConstraints, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from ..jobs.matching import MatchProfile, title_family
from .calendar import current_month
from .content import Profile
from .links import frontend_url
from .service import generate_demo_newsletter

MAX_REQUEST_BYTES = 8192
RATE_LIMIT = 30
RATE_WINDOW_SECONDS = 60
_rate_lock = Lock()
_rate_events: dict[str, deque[float]] = {}

SkillName = Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
PARTIAL_DATE = r"^$|^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$"


class DemoRole(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=150)
    is_current: StrictBool = False
    start_date: str = Field(default="", max_length=10, pattern=PARTIAL_DATE)
    end_date: str = Field(default="", max_length=10, pattern=PARTIAL_DATE)


class DemoProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    synthetic: Literal[True]
    first_name: str = Field(default="", max_length=80)
    city: str | None = Field(default=None, max_length=120)
    cohort: str | None = Field(default=None, pattern=r"^\d{4}$")
    skills: list[SkillName] = Field(default_factory=list, max_length=30)
    roles: list[DemoRole] = Field(default_factory=list, max_length=15)


def _limit_request(host: str) -> None:
    now = monotonic()
    cutoff = now - RATE_WINDOW_SECONDS
    with _rate_lock:
        for address in list(_rate_events):
            recent = _rate_events[address]
            while recent and recent[0] <= cutoff:
                recent.popleft()
            if not recent:
                del _rate_events[address]
        recent = _rate_events.setdefault(host, deque())
        if len(recent) >= RATE_LIMIT:
            raise HTTPException(429, "Demo newsletter request limit reached; try again shortly")
        recent.append(now)


async def _validated_profile(request: Request) -> DemoProfile:
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        raise HTTPException(415, "Use application/json for synthetic demo profiles")
    try:
        content_length = int(request.headers.get("content-length", "0"))
    except ValueError:
        raise HTTPException(400, "Invalid request length") from None
    if content_length > MAX_REQUEST_BYTES:
        raise HTTPException(413, "Synthetic demo profile is too large")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_REQUEST_BYTES:
            raise HTTPException(413, "Synthetic demo profile is too large")
    try:
        return DemoProfile.model_validate_json(bytes(body))
    except ValidationError:
        raise HTTPException(422, "Provide a valid, explicitly synthetic demo profile") from None


def _matching(profile: DemoProfile) -> MatchProfile | None:
    today = datetime.now(timezone.utc).date().isoformat()
    eligible = [role for role in profile.roles if not role.start_date or role.start_date <= today[:len(role.start_date)]]
    eligible.sort(key=lambda role: (role.is_current and not role.end_date, role.start_date, role.title.casefold()),
                  reverse=True)
    if not eligible:
        return None
    current = [role for role in eligible if role.is_current and not role.end_date]
    choices = current or eligible
    title = next((role.title for role in choices if title_family(role.title)), choices[0].title)
    return MatchProfile(title, profile.city, skills=tuple(profile.skills))


async def compute(request: Request) -> JSONResponse:
    """Only caller-supplied synthetic fields, public jobs, and safe demo aggregates."""
    _limit_request(request.client.host if request.client else "unknown")
    data = await _validated_profile(request)
    profile = Profile(data.first_name, data.city, data.cohort, True)
    try:
        content = generate_demo_newsletter(profile, _matching(data), app_url=frontend_url()).content
    except (ValueError, SQLAlchemyError):
        raise HTTPException(503, "Demo newsletter content is temporarily unavailable") from None
    return JSONResponse(jsonable_encoder({"month": current_month(), "demo_only": True,
                                          "content": asdict(content)}),
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                                 "X-Content-Type-Options": "nosniff"})
