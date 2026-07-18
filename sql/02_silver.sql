CREATE SCHEMA IF NOT EXISTS silver;

DROP TABLE IF EXISTS silver.origination CASCADE;
CREATE TABLE silver.origination AS
WITH deduped AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY loan_sequence_number
               ORDER BY loaded_at, source_file
           ) AS rn
    FROM bronze.origination_raw
    WHERE loan_sequence_number IS NOT NULL
)
SELECT
    loan_sequence_number,
    NULLIF(credit_score, '9999')::INTEGER                    AS credit_score,
    to_date(first_payment_date, 'YYYYMM')                    AS first_payment_date,
    CASE WHEN first_time_homebuyer_flag IN ('Y', 'N')
         THEN first_time_homebuyer_flag END                  AS first_time_homebuyer_flag,
    to_date(maturity_date, 'YYYYMM')                         AS maturity_date,
    msa::INTEGER                                             AS msa,
    NULLIF(mortgage_insurance_pct, '999')::INTEGER           AS mortgage_insurance_pct,
    NULLIF(number_of_units, '99')::INTEGER                   AS number_of_units,
    NULLIF(occupancy_status, '9')                            AS occupancy_status,
    NULLIF(cltv, '999')::INTEGER                             AS cltv,
    NULLIF(dti, '999')::INTEGER                              AS dti,
    original_upb::NUMERIC(12, 2)                             AS original_upb,
    NULLIF(ltv, '999')::INTEGER                              AS ltv,
    original_interest_rate::NUMERIC(8, 3)                    AS original_interest_rate,
    NULLIF(channel, '9')                                     AS channel,
    ppm_flag,
    amortization_type,
    property_state,
    NULLIF(property_type, '99')                              AS property_type,
    postal_code,
    NULLIF(loan_purpose, '9')                                AS loan_purpose,
    original_loan_term::INTEGER                              AS original_loan_term,
    NULLIF(number_of_borrowers, '99')::INTEGER               AS number_of_borrowers,
    seller_name,
    servicer_name,
    COALESCE(super_conforming_flag, 'N')                     AS super_conforming_flag,
    NULLIF(property_valuation_method, '9')                   AS property_valuation_method,
    interest_only_indicator,
    mi_cancellation_indicator,
    '20' || substr(loan_sequence_number, 2, 4)               AS vintage_quarter,
    CASE
        WHEN credit_score = '9999' OR credit_score IS NULL THEN NULL
        WHEN credit_score::INTEGER < 660 THEN '01 under 660'
        WHEN credit_score::INTEGER < 700 THEN '02 660-699'
        WHEN credit_score::INTEGER < 740 THEN '03 700-739'
        WHEN credit_score::INTEGER < 780 THEN '04 740-779'
        ELSE '05 780 plus'
    END                                                      AS credit_score_band,
    CASE
        WHEN ltv = '999' OR ltv IS NULL THEN NULL
        WHEN ltv::INTEGER <= 60 THEN '01 up to 60'
        WHEN ltv::INTEGER <= 70 THEN '02 60-70'
        WHEN ltv::INTEGER <= 80 THEN '03 70-80'
        WHEN ltv::INTEGER <= 90 THEN '04 80-90'
        WHEN ltv::INTEGER <= 95 THEN '05 90-95'
        ELSE '06 over 95'
    END                                                      AS ltv_band,
    CASE
        WHEN dti = '999' OR dti IS NULL THEN NULL
        WHEN dti::INTEGER <= 25 THEN '01 up to 25'
        WHEN dti::INTEGER <= 35 THEN '02 25-35'
        WHEN dti::INTEGER <= 43 THEN '03 35-43'
        ELSE '04 over 43'
    END                                                      AS dti_band
FROM deduped
WHERE rn = 1;

ALTER TABLE silver.origination ADD PRIMARY KEY (loan_sequence_number);

DROP TABLE IF EXISTS silver.performance CASCADE;
CREATE TABLE silver.performance AS
WITH deduped AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY loan_sequence_number, monthly_reporting_period
               ORDER BY loaded_at, source_file
           ) AS rn
    FROM bronze.performance_raw
    WHERE loan_sequence_number IS NOT NULL
      AND monthly_reporting_period ~ '^[0-9]{6}$'
)
SELECT
    loan_sequence_number,
    to_date(monthly_reporting_period, 'YYYYMM')              AS reporting_month,
    current_actual_upb::NUMERIC(14, 2)                       AS current_actual_upb,
    current_loan_delinquency_status                          AS delinquency_status,
    CASE WHEN current_loan_delinquency_status ~ '^[0-9]+$'
         THEN current_loan_delinquency_status::INTEGER END   AS delinquency_bucket,
    (current_loan_delinquency_status = 'RA')                 AS is_reo,
    loan_age::INTEGER                                        AS loan_age,
    remaining_months_to_maturity::INTEGER                    AS remaining_months_to_maturity,
    to_date(defect_settlement_date, 'YYYYMM')                AS defect_settlement_date,
    modification_flag,
    zero_balance_code,
    CASE
        WHEN zero_balance_code = '01' THEN 'prepaid'
        WHEN zero_balance_code IN ('02', '03', '09') THEN 'credit_event'
        WHEN zero_balance_code IN ('15', '16', '96') THEN 'removal'
        WHEN zero_balance_code IS NOT NULL THEN 'other'
    END                                                      AS termination_type,
    to_date(zero_balance_effective_date, 'YYYYMM')           AS zero_balance_date,
    current_interest_rate::NUMERIC(8, 3)                     AS current_interest_rate,
    current_deferred_upb::NUMERIC(14, 2)                     AS current_deferred_upb,
    to_date(ddlpi, 'YYYYMM')                                 AS ddlpi,
    mi_recoveries::NUMERIC(14, 2)                            AS mi_recoveries,
    CASE WHEN net_sales_proceeds ~ '^-?[0-9]+(\.[0-9]+)?$'
         THEN net_sales_proceeds::NUMERIC(14, 2) END         AS net_sales_proceeds,
    non_mi_recoveries::NUMERIC(14, 2)                        AS non_mi_recoveries,
    expenses::NUMERIC(14, 2)                                 AS expenses,
    legal_costs::NUMERIC(14, 2)                              AS legal_costs,
    maintenance_costs::NUMERIC(14, 2)                        AS maintenance_costs,
    taxes_and_insurance::NUMERIC(14, 2)                      AS taxes_and_insurance,
    misc_expenses::NUMERIC(14, 2)                            AS misc_expenses,
    actual_loss::NUMERIC(14, 2)                              AS actual_loss,
    modification_cost::NUMERIC(14, 2)                        AS modification_cost,
    step_modification_flag,
    deferred_payment_plan,
    NULLIF(estimated_ltv, '999')::INTEGER                    AS estimated_ltv,
    zero_balance_removal_upb::NUMERIC(14, 2)                 AS zero_balance_removal_upb,
    delinquent_accrued_interest::NUMERIC(14, 2)              AS delinquent_accrued_interest,
    delinquency_due_to_disaster,
    borrower_assistance_status,
    current_month_modification_cost::NUMERIC(14, 2)          AS current_month_modification_cost,
    interest_bearing_upb::NUMERIC(14, 2)                     AS interest_bearing_upb,
    (current_loan_delinquency_status = 'RA'
     OR (current_loan_delinquency_status ~ '^[0-9]+$'
         AND current_loan_delinquency_status::INTEGER >= 1)) AS is_d30_plus,
    (current_loan_delinquency_status = 'RA'
     OR (current_loan_delinquency_status ~ '^[0-9]+$'
         AND current_loan_delinquency_status::INTEGER >= 2)) AS is_d60_plus,
    (current_loan_delinquency_status = 'RA'
     OR (current_loan_delinquency_status ~ '^[0-9]+$'
         AND current_loan_delinquency_status::INTEGER >= 3)) AS is_d90_plus
FROM deduped
WHERE rn = 1;

ALTER TABLE silver.performance ADD PRIMARY KEY (loan_sequence_number, reporting_month);
CREATE INDEX idx_silver_perf_month ON silver.performance (reporting_month);
CREATE INDEX idx_silver_perf_zb ON silver.performance (zero_balance_code)
    WHERE zero_balance_code IS NOT NULL;
