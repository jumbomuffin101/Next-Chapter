"""Database configuration shared by SQLAlchemy and the canonical FastAPI app."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

ENV_PATH = Path(__file__).resolve().parent / ".env"


def get_database_url() -> URL:
    """Load the existing database .env without replacing external configuration.

    Bare PostgreSQL URLs use Psycopg 3, matching backend/requirements.txt.
    Other SQLAlchemy dialects are left intact for offline schema generation.
    Never include the supplied URL in configuration errors.
    """
    load_dotenv(dotenv_path=ENV_PATH, override=False)
    value = os.getenv("DATABASE_URL")
    if not value or not value.strip():
        raise RuntimeError(
            "DATABASE_URL is required; set it externally or in work/database/.env"
        )
    try:
        url = make_url(value.strip())
        # Access the port here too, so malformed ports get a secret-free error.
        url.port
    except (ArgumentError, ValueError):
        raise RuntimeError("DATABASE_URL must be a valid SQLAlchemy URL") from None
    if url.get_backend_name() in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return url
