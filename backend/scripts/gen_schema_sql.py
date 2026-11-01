"""Regenerate sql/schema.sql from the DB owner's SQLAlchemy models (work/database/models.py).

    pip install sqlalchemy        # only needed for this script, not for running the API
    python scripts/gen_schema_sql.py

Run it again whenever work/database/models.py changes, so `python -m app.init_db` stays in sync.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")  # never connects; only needed to import the models
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND.parent))

from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from work.database import models  # noqa: E402, F401
from work.database.database import Base  # noqa: E402

HEADER = """-- GENERATED from work/database/models.py by scripts/gen_schema_sql.py. Do not edit by hand.
-- The DB owner's models are the source of truth; re-run the script after they change.
-- All statements are IF NOT EXISTS, so running init_db against a DB created by
-- work/database/create_tables.py is a no-op.
"""

d = postgresql.dialect()
out = [HEADER]
for table in Base.metadata.sorted_tables:
    out.append(str(CreateTable(table, if_not_exists=True).compile(dialect=d)).strip() + ";\n")
    for index in sorted(table.indexes, key=lambda i: i.name):
        out.append(str(CreateIndex(index, if_not_exists=True).compile(dialect=d)).strip() + ";\n")
(BACKEND / "sql" / "schema.sql").write_text("\n".join(out))
print("wrote sql/schema.sql:", ", ".join(t.name for t in Base.metadata.sorted_tables))
