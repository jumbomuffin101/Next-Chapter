"""GET /salary/estimate?title=...: what BLS says people in the closest occupation typically earn (national, annual)."""
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

from .occupations import occupation_for

router = APIRouter(prefix="/salary", tags=["salary"])
DATA = Path(__file__).with_name("bls_wages.json")  # written by backend/scripts/fetch_bls_wages.py


@lru_cache
def _wages() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def estimate(title: Optional[str]) -> dict:
    data = _wages()
    match = occupation_for(title)
    row = data["occupations"].get(match[0]) if match else None
    if not row:
        return {"matched": False, "title": title, "source": data["source"]}
    return {
        "matched": True, "title": title, "soc": match[0], "occupation": row["name"],
        "p25": row["p25"], "median": row["median"], "p75": row["p75"],
        "area": "United States", "year": data["estimates_year"], "source": data["source"],
    }


@router.get("/estimate")
def salary_estimate(title: str = Query(..., min_length=1, max_length=200)):
    """A typical range (25th to 75th percentile) for the closest BLS occupation; matched=false if none fits."""
    return estimate(title)
