# Congress Scorecard

Interactive look at every current member of the U.S. Congress: how many
**bills and joint resolutions** they primarily sponsored, and how many of those
measures **became law** — including cases where Congressional Research Service
(CRS) linked the text to another enacted vehicle.

Primary view is the completed **118th Congress (2023–2025)**. Switch to the
**119th Congress so far** or to **career totals** for the Congresses you have
downloaded. The GPO Bill Status bulk feed begins with the **108th Congress**;
career mode therefore covers **108th–119th (2003–present)** so that long-serving
members (e.g. Pelosi, Waters) receive complete primary-sponsorship counts for
the available modern era.

No API key is required.

## How to use

### 1. Install

You need [Python 3.11+](https://www.python.org/downloads/).

```powershell
git clone https://github.com/daexchef/congress-accomplishments.git
cd congress-accomplishments
python -m venv .venv
.\ .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On macOS/Linux, activate with `source .venv/bin/activate`.

### 2. Run the app

Processed tables are already in `data/processed/`, so you can open the
scorecard immediately:

```powershell
streamlit run app.py
```

Then open the URL Streamlit prints (usually http://localhost:8501).

On Windows you can also double-click `run.bat`. It creates the venv, builds
data if needed, and starts the app.

### 3. Use the interface

| Control | What it does |
| --- | --- |
| **Time window** | 118th Congress, 119th so far, or career (downloaded years) |
| **Count related / incorporated vehicles** | On (default): credit a bill if it became law *or* CRS linked it to an enacted vehicle. Off: only bills that themselves became public/private law |
| **Voting members only** | Hides delegates and the Resident Commissioner (DC, PR, GU, VI, AS, MP) |
| **Chamber / party / state / seniority** | Filter the table, plot, stats, and rankings |
| **Search** | Name or bioguide ID. Narrow a search to a few people to see their individual bills |
| **Download** | CSV of the current filtered view, or the full multi-period dataset |

The scatter plot is introduced (x) vs enacted (y). Color is party; size is
seniority. Rankings cover top 20 enacted, top 20 introduced, and highest
enactment rate (with a minimum-bill floor you can change).

### 4. Refresh or expand the data

Re-run whenever you want newer 119th numbers. ZIPs are cached under
`data/cache/` and skipped unless you pass `--force`.

```powershell
# Default: 118th + 119th only (~50 MB)
python scripts/build_dataset.py

# 108th–119th so career totals cover 2003–present (GPO bulk start; ~500–700 MB)
python scripts/build_dataset.py --career

# Specific Congresses, re-download
python scripts/build_dataset.py --congresses 119 --force
python scripts/build_dataset.py --congresses 108 109 110 111 112 113 114 115 116 117 118 119
```

Then reload the Streamlit page. No API key is needed for this path.

Optional: set `CONGRESS_GOV_API_KEY` (free at
[api.congress.gov/sign-up](https://api.congress.gov/sign-up/)) if you want the
helper in `src/congress_api.py`. Copy `.env.example` to start.

## What the numbers mean

**Universe.** Current members from the
[congress-legislators](https://github.com/unitedstates/congress-legislators)
roster, matched by official **bioguide ID**. The live roster will be a few
seats short of 535 whenever the House has vacancies.

The **118th** tab lists current members who also served in that Congress.
People who left after 2024 are not in the current roster; 119th freshmen did
not serve in the 118th.

**Proposed accomplishments.** Count of bills (`HR`, `S`) and joint resolutions
(`HJRES`, `SJRES`) on which the member is the *primary sponsor*. Concurrent and
simple resolutions cannot become statute and are dropped. Cosponsorships do
not count.

**Standalone enactment.** The GPO Bill Status file has a `<laws>` citation
(public or private law), or an action of type `BecameLaw`.

**Enactment including incorporation (default toggle).** The measure itself
became law, **or** CRS/Congress tagged a same-Congress relationship of type
**Identical bill**, **Companion measure**, **Text similarities**, **Contained
in public law**, or **Public law contains the text** pointing at a measure that
became law. Relationships are walked in both directions because omnibuses
often list the source bills. Notes/actions are also scanned for phrases such
as “incorporated into”. Each sponsored measure is counted at most once.

This is **not** the Center for Effective Lawmaking 5-gram Jaccard method
(LES 2.0). CEL’s bill-level file is not published. The related-bill rule is a
transparent CRS-based fallback. Audit it in `data/processed/bills.csv`
(`became_law`, `incorporated`, `incorporation_basis`, `related_enacted_ids`).

## Data sources

| Role | Source | Key |
| --- | --- | --- |
| Members | [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators) current JSON | none |
| Bills, sponsors, laws, related bills | [GPO Bill Status bulk XML](https://www.govinfo.gov/bulkdata/BILLSTATUS) | none |
| Optional career API | [Congress.gov API](https://api.congress.gov/) | `CONGRESS_GOV_API_KEY` |

## Limitations

- Most bills never become law. A low enactment count is the norm.
- Committee work, amendments, oversight, nominations, and deal-making on
  *other people’s* bills are invisible.
- Naming post offices and commemorative measures inflate introduction counts.
- Leadership and chairs often fold ideas into must-pass vehicles; standalone
  sponsorship understates that work.
- Career totals only include Congresses you downloaded. GPO Bill Status bulk
  data begins at the 108th Congress (2003). Members whose primary-sponsored
  laws pre-date 2003 (rare for current members) will still show truncated
  counts unless you supplement with other sources.
- The 119th Congress is still in session; its counts will change.
- Vacancies and mid-session special elections follow the current
  congress-legislators snapshot.

## Project layout

```
app.py                      Streamlit UI
scripts/build_dataset.py    Download + parse + aggregate
src/members.py              Current roster
src/bills.py                GPO ZIP download and XML parse
src/metrics.py              Per-member, per-period metrics
src/congress_api.py         Optional Congress.gov API helper
data/cache/                 Downloaded ZIPs and roster (gitignored)
data/processed/             members.csv, bills.csv, member_metrics.csv
```

Not an official U.S. government publication.
