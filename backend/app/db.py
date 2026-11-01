"""Psycopg connections using the authoritative database package's configuration."""
import psycopg
from sqlalchemy.dialects.postgresql.psycopg import dialect

from work.database.config import get_database_url


def get_conn():
    url = get_database_url()
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("The FastAPI database connection requires PostgreSQL")
    # Let SQLAlchemy decode credentials and translate query/connection options;
    # libpq cannot consume a postgresql+psycopg:// URL directly.
    args, kwargs = dialect().create_connect_args(url)
    kwargs.setdefault("connect_timeout", 10)
    return psycopg.connect(*args, **kwargs)
