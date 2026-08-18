"""Paths, source URLs, and scoring rules for the pipeline."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
PROCESSED_DIR = DATA_DIR / "processed"

MEMBERS_URL = (
    "https://unitedstates.github.io/congress-legislators/legislators-current.json"
)
MEMBERS_CACHE = CACHE_DIR / "legislators-current.json"

# GPO Bill Status ZIP layout:
# https://www.govinfo.gov/bulkdata/BILLSTATUS/{congress}/{type}/BILLSTATUS-{congress}-{type}.zip
BILLSTATUS_ZIP = (
    "https://www.govinfo.gov/bulkdata/BILLSTATUS/{congress}/{bill_type}/"
    "BILLSTATUS-{congress}-{bill_type}.zip"
)

# Only measures that can become law. Concurrent/simple resolutions cannot.
LAWMAKING_TYPES = ("hr", "s", "hjres", "sjres")
TYPE_DISPLAY = {
    "hr": "HR",
    "s": "S",
    "hjres": "HJRES",
    "sjres": "SJRES",
    "HR": "HR",
    "S": "S",
    "HJRES": "HJRES",
    "SJRES": "SJRES",
}

# Current members who do not have a floor vote in the House or Senate.
NONVOTING_STATES = frozenset({"DC", "PR", "GU", "VI", "AS", "MP"})

USER_AGENT = (
    "congress-accomplishments/1.0 "
    "(research tool; +https://www.govinfo.gov/bulkdata/BILLSTATUS)"
)

# CRS/House/Senate related-bill types that credit a sponsored measure
# when its language advanced as another vehicle that became law.
# "Related bill" alone is too loose (often topical, not textual).
# "Text similarities" is the CRS label that includes language found
# intact inside a larger measure. "Contained in public law" /
# "Public law contains the text" are explicit incorporation tags.
INCORPORATION_REL_TYPES = frozenset(
    {
        "identical bill",
        "companion measure",
        "text similarities",
        "contained in public law",
        "public law contains the text",
        "identical bill (became law)",
    }
)

# Extra note/action phrases that sometimes record incorporation when CRS
# has not yet assigned a structured relationship.
INCORPORATION_PHRASES = (
    "incorporated into",
    "incorporated in",
    "language was included in",
    "provisions were included in",
)

# GPO Bill Status bulk XML is available starting with the 108th Congress.
# Earlier Congresses require other sources (Congress.gov API or historical scrapes).
CONGRESS_RANGES = {
    108: ("2003-01-07", "2005-01-03"),
    109: ("2005-01-04", "2007-01-03"),
    110: ("2007-01-04", "2009-01-03"),
    111: ("2009-01-06", "2011-01-03"),
    112: ("2011-01-05", "2013-01-03"),
    113: ("2013-01-03", "2015-01-03"),
    114: ("2015-01-06", "2017-01-03"),
    115: ("2017-01-03", "2019-01-03"),
    116: ("2019-01-03", "2021-01-03"),
    117: ("2021-01-03", "2023-01-03"),
    118: ("2023-01-03", "2025-01-03"),
    119: ("2025-01-03", "2027-01-03"),
}

DEFAULT_CONGRESSES = (118, 119)
# Full GPO-available range so career totals cover 2003–present for long-serving members.
CAREER_CONGRESSES = tuple(range(108, 120))  # 108 … 119

PERIODS = {
    "118": {
        "label": "118th Congress (2023–2025)",
        "congresses": (118,),
        "as_of": "2025-01-03",
        "require_service": 118,
    },
    "119": {
        "label": "119th Congress so far (2025–)",
        "congresses": (119,),
        "as_of": None,  # today
        "require_service": 119,
    },
    "career": {
        "label": "Career totals (108th–119th / 2003–present)",
        "congresses": None,  # all bills on disk
        "as_of": None,
        "require_service": None,
    },
}

REQUEST_TIMEOUT = 120
MAX_RETRIES = 5
RETRY_BACKOFF = 2.0
