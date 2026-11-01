"""Offline tests: peer ranking, events, certification suggestions, LinkedIn extraction, URL validation."""
from datetime import date

import pytest

from app.growth.certs import recommend
from app.network.events import events_for, metro_key
from app.network.router import filter_scope, linkedin_for, rank_peers
from app.parsing.extract import find_linkedin
from app.parsing.rule_parser import parse_resume_text


def person(i, title="Software Engineer", employer="Acme", city="Hoboken, NJ", **kw):
    base = {"id": i, "first_name": f"First{i}", "last_name": f"Last{i}", "email": f"p{i}@x.com", "city": city, "cohort": "2024",
            "role_title": title, "employer": employer, "linkedin_url": None}
    base.update(kw)
    return base


# ------------------------------------------------------------------ peers
def test_peers_are_ranked_company_then_metro_then_role():
    me = person(0)
    others = [person(1, employer="Other", city="Chicago, IL"),            # same role, far away
              person(2, employer="Other", city="Newark, NJ"),             # same role, same metro (Hoboken ~ Newark)
              person(3, employer="Acme", city="Atlanta, GA"),             # same company, different city
              person(4, title="Barista", employer="Cafe"),                # unrelated: excluded
              person(5, title="Data Analyst", employer="Other", city="Hoboken, NJ")]  # different field: excluded
    ranked = rank_peers(me, others)
    assert [p["id"] for p in ranked] == ["3", "2", "1"]  # company (3+2) > metro+role (2+2) > role only (2)
    assert ranked[0]["reasons"] == ["Same company", "Same role type"]
    assert ranked[1]["reasons"] == ["Same metro area", "Same role type"]
    assert ranked[2]["reasons"] == ["Same role type"]
    assert all(not k.startswith("_") or k in ("_flags", "_score") for k in ranked[0])


def test_same_city_is_distinguished_from_same_metro():
    ranked = rank_peers(person(0, city="Newark, NJ"), [person(1, city="Newark, NJ", employer="X"), person(2, city="Brooklyn, NY", employer="Y")])
    assert [p["reasons"][0] for p in sorted(ranked, key=lambda p: p["id"])] == ["Same city", "Same metro area"]


def test_just_joined_flag_is_passed_through_and_defaults_off():
    me = {"role_title": "Data Analyst", "employer": "X", "city": "Atlanta, GA"}
    people = [{"id": i, "first_name": n, "last_name": "", "email": f"{n}@e.com", "city": "Atlanta, GA", "cohort": "2020",
               "is_demo": True, "role_title": "Data Analyst", "employer": "Y", "linkedin_url": None, **extra}
              for i, (n, extra) in enumerate([("New", {"just_joined": True}), ("Old", {"just_joined": False}), ("Unknown", {})])]
    assert {p["name"]: p["just_joined"] for p in rank_peers(me, people)} == {"New": True, "Old": False, "Unknown": False}


def test_scopes():
    me = person(0)
    ranked = rank_peers(me, [person(1, employer="Acme", city="Atlanta, GA"), person(2, employer="Other", city="Newark, NJ"),
                             person(3, employer="Other", city="Chicago, IL")])
    ids = lambda scope: sorted(p["id"] for p in filter_scope(ranked, scope))
    assert ids("all") == ["1", "2", "3"] and ids("company") == ["1"] and ids("city") == ["2"] and ids("role") == ["1", "2", "3"]


def test_someone_with_no_known_role_type_matches_only_by_company():
    ranked = rank_peers(person(0, title="Barista", employer="Cafe"), [person(1, title="Barista", employer="Other"), person(2, title="Cook", employer="Cafe")])
    assert [p["id"] for p in ranked] == ["2"]  # "other" role types never match each other, same company still does


def test_a_person_with_no_role_gets_no_role_peers():
    assert rank_peers(person(0, title=None, employer=None), [person(1)]) == []


# ------------------------------------------------------------------ events
TODAY = date(2026, 10, 17)


def test_events_are_local_to_the_metro_and_always_upcoming():
    out = events_for("Brooklyn, NY", "software", TODAY)
    assert out["metro"] == "New York metro" and metro_key("Newark") == metro_key("Jersey City") == "new york"
    assert out["local"] and all(e["date"] > TODAY.isoformat() and e["sample"] for e in out["local"] + out["online"])
    assert out["local"][0]["for_you"] and "Software" in out["local"][0]["title"]  # role-matched events first
    assert all(not e["virtual"] for e in out["local"]) and all(e["virtual"] for e in out["online"])


def test_unknown_city_still_gets_online_events():
    out = events_for("Smallville, KS", "data", TODAY)
    assert out["metro"] is None and out["local"] == [] and len(out["online"]) >= 1
    assert events_for(None, "other", TODAY)["local"] == []


# ------------------------------------------------------------------ certifications
def test_recommendations_follow_role_type_and_skills_and_skip_held_certs():
    rec = recommend(["Python", "AWS", "Docker"], ["AWS Certified Cloud Practitioner"], "Software Engineer")
    names = [r["name"] for r in rec["recommended"]]
    assert rec["family"] == "software" and "AWS Certified Cloud Practitioner" not in names
    assert names[0] == "AWS Certified Developer – Associate"  # builds on the AWS / Python skills
    assert "Builds on your" in rec["recommended"][0]["why"]
    assert all(r["url"].startswith("https://") for r in rec["recommended"]) and rec["programs"]
    assert "Docker" not in rec["skills_to_add"] and "TypeScript" in rec["skills_to_add"]


def test_never_recommends_a_lower_level_from_a_provider_where_you_hold_a_higher_one():
    rec = recommend(["Python"], ["AWS Certified Developer – Associate"], "Software Engineer")
    names = [r["name"] for r in rec["recommended"]]
    assert "AWS Certified Cloud Practitioner" not in names  # foundational, below the Associate they already hold
    assert "Microsoft Azure Fundamentals (AZ-900)" in names  # a different provider is still fair game


def test_recommendations_for_an_unclassified_role_fall_back_to_general_ones():
    rec = recommend([], [], "Barista")
    assert rec["family"] == "other" and rec["recommended"] and rec["skills_to_add"]
    assert recommend([], [], None)["family"] == "other"


# ------------------------------------------------------------------ LinkedIn + URL validation
@pytest.mark.parametrize("text,expected", [
    ("Jane Doe | linkedin.com/in/jane-doe-123 | github.com/jane", "https://www.linkedin.com/in/jane-doe-123"),
    ("https://www.linkedin.com/in/jane-doe-123/", "https://www.linkedin.com/in/jane-doe-123"),
    ("LinkedIn: LINKEDIN.COM/IN/Jane_Doe", "https://www.linkedin.com/in/Jane_Doe"),
    ("https://www.linkedin.com/company/acme", None),     # a company page is not a person
    ("LinkedIn ↗ | GitHub ↗", None),                      # a label with no printed URL
    ("", None),
])
def test_find_linkedin_in_text(text, expected):
    assert find_linkedin(text) == expected


def test_find_linkedin_falls_back_to_the_pdf_hyperlinks():
    assert find_linkedin("LinkedIn ↗", ["https://github.com/x", "https://www.linkedin.com/in/aryan-rawat-bbb0a6276"]) == \
        "https://www.linkedin.com/in/aryan-rawat-bbb0a6276"
    assert find_linkedin("LinkedIn ↗", ["https://github.com/x"]) is None


def test_parser_picks_linkedin_up_from_the_header_and_never_requires_it():
    base = "Jane Doe\njane@example.com | (555) 123-4567{extra}\nExperience\nAcme Corp, Hoboken, NJ\nSoftware Engineer   Jan 2024 - Present\n- Built things\n"
    assert parse_resume_text(base.format(extra=" | linkedin.com/in/jane-doe-123")).linkedin_url == "https://www.linkedin.com/in/jane-doe-123"
    assert parse_resume_text(base.format(extra="")).linkedin_url is None
