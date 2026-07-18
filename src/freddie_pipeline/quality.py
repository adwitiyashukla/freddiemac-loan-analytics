from __future__ import annotations

import psycopg

from .db import fetch_one, table_count
from .utils import PipelineError, get_logger

log = get_logger(__name__)


def run_quality_checks(conn: psycopg.Connection) -> dict[str, int]:
    counts = {
        "bronze_origination": table_count(conn, "bronze.origination_raw"),
        "bronze_performance": table_count(conn, "bronze.performance_raw"),
        "silver_origination": table_count(conn, "silver.origination"),
        "silver_performance": table_count(conn, "silver.performance"),
        "rejects": table_count(conn, "bronze.load_rejects"),
    }
    for name, value in counts.items():
        log.info("Row count %-22s %s", name, f"{value:,}")

    if counts["silver_origination"] == 0:
        raise PipelineError("silver.origination is empty: nothing was transformed")
    if counts["silver_performance"] == 0:
        raise PipelineError("silver.performance is empty: nothing was transformed")

    orphans = int(
        fetch_one(
            conn,
            "SELECT COUNT(DISTINCT p.loan_sequence_number) FROM silver.performance p "
            "LEFT JOIN silver.origination o USING (loan_sequence_number) "
            "WHERE o.loan_sequence_number IS NULL",
        )[0]
    )
    if orphans:
        log.warning(
            "%s loans appear in performance but not in origination "
            "(kept in silver, excluded from origination joins)", f"{orphans:,}",
        )

    bad_rates = int(
        fetch_one(
            conn,
            "SELECT COUNT(*) FROM gold.monthly_portfolio "
            "WHERE d30_plus_rate_pct NOT BETWEEN 0 AND 100 "
            "   OR d60_plus_rate_pct NOT BETWEEN 0 AND 100 "
            "   OR d90_plus_rate_pct NOT BETWEEN 0 AND 100",
        )[0]
    )
    if bad_rates:
        raise PipelineError(f"gold.monthly_portfolio has {bad_rates} rows with rates outside 0-100")

    non_monotonic = int(
        fetch_one(
            conn,
            "SELECT COUNT(*) FROM ("
            "  SELECT cum_d90_rate_pct - LAG(cum_d90_rate_pct) OVER ("
            "      PARTITION BY vintage_quarter ORDER BY loan_age) AS step "
            "  FROM gold.vintage_delinquency) s "
            "WHERE step < 0",
        )[0]
    )
    if non_monotonic:
        raise PipelineError(
            f"gold.vintage_delinquency has {non_monotonic} non monotonic steps"
        )

    bad_matrix_rows = int(
        fetch_one(
            conn,
            "SELECT COUNT(*) FROM ("
            "  SELECT from_state, SUM(probability_pct) AS total "
            "  FROM gold.transition_matrix GROUP BY from_state) s "
            "WHERE total NOT BETWEEN 99.5 AND 100.5",
        )[0]
    )
    if bad_matrix_rows:
        raise PipelineError(
            f"gold.transition_matrix has {bad_matrix_rows} from_states not summing to 100"
        )

    log.info("All data quality checks passed")
    return counts
