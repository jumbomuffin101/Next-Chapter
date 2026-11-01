"""Admin on/off switch for the scheduled monthly newsletter (admin Automation page). On unless the career team turns it off."""
from psycopg.types.json import Jsonb

SETTING = "newsletter_monthly_enabled"


def monthly_enabled(cur) -> bool:
    cur.execute("SELECT value FROM app_settings WHERE key = %s", (SETTING,))
    row = cur.fetchone()
    return True if row is None else bool(row["value"])


def set_monthly_enabled(cur, enabled: bool) -> None:
    cur.execute("""INSERT INTO app_settings (key, value) VALUES (%s, %s)
                   ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()""", (SETTING, Jsonb(enabled)))
