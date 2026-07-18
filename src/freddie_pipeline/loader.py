from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import psycopg

from .utils import PipelineError, get_logger

log = get_logger(__name__)

FIELD_COUNT = 32
COPY_BATCH_LINES = 50_000
MAX_REJECT_SAMPLE_CHARS = 500

ORIGINATION_COLUMNS = [
    "credit_score",
    "first_payment_date",
    "first_time_homebuyer_flag",
    "maturity_date",
    "msa",
    "mortgage_insurance_pct",
    "number_of_units",
    "occupancy_status",
    "cltv",
    "dti",
    "original_upb",
    "ltv",
    "original_interest_rate",
    "channel",
    "ppm_flag",
    "amortization_type",
    "property_state",
    "property_type",
    "postal_code",
    "loan_sequence_number",
    "loan_purpose",
    "original_loan_term",
    "number_of_borrowers",
    "seller_name",
    "servicer_name",
    "super_conforming_flag",
    "pre_harp_loan_sequence_number",
    "program_indicator",
    "harp_indicator",
    "property_valuation_method",
    "interest_only_indicator",
    "mi_cancellation_indicator",
]

PERFORMANCE_COLUMNS = [
    "loan_sequence_number",
    "monthly_reporting_period",
    "current_actual_upb",
    "current_loan_delinquency_status",
    "loan_age",
    "remaining_months_to_maturity",
    "defect_settlement_date",
    "modification_flag",
    "zero_balance_code",
    "zero_balance_effective_date",
    "current_interest_rate",
    "current_deferred_upb",
    "ddlpi",
    "mi_recoveries",
    "net_sales_proceeds",
    "non_mi_recoveries",
    "expenses",
    "legal_costs",
    "maintenance_costs",
    "taxes_and_insurance",
    "misc_expenses",
    "actual_loss",
    "modification_cost",
    "step_modification_flag",
    "deferred_payment_plan",
    "estimated_ltv",
    "zero_balance_removal_upb",
    "delinquent_accrued_interest",
    "delinquency_due_to_disaster",
    "borrower_assistance_status",
    "current_month_modification_cost",
    "interest_bearing_upb",
]

TARGETS = {
    "origination": ("bronze.origination_raw", ORIGINATION_COLUMNS),
    "performance": ("bronze.performance_raw", PERFORMANCE_COLUMNS),
}


@dataclass
class LoadResult:
    source_file: str
    target_table: str
    rows_loaded: int
    rows_rejected: int
    seconds: float


def escape_copy_text(field: str) -> str:
    return field.replace("\\", "\\\\") if "\\" in field else field


def _validated_lines(path: Path, source_name: str, rejects: list[tuple]):
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        for line_number, raw in enumerate(fh, start=1):
            line = raw.rstrip("\r\n")
            if not line:
                continue
            fields = line.split("|")
            if len(fields) != FIELD_COUNT:
                rejects.append(
                    (
                        source_name,
                        line_number,
                        len(fields),
                        f"expected {FIELD_COUNT} fields, got {len(fields)}",
                        line[:MAX_REJECT_SAMPLE_CHARS],
                    )
                )
                continue
            fields.append(source_name)
            yield "|".join(escape_copy_text(f) for f in fields)


def load_file(
    conn: psycopg.Connection, kind: str, path: Path, truncate: bool = False
) -> LoadResult:
    if kind not in TARGETS:
        raise PipelineError(f"Unknown load kind {kind!r}, expected one of {sorted(TARGETS)}")
    path = Path(path)
    if not path.is_file():
        raise PipelineError(f"Input file not found: {path}")
    if path.stat().st_size == 0:
        raise PipelineError(f"Input file is empty: {path}")

    table, columns = TARGETS[kind]
    source_name = path.name
    started = time.time()
    rejects: list[tuple] = []
    rows_loaded = 0

    copy_sql = (
        f"COPY {table} ({', '.join(columns)}, source_file) "
        f"FROM STDIN (FORMAT text, DELIMITER '|', NULL '')"
    )

    with conn.cursor() as cur:
        if truncate:
            log.info("Truncating %s before load", table)
            cur.execute(f"TRUNCATE {table}")
        batch: list[str] = []
        with cur.copy(copy_sql) as copy:
            for prepared in _validated_lines(path, source_name, rejects):
                batch.append(prepared)
                rows_loaded += 1
                if len(batch) >= COPY_BATCH_LINES:
                    copy.write("\n".join(batch) + "\n")
                    batch.clear()
            if batch:
                copy.write("\n".join(batch) + "\n")

        if rejects:
            cur.executemany(
                "INSERT INTO bronze.load_rejects "
                "(source_file, line_number, field_count, reason, raw_line) "
                "VALUES (%s, %s, %s, %s, %s)",
                rejects,
            )
        cur.execute(
            "INSERT INTO bronze.load_audit "
            "(source_file, target_table, rows_loaded, rows_rejected, started_at, finished_at) "
            "VALUES (%s, %s, %s, %s, to_timestamp(%s), now())",
            (source_name, table, rows_loaded, len(rejects), started),
        )
    conn.commit()

    seconds = time.time() - started
    result = LoadResult(source_name, table, rows_loaded, len(rejects), seconds)
    log.info(
        "Loaded %s rows from %s into %s in %.1fs (%s rejected)",
        f"{rows_loaded:,}", source_name, table, seconds, len(rejects),
    )
    if rows_loaded == 0:
        raise PipelineError(
            f"No valid rows found in {path}: all {len(rejects)} lines failed validation"
        )
    return result
