"""Interactive scorecard of current members of Congress."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import PERIODS, PROCESSED_DIR
from src.metrics import summary_stats

PARTY_COLORS = {
    "Democratic": "#1f4e79",
    "Republican": "#9b2c2c",
    "Independent": "#6a542e",
    "Libertarian": "#3d6b4f",
}
PARTY_ORDER = ["Democratic", "Republican", "Independent", "Libertarian"]

st.set_page_config(
    page_title="Congress Scorecard",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Libre+Baskerville:wght@400;700&display=swap');
        html, body, [class*="css"]  { font-family: 'IBM Plex Sans', sans-serif; }
        .stApp { background: #f3efe4; color: #1c1914; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] { background: #e8e0cf; }
        h1, h2, h3 { font-family: 'Libre Baskerville', Georgia, serif; color: #1c1914; }
        .hero-kicker { letter-spacing: 0.16em; text-transform: uppercase; font-size: 0.78rem;
                        color: #8b3a2a; font-weight: 600; margin-bottom: 0.2rem; }
        .hero-sub { color: #4a453c; max-width: 52rem; line-height: 1.5; margin-bottom: 0.6rem; }
        .metric-card { background: #fffdf7; border: 1px solid #d8cfc0; padding: 0.85rem 1rem;
                       border-radius: 2px; }
        .metric-card .label { font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase;
                              color: #6b6458; }
        .metric-card .value { font-family: 'Libre Baskerville', Georgia, serif; font-size: 1.7rem;
                              line-height: 1.2; }
        .metric-card .hint { font-size: 0.8rem; color: #6b6458; }
        .footnote { color: #5c564c; font-size: 0.88rem; }
        div[data-testid="stMetricValue"] { font-family: 'Libre Baskerville', Georgia, serif; }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_processed() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    metrics_path = PROCESSED_DIR / "member_metrics.csv"
    bills_path = PROCESSED_DIR / "bills.csv"
    meta_path = PROCESSED_DIR / "build_meta.json"
    if not metrics_path.exists():
        return pd.DataFrame(), pd.DataFrame(), {}
    metrics = pd.read_csv(metrics_path)
    bills = pd.read_csv(bills_path) if bills_path.exists() else pd.DataFrame()
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return metrics, bills, meta


def _enacted_col(include_related: bool) -> str:
    return "laws_enacted_including" if include_related else "laws_enacted"


def apply_filters(
    df: pd.DataFrame,
    *,
    chamber: list[str],
    party: list[str],
    states: list[str],
    seniority: tuple[float, float],
    query: str,
    voting_only: bool,
) -> pd.DataFrame:
    out = df.copy()
    if voting_only:
        out = out[out["voting_member"]]
    if chamber:
        out = out[out["chamber"].isin(chamber)]
    if party:
        out = out[out["party"].isin(party)]
    if states:
        out = out[out["state"].isin(states)]
    lo, hi = seniority
    out = out[(out["seniority_years"] >= lo) & (out["seniority_years"] <= hi)]
    q = query.strip().lower()
    if q:
        hay = (
            out["full_name"].fillna("").str.lower()
            + " "
            + out["bioguide_id"].fillna("").str.lower()
            + " "
            + out["seat"].fillna("").str.lower()
        )
        out = out[hay.str.contains(q, regex=False)]
    return out


def scatter(df: pd.DataFrame, enacted_col: str) -> go.Figure:
    fig = go.Figure()
    for party in PARTY_ORDER:
        sub = df[df["party"] == party]
        if sub.empty:
            continue
        jitter_x = (pd.util.hash_pandas_object(sub["bioguide_id"]) % 17) / 17.0 * 0.35
        jitter_y = (pd.util.hash_pandas_object(sub["full_name"]) % 13) / 13.0 * 0.12
        fig.add_trace(
            go.Scatter(
                x=sub["bills_introduced"] + jitter_x,
                y=sub[enacted_col] + jitter_y,
                mode="markers",
                name=party,
                marker=dict(
                    color=PARTY_COLORS.get(party, "#444"),
                    size=(sub["seniority_years"].clip(lower=1) ** 0.55) * 3.2 + 6,
                    opacity=0.78,
                    line=dict(width=0.4, color="#f3efe4"),
                ),
                customdata=list(
                    zip(
                        sub["full_name"],
                        sub["chamber"],
                        sub["party"],
                        sub["seat"],
                        sub["seniority_years"],
                        sub["bills_introduced"],
                        sub[enacted_col],
                        sub["enactment_rate"].fillna(-1),
                        sub["bioguide_id"],
                    )
                ),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "%{customdata[1]} · %{customdata[2]} · %{customdata[3]}<br>"
                    "Seniority: %{customdata[4]:.1f} years<br>"
                    "Introduced: %{customdata[5]}<br>"
                    "Enacted: %{customdata[6]}<br>"
                    "Rate: %{customdata[7]:.1%}<br>"
                    "<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        paper_bgcolor="#f3efe4",
        plot_bgcolor="#fffdf7",
        font=dict(family="IBM Plex Sans, sans-serif", color="#1c1914"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(
            title="Bills & joint resolutions introduced (proposed)",
            gridcolor="#e6ddcc",
            zeroline=False,
        ),
        yaxis=dict(
            title="Those measures enacted (accomplishments)",
            gridcolor="#e6ddcc",
            zeroline=False,
        ),
        height=520,
    )
    return fig


def ranking_table(df: pd.DataFrame, enacted_col: str, kind: str, min_intro: int) -> pd.DataFrame:
    work = df.copy()
    if kind == "enacted":
        work = work.sort_values([enacted_col, "bills_introduced"], ascending=False)
    elif kind == "introduced":
        work = work.sort_values(["bills_introduced", enacted_col], ascending=False)
    else:
        work = work[work["bills_introduced"] >= min_intro].copy()
        rate_col = "enactment_rate" if enacted_col.endswith("including") else "standalone_rate"
        work = work.sort_values([rate_col, enacted_col], ascending=False)
    work = work.head(20)
    rate = work["enactment_rate"] if enacted_col.endswith("including") else work["standalone_rate"]
    show = pd.DataFrame(
        {
            "Rank": range(1, len(work) + 1),
            "Name": work["full_name"].values,
            "Chamber": work["chamber"].values,
            "Party": work["party"].values,
            "Seat": work["seat"].values,
            "Introduced": work["bills_introduced"].values,
            "Enacted": work[enacted_col].values,
            "Rate": rate.map(lambda v: "" if pd.isna(v) else f"{v:.1%}").values,
        }
    )
    return show


def main() -> None:
    _inject_css()
    metrics, bills, meta = load_processed()

    st.markdown('<div class="hero-kicker">United States Congress</div>', unsafe_allow_html=True)
    st.title("Who gets laws enacted?")
    st.markdown(
        '<div class="hero-sub">A scorecard of every current voting member: how many '
        "bills and joint resolutions they primarily sponsored, and how many of those "
        "measures became law — including cases where CRS linked the text to another "
        "enacted vehicle.</div>",
        unsafe_allow_html=True,
    )

    if metrics.empty:
        st.error(
            "No processed data found. From the project folder run "
            "`python scripts/build_dataset.py --career` then reload this page."
        )
        st.stop()

    with st.sidebar:
        st.header("View")
        period_labels = {k: v["label"] for k, v in PERIODS.items()}
        period_key = st.radio(
            "Time window",
            options=list(PERIODS.keys()),
            format_func=lambda k: period_labels[k],
            index=0,
        )
        include_related = st.toggle(
            "Count related / incorporated vehicles",
            value=True,
            help=(
                "On: a sponsored bill counts as enacted if it became law itself, or if CRS "
                "tagged it as identical / companion / text-similar / contained in a public law "
                "that was enacted. Off: only bills that themselves became public or private law."
            ),
        )
        voting_only = st.toggle("Voting members only", value=True)
        st.divider()
        st.header("Filters")
        period_df = metrics[metrics["period"] == period_key]
        chambers = st.multiselect("Chamber", ["House", "Senate"])
        parties = st.multiselect("Party", sorted(period_df["party"].dropna().unique()))
        states = st.multiselect("State / territory", sorted(period_df["state"].dropna().unique()))
        smin = float(period_df["seniority_years"].min())
        smax = float(period_df["seniority_years"].max())
        seniority = st.slider("Seniority (years in Congress)", smin, smax, (smin, smax))
        query = st.text_input("Search name or bioguide ID")
        min_intro = st.number_input(
            "Min. bills for rate rankings", min_value=1, max_value=50, value=10
        )
        filled = int(meta.get("voting_member_count") or 0)
        st.caption(
            "Built "
            + str(meta.get("built_at", "unknown"))[:19].replace("T", " ")
            + " UTC · Congresses "
            + ", ".join(str(c) for c in meta.get("congresses", []))
            + f" · {filled} of 535 voting seats filled"
        )

    enacted_col = _enacted_col(include_related)
    filtered = apply_filters(
        period_df,
        chamber=chambers,
        party=parties,
        states=states,
        seniority=seniority,
        query=query,
        voting_only=voting_only,
    )
    stats = summary_stats(filtered, enacted_col=enacted_col)

    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        (c1, "Members", f"{stats['members']:,}", "in this filtered view"),
        (c2, "Avg introduced", f"{stats['avg_introduced']:.1f}", f"median {stats['median_introduced']:.0f}"),
        (c3, "Avg enacted", f"{stats['avg_enacted']:.2f}", f"max {stats['max_enacted']}"),
        (c4, "Zero enacted", f"{stats['pct_zero_enacted']:.0f}%", f"{stats['members_with_zero_enacted']} members"),
        (c5, "Success rate", f"{stats['overall_success_rate']:.2f}%", "enacted ÷ introduced"),
    ]
    for col, label, value, hint in cards:
        with col:
            st.markdown(
                f'<div class="metric-card"><div class="label">{label}</div>'
                f'<div class="value">{value}</div><div class="hint">{hint}</div></div>',
                unsafe_allow_html=True,
            )

    if period_key == "118":
        st.caption(
            "118th view lists current members who also served in that Congress. "
            "Members who left after 2024 are out of the roster; 119th freshmen are omitted here."
        )

    st.plotly_chart(scatter(filtered, enacted_col), use_container_width=True)
    st.caption(
        "Point color is party. Point size is seniority. A small jitter is added so members "
        "stacked at the same integer counts remain visible."
    )

    st.subheader("Rankings")
    t1, t2, t3 = st.tabs(
        [
            "Top 20 by enacted",
            "Top 20 by introduced",
            f"Highest rate (≥ {min_intro} introduced)",
        ]
    )
    with t1:
        st.dataframe(ranking_table(filtered, enacted_col, "enacted", min_intro), hide_index=True, use_container_width=True)
    with t2:
        st.dataframe(ranking_table(filtered, enacted_col, "introduced", min_intro), hide_index=True, use_container_width=True)
    with t3:
        st.dataframe(ranking_table(filtered, enacted_col, "rate", min_intro), hide_index=True, use_container_width=True)

    st.subheader("All members")
    table = filtered.copy()
    rate_src = table["enactment_rate"] if include_related else table["standalone_rate"]
    display = pd.DataFrame(
        {
            "Name": table["full_name"],
            "Chamber": table["chamber"],
            "Party": table["party"],
            "State": table["state"],
            "Seat": table["seat"],
            "Seniority (yrs)": table["seniority_years"],
            "Introduced": table["bills_introduced"],
            "Enacted (standalone)": table["laws_enacted"],
            "Enacted via related": table["laws_via_related"],
            "Enacted (incl. related)": table["laws_enacted_including"],
            "Rate": rate_src,
            "Voting": table["voting_member"].map({True: "Yes", False: "No"}),
            "Bioguide": table["bioguide_id"],
        }
    )
    st.dataframe(
        display.sort_values(["Enacted (incl. related)", "Introduced"], ascending=False),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Rate": st.column_config.NumberColumn(format="%.1%"),
            "Seniority (yrs)": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    csv_bytes = display.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download this view as CSV",
        data=csv_bytes,
        file_name=f"congress-scorecard-{period_key}.csv",
        mime="text/csv",
    )
    full_path = PROCESSED_DIR / "member_metrics.csv"
    if full_path.exists():
        st.download_button(
            "Download full dataset (all periods)",
            data=full_path.read_bytes(),
            file_name="member_metrics.csv",
            mime="text/csv",
            key="full-dl",
        )

    if query.strip() and not filtered.empty and len(filtered) <= 8 and not bills.empty:
        st.subheader("Sponsored measures")
        ids = set(filtered["bioguide_id"])
        scoped = bills[bills["sponsor_bioguide"].isin(ids)].copy()
        period_congresses = PERIODS[period_key]["congresses"]
        if period_congresses:
            scoped = scoped[scoped["congress"].isin(period_congresses)]
        scoped = scoped.sort_values(["enacted_including", "became_law", "congress"], ascending=False)
        st.dataframe(
            scoped[
                [
                    "bill_id",
                    "title",
                    "sponsor_name",
                    "became_law",
                    "law_citation",
                    "incorporated",
                    "incorporation_basis",
                    "related_enacted_ids",
                    "latest_action",
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("How the numbers are calculated", expanded=False):
        st.markdown(
            """
**Universe.** Current members of Congress from the
[congress-legislators](https://github.com/unitedstates/congress-legislators) roster,
matched by official **bioguide ID**. Delegates and the Resident Commissioner
(DC, PR, GU, VI, AS, MP) are flagged as non-voting and hidden by default.

**Proposed accomplishments.** Count of bills (`HR`, `S`) and joint resolutions
(`HJRES`, `SJRES`) on which the member is the *primary sponsor*. Concurrent and
simple resolutions cannot become law and are excluded. Cosponsorships do not count.

**Standalone enactment.** The measure has a public- or private-law citation in
GPO Bill Status XML (`<laws>`), or an action of type `BecameLaw`.

**Enactment including incorporation (default).** The measure itself became law,
**or** CRS/Congress tagged a same-Congress relationship of type **identical
bill**, **companion measure**, **text similarities**, **contained in public
law**, or **public law contains the text** pointing at a measure that became
law. CRS defines “text similarities” as substantially similar text *and* cases
where language of one measure is found intact in another, often larger, measure.
Notes/actions are also scanned for phrases such as “incorporated into”.

This is **not** the Center for Effective Lawmaking 5-gram Jaccard method (LES 2.0).
CEL’s bill-level incorporation file is not published. Our related-bill rule is a
transparent CRS-based fallback and will miss some omnibus insertions and count
some near-duplicates more generously than a text-overlap model.

**What these numbers miss.** Committee work, amendments to other members’ bills,
oversight, nominations, and appropriations bargaining are invisible here. Most
bills never become law. Commemorative and post-office-naming bills can inflate
introduction counts. Leadership and committee chairs often fold ideas into must-pass
vehicles, so a low standalone count is not the same as inactivity.

**119th Congress** is incomplete. **Career** totals cover only the Congresses
present in `data/processed/` (see the sidebar). Refresh with
`python scripts/build_dataset.py --career`.
            """
        )

    st.markdown(
        '<p class="footnote">Sources: GPO Bill Status bulk XML via govinfo.gov; '
        "member roster from unitedstates/congress-legislators. Not an official "
        "U.S. government publication.</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
