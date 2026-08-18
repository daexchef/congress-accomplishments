"""Download official sources and write processed member/bill tables.

Examples:
    python scripts/build_dataset.py
    python scripts/build_dataset.py --career          # 108–119 (2003–present)
    python scripts/build_dataset.py --congresses 118 119
    python scripts/build_dataset.py --congresses 108 109 110 111 112 113 114 115 116 117 118 119
    python scripts/build_dataset.py --force
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bills import load_bills, mark_incorporation  # noqa: E402
from src.config import (  # noqa: E402
    CAREER_CONGRESSES,
    DEFAULT_CONGRESSES,
    PROCESSED_DIR,
)
from src.members import members_frame  # noqa: E402
from src.metrics import all_period_metrics, bills_frame, summary_stats  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build the Congress accomplishments dataset.")
    p.add_argument(
        "--congresses",
        nargs="+",
        type=int,
        default=None,
        help="Congress numbers to download (default: 118 119).",
    )
    p.add_argument(
        "--career",
        action="store_true",
        help="Download 108th–119th Congresses so career totals cover 2003–present (GPO bulk availability).",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-download cached ZIPs and the member roster.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.congresses:
        congresses = tuple(args.congresses)
    elif args.career:
        congresses = CAREER_CONGRESSES
    else:
        congresses = DEFAULT_CONGRESSES

    print(f"Building dataset for Congresses: {', '.join(map(str, congresses))}")
    members = members_frame()
    print(f"Current members: {len(members)}  voting: {int(members['voting_member'].sum())}")

    raw_bills = load_bills(congresses, force=args.force)
    raw_bills = mark_incorporation(raw_bills)
    bills = bills_frame(raw_bills)
    metrics = all_period_metrics(members, bills)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    members_path = PROCESSED_DIR / "members.csv"
    bills_path = PROCESSED_DIR / "bills.csv"
    metrics_path = PROCESSED_DIR / "member_metrics.csv"
    meta_path = PROCESSED_DIR / "build_meta.json"

    members.to_csv(members_path, index=False)
    bills.to_csv(bills_path, index=False)
    metrics.to_csv(metrics_path, index=False)

    rel_types: dict[str, int] = {}
    for rec in raw_bills:
        for rel in rec.get("related") or []:
            key = (rel.get("rel_type") or "unknown").strip()
            rel_types[key] = rel_types.get(key, 0) + 1

    period_summaries = {}
    for period in metrics["period"].unique():
        period_summaries[period] = summary_stats(metrics[metrics["period"] == period])

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "congresses": list(congresses),
        "member_count": int(len(members)),
        "voting_member_count": int(members["voting_member"].sum()),
        "bill_count": int(len(bills)),
        "bills_became_law": int(bills["became_law"].sum()) if not bills.empty else 0,
        "bills_incorporated_only": int(bills["incorporated"].sum()) if not bills.empty else 0,
        "related_type_counts": dict(sorted(rel_types.items(), key=lambda kv: (-kv[1], kv[0]))),
        "period_summaries": period_summaries,
        "sources": {
            "members": "https://unitedstates.github.io/congress-legislators/legislators-current.json",
            "bills": "https://www.govinfo.gov/bulkdata/BILLSTATUS",
        },
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print()
    print(f"Wrote {members_path}")
    print(f"Wrote {bills_path} ({len(bills):,} rows)")
    print(f"Wrote {metrics_path} ({len(metrics):,} rows)")
    print(f"Wrote {meta_path}")
    print()
    print("118th snapshot (voting members):")
    s = period_summaries.get("118", {})
    print(
        f"  n={s.get('members')}  intro={s.get('bills_introduced_total')}  "
        f"enacted+related={s.get('laws_enacted_total')}  "
        f"success={s.get('overall_success_rate', 0):.2f}%  "
        f"zero_enacted={s.get('pct_zero_enacted', 0):.1f}%"
    )


if __name__ == "__main__":
    main()
