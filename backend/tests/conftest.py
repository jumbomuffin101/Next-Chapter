"""Explicitly isolated fixtures for new write tests; never the configured database."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles


@compiles(UUID, "sqlite")
def sqlite_uuid(type_, compiler, **kwargs):
    # PostgreSQL UUIDs need text affinity here, including all-numeric UUID values.
    return "CHAR(32)"


@pytest.fixture
def isolated_db(monkeypatch):
    from work.database import crud, database
    from backend.app.analytics import router as analytics
    from backend.app.profiles import outreach

    # Fail closed if any new test accidentally reaches either production client.
    monkeypatch.setattr(database.engine, "connect", Mock(side_effect=AssertionError("Live database forbidden in offline tests")))
    monkeypatch.setattr("psycopg.connect", Mock(side_effect=AssertionError("Live database forbidden in offline tests")))
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    assert engine.url.get_backend_name() == "sqlite" and engine.url.database == ":memory:"

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys = ON")

    # Only this asserted in-memory engine is initialized. No seed/migration scripts.
    database.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(crud, "SessionLocal", factory)

    @contextmanager
    def readonly():
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA query_only = ON")
            try:
                with factory(bind=connection) as session:
                    yield session
            finally:
                connection.exec_driver_sql("PRAGMA query_only = OFF")

    monkeypatch.setattr(analytics, "readonly_session", readonly)
    monkeypatch.setattr(outreach, "readonly_session", readonly)
    yield SimpleNamespace(engine=engine, Session=factory)
    engine.dispose()
