"""Optional Congress.gov API path for career totals when bulk years are missing.

Set CONGRESS_GOV_API_KEY (free at https://api.congress.gov/sign-up/) to use this.
The default pipeline does not need a key: it reads GPO Bill Status ZIPs.
"""

from __future__ import annotations

import os
import time
from typing import Any

from .http_util import session

API_ROOT = "https://api.congress.gov/v3"
LAWMAKING = {"HR", "S", "HJRES", "SJRES"}


def api_key() -> str | None:
    return os.environ.get("CONGRESS_GOV_API_KEY") or os.environ.get("CONGRESS_API_KEY")


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    key = api_key()
    if not key:
        raise RuntimeError("Set CONGRESS_GOV_API_KEY to use the Congress.gov API.")
    q = {"api_key": key, "format": "json", "limit": 250}
    if params:
        q.update(params)
    s = session()
    resp = s.get(f"{API_ROOT}{path}", params=q, timeout=60)
    if resp.status_code == 429:
        time.sleep(2)
        resp = s.get(f"{API_ROOT}{path}", params=q, timeout=60)
    resp.raise_for_status()
    return resp.json()


def sponsored_counts(bioguide_id: str, congresses: set[int] | None = None) -> dict[str, int]:
    """Count sponsored lawmaking measures and those whose latest action is enactment."""
    introduced = 0
    enacted = 0
    offset = 0
    while True:
        data = _get(
            f"/member/{bioguide_id}/sponsored-legislation",
            {"offset": offset},
        )
        items = data.get("sponsoredLegislation") or []
        if not items:
            break
        for item in items:
            btype = (item.get("type") or "").upper()
            if btype not in LAWMAKING:
                continue
            congress = item.get("congress")
            if congresses is not None and congress not in congresses:
                continue
            introduced += 1
            action = ((item.get("latestAction") or {}).get("text") or "").lower()
            if "became public law" in action or "became private law" in action:
                enacted += 1
        if len(items) < 250:
            break
        offset += 250
        time.sleep(0.2)  # stay well under the public rate limit
    return {"bills_introduced": introduced, "laws_enacted": enacted}
