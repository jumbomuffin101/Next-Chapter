"""Create tables: `python -m app.init_db`. Safe to re-run (CREATE IF NOT EXISTS)."""
from pathlib import Path

from dotenv import load_dotenv

from .db import get_conn

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def init_db() -> None:
    # schema.sql is generated from work/database/models.py; extras.sql holds the admin/onboarding tables
    statements = (SQL_DIR / "schema.sql").read_text() + "\n" + (SQL_DIR / "extras.sql").read_text()
    with get_conn() as conn:
        conn.execute(statements)
        conn.commit()


if __name__ == "__main__":
    load_dotenv()
    init_db()
    print("tables ready")
