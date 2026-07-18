CREATE SCHEMA IF NOT EXISTS bronze;

DROP TABLE IF EXISTS bronze.origination_raw CASCADE;
CREATE TABLE bronze.origination_raw (
    credit_score                    TEXT,
    first_payment_date              TEXT,
    first_time_homebuyer_flag       TEXT,
    maturity_date                   TEXT,
    msa                             TEXT,
    mortgage_insurance_pct          TEXT,
    number_of_units                 TEXT,
    occupancy_status                TEXT,
    cltv                            TEXT,
    dti                             TEXT,
    original_upb                    TEXT,
    ltv                             TEXT,
    original_interest_rate          TEXT,
    channel                         TEXT,
    ppm_flag                        TEXT,
    amortization_type               TEXT,
    property_state                  TEXT,
    property_type                   TEXT,
    postal_code                     TEXT,
    loan_sequence_number            TEXT,
    loan_purpose                    TEXT,
    original_loan_term              TEXT,
    number_of_borrowers             TEXT,
    seller_name                     TEXT,
    servicer_name                   TEXT,
    super_conforming_flag           TEXT,
    pre_harp_loan_sequence_number   TEXT,
    program_indicator               TEXT,
    harp_indicator                  TEXT,
    property_valuation_method       TEXT,
    interest_only_indicator         TEXT,
    mi_cancellation_indicator       TEXT,
    source_file                     TEXT,
    loaded_at                       TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TABLE IF EXISTS bronze.performance_raw CASCADE;
CREATE TABLE bronze.performance_raw (
    loan_sequence_number            TEXT,
    monthly_reporting_period        TEXT,
    current_actual_upb              TEXT,
    current_loan_delinquency_status TEXT,
    loan_age                        TEXT,
    remaining_months_to_maturity    TEXT,
    defect_settlement_date          TEXT,
    modification_flag               TEXT,
    zero_balance_code               TEXT,
    zero_balance_effective_date     TEXT,
    current_interest_rate           TEXT,
    current_deferred_upb            TEXT,
    ddlpi                           TEXT,
    mi_recoveries                   TEXT,
    net_sales_proceeds              TEXT,
    non_mi_recoveries               TEXT,
    expenses                        TEXT,
    legal_costs                     TEXT,
    maintenance_costs               TEXT,
    taxes_and_insurance             TEXT,
    misc_expenses                   TEXT,
    actual_loss                     TEXT,
    modification_cost               TEXT,
    step_modification_flag          TEXT,
    deferred_payment_plan           TEXT,
    estimated_ltv                   TEXT,
    zero_balance_removal_upb        TEXT,
    delinquent_accrued_interest     TEXT,
    delinquency_due_to_disaster     TEXT,
    borrower_assistance_status      TEXT,
    current_month_modification_cost TEXT,
    interest_bearing_upb            TEXT,
    source_file                     TEXT,
    loaded_at                       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.load_rejects (
    reject_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file     TEXT NOT NULL,
    line_number     BIGINT NOT NULL,
    field_count     INTEGER,
    reason          TEXT NOT NULL,
    raw_line        TEXT,
    rejected_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.load_audit (
    audit_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file     TEXT NOT NULL,
    target_table    TEXT NOT NULL,
    rows_loaded     BIGINT NOT NULL,
    rows_rejected   BIGINT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ NOT NULL
);
