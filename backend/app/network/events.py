"""SAMPLE meetups and events, tailored to the alumnus's metro area and role type. All data here is stub data:
dates are generated relative to today so the list is always upcoming. Replace with a real events source later."""
from datetime import date, timedelta
from typing import Optional

from ..jobs.matching import METRO_GROUPS

ALL = ("software", "data", "product", "design", "support", "ops", "sales", "other")
LOCAL_TEMPLATES = [  # kind, title, host, offset days, time, role types it suits
    ("Alumni mixer", "{metro} Alumni Mixer", "TKH Alumni Team", 6, "6:30 PM", ALL),
    ("Workshop", "Resume & LinkedIn Clinic", "TKH Career Team", 9, "6:00 PM", ALL),
    ("Meetup", "Software & Web Dev Meetup", "Alumni volunteers", 12, "7:00 PM", ("software",)),
    ("Meetup", "Data & Analytics Circle", "Alumni volunteers", 15, "6:30 PM", ("data",)),
    ("Meetup", "IT & Cloud Support Meetup", "Alumni volunteers", 17, "6:30 PM", ("support", "ops")),
    ("Panel", "Product & Design Panel", "Alumni volunteers", 20, "7:00 PM", ("product", "design")),
    ("Workshop", "Interview Practice Night", "TKH Career Team", 24, "6:00 PM", ALL),
    ("Career fair", "{metro} Tech Career Fair", "Hiring partners", 30, "11:00 AM", ALL),
]
ONLINE_TEMPLATES = [
    ("Workshop", "Salary Negotiation Workshop", "TKH Career Team", 8, "12:30 PM", ALL),
    ("Study group", "Cert Study Group: cloud and IT fundamentals", "Alumni volunteers", 11, "7:30 PM", ("software", "support", "data")),
    ("Q&A", "Ask the Career Team Anything", "TKH Career Team", 18, "1:00 PM", ALL),
]
METRO_NAMES = {"new york": "New York metro", "atlanta": "Atlanta", "los angeles": "Los Angeles", "chicago": "Chicago",
               "san francisco": "San Francisco", "washington": "Washington, DC", "houston": "Houston", "boston": "Boston",
               "philadelphia": "Philadelphia", "dallas": "Dallas"}


def metro_key(city: Optional[str]) -> Optional[str]:
    """'Brooklyn, NY' / 'Newark' -> 'new york' (one labor market); other cities by their own name."""
    name = (city or "").split(",")[0].strip().lower()
    if not name:
        return None
    return "new york" if any(name in group for group in METRO_GROUPS) else name


def events_for(city: Optional[str], family: str, today: date) -> dict:
    key = metro_key(city)
    metro = METRO_NAMES.get(key) if key else None

    def build(templates, where, virtual):
        out = []
        for i, (kind, title, host, offset, at, suits) in enumerate(templates):
            when = today + timedelta(days=offset)
            out.append({"id": f"{'online' if virtual else key}-{i}", "kind": kind, "title": title.format(metro=metro or ""),
                        "host": host, "date": when.isoformat(), "time": at, "where": where, "virtual": virtual,
                        "for_you": family in suits and suits != ALL, "sample": True})
        return out

    local = build(LOCAL_TEMPLATES, f"{metro}" if metro else "", False) if metro else []
    online = build(ONLINE_TEMPLATES, "Online", True)
    order = lambda e: (not e["for_you"], e["date"])
    return {"metro": metro, "local": sorted(local, key=order), "online": sorted(online, key=order),
            "note": "Sample events for the demo. Real local events will appear here once connected."}
