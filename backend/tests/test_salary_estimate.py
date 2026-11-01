import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.salary.occupations import occupation_for
from backend.app.salary.router import router


@pytest.mark.parametrize("title,soc", [
    ("Software Engineer", "15-1252"), ("Senior Backend Developer", "15-1252"),
    ("Front-end Developer", "15-1254"), ("Data Analyst", "15-2051"), ("Cybersecurity Analyst", "15-1212"),
    ("IT Support Specialist", "15-1232"), ("Help Desk Technician", "15-1232"), ("Customer Support Specialist", "43-4051"),
    ("Cloud Engineer", "15-1244"), ("QA Engineer", "15-1253"), ("UX Designer", "15-1255"),
    ("Engineering Manager", "11-3021"), ("Project Manager", "13-1082"), ("Account Executive", "41-3091"),
])
def test_titles_map_to_the_closest_bls_occupation(title, soc):
    assert occupation_for(title)[0] == soc


def test_unknown_or_empty_titles_match_nothing():
    assert occupation_for("Barista") is None and occupation_for(None) is None and occupation_for("") is None


def test_endpoint_returns_a_typical_range_from_bls():
    client = TestClient(FastAPI(routes=router.routes))
    body = client.get("/salary/estimate", params={"title": "Software Engineer"}).json()
    assert body["matched"] and body["occupation"] == "Software Developers"
    assert body["p25"] < body["median"] < body["p75"] and body["area"] == "United States"
    assert client.get("/salary/estimate", params={"title": "Barista"}).json()["matched"] is False
    assert client.get("/salary/estimate").status_code == 422
