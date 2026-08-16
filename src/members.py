"""Current-member roster from the congress-legislators project."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import pandas as pd

from .config import (
    CONGRESS_RANGES,
    MEMBERS_CACHE,
    MEMBERS_URL,
    NONVOTING_STATES,
)
from .http_util import download_file

PARTY_MAP = {
    "Democrat": "Democratic",
    "Democratic": "Democratic",
    "Republican": "Republican",
    "Independent": "Independent",
    "Independent Democrat": "Independent",
    "Libertarian": "Libertarian",
}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _term_overlaps(term: dict[str, Any], start: date, end: date) -> bool:
    t0 = _parse_date(term.get("start"))
    t1 = _parse_date(term.get("end")) or date.today()
    if t0 is None:
        return False
    return t0 < end and t1 > start


def _years_served(first_start: date, as_of: date) -> float:
    days = (as_of - first_start).days
    return round(max(days, 0) / 365.25, 1)


def fetch_members(*, force: bool = False) -> list[dict[str, Any]]:
    download_file(MEMBERS_URL, MEMBERS_CACHE, force=force)
    return json.loads(MEMBERS_CACHE.read_text(encoding="utf-8"))


def members_frame(raw: list[dict[str, Any]] | None = None) -> pd.DataFrame:
    """One row per currently serving legislator, keyed by bioguide ID."""
    if raw is None:
        raw = fetch_members()

    today = date.today()
    rows: list[dict[str, Any]] = []
    for person in raw:
        bioguide = (person.get("id") or {}).get("bioguide")
        if not bioguide:
            continue
        terms = person.get("terms") or []
        if not terms:
            continue
        current = terms[-1]
        name = person.get("name") or {}
        official = name.get("official_full") or " ".join(
            p for p in (name.get("first"), name.get("last")) if p
        )
        chamber = "Senate" if current.get("type") == "sen" else "House"
        party = PARTY_MAP.get(current.get("party") or "", current.get("party") or "Unknown")
        state = current.get("state") or ""
        district = current.get("district")
        if chamber == "Senate":
            district_label = ""
            seat = f"{state}"
        elif district in (0, "0", None):
            district_label = "At-Large"
            seat = f"{state}-AL"
        else:
            district_label = str(int(district))
            seat = f"{state}-{int(district)}"

        first_start = None
        for term in terms:
            d = _parse_date(term.get("start"))
            if d and (first_start is None or d < first_start):
                first_start = d
        if first_start is None:
            first_start = _parse_date(current.get("start")) or today

        served = {}
        for congress, (c0, c1) in CONGRESS_RANGES.items():
            start, end = _parse_date(c0), _parse_date(c1)
            served[f"served_{congress}"] = any(
                _term_overlaps(term, start, end) for term in terms  # type: ignore[arg-type]
            )

        voting = state not in NONVOTING_STATES
        member_type = "Senator" if chamber == "Senate" else (
            "Delegate/Resident Commissioner" if not voting else "Representative"
        )

        rows.append(
            {
                "bioguide_id": bioguide,
                "full_name": official,
                "chamber": chamber,
                "party": party,
                "state": state,
                "district": district_label,
                "seat": seat,
                "member_type": member_type,
                "voting_member": voting,
                "first_term_start": first_start.isoformat(),
                "seniority_years": _years_served(first_start, today),
                "govtrack_id": (person.get("id") or {}).get("govtrack"),
                **served,
            }
        )

    df = pd.DataFrame(rows).sort_values(["chamber", "state", "district", "full_name"])
    return df.reset_index(drop=True)
