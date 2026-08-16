"""Aggregate per-member proposed vs. enacted counts."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from .config import CONGRESS_RANGES, PERIODS
from .members import _years_served, _parse_date


def bills_frame(bills: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for b in bills:
        rows.append(
            {
                "bill_id": b["bill_id"],
                "congress": b["congress"],
                "bill_type": b["bill_type"],
                "number": b["number"],
                "title": b.get("title") or "",
                "policy_area": b.get("policy_area") or "",
                "sponsor_bioguide": b["sponsor_bioguide"],
                "sponsor_name": b.get("sponsor_name") or "",
                "introduced_date": b.get("introduced_date") or "",
                "latest_action": b.get("latest_action") or "",
                "became_law": bool(b.get("became_law")),
                "law_citation": b.get("law_citation") or "",
                "incorporated": bool(b.get("incorporated")),
                "related_enacted_ids": b.get("related_enacted_ids") or "",
                "incorporation_basis": b.get("incorporation_basis") or "",
                "enacted_including": bool(b.get("enacted_including")),
            }
        )
    return pd.DataFrame(rows)


def _period_congresses(period_key: str, available: list[int]) -> list[int]:
    spec = PERIODS[period_key]
    if spec["congresses"] is None:
        return sorted(available)
    return [c for c in spec["congresses"] if c in available]


def _as_of(period_key: str) -> date:
    spec = PERIODS[period_key]
    if spec["as_of"]:
        return date.fromisoformat(spec["as_of"])
    return date.today()


def member_metrics(
    members: pd.DataFrame,
    bills: pd.DataFrame,
    *,
    period_key: str,
) -> pd.DataFrame:
    available = sorted(bills["congress"].dropna().unique().tolist()) if not bills.empty else []
    congresses = _period_congresses(period_key, available)
    as_of = _as_of(period_key)
    spec = PERIODS[period_key]

    scoped = bills[bills["congress"].isin(congresses)].copy() if congresses else bills.iloc[0:0]
    grouped = (
        scoped.groupby("sponsor_bioguide", dropna=True)
        .agg(
            bills_introduced=("bill_id", "size"),
            laws_enacted=("became_law", "sum"),
            laws_via_related=("incorporated", "sum"),
            laws_enacted_including=("enacted_including", "sum"),
        )
        .reset_index()
        .rename(columns={"sponsor_bioguide": "bioguide_id"})
    )

    out = members.merge(grouped, on="bioguide_id", how="left")
    for col in (
        "bills_introduced",
        "laws_enacted",
        "laws_via_related",
        "laws_enacted_including",
    ):
        out[col] = out[col].fillna(0).astype(int)

    first_starts = out["first_term_start"].map(_parse_date)
    out["seniority_years"] = [
        _years_served(fs, as_of) if fs else 0.0 for fs in first_starts
    ]

    intro = out["bills_introduced"].replace(0, float("nan"))
    out["enactment_rate"] = out["laws_enacted_including"] / intro
    out["standalone_rate"] = out["laws_enacted"] / intro

    required = spec.get("require_service")
    if required is not None:
        flag = f"served_{required}"
        if flag in out.columns:
            out = out[out[flag]].copy()

    out["period"] = period_key
    out["period_label"] = spec["label"]
    out["congresses_included"] = ",".join(str(c) for c in congresses)
    return out.reset_index(drop=True)


def all_period_metrics(members: pd.DataFrame, bills: pd.DataFrame) -> pd.DataFrame:
    frames = [member_metrics(members, bills, period_key=key) for key in PERIODS]
    return pd.concat(frames, ignore_index=True)


def summary_stats(df: pd.DataFrame, enacted_col: str = "laws_enacted_including") -> dict[str, Any]:
    voting = df[df["voting_member"]].copy() if "voting_member" in df.columns else df
    n = len(voting)
    intro = voting["bills_introduced"]
    enacted = voting[enacted_col]
    zero = int((enacted == 0).sum()) if n else 0
    total_intro = int(intro.sum()) if n else 0
    total_enacted = int(enacted.sum()) if n else 0
    return {
        "members": n,
        "bills_introduced_total": total_intro,
        "laws_enacted_total": total_enacted,
        "avg_introduced": float(intro.mean()) if n else 0.0,
        "median_introduced": float(intro.median()) if n else 0.0,
        "max_introduced": int(intro.max()) if n else 0,
        "avg_enacted": float(enacted.mean()) if n else 0.0,
        "median_enacted": float(enacted.median()) if n else 0.0,
        "max_enacted": int(enacted.max()) if n else 0,
        "pct_zero_enacted": (100.0 * zero / n) if n else 0.0,
        "members_with_zero_enacted": zero,
        "overall_success_rate": (100.0 * total_enacted / total_intro) if total_intro else 0.0,
        "congress_range": voting["congresses_included"].iloc[0] if n else "",
    }


def congress_coverage_note(bills: pd.DataFrame) -> str:
    if bills.empty:
        return "No bill data on disk."
    years = []
    for congress in sorted(bills["congress"].unique()):
        span = CONGRESS_RANGES.get(int(congress))
        if span:
            years.append(f"{congress} ({span[0][:4]}–{span[1][:4]})")
        else:
            years.append(str(congress))
    return ", ".join(years)
