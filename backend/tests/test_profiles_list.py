"""Alumni listing tests using isolated, in-memory SQLite; never Supabase.

The adapter translates Psycopg parameter markers only. The endpoint's actual
SELECT statements, filtering, ordering, pagination, and role ranking execute
against synthetic fixtures. No database initialization scripts are imported.
"""
import sqlite3
import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import IsolationLevel

from backend.app.profiles import router as profiles


def identifier(number):
    return str(uuid.UUID(int=number))


class CursorAdapter:
    def __init__(self, connection):
        self.connection = connection
        self.cursor = connection.database.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cursor.close()

    def execute(self, sql, params):
        assert self.connection.read_only is True
        assert self.connection.isolation_level == IsolationLevel.REPEATABLE_READ
        assert sql.lstrip().upper().startswith(("SELECT", "WITH"))
        self.cursor.execute(sql.replace("%s", "?"), params)

    def fetchone(self):
        return dict(self.cursor.fetchone())

    def fetchall(self):
        return [dict(row) for row in self.cursor.fetchall()]


class ConnectionAdapter:
    def __init__(self, database):
        self.database = database
        self.read_only = False
        self.isolation_level = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def cursor(self, **kwargs):
        return CursorAdapter(self)


@pytest.fixture
def client(monkeypatch):
    database = sqlite3.connect(":memory:", check_same_thread=False)
    database.row_factory = sqlite3.Row
    database.executescript("""
        CREATE TABLE alumni (
            id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, email TEXT,
            city TEXT, cohort TEXT, graduation_year INTEGER, is_demo BOOLEAN,
            updated_at TEXT
        );
        CREATE TABLE work_experience (
            id TEXT PRIMARY KEY, alumni_id TEXT, title TEXT, employer TEXT,
            start_date TEXT, end_date TEXT, is_current BOOLEAN
        );
    """)
    people = [
        (1, "Zoe", "Adams", "New York", "2022"),
        (2, "Alex", "Brown", "Newark", "2023"),
        (3, "alex", "brown", "New York", "2022"),
        (4, "Mina", "Chen", None, None),
        (5, "Sam", "Diaz", "Atlanta", "2024"),
    ]
    # Insert in reverse order to ensure results follow the SQL ordering.
    database.executemany(
        "INSERT INTO alumni VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(identifier(n), first, last, f"person{n}@example.com", city, cohort,
          int(cohort) if cohort else None, n != 4, "2026-10-16T12:00:00+00:00")
         for n, first, last, city, cohort in reversed(people)],
    )
    roles = [
        # Multiple open roles: the newest dated one wins, even over an undated role.
        (11, 1, "Old open role", "2019-01-01", None, True),
        (12, 1, "Current engineer", "2024-01-01", None, True),
        (13, 1, "Unknown start", None, None, True),
        # Closed, future, and non-current rows cannot displace the current role.
        (14, 1, "Closed role", "2025-01-01", "2025-12-31", True),
        (15, 1, "Future role", "9999-01-01", None, True),
        (16, 1, "Not current", "2025-06-01", None, False),
        # A profile with historical jobs only must have current_role=null.
        (21, 2, "Historical", "2020-01-01", "2021-01-01", True),
        (22, 2, "Unflagged", "2022-01-01", None, False),
        # Equal start dates use the lowest UUID, irrespective of insertion order.
        (32, 3, "Tie second", "2023-01-01", None, True),
        (31, 3, "Tie first", "2023-01-01", None, True),
        (51, 5, "Undated current", None, None, True),
    ]
    database.executemany(
        "INSERT INTO work_experience VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(identifier(n), identifier(person), title, "Synthetic Employer", start, end, current)
         for n, person, title, start, end, current in roles],
    )
    database.commit()
    # Even the fixture database rejects writes once setup is complete.
    database.execute("PRAGMA query_only = ON")
    monkeypatch.setattr(profiles, "get_conn", lambda: ConnectionAdapter(database))
    app = FastAPI()
    app.include_router(profiles.router)
    with TestClient(app) as api:
        yield api
    database.close()


def test_defaults_and_stable_order(client):
    response = client.get("/profiles")
    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["limit"], body["offset"]) == (5, 20, 0)
    assert [item["id"] for item in body["items"]] == [identifier(n) for n in range(1, 6)]
    assert client.get("/profiles").json() == body


def test_pagination_counts_alumni_without_role_duplicates(client):
    first = client.get("/profiles", params={"limit": 2}).json()
    second = client.get("/profiles", params={"limit": 2, "offset": 2}).json()
    assert first["total"] == second["total"] == 5
    assert [p["id"] for p in first["items"]] == [identifier(1), identifier(2)]
    assert [p["id"] for p in second["items"]] == [identifier(3), identifier(4)]
    assert (second["limit"], second["offset"]) == (2, 2)


@pytest.mark.parametrize("params, expected", [
    ({"city": "new YORK"}, [1, 3]),
    ({"cohort": "2023"}, [2]),
    ({"city": " New York ", "cohort": " 2022 "}, [1, 3]),
    ({"city": "Newark", "cohort": "2022"}, []),
    ({"city": "York"}, []),
    ({"city": "New York' OR 1=1 --"}, []),
])
def test_filters_are_exact_case_insensitive_and_parameterized(client, params, expected):
    response = client.get("/profiles", params=params)
    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [identifier(n) for n in expected]
    assert body["total"] == len(expected)


def test_filtered_count_is_not_page_size(client):
    body = client.get("/profiles", params={"cohort": "2022", "limit": 1, "offset": 1}).json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [identifier(3)]


def test_empty_and_out_of_range_pages(client):
    assert client.get("/profiles", params={"city": "Missing"}).json() == {
        "items": [], "total": 0, "limit": 20, "offset": 0,
    }
    assert client.get("/profiles", params={"offset": 999}).json() == {
        "items": [], "total": 5, "limit": 20, "offset": 999,
    }


def test_current_role_selection(client):
    items = client.get("/profiles").json()["items"]
    assert items[0]["current_role"] == {
        "title": "Current engineer", "employer": "Synthetic Employer", "start_date": "2024-01-01",
    }
    assert items[1]["current_role"] is None
    assert items[2]["current_role"]["title"] == "Tie first"
    assert items[3]["current_role"] is None
    assert items[4]["current_role"]["start_date"] is None


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 101}, {"limit": -1}, {"limit": "invalid"},
    {"offset": -1}, {"offset": "invalid"}, {"cohort": ""}, {"city": ""},
])
def test_invalid_parameters_do_not_access_database(client, monkeypatch, params):
    connection = MagicMock(side_effect=AssertionError("Database must not be accessed"))
    monkeypatch.setattr(profiles, "get_conn", connection)
    assert client.get("/profiles", params=params).status_code == 422
    connection.assert_not_called()


@pytest.mark.parametrize("limit", [1, 100])
def test_limit_boundaries(client, limit):
    response = client.get("/profiles", params={"limit": limit, "offset": 0})
    assert response.status_code == 200
    assert response.json()["limit"] == limit


def test_native_postgres_types_serialize_without_internal_fields(monkeypatch):
    row = {
        "id": uuid.UUID(int=1), "full_name": "Synthetic Person", "email": "test@example.com",
        "city": None, "cohort": None, "graduation_year": None, "is_demo": True,
        "last_updated_at": datetime(2026, 10, 16, 12, tzinfo=timezone.utc),
        "role_id": uuid.UUID(int=2), "role_title": "Engineer", "role_employer": "Demo",
        "role_start_date": date(2026, 1, 1),
    }
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"total": 1}
    cursor.fetchall.return_value = [row]
    monkeypatch.setattr(profiles, "get_conn", lambda: connection)
    app = FastAPI()
    app.include_router(profiles.router)
    with TestClient(app) as api:
        response = api.get("/profiles")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == identifier(1)
    assert item["last_updated_at"] == "2026-10-16T12:00:00Z"
    assert item["current_role"]["start_date"] == "2026-01-01"
    assert item["is_demo"] is True
    assert set(item) == {
        "id", "full_name", "email", "city", "cohort", "graduation_year",
        "is_demo", "last_updated_at", "current_role",
    }
