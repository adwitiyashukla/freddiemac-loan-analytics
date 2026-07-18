from __future__ import annotations

from pathlib import Path

import psycopg

from .db import fetch_all, fetch_one
from .utils import get_logger

log = get_logger(__name__)

EXPORT_TABLES = [
    "portfolio_summary",
    "monthly_portfolio",
    "vintage_delinquency",
    "transition_matrix",
    "state_risk",
    "segment_risk",
]


def export_gold_csv(conn: psycopg.Connection, out_dir: Path) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with conn.cursor() as cur:
        for table in EXPORT_TABLES:
            target = out_dir / f"{table}.csv"
            with target.open("wb") as fh, cur.copy(
                f"COPY (SELECT * FROM gold.{table}) TO STDOUT (FORMAT csv, HEADER true)"
            ) as copy:
                for chunk in copy:
                    fh.write(chunk)
            written.append(target)
            log.info("Wrote %s", target)
    return written


def collect_metrics(conn: psycopg.Connection) -> dict[str, object]:
    summary = fetch_one(
        conn,
        "SELECT n_loans, total_orig_upb_billions, avg_credit_score, avg_ltv, "
        "avg_dti, avg_interest_rate, pct_ever_d30, pct_ever_d90, pct_prepaid, "
        "pct_credit_event, n_states FROM gold.portfolio_summary",
    )
    latest = fetch_one(
        conn,
        "SELECT reporting_month, active_loans, d30_plus_rate_pct, d90_plus_rate_pct "
        "FROM gold.monthly_portfolio WHERE active_loans > 0 "
        "ORDER BY reporting_month DESC LIMIT 1",
    )
    stay_current = fetch_one(
        conn,
        "SELECT probability_pct FROM gold.transition_matrix "
        "WHERE from_state = 'current' AND to_state = 'current'",
    )
    top_states = fetch_all(
        conn,
        "SELECT property_state, n_loans, ever_d90_rate_pct FROM gold.state_risk "
        "WHERE n_loans >= 50 ORDER BY ever_d90_rate_pct DESC LIMIT 5",
    )
    return {
        "n_loans": summary[0],
        "total_orig_upb_billions": summary[1],
        "avg_credit_score": summary[2],
        "avg_ltv": summary[3],
        "avg_dti": summary[4],
        "avg_interest_rate": summary[5],
        "pct_ever_d30": summary[6],
        "pct_ever_d90": summary[7],
        "pct_prepaid": summary[8],
        "pct_credit_event": summary[9],
        "n_states": summary[10],
        "latest_month": latest[0],
        "latest_active_loans": latest[1],
        "latest_d30_rate_pct": latest[2],
        "latest_d90_rate_pct": latest[3],
        "stay_current_pct": stay_current[0],
        "top_risk_states": top_states,
    }


def write_summary(metrics: dict[str, object], out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "summary.md"
    m = metrics
    lines = [
        "# Portfolio summary",
        "",
        f"Loans: {m['n_loans']:,} | Original UPB: ${m['total_orig_upb_billions']}B "
        f"| States: {m['n_states']}",
        "",
        f"Averages: credit score {m['avg_credit_score']}, LTV {m['avg_ltv']}, "
        f"DTI {m['avg_dti']}, note rate {m['avg_interest_rate']}%",
        "",
        "## Lifetime outcomes",
        "",
        f"- Ever 30+ days delinquent: {m['pct_ever_d30']}% of loans",
        f"- Ever 90+ days delinquent: {m['pct_ever_d90']}% of loans",
        f"- Prepaid in full: {m['pct_prepaid']}%",
        f"- Terminated by credit event: {m['pct_credit_event']}%",
        "",
        "## Latest month",
        "",
        f"As of {m['latest_month']}: {m['latest_active_loans']:,} active loans, "
        f"{m['latest_d30_rate_pct']}% 30+ delinquent, "
        f"{m['latest_d90_rate_pct']}% 90+ delinquent.",
        "",
        f"A current loan stays current next month with probability "
        f"{m['stay_current_pct']}%.",
        "",
        "## Highest ever-D90 states (min 50 loans)",
        "",
    ]
    for state, n_loans, d90 in m["top_risk_states"]:
        lines.append(f"- {state}: {d90}% of {n_loans:,} loans")
    lines.append("")
    target.write_text("\n".join(lines), encoding="utf-8")
    log.info("Wrote %s", target)
    return target
