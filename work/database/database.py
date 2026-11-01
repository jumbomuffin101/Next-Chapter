
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import ENV_PATH, get_database_url

DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def readonly_session():
    """A PostgreSQL snapshot with database-enforced read-only transactions."""
    with engine.connect().execution_options(
        isolation_level="REPEATABLE READ", postgresql_readonly=True,
    ) as connection:
        with Session(bind=connection) as session:
            yield session
