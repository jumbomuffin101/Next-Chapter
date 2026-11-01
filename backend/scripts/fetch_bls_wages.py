"""Download national annual wages from the BLS (OEWS) for the occupations TKH alumni usually hold.

    python -m backend.scripts.fetch_bls_wages

Writes backend/app/salary/bls_wages.json, which the API reads; re-run once a year when BLS publishes new estimates.
Uses the public v1 API (no key; 25 series per request, 25 requests a day). Run from the repository root.
"""
import json
import urllib.request
from datetime import date
from pathlib import Path

from backend.app.salary.occupations import OCCUPATIONS

API = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
OUT = Path(__file__).resolve().parent.parent / "app" / "salary" / "bls_wages.json"
# OEWS series: OEU + N (national) + area 0000000 + industry 000000 + SOC (6 digits) + datatype
DATATYPES = {"p25": "12", "median": "13", "p75": "14"}


def series_id(soc: str, datatype: str) -> str:
    return f"OEUN0000000000000{soc.replace('-', '')}{datatype}"


def fetch(ids: list[str]) -> dict[str, tuple[str, int]]:
    request = urllib.request.Request(API, data=json.dumps({"seriesid": ids}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)
    if body.get("status") != "REQUEST_SUCCEEDED":
        raise SystemExit(f"BLS request failed: {body.get('message')}")
    found = {}
    for series in body["Results"]["series"]:
        latest = next((row for row in series["data"] if row.get("latest") == "true"), None)
        if latest and latest["value"].replace(".", "").isdigit():  # BLS uses '*' or '#' for suppressed values
            found[series["seriesID"]] = (latest["year"], int(float(latest["value"])))
    return found


def main() -> None:
    ids = [series_id(soc, code) for soc, _, _ in OCCUPATIONS for code in DATATYPES.values()]
    values = {}
    for start in range(0, len(ids), 25):
        values.update(fetch(ids[start:start + 25]))
    occupations, years = {}, set()
    for soc, name, _ in OCCUPATIONS:
        row = {key: values.get(series_id(soc, code)) for key, code in DATATYPES.items()}
        if not all(row.values()):
            print(f"skipped {soc} {name}: BLS has no published value")
            continue
        years.update(year for year, _ in row.values())
        occupations[soc] = {"name": name, **{key: value for key, (_, value) in row.items()}}
    OUT.write_text(json.dumps({
        "source": "U.S. Bureau of Labor Statistics, Occupational Employment and Wage Statistics (OEWS), national annual wages",
        "estimates_year": max(years), "fetched": date.today().isoformat(), "occupations": occupations,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(occupations)} occupations to {OUT}")


if __name__ == "__main__":
    main()
