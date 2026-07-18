CREATE SCHEMA IF NOT EXISTS gold;

DROP TABLE IF EXISTS gold.loan_outcomes CASCADE;
CREATE TABLE gold.loan_outcomes AS
SELECT
    o.loan_sequence_number,
    o.vintage_quarter,
    o.credit_score,
    o.credit_score_band,
    o.ltv,
    o.ltv_band,
    o.dti,
    o.dti_band,
    o.property_state,
    o.loan_purpose,
    o.original_upb,
    o.original_interest_rate,
    p.n_months,
    p.last_reporting_month,
    p.max_delinquency_bucket,
    COALESCE(p.ever_d30, FALSE) AS ever_d30,
    COALESCE(p.ever_d60, FALSE) AS ever_d60,
    COALESCE(p.ever_d90, FALSE) AS ever_d90,
    p.first_d30_age,
    p.first_d90_age,
    p.termination_type,
    p.termination_age,
    p.actual_loss
FROM silver.origination o
LEFT JOIN (
    SELECT
        loan_sequence_number,
        COUNT(*)                                        AS n_months,
        MAX(reporting_month)                            AS last_reporting_month,
        MAX(delinquency_bucket)                         AS max_delinquency_bucket,
        BOOL_OR(is_d30_plus)                            AS ever_d30,
        BOOL_OR(is_d60_plus)                            AS ever_d60,
        BOOL_OR(is_d90_plus)                            AS ever_d90,
        MIN(loan_age) FILTER (WHERE is_d30_plus)        AS first_d30_age,
        MIN(loan_age) FILTER (WHERE is_d90_plus)        AS first_d90_age,
        MAX(termination_type)                           AS termination_type,
        MAX(loan_age) FILTER
            (WHERE termination_type IS NOT NULL)        AS termination_age,
        SUM(actual_loss)                                AS actual_loss
    FROM silver.performance
    GROUP BY loan_sequence_number
) p USING (loan_sequence_number);

ALTER TABLE gold.loan_outcomes ADD PRIMARY KEY (loan_sequence_number);

DROP TABLE IF EXISTS gold.portfolio_summary CASCADE;
CREATE TABLE gold.portfolio_summary AS
SELECT
    COUNT(*)                                                    AS n_loans,
    ROUND(SUM(original_upb) / 1e9, 3)                           AS total_orig_upb_billions,
    ROUND(AVG(original_upb), 0)                                 AS avg_orig_upb,
    ROUND(AVG(credit_score), 1)                                 AS avg_credit_score,
    ROUND(AVG(ltv), 1)                                          AS avg_ltv,
    ROUND(AVG(dti), 1)                                          AS avg_dti,
    ROUND(AVG(original_interest_rate), 3)                       AS avg_interest_rate,
    COUNT(DISTINCT property_state)                              AS n_states,
    ROUND(AVG((loan_purpose = 'P')::INT) * 100, 2)              AS pct_purchase,
    ROUND(AVG(ever_d30::INT) * 100, 3)                          AS pct_ever_d30,
    ROUND(AVG(ever_d90::INT) * 100, 3)                          AS pct_ever_d90,
    ROUND(AVG(CASE WHEN termination_type = 'prepaid'
              THEN 1 ELSE 0 END) * 100.0, 3)                    AS pct_prepaid,
    ROUND(AVG(CASE WHEN termination_type = 'credit_event'
              THEN 1 ELSE 0 END) * 100.0, 3)                    AS pct_credit_event
FROM gold.loan_outcomes;

DROP TABLE IF EXISTS gold.monthly_portfolio CASCADE;
CREATE TABLE gold.monthly_portfolio AS
WITH monthly AS (
    SELECT
        reporting_month,
        COUNT(*) FILTER (WHERE zero_balance_code IS NULL)       AS active_loans,
        SUM(current_actual_upb)
            FILTER (WHERE zero_balance_code IS NULL)            AS active_upb,
        COUNT(*) FILTER (WHERE is_d30_plus
                         AND zero_balance_code IS NULL)         AS d30_plus_loans,
        COUNT(*) FILTER (WHERE is_d60_plus
                         AND zero_balance_code IS NULL)         AS d60_plus_loans,
        COUNT(*) FILTER (WHERE is_d90_plus
                         AND zero_balance_code IS NULL)         AS d90_plus_loans,
        SUM(current_actual_upb) FILTER (WHERE is_d90_plus
                         AND zero_balance_code IS NULL)         AS d90_plus_upb,
        COUNT(*) FILTER (WHERE termination_type = 'prepaid')    AS prepaid_loans,
        COUNT(*) FILTER (WHERE termination_type = 'credit_event') AS credit_event_loans
    FROM silver.performance
    GROUP BY reporting_month
)
SELECT
    reporting_month,
    active_loans,
    ROUND(active_upb / 1e6, 2)                                  AS active_upb_millions,
    d30_plus_loans,
    d60_plus_loans,
    d90_plus_loans,
    prepaid_loans,
    credit_event_loans,
    ROUND(d30_plus_loans::NUMERIC / NULLIF(active_loans, 0) * 100, 3) AS d30_plus_rate_pct,
    ROUND(d60_plus_loans::NUMERIC / NULLIF(active_loans, 0) * 100, 3) AS d60_plus_rate_pct,
    ROUND(d90_plus_loans::NUMERIC / NULLIF(active_loans, 0) * 100, 3) AS d90_plus_rate_pct,
    ROUND(d90_plus_upb / NULLIF(active_upb, 0) * 100, 3)        AS d90_plus_upb_rate_pct,
    ROUND((1 - power(
        1 - prepaid_loans::NUMERIC
            / NULLIF(LAG(active_loans) OVER (ORDER BY reporting_month), 0),
        12)) * 100, 3)                                          AS cpr_pct
FROM monthly
ORDER BY reporting_month;

DROP TABLE IF EXISTS gold.vintage_delinquency CASCADE;
CREATE TABLE gold.vintage_delinquency AS
WITH vintage_size AS (
    SELECT vintage_quarter, COUNT(*) AS vintage_loans
    FROM gold.loan_outcomes
    GROUP BY vintage_quarter
),
ages AS (
    SELECT DISTINCT vintage_quarter, loan_age
    FROM silver.performance p
    JOIN silver.origination o USING (loan_sequence_number)
    WHERE loan_age >= 0
),
firsts AS (
    SELECT vintage_quarter, first_d90_age, COUNT(*) AS n_new_d90
    FROM gold.loan_outcomes
    WHERE first_d90_age IS NOT NULL
    GROUP BY vintage_quarter, first_d90_age
)
SELECT
    a.vintage_quarter,
    a.loan_age,
    v.vintage_loans,
    COALESCE(SUM(f.n_new_d90) OVER (
        PARTITION BY a.vintage_quarter
        ORDER BY a.loan_age
        ROWS UNBOUNDED PRECEDING), 0)                           AS cum_d90_loans,
    ROUND(COALESCE(SUM(f.n_new_d90) OVER (
        PARTITION BY a.vintage_quarter
        ORDER BY a.loan_age
        ROWS UNBOUNDED PRECEDING), 0)::NUMERIC
        / v.vintage_loans * 100, 4)                             AS cum_d90_rate_pct
FROM ages a
JOIN vintage_size v USING (vintage_quarter)
LEFT JOIN firsts f
       ON f.vintage_quarter = a.vintage_quarter
      AND f.first_d90_age = a.loan_age
ORDER BY a.vintage_quarter, a.loan_age;

DROP TABLE IF EXISTS gold.transition_matrix CASCADE;
CREATE TABLE gold.transition_matrix AS
WITH states AS (
    SELECT
        loan_sequence_number,
        reporting_month,
        CASE
            WHEN termination_type = 'prepaid'      THEN 'prepaid'
            WHEN termination_type = 'credit_event' THEN 'credit_event'
            WHEN termination_type IS NOT NULL      THEN 'removed'
            WHEN is_reo                            THEN 'd90_plus'
            WHEN delinquency_bucket >= 3           THEN 'd90_plus'
            WHEN delinquency_bucket = 2            THEN 'd60'
            WHEN delinquency_bucket = 1            THEN 'd30'
            ELSE 'current'
        END AS state
    FROM silver.performance
),
pairs AS (
    SELECT
        state AS to_state,
        LAG(state) OVER (
            PARTITION BY loan_sequence_number ORDER BY reporting_month
        ) AS from_state,
        reporting_month,
        LAG(reporting_month) OVER (
            PARTITION BY loan_sequence_number ORDER BY reporting_month
        ) AS prev_month
    FROM states
)
SELECT
    from_state,
    to_state,
    COUNT(*) AS n_transitions,
    ROUND(COUNT(*)::NUMERIC
        / SUM(COUNT(*)) OVER (PARTITION BY from_state) * 100, 4) AS probability_pct
FROM pairs
WHERE from_state IS NOT NULL
  AND from_state NOT IN ('prepaid', 'credit_event', 'removed')
  AND reporting_month = prev_month + INTERVAL '1 month'
GROUP BY from_state, to_state
ORDER BY from_state, to_state;

DROP TABLE IF EXISTS gold.state_risk CASCADE;
CREATE TABLE gold.state_risk AS
SELECT
    property_state,
    COUNT(*)                                                    AS n_loans,
    ROUND(COUNT(*)::NUMERIC
        / SUM(COUNT(*)) OVER () * 100, 2)                       AS pct_of_portfolio,
    ROUND(SUM(original_upb) / 1e6, 1)                           AS orig_upb_millions,
    ROUND(AVG(credit_score), 0)                                 AS avg_credit_score,
    ROUND(AVG(ltv), 1)                                          AS avg_ltv,
    ROUND(AVG(dti), 1)                                          AS avg_dti,
    ROUND(AVG(original_interest_rate), 3)                       AS avg_interest_rate,
    ROUND(AVG(ever_d30::INT) * 100, 3)                          AS ever_d30_rate_pct,
    ROUND(AVG(ever_d90::INT) * 100, 3)                          AS ever_d90_rate_pct,
    ROUND(AVG(CASE WHEN termination_type = 'prepaid'
              THEN 1 ELSE 0 END) * 100.0, 3)                    AS prepaid_rate_pct
FROM gold.loan_outcomes
GROUP BY property_state
ORDER BY n_loans DESC;

DROP TABLE IF EXISTS gold.segment_risk CASCADE;
CREATE TABLE gold.segment_risk AS
SELECT
    credit_score_band,
    ltv_band,
    COUNT(*)                                                    AS n_loans,
    ROUND(AVG(original_interest_rate), 3)                       AS avg_interest_rate,
    ROUND(AVG(dti), 1)                                          AS avg_dti,
    ROUND(AVG(ever_d30::INT) * 100, 3)                          AS ever_d30_rate_pct,
    ROUND(AVG(ever_d60::INT) * 100, 3)                          AS ever_d60_rate_pct,
    ROUND(AVG(ever_d90::INT) * 100, 3)                          AS ever_d90_rate_pct
FROM gold.loan_outcomes
WHERE credit_score_band IS NOT NULL AND ltv_band IS NOT NULL
GROUP BY credit_score_band, ltv_band
ORDER BY credit_score_band, ltv_band;
