"""Demo-authorized preferences, admin dispatch, and bearer-link unsubscribe."""
from html import escape
from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy.exc import SQLAlchemyError

from ..auth.router import require_admin
from . import delivery, demo, preferences
from .security import verify
from .calendar import current_month
from .links import frontend_url
from .service import generate_newsletter

router = APIRouter(prefix="/newsletter", tags=["newsletter"])


def current_demo(authorization: str | None = Header(None)) -> UUID:
    scheme, _, token = (authorization or "").partition(" ")
    try:
        if scheme.lower() != "bearer":
            raise ValueError
        return UUID(verify(token, "demo"))
    except ValueError:
        raise HTTPException(401, "Sign in again with a synthetic demo account; newsletter sessions require configured signing.") from None


def call(function, *args):
    try:
        return function(*args)
    except preferences.NewsletterUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


class PreferenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subscribed: StrictBool


@router.get("/preferences")
def get_preference(identifier: UUID = Depends(current_demo)):
    return call(preferences.read_preference, identifier)


@router.put("/preferences")
def set_preference(body: PreferenceIn, identifier: UUID = Depends(current_demo)):
    return call(preferences.update_preference, identifier, body.subscribed)


@router.get("/current")
def current_newsletter(identifier: UUID = Depends(current_demo)):
    """A signed demo session may read only its own synthetic digest; no delivery writes."""
    try:
        content = generate_newsletter(identifier, app_url=frontend_url(), demo_only=True).content
    except (LookupError, PermissionError):
        raise HTTPException(403, "Interactive newsletters are available for synthetic demo accounts only") from None
    except (ValueError, SQLAlchemyError):
        raise HTTPException(503, "Newsletter content is temporarily unavailable") from None
    return JSONResponse(jsonable_encoder({"month": current_month(), "demo_only": True,
                                          "content": asdict(content)}),
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.post("/demo")
async def demo_newsletter(request: Request):
    """Calculate from explicitly synthetic input; never accepts or resolves an alumni ID."""
    return await demo.compute(request)


class DispatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: str


@router.post("/deliveries/{profile_id}", dependencies=[Depends(require_admin)])
def dispatch(profile_id: UUID, body: DispatchIn):
    return call(delivery.deliver, profile_id, body.month)


@router.get("/deliveries/{profile_id}", dependencies=[Depends(require_admin)])
def get_delivery(profile_id: UUID, month: str = Query(..., pattern=r"^\d{4}-\d{2}$")):
    return call(delivery.get_delivery, profile_id, month)


PRIVATE_HEADERS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                   "Content-Security-Policy": "default-src 'none'; form-action 'self'; frame-ancestors 'none'"}


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_page(token: str = Query(..., max_length=256)):
    try:
        verify(token, "unsubscribe")
    except ValueError:
        raise HTTPException(400, "Invalid or expired unsubscribe link.") from None
    # GET never changes consent; automated email security scanners cannot opt people out.
    return HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><title>Unsubscribe</title>'
                        '<h1>Next Chapter Monthly</h1><p>Stop receiving your monthly digest?</p>'
                        f'<form method="post" action="?token={escape(token, quote=True)}"><button>Unsubscribe</button></form></html>',
                        headers=PRIVATE_HEADERS)


@router.post("/unsubscribe")
def unsubscribe_link(token: str = Query(..., max_length=256)):
    call(preferences.unsubscribe, token)
    return HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><title>Unsubscribed</title>'
                        '<h1>Unsubscribe request processed</h1><p>This subscription link has been processed. '
                        'If you subscribed again after receiving this link, manage your current preference in Next Chapter.</p></html>',
                        headers=PRIVATE_HEADERS)
