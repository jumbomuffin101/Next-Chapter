"""From the repository root: python -m uvicorn backend.app.main:app --reload."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from work.database.config import get_database_url

# Load the one shared .env and validate configuration without opening a connection.
get_database_url()

from .admin.automation import router as automation_router  # noqa: E402
from .admin.dashboard import router as dashboard_router  # noqa: E402
from .admin.outcomes import router as outcomes_router  # noqa: E402
from .admin.router import router as admin_router  # noqa: E402
from .auth.router import require_admin, router as auth_router  # noqa: E402
from .invites.router import router as invites_router  # noqa: E402
from .jobs import scheduler  # noqa: E402
from .jobs.router import router as jobs_router  # noqa: E402
from .network.router import router as network_router  # noqa: E402
from .onboarding.router import router as onboarding_router  # noqa: E402
from .parsing.router import router as resume_router  # noqa: E402
from .profiles.router import router as profiles_router  # noqa: E402
from .salary.router import router as salary_router  # noqa: E402
from .analytics.router import router as analytics_router  # noqa: E402
from .newsletter.router import router as newsletter_router  # noqa: E402


@asynccontextmanager
async def lifespan(_app):
    # Greenhouse jobs refresh on a schedule while the API runs (JOB_REFRESH_HOURS, default 24; 0 = off)
    stop = scheduler.start()
    yield
    if stop is not None:
        stop.set()


app = FastAPI(title="TKH Career Mobility Tracker (parsing + jobs)", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(profiles_router)
app.include_router(resume_router)
app.include_router(jobs_router)
app.include_router(onboarding_router)
app.include_router(invites_router)
app.include_router(network_router)
app.include_router(salary_router)
app.include_router(auth_router)
app.include_router(newsletter_router)
# Admin-only data needs the token from POST /auth/admin/login (stub auth, see app/auth/router.py)
app.include_router(analytics_router, dependencies=[Depends(require_admin)])
app.include_router(admin_router, dependencies=[Depends(require_admin)])
app.include_router(dashboard_router, dependencies=[Depends(require_admin)])
app.include_router(outcomes_router, dependencies=[Depends(require_admin)])
app.include_router(automation_router, dependencies=[Depends(require_admin)])


@app.get("/health")
def health():
    return {"ok": True}
