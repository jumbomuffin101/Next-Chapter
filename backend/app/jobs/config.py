"""Hardcoded Greenhouse board tokens (the token is in boards.greenhouse.io/{token}).

Target cities: New York, Newark, Atlanta, Los Angeles (named in public sources on The Knowledge
House's locations) + Chicago (my pick; TKH's fifth city isn't published). Remote-US roles also match.

Each board below returned live jobs when spot-checked (Oct 2026) and has postings in those cities or
remote. Counts are approximate. Re-check with `python scripts/check_boards.py`. Atlanta/Newark
coverage is thin (ziprecruiter has Atlanta); add more tokens there if you find them.
"""
BOARD_TOKENS: list[str] = [
    # NYC / remote, many ops, sales, support, intern roles
    "coinbase",
    "squarespace",
    "lyft",
    "reddit",
    "instacart",
    "affirm",
    "datadog",
    "robinhood",
    "figma",
    "stripe",
    # Chicago / Atlanta / LA / remote
    "sproutsocial",
    "ziprecruiter",
    "groupon",
]

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true&pay_transparency=true"
