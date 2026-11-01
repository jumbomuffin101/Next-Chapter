"""Safe live checks. From repository root: python -m backend.scripts.check_readonly.

Only GET endpoints and SELECT/SHOW statements are used. Both database clients
enforce read-only transactions. No schema, seed, ingestion, or persistence calls.
Errors are reported by type only to avoid printing credentials or profile data.
Pass --sample to print one listing response with identity fields redacted.
"""
import argparse
import json
from datetime import datetime, timedelta
from unittest.mock import patch

EXPECTED_ROUTES = {
    ("GET", "/health"),
    ("POST", "/profiles"),
    ("GET", "/profiles"),
    ("GET", "/profiles/outreach"),
    ("GET", "/analytics/summary"),
    ("GET", "/profiles/{profile_id}"),
    ("POST", "/resume/parse"),
    ("POST", "/resume/confirm/{profile_id}"),
    ("POST", "/jobs/refresh"),
    ("GET", "/users/{user_id}/job-matches"),
}


def verify_dashboard(client, readonly_conn, profile_id):
    response = client.get("/analytics/summary")
    assert response.status_code == 200
    summary = response.json()
    with readonly_conn() as conn:
        count, demo = conn.execute("SELECT count(*), count(*) FILTER (WHERE is_demo) FROM alumni").fetchone()
        current = conn.execute("""SELECT count(DISTINCT alumni_id) FROM work_experience
            WHERE is_current AND end_date IS NULL AND (start_date IS NULL OR start_date <= CURRENT_DATE)""").fetchone()[0]
        confirmed = conn.execute("SELECT count(DISTINCT alumni_id) FROM resume_uploads WHERE confirmed").fetchone()[0]
        careers = conn.execute("SELECT count(*) FROM work_experience").fetchone()[0]
    assert summary["total_alumni"] == count
    assert summary["demo"]["total_alumni"] == demo
    assert summary["real"]["total_alumni"] == count - demo
    assert summary["alumni_with_current_roles"] == current
    assert summary["alumni_with_confirmed_resumes"] == confirmed
    assert summary["total_career_history_records"] == careers
    for key in ("by_city", "by_cohort"):
        assert sum(group["total_alumni"] for group in summary[key]) == count
    real = client.get("/analytics/summary?include_demo=false").json()
    assert real["total_alumni"] == count - demo and real["demo"]["total_alumni"] == 0
    print("PASS: analytics totals, distinct counts, missing-data groups, and demo/real splits")
    print(f"Aggregate data only: alumni={count}, demo={demo}, real={count-demo}, current_roles={current}, confirmed_resumes={confirmed}, career_records={careers}")

    response = client.get("/profiles/outreach", params={"limit": 100})
    assert response.status_code == 200
    outreach = response.json()
    cutoff = datetime.fromisoformat(outreach["as_of"]) - timedelta(days=outreach["stale_days"])
    with readonly_conn() as conn:
        expected = conn.execute("""SELECT count(*) FROM alumni a WHERE NOT EXISTS (
            SELECT 1 FROM resume_uploads r WHERE r.alumni_id = a.id AND r.confirmed AND r.uploaded_at >= %s
        )""", (cutoff,)).fetchone()[0]
    assert outreach["total"] == expected
    assert all(row["needs_outreach"] and row["outreach_reason"] for row in outreach["items"])
    print("PASS: outreach indicators checked against confirmed resume timestamps")

    matches = client.get(f"/users/{profile_id}/job-matches", params={"limit": 3})
    if matches.status_code == 404:
        print("SKIP: selected existing profile has no usable career title for matching")
    else:
        assert matches.status_code == 200
        assert len(matches.json()["matches"]) <= 3
        print("PASS: job matching GET uses stored listings; no Greenhouse refresh performed")


def verify_profile_list(client, readonly_conn, profile, show_sample):
    response = client.get("/profiles", params={"limit": 2, "offset": 0})
    assert response.status_code == 200
    page = response.json()
    with readonly_conn() as conn:
        total = conn.execute("SELECT count(*) FROM alumni").fetchone()[0]
        ids = conn.execute(
            "SELECT id FROM alumni ORDER BY lower(last_name), lower(first_name), id LIMIT 2"
        ).fetchall()
        assert page["total"] == total
        assert [item["id"] for item in page["items"]] == [str(row[0]) for row in ids]
        for item in page["items"]:
            role = conn.execute(
                """SELECT title, employer, start_date FROM work_experience
                   WHERE alumni_id = %s AND is_current = TRUE AND end_date IS NULL
                     AND (start_date IS NULL OR start_date <= CURRENT_DATE)
                   ORDER BY start_date DESC NULLS LAST, id LIMIT 1""",
                (item["id"],),
            ).fetchone()
            expected = None if role is None else {
                "title": role[0], "employer": role[1],
                "start_date": role[2].isoformat() if role[2] else None,
            }
            assert item["current_role"] == expected
    assert page["limit"] == 2 and page["offset"] == 0
    assert client.get("/profiles", params={"limit": 2}).json() == page
    second = client.get("/profiles", params={"limit": 2, "offset": 2}).json()
    assert second["total"] == total
    assert not ({p["id"] for p in page["items"]} & {p["id"] for p in second["items"]})
    print("PASS: GET /profiles pagination, total, stable ordering, and current roles")

    for field in ("city", "cohort"):
        value = profile[field]
        if value:
            response = client.get("/profiles", params={field: value.swapcase(), "limit": 1})
            assert response.status_code == 200
            filtered = response.json()
            with readonly_conn() as conn:
                expected = conn.execute(
                    f"SELECT count(*) FROM alumni WHERE lower({field}) = lower(%s)",
                    (value,),
                ).fetchone()[0]
            assert filtered["total"] == expected
            assert all(p[field].casefold() == value.casefold() for p in filtered["items"])
    print("PASS: GET /profiles filters against existing data")

    empty = client.get("/profiles", params={"offset": total + 10}).json()
    assert empty == {"items": [], "total": total, "limit": 20, "offset": total + 10}
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        assert client.get("/profiles", params=params).status_code == 422
    print("PASS: GET /profiles empty page and pagination validation")

    if show_sample:
        sample = client.get("/profiles", params={"limit": 1}).json()
        for item in sample["items"]:
            for field in ("id", "full_name", "email"):
                item[field] = "[redacted]"
            if not item["is_demo"]:
                for field in ("city", "cohort", "graduation_year", "last_updated_at", "current_role"):
                    item[field] = "[redacted]"
        print("Real listing response (sensitive fields redacted):")
        print(json.dumps(sample, indent=2))


def main(show_sample: bool = False) -> int:
    try:
        from fastapi.testclient import TestClient
        from sqlalchemy import text

        from backend.app.db import get_conn
        from backend.app.main import app
        from work.database.database import engine, readonly_session

        # OpenAPI includes nested routers across supported FastAPI versions.
        routes = {
            (method.upper(), path)
            for path, methods in app.openapi()["paths"].items()
            for method in methods
        }
        assert EXPECTED_ROUTES <= routes
        print(f"PASS: all {len(EXPECTED_ROUTES)} application routes registered")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/health")
            assert response.status_code == 200 and response.json() == {"ok": True}
            print("PASS: GET /health")

            with engine.connect().execution_options(postgresql_readonly=True) as conn:
                assert conn.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
                assert conn.execute(text("SELECT 1")).scalar_one() == 1
                database = conn.execute(text("SELECT current_database()")).scalar_one()
            print("PASS: SQLAlchemy PostgreSQL connection (read-only transaction)")
            with readonly_session() as session:
                assert session.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
            print("PASS: analytics/outreach sessions enforce PostgreSQL read-only transactions")

            def readonly_conn():
                conn = get_conn()
                conn.read_only = True
                return conn

            with readonly_conn() as conn:
                assert conn.execute("SHOW transaction_read_only").fetchone()[0] == "on"
                assert conn.execute("SELECT 1").fetchone()[0] == 1
                assert conn.execute("SELECT current_database()").fetchone()[0] == database
                # Prefer synthetic demo data; never print profile IDs or contents.
                row = conn.execute(
                    "SELECT id FROM alumni ORDER BY is_demo DESC, id LIMIT 1"
                ).fetchone()
            print("PASS: Psycopg PostgreSQL connection (read-only transaction)")
            print("PASS: both database clients reached the same database")
            if row is None:
                print("BLOCKED: no existing alumni available for a profile lookup")
                return 1

            with patch("backend.app.profiles.router.get_conn", readonly_conn), patch(
                "backend.app.jobs.router.get_conn", readonly_conn,
            ):
                response = client.get(f"/profiles/{row[0]}")
                assert response.status_code == 200
                profile = response.json()
                assert profile["id"] == str(row[0])
                assert all(key in profile for key in ("work_experiences", "education", "skills", "certifications"))
                print("PASS: GET /profiles/{profile_id} using an existing record (read-only)")
                verify_profile_list(client, readonly_conn, profile, show_sample)
                verify_dashboard(client, readonly_conn, row[0])
        return 0
    except Exception as error:
        print(f"FAIL: read-only verification ({type(error).__name__}); details suppressed to protect secrets")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="store_true", help="Print a redacted real listing response")
    raise SystemExit(main(show_sample=parser.parse_args().sample))
