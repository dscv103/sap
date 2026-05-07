/*
================================================================================
  PAYMENT COMPRESSION & CURE RATE DASHBOARD — SQL QUERIES
  Source table : [OFS].[MONTHLY].[STG_CREDIT_CARD]
  Server       : SQL Server 2016 (v13 RTM)  — no named WINDOW clause,
                 LAG/LEAD/ROW_NUMBER/SUM OVER available.
  Access       : READ ONLY

  QUERY INDEX
  ──────────────────────────────────────────────────────────────────────────────
  Q1  Portfolio Monthly Payment Rate (MPR) trend
  Q2  Minimum Payment Rate (MMPR) — share of accounts paying only the minimum
  Q3  Payment Compression Ratio (PCR) — account-level payment / minimum due
  Q4  Payment Compression Cohorts — distribution buckets for Power BI histogram
  Q5  Total Payment Ratio (TPR) by behaviour score band
  Q6  Roll-rate matrix — monthly transition between DPD states
  Q7  Cure rate — 30/60/90 DPD accounts returning to current, 1-cycle look-ahead
  Q8  Vintage cure curves — cumulative cure % by months-since-first-delinquency
  Q9  Delinquency bucket balance waterfall
  Q10 Net charge-off rate (NCO) by month and product
  Q11 Recovery rate by month
  Q12 Payment stress segmentation — high-risk account flags
  Q13 Provision vs expected loss comparison
  Q14 Credit utilisation distribution
  ================================================================================
*/

/* ─────────────────────────────────────────────────────────────────────────────
   Q1  PORTFOLIO MONTHLY PAYMENT RATE (MPR)
       MPR = Total payments collected / Beginning-of-period balance
       Proxy: sum(CYC_PMT_AMT) / sum(ACCT_CYC_BALANCE)
       Excludes zero-balance accounts.
       Power BI use: KPI card + line chart over time
   ───────────────────────────────────────────────────────────────────────────── */
SELECT
    FIC_MIS_DATE                                              AS report_date,
    PROD_CODE                                                 AS product,
    COUNT(DISTINCT ACCOUNT_NUMBER)                            AS total_accounts,
    SUM(CASE WHEN EOP_BAL > 0 THEN 1 ELSE 0 END)             AS accounts_with_balance,
    SUM(CYC_PMT_AMT)                                          AS total_payments,
    SUM(ACCT_CYC_BALANCE)                                     AS total_beginning_balance,
    SUM(EOP_BAL)                                              AS total_eop_balance,
    -- MPR: payments as % of beginning balance
    CASE
        WHEN SUM(ACCT_CYC_BALANCE) > 0
        THEN CAST(SUM(CYC_PMT_AMT) AS FLOAT) / SUM(ACCT_CYC_BALANCE) * 100
        ELSE NULL
    END                                                       AS mpr_pct,
    -- Excess payment beyond minimum
    SUM(CASE WHEN CYC_PMT_AMT > ACCT_CYC_MIN_DUE_BAL
             THEN CYC_PMT_AMT - ACCT_CYC_MIN_DUE_BAL
             ELSE 0 END)                                      AS aggregate_excess_payment,
    -- Aggregate min due
    SUM(ACCT_CYC_MIN_DUE_BAL)                                AS total_min_due
FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
WHERE ACCT_CYC_BALANCE > 0          -- revolving accounts only
  AND CYC_CARD_STATUS NOT IN ('C','W','X')  -- exclude closed/written-off
GROUP BY
    FIC_MIS_DATE,
    PROD_CODE
ORDER BY
    FIC_MIS_DATE,
    PROD_CODE;


/* ─────────────────────────────────────────────────────────────────────────────
   Q2  MINIMUM PAYMENT RATE (MMPR)
       Share of active accounts making ONLY the minimum payment (±2% tolerance).
       Core leading indicator — compare to the Philadelphia Fed 10.75% (Q3 2024).
       Power BI use: KPI card vs benchmark, line chart trend
   ───────────────────────────────────────────────────────────────────────────── */
SELECT
    FIC_MIS_DATE                                              AS report_date,
    PROD_CODE                                                 AS product,
    COUNT(DISTINCT ACCOUNT_NUMBER)                            AS active_accounts,
    -- Accounts paying exactly (within 2%) the minimum
    SUM(CASE
            WHEN ACCT_CYC_MIN_DUE_BAL > 0
             AND CYC_PMT_AMT > 0
             AND CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 1.02
            THEN 1 ELSE 0
        END)                                                  AS min_pmt_accounts,
    -- Accounts paying zero (missed)
    SUM(CASE WHEN CYC_PMT_AMT = 0 AND ACCT_CYC_MIN_DUE_BAL > 0
             THEN 1 ELSE 0 END)                               AS zero_pmt_accounts,
    -- Accounts paying between min and full balance
    SUM(CASE
            WHEN CYC_PMT_AMT > ACCT_CYC_MIN_DUE_BAL * 1.02
             AND CYC_PMT_AMT < EOP_PRIN_BAL
            THEN 1 ELSE 0
        END)                                                  AS partial_excess_accounts,
    -- Full pay accounts (transactors)
    SUM(CASE WHEN CYC_PMT_AMT >= EOP_PRIN_BAL AND EOP_PRIN_BAL > 0
             THEN 1 ELSE 0 END)                               AS full_pay_accounts,
    -- MMPR as percentage
    CASE
        WHEN COUNT(DISTINCT ACCOUNT_NUMBER) > 0
        THEN CAST(SUM(CASE
                          WHEN ACCT_CYC_MIN_DUE_BAL > 0
                           AND CYC_PMT_AMT > 0
                           AND CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 1.02
                          THEN 1 ELSE 0
                      END) AS FLOAT)
             / COUNT(DISTINCT ACCOUNT_NUMBER) * 100
        ELSE NULL
    END                                                       AS mmpr_pct
FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
WHERE CYC_CARD_STATUS NOT IN ('C','W','X')
  AND ACCT_CYC_MIN_DUE_BAL > 0        -- only billing accounts
GROUP BY
    FIC_MIS_DATE,
    PROD_CODE
ORDER BY
    FIC_MIS_DATE,
    PROD_CODE;


/* ─────────────────────────────────────────────────────────────────────────────
   Q3  PAYMENT COMPRESSION RATIO (PCR) — ACCOUNT LEVEL
       PCR = CYC_PMT_AMT / ACCT_CYC_MIN_DUE_BAL
       1.00 = paying exactly minimum  (compressed)
       > 1.0 = paying above minimum
       Includes 3-month rolling average using LAG for trend detection.
       Power BI use: scatter plot, individual account drill-through
   ───────────────────────────────────────────────────────────────────────────── */
WITH base AS (
    SELECT
        FIC_MIS_DATE,
        ACCOUNT_NUMBER,
        PROD_CODE,
        BEHAVIOUR_SCORE,
        ACCT_DELQ_DAYS,
        EOP_BAL,
        ACCT_CYC_BALANCE,
        CYC_PMT_AMT,
        ACCT_CYC_MIN_DUE_BAL,
        EOP_PMT_AMT,
        CURRENT_CREDIT_LIMIT,
        -- Payment Compression Ratio
        CASE
            WHEN ACCT_CYC_MIN_DUE_BAL > 0
            THEN CAST(CYC_PMT_AMT AS FLOAT) / ACCT_CYC_MIN_DUE_BAL
            ELSE NULL
        END                              AS pcr,
        -- Utilisation
        CASE
            WHEN CURRENT_CREDIT_LIMIT > 0
            THEN CAST(EOP_BAL AS FLOAT) / CURRENT_CREDIT_LIMIT * 100
            ELSE NULL
        END                              AS utilisation_pct,
        -- Excess payment dollars
        CASE
            WHEN CYC_PMT_AMT > ACCT_CYC_MIN_DUE_BAL
            THEN CYC_PMT_AMT - ACCT_CYC_MIN_DUE_BAL
            ELSE 0
        END                              AS excess_payment_amt,
        -- Flag: compressed (PCR between 0.98 and 1.05)
        CASE
            WHEN ACCT_CYC_MIN_DUE_BAL > 0
             AND CYC_PMT_AMT BETWEEN ACCT_CYC_MIN_DUE_BAL * 0.98
                                 AND ACCT_CYC_MIN_DUE_BAL * 1.05
            THEN 1 ELSE 0
        END                              AS is_compressed
    FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
    WHERE CYC_CARD_STATUS NOT IN ('C','W','X')
      AND ACCT_CYC_MIN_DUE_BAL > 0
),
with_lag AS (
    SELECT
        *,
        LAG(pcr, 1) OVER (PARTITION BY ACCOUNT_NUMBER ORDER BY FIC_MIS_DATE) AS pcr_lag1,
        LAG(pcr, 2) OVER (PARTITION BY ACCOUNT_NUMBER ORDER BY FIC_MIS_DATE) AS pcr_lag2,
        LAG(is_compressed, 1) OVER (PARTITION BY ACCOUNT_NUMBER ORDER BY FIC_MIS_DATE) AS was_compressed_last,
        LAG(is_compressed, 2) OVER (PARTITION BY ACCOUNT_NUMBER ORDER BY FIC_MIS_DATE) AS was_compressed_2ago
    FROM base
)
SELECT
    FIC_MIS_DATE                                              AS report_date,
    ACCOUNT_NUMBER,
    PROD_CODE,
    BEHAVIOUR_SCORE,
    ACCT_DELQ_DAYS,
    EOP_BAL,
    CURRENT_CREDIT_LIMIT,
    utilisation_pct,
    CYC_PMT_AMT,
    ACCT_CYC_MIN_DUE_BAL,
    excess_payment_amt,
    pcr,
    pcr_lag1,
    pcr_lag2,
    -- 3-month rolling average PCR
    CASE
        WHEN pcr IS NOT NULL AND pcr_lag1 IS NOT NULL AND pcr_lag2 IS NOT NULL
        THEN (pcr + pcr_lag1 + pcr_lag2) / 3.0
        ELSE NULL
    END                                                       AS pcr_3m_avg,
    is_compressed,
    -- Consecutive compression flag: 2+ months compressed = high risk
    CASE
        WHEN is_compressed = 1
         AND was_compressed_last = 1
        THEN 1 ELSE 0
    END                                                       AS compressed_2m_flag,
    -- Three consecutive months compressed = critical
    CASE
        WHEN is_compressed = 1
         AND was_compressed_last = 1
         AND was_compressed_2ago = 1
        THEN 1 ELSE 0
    END                                                       AS compressed_3m_flag
FROM with_lag
ORDER BY
    FIC_MIS_DATE,
    ACCOUNT_NUMBER;


/* ─────────────────────────────────────────────────────────────────────────────
   Q4  PAYMENT COMPRESSION COHORT DISTRIBUTION
       Buckets accounts by PCR for histogram visualisation.
       Power BI use: clustered bar chart, slice by month / product / score band
   ───────────────────────────────────────────────────────────────────────────── */
SELECT
    FIC_MIS_DATE                                              AS report_date,
    PROD_CODE                                                 AS product,
    -- Score band (behaviour score quintiles — adjust thresholds to your data)
    CASE
        WHEN BEHAVIOUR_SCORE <  500 THEN '1-Sub600'
        WHEN BEHAVIOUR_SCORE <  620 THEN '2-600-620'
        WHEN BEHAVIOUR_SCORE <  680 THEN '3-620-680'
        WHEN BEHAVIOUR_SCORE <  720 THEN '4-680-720'
        ELSE                             '5-720+'
    END                                                       AS score_band,
    -- PCR bucket
    CASE
        WHEN ACCT_CYC_MIN_DUE_BAL <= 0                                    THEN '0-NoMinDue'
        WHEN CYC_PMT_AMT = 0                                               THEN '1-ZeroPay'
        WHEN CYC_PMT_AMT < ACCT_CYC_MIN_DUE_BAL * 0.50                   THEN '2-Below50pct'
        WHEN CYC_PMT_AMT < ACCT_CYC_MIN_DUE_BAL * 0.98                   THEN '3-50-98pct'
        WHEN CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 1.05                  THEN '4-AtMin(98-105)'
        WHEN CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 1.50                  THEN '5-105-150pct'
        WHEN CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 3.00                  THEN '6-150-300pct'
        WHEN CYC_PMT_AMT < EOP_PRIN_BAL                                    THEN '7-Above300pct'
        ELSE                                                                    '8-FullPay'
    END                                                       AS pcr_bucket,
    COUNT(DISTINCT ACCOUNT_NUMBER)                            AS account_count,
    SUM(EOP_BAL)                                              AS balance_in_bucket,
    AVG(CAST(ACCT_DELQ_DAYS AS FLOAT))                        AS avg_delq_days,
    AVG(CAST(BEHAVIOUR_SCORE AS FLOAT))                       AS avg_behaviour_score
FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
WHERE CYC_CARD_STATUS NOT IN ('C','W','X')
GROUP BY
    FIC_MIS_DATE,
    PROD_CODE,
    CASE
        WHEN BEHAVIOUR_SCORE <  500 THEN '1-Sub600'
        WHEN BEHAVIOUR_SCORE <  620 THEN '2-600-620'
        WHEN BEHAVIOUR_SCORE <  680 THEN '3-620-680'
        WHEN BEHAVIOUR_SCORE <  720 THEN '4-680-720'
        ELSE                             '5-720+'
    END,
    CASE
        WHEN ACCT_CYC_MIN_DUE_BAL <= 0                                    THEN '0-NoMinDue'
        WHEN CYC_PMT_AMT = 0                                               THEN '1-ZeroPay'
        WHEN CYC_PMT_AMT < ACCT_CYC_MIN_DUE_BAL * 0.50                   THEN '2-Below50pct'
        WHEN CYC_PMT_AMT < ACCT_CYC_MIN_DUE_BAL * 0.98                   THEN '3-50-98pct'
        WHEN CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 1.05                  THEN '4-AtMin(98-105)'
        WHEN CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 1.50                  THEN '5-105-150pct'
        WHEN CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 3.00                  THEN '6-150-300pct'
        WHEN CYC_PMT_AMT < EOP_PRIN_BAL                                    THEN '7-Above300pct'
        ELSE                                                                    '8-FullPay'
    END
ORDER BY
    FIC_MIS_DATE,
    pcr_bucket,
    score_band;


/* ─────────────────────────────────────────────────────────────────────────────
   Q5  TOTAL PAYMENT RATIO (TPR) BY BEHAVIOUR SCORE BAND
       Mirrors TransUnion's 2013 study metric.
       TPR = Total payments / Total minimum due per score band
       Power BI use: grouped bar, with forward delinquency rate overlay
   ───────────────────────────────────────────────────────────────────────────── */
SELECT
    FIC_MIS_DATE                                              AS report_date,
    PROD_CODE                                                 AS product,
    CASE
        WHEN BEHAVIOUR_SCORE <  500 THEN '1-Sub500'
        WHEN BEHAVIOUR_SCORE <  580 THEN '2-500-580'
        WHEN BEHAVIOUR_SCORE <  650 THEN '3-580-650'
        WHEN BEHAVIOUR_SCORE <  720 THEN '4-650-720'
        ELSE                             '5-720+'
    END                                                       AS score_band,
    COUNT(DISTINCT ACCOUNT_NUMBER)                            AS accounts,
    SUM(CYC_PMT_AMT)                                          AS total_payments,
    SUM(ACCT_CYC_MIN_DUE_BAL)                                AS total_min_due,
    SUM(CYC_PMT_AMT - ACCT_CYC_MIN_DUE_BAL)                  AS aggregate_excess_payment,
    -- TPR
    CASE
        WHEN SUM(ACCT_CYC_MIN_DUE_BAL) > 0
        THEN CAST(SUM(CYC_PMT_AMT) AS FLOAT) / SUM(ACCT_CYC_MIN_DUE_BAL)
        ELSE NULL
    END                                                       AS tpr,
    -- Current delinquency rate within band
    CAST(SUM(CASE WHEN ACCT_DELQ_DAYS > 0 THEN 1 ELSE 0 END) AS FLOAT)
        / NULLIF(COUNT(DISTINCT ACCOUNT_NUMBER), 0) * 100    AS current_delq_rate_pct,
    -- 30+ DPD rate
    CAST(SUM(CASE WHEN ACCT_DELQ_DAYS >= 30 THEN 1 ELSE 0 END) AS FLOAT)
        / NULLIF(COUNT(DISTINCT ACCOUNT_NUMBER), 0) * 100    AS delq_30plus_rate_pct
FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
WHERE CYC_CARD_STATUS NOT IN ('C','W','X')
  AND ACCT_CYC_MIN_DUE_BAL > 0
GROUP BY
    FIC_MIS_DATE,
    PROD_CODE,
    CASE
        WHEN BEHAVIOUR_SCORE <  500 THEN '1-Sub500'
        WHEN BEHAVIOUR_SCORE <  580 THEN '2-500-580'
        WHEN BEHAVIOUR_SCORE <  650 THEN '3-580-650'
        WHEN BEHAVIOUR_SCORE <  720 THEN '4-650-720'
        ELSE                             '5-720+'
    END
ORDER BY
    FIC_MIS_DATE,
    score_band;


/* ─────────────────────────────────────────────────────────────────────────────
   Q6  ROLL-RATE MATRIX (MONTHLY DPD STATE TRANSITIONS)
       Joins each account's state this month to its state last month.
       Produces the transition probability matrix for Power BI matrix visual.
       States: Current | 30DPD | 60DPD | 90DPD | 120DPD | 150DPD | 180+DPD | CO
       NOTE: CYC_WRITE_OFF_BAL > 0 used as charge-off proxy.
   ───────────────────────────────────────────────────────────────────────────── */
WITH state_current AS (
    SELECT
        FIC_MIS_DATE,
        ACCOUNT_NUMBER,
        PROD_CODE,
        EOP_BAL,
        CYC_PMT_AMT,
        ACCT_CYC_MIN_DUE_BAL,
        CYC_WRITE_OFF_BAL,
        -- Assign DPD state from bucket balances
        CASE
            WHEN CYC_WRITE_OFF_BAL > 0                         THEN '7-ChargeOff'
            WHEN DUE_181DPD_UP_BAL > 0                         THEN '6-180+DPD'
            WHEN DUE_150DPD_BAL    > 0                         THEN '5-150DPD'
            WHEN DUE_121DPD_UP_BAL > 0                         THEN '4-120DPD'
            WHEN DUE_90DPD_BAL     > 0                         THEN '3-90DPD'
            WHEN DUE_60DPD_BAL     > 0                         THEN '2-60DPD'
            WHEN DUE_30DPD_BAL     > 0                         THEN '1-30DPD'
            ELSE                                                    '0-Current'
        END                                                     AS dpd_state
    FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
),
state_with_prior AS (
    SELECT
        c.FIC_MIS_DATE,
        c.ACCOUNT_NUMBER,
        c.PROD_CODE,
        c.EOP_BAL,
        c.dpd_state                                             AS state_now,
        LAG(c.dpd_state) OVER (
            PARTITION BY c.ACCOUNT_NUMBER
            ORDER BY c.FIC_MIS_DATE
        )                                                       AS state_prior
    FROM state_current c
)
SELECT
    FIC_MIS_DATE                                              AS report_date,
    PROD_CODE                                                 AS product,
    state_prior,
    state_now,
    COUNT(DISTINCT ACCOUNT_NUMBER)                            AS account_count,
    SUM(EOP_BAL)                                              AS balance_transitioned,
    -- Transition rate within prior state (calculated in Power BI via DAX measure)
    -- Raw counts here; Power BI divides by state_prior total
    CAST(COUNT(DISTINCT ACCOUNT_NUMBER) AS FLOAT)             AS flow_count_float
FROM state_with_prior
WHERE state_prior IS NOT NULL
GROUP BY
    FIC_MIS_DATE,
    PROD_CODE,
    state_prior,
    state_now
ORDER BY
    FIC_MIS_DATE,
    state_prior,
    state_now;


/* ─────────────────────────────────────────────────────────────────────────────
   Q7  CURE RATE — 1-CYCLE LOOK-AHEAD
       For each account in 30/60/90 DPD this month, check if next month's
       state is Current or an improvement.
       This requires joining month N to month N+1 via LEAD.
       "Cure" = account was delinquent, and moves back to Current.
       Power BI use: KPI card, line trend by delinquency entry bucket
   ───────────────────────────────────────────────────────────────────────────── */
WITH dpd_states AS (
    SELECT
        FIC_MIS_DATE,
        ACCOUNT_NUMBER,
        PROD_CODE,
        BEHAVIOUR_SCORE,
        EOP_BAL,
        CYC_PMT_AMT,
        ACCT_CYC_MIN_DUE_BAL,
        CYC_WRITE_OFF_BAL,
        CASE
            WHEN CYC_WRITE_OFF_BAL > 0     THEN '7-ChargeOff'
            WHEN DUE_181DPD_UP_BAL > 0     THEN '6-180+DPD'
            WHEN DUE_150DPD_BAL    > 0     THEN '5-150DPD'
            WHEN DUE_121DPD_UP_BAL > 0     THEN '4-120DPD'
            WHEN DUE_90DPD_BAL     > 0     THEN '3-90DPD'
            WHEN DUE_60DPD_BAL     > 0     THEN '2-60DPD'
            WHEN DUE_30DPD_BAL     > 0     THEN '1-30DPD'
            ELSE                               '0-Current'
        END                                AS dpd_state
    FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
),
with_next_state AS (
    SELECT
        FIC_MIS_DATE,
        ACCOUNT_NUMBER,
        PROD_CODE,
        BEHAVIOUR_SCORE,
        EOP_BAL,
        CYC_PMT_AMT,
        ACCT_CYC_MIN_DUE_BAL,
        dpd_state,
        LEAD(dpd_state) OVER (
            PARTITION BY ACCOUNT_NUMBER
            ORDER BY FIC_MIS_DATE
        )                                  AS next_dpd_state
    FROM dpd_states
)
SELECT
    FIC_MIS_DATE                                              AS cohort_date,
    PROD_CODE                                                 AS product,
    dpd_state                                                 AS entry_state,
    -- Score band at entry
    CASE
        WHEN BEHAVIOUR_SCORE <  580 THEN '1-Sub580'
        WHEN BEHAVIOUR_SCORE <  650 THEN '2-580-650'
        WHEN BEHAVIOUR_SCORE <  720 THEN '3-650-720'
        ELSE                             '4-720+'
    END                                                       AS score_band,
    COUNT(DISTINCT ACCOUNT_NUMBER)                            AS cohort_count,
    SUM(EOP_BAL)                                              AS cohort_balance,
    -- Cured = moved to Current next month
    SUM(CASE WHEN next_dpd_state = '0-Current' THEN 1 ELSE 0 END) AS cured_count,
    SUM(CASE WHEN next_dpd_state = '0-Current' THEN EOP_BAL ELSE 0 END) AS cured_balance,
    -- Worsened = rolled deeper
    SUM(CASE WHEN next_dpd_state > dpd_state   THEN 1 ELSE 0 END) AS worsened_count,
    -- Charged off from this cohort
    SUM(CASE WHEN next_dpd_state = '7-ChargeOff' THEN 1 ELSE 0 END) AS chargeoff_count,
    -- Cure rate %
    CASE
        WHEN COUNT(DISTINCT ACCOUNT_NUMBER) > 0
        THEN CAST(SUM(CASE WHEN next_dpd_state = '0-Current' THEN 1 ELSE 0 END) AS FLOAT)
             / COUNT(DISTINCT ACCOUNT_NUMBER) * 100
        ELSE NULL
    END                                                       AS cure_rate_pct,
    -- Balance cure rate
    CASE
        WHEN SUM(EOP_BAL) > 0
        THEN CAST(SUM(CASE WHEN next_dpd_state = '0-Current' THEN EOP_BAL ELSE 0 END) AS FLOAT)
             / SUM(EOP_BAL) * 100
        ELSE NULL
    END                                                       AS cure_rate_bal_pct
FROM with_next_state
WHERE dpd_state IN ('1-30DPD','2-60DPD','3-90DPD','4-120DPD')  -- delinquent entry states
  AND next_dpd_state IS NOT NULL                                  -- exclude last month in data
GROUP BY
    FIC_MIS_DATE,
    PROD_CODE,
    dpd_state,
    CASE
        WHEN BEHAVIOUR_SCORE <  580 THEN '1-Sub580'
        WHEN BEHAVIOUR_SCORE <  650 THEN '2-580-650'
        WHEN BEHAVIOUR_SCORE <  720 THEN '3-650-720'
        ELSE                             '4-720+'
    END
ORDER BY
    FIC_MIS_DATE,
    entry_state;


/* ─────────────────────────────────────────────────────────────────────────────
   Q8  VINTAGE CURE CURVES
       For each account's first-delinquency month (vintage), track cumulative
       cure % at 1, 3, 6, 9, 12 months out.
       Step 1: Identify vintage (first month ACCT_DELQ_DAYS > 0).
       Step 2: For each vintage cohort, compute cumulative cure at each age.
       Power BI use: multi-line chart by vintage with months-since-DPD on x-axis
   ───────────────────────────────────────────────────────────────────────────── */
WITH first_delq AS (
    -- Find each account's first delinquency date
    SELECT
        ACCOUNT_NUMBER,
        PROD_CODE,
        MIN(FIC_MIS_DATE)                  AS first_delq_date,
        MIN(BEHAVIOUR_SCORE)               AS entry_score     -- score at entry
    FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
    WHERE ACCT_DELQ_DAYS > 0
    GROUP BY ACCOUNT_NUMBER, PROD_CODE
),
delq_history AS (
    -- For each account, get all subsequent monthly states
    SELECT
        s.FIC_MIS_DATE,
        s.ACCOUNT_NUMBER,
        s.PROD_CODE,
        fd.first_delq_date,
        fd.entry_score,
        s.EOP_BAL,
        s.CYC_PMT_AMT,
        s.ACCT_DELQ_DAYS,
        s.CYC_WRITE_OFF_BAL,
        -- Months since first delinquency
        DATEDIFF(MONTH, fd.first_delq_date, s.FIC_MIS_DATE) AS months_on_book,
        -- Is the account current this month?
        CASE WHEN s.ACCT_DELQ_DAYS = 0 AND s.CYC_WRITE_OFF_BAL = 0 THEN 1 ELSE 0 END AS is_current,
        -- Is it charged off?
        CASE WHEN s.CYC_WRITE_OFF_BAL > 0 THEN 1 ELSE 0 END  AS is_chargeoff
    FROM [OFS].[MONTHLY].[STG_CREDIT_CARD] s
    INNER JOIN first_delq fd
        ON s.ACCOUNT_NUMBER = fd.ACCOUNT_NUMBER
       AND s.FIC_MIS_DATE >= fd.first_delq_date
)
SELECT
    -- Vintage = first delinquency calendar quarter (group months to reduce cardinality)
    CAST(YEAR(first_delq_date) AS VARCHAR(4)) + '-Q'
        + CAST(DATEPART(QUARTER, first_delq_date) AS VARCHAR(1)) AS vintage_quarter,
    PROD_CODE                                                      AS product,
    CASE
        WHEN entry_score <  580 THEN '1-Sub580'
        WHEN entry_score <  650 THEN '2-580-650'
        WHEN entry_score <  720 THEN '3-650-720'
        ELSE                         '4-720+'
    END                                                            AS entry_score_band,
    months_on_book,
    COUNT(DISTINCT ACCOUNT_NUMBER)                                 AS cohort_size,
    SUM(is_current)                                                AS cured_ever_this_month,
    SUM(is_chargeoff)                                              AS charged_off_this_month,
    -- Cumulative cure: account is current AND has not charged off yet
    -- (Power BI running total measure will compute cumulative; provide monthly snapshot here)
    CAST(SUM(is_current) AS FLOAT)
        / NULLIF(COUNT(DISTINCT ACCOUNT_NUMBER), 0) * 100         AS pct_current_this_month,
    CAST(SUM(is_chargeoff) AS FLOAT)
        / NULLIF(COUNT(DISTINCT ACCOUNT_NUMBER), 0) * 100         AS pct_chargeoff_this_month
FROM delq_history
WHERE months_on_book BETWEEN 0 AND 24   -- track 2 years out
GROUP BY
    CAST(YEAR(first_delq_date) AS VARCHAR(4)) + '-Q'
        + CAST(DATEPART(QUARTER, first_delq_date) AS VARCHAR(1)),
    PROD_CODE,
    CASE
        WHEN entry_score <  580 THEN '1-Sub580'
        WHEN entry_score <  650 THEN '2-580-650'
        WHEN entry_score <  720 THEN '3-650-720'
        ELSE                         '4-720+'
    END,
    months_on_book
ORDER BY
    vintage_quarter,
    months_on_book;


/* ─────────────────────────────────────────────────────────────────────────────
   Q9  DELINQUENCY BUCKET BALANCE WATERFALL
       Total balance in each DPD bucket by month and product.
       Power BI use: waterfall or stacked bar chart
   ───────────────────────────────────────────────────────────────────────────── */
SELECT
    FIC_MIS_DATE                                              AS report_date,
    PROD_CODE                                                 AS product,
    -- Current balance (not delinquent)
    SUM(CASE WHEN DUE_30DPD_BAL = 0 AND DUE_60DPD_BAL = 0
              AND DUE_90DPD_BAL = 0 AND CYC_WRITE_OFF_BAL = 0
             THEN EOP_BAL ELSE 0 END)                         AS current_balance,
    SUM(DUE_30DPD_BAL)                                        AS bal_30dpd,
    SUM(DUE_60DPD_BAL)                                        AS bal_60dpd,
    SUM(DUE_90DPD_BAL)                                        AS bal_90dpd,
    SUM(DUE_120DPD_BAL)                                       AS bal_120dpd,
    SUM(DUE_150DPD_BAL)                                       AS bal_150dpd,
    SUM(DUE_181DPD_UP_BAL)                                    AS bal_180plus,
    SUM(CYC_WRITE_OFF_BAL)                                    AS bal_chargeoff,
    SUM(EOP_BAL)                                              AS total_portfolio_balance,
    -- Delinquency rate (balance-weighted)
    CASE
        WHEN SUM(EOP_BAL) > 0
        THEN CAST(SUM(DUE_30DPD_BAL + DUE_60DPD_BAL + DUE_90DPD_BAL
                      + DUE_120DPD_BAL + DUE_150DPD_BAL + DUE_181DPD_UP_BAL) AS FLOAT)
             / SUM(EOP_BAL) * 100
        ELSE NULL
    END                                                       AS delinquency_rate_pct,
    -- 90+ DPD serious delinquency rate
    CASE
        WHEN SUM(EOP_BAL) > 0
        THEN CAST(SUM(DUE_90DPD_BAL + DUE_120DPD_BAL
                      + DUE_150DPD_BAL + DUE_181DPD_UP_BAL) AS FLOAT)
             / SUM(EOP_BAL) * 100
        ELSE NULL
    END                                                       AS serious_delinq_rate_pct,
    -- Account count per bucket
    SUM(CASE WHEN DUE_30DPD_BAL > 0 THEN 1 ELSE 0 END)       AS accts_30dpd,
    SUM(CASE WHEN DUE_60DPD_BAL > 0 THEN 1 ELSE 0 END)       AS accts_60dpd,
    SUM(CASE WHEN DUE_90DPD_BAL > 0 THEN 1 ELSE 0 END)       AS accts_90dpd,
    SUM(CASE WHEN DUE_120DPD_BAL > 0 OR DUE_150DPD_BAL > 0
              OR DUE_181DPD_UP_BAL > 0 THEN 1 ELSE 0 END)    AS accts_120plus,
    SUM(CASE WHEN CYC_WRITE_OFF_BAL > 0 THEN 1 ELSE 0 END)   AS accts_chargeoff
FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
GROUP BY
    FIC_MIS_DATE,
    PROD_CODE
ORDER BY
    FIC_MIS_DATE,
    PROD_CODE;


/* ─────────────────────────────────────────────────────────────────────────────
   Q10  NET CHARGE-OFF RATE (NCO) BY MONTH AND PRODUCT
        NCO = (Gross charge-off - Recoveries) / Average outstanding balance
        Power BI use: KPI + line chart, annualised NCO = monthly × 12
   ───────────────────────────────────────────────────────────────────────────── */
SELECT
    FIC_MIS_DATE                                              AS report_date,
    PROD_CODE                                                 AS product,
    SUM(CYC_WRITE_OFF_BAL)                                    AS gross_chargeoff,
    SUM(PRIN_WRITE_OFF_BAL)                                   AS principal_chargeoff,
    SUM(INT_WRITE_OFF_BAL)                                    AS interest_chargeoff,
    SUM(OTHER_WRITE_OFF_BAL)                                  AS other_chargeoff,
    SUM(CYC_RECOVERY_BAL)                                     AS gross_recovery,
    SUM(PRIN_RECOVERY_BAL)                                    AS principal_recovery,
    -- Net charge-off
    SUM(CYC_WRITE_OFF_BAL) - SUM(CYC_RECOVERY_BAL)           AS net_chargeoff,
    -- Average balance (use EOP_AVG_BAL if populated, fallback to EOP_BAL)
    SUM(COALESCE(EOP_AVG_BAL, EOP_BAL))                       AS avg_balance,
    -- Monthly NCO rate
    CASE
        WHEN SUM(COALESCE(EOP_AVG_BAL, EOP_BAL)) > 0
        THEN CAST(SUM(CYC_WRITE_OFF_BAL) - SUM(CYC_RECOVERY_BAL) AS FLOAT)
             / SUM(COALESCE(EOP_AVG_BAL, EOP_BAL)) * 100
        ELSE NULL
    END                                                       AS nco_rate_monthly_pct,
    -- Annualised NCO rate (× 12)
    CASE
        WHEN SUM(COALESCE(EOP_AVG_BAL, EOP_BAL)) > 0
        THEN CAST(SUM(CYC_WRITE_OFF_BAL) - SUM(CYC_RECOVERY_BAL) AS FLOAT)
             / SUM(COALESCE(EOP_AVG_BAL, EOP_BAL)) * 100 * 12
        ELSE NULL
    END                                                       AS nco_rate_annualised_pct,
    -- Accounts charged off
    SUM(CASE WHEN CYC_WRITE_OFF_BAL > 0 THEN 1 ELSE 0 END)   AS accounts_chargedoff,
    COUNT(DISTINCT ACCOUNT_NUMBER)                            AS total_accounts
FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
GROUP BY
    FIC_MIS_DATE,
    PROD_CODE
ORDER BY
    FIC_MIS_DATE,
    PROD_CODE;


/* ─────────────────────────────────────────────────────────────────────────────
   Q11  RECOVERY RATE BY MONTH
        Recovery rate = Recoveries / Gross charge-off (lagged)
        Uses current-month recoveries vs current-month gross charge-off as proxy.
        True recovery rate requires matching to prior charge-off vintages —
        use Power BI running total on gross CO vs cumulative recovery.
        Power BI use: line chart, compare to NCO rate
   ───────────────────────────────────────────────────────────────────────────── */
WITH co_and_recovery AS (
    SELECT
        FIC_MIS_DATE,
        PROD_CODE,
        SUM(CYC_WRITE_OFF_BAL)    AS gross_co,
        SUM(CYC_RECOVERY_BAL)     AS gross_recovery,
        SUM(PRIN_WRITE_OFF_BAL)   AS prin_co,
        SUM(PRIN_RECOVERY_BAL)    AS prin_recovery
    FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
    GROUP BY FIC_MIS_DATE, PROD_CODE
),
with_cumulative AS (
    SELECT
        *,
        SUM(gross_co) OVER (
            PARTITION BY PROD_CODE
            ORDER BY FIC_MIS_DATE
            ROWS UNBOUNDED PRECEDING
        )                          AS cumulative_gross_co,
        SUM(gross_recovery) OVER (
            PARTITION BY PROD_CODE
            ORDER BY FIC_MIS_DATE
            ROWS UNBOUNDED PRECEDING
        )                          AS cumulative_recovery
    FROM co_and_recovery
)
SELECT
    FIC_MIS_DATE                                              AS report_date,
    PROD_CODE                                                 AS product,
    gross_co,
    gross_recovery,
    prin_co,
    prin_recovery,
    cumulative_gross_co,
    cumulative_recovery,
    -- Cumulative recovery rate (more meaningful than monthly)
    CASE
        WHEN cumulative_gross_co > 0
        THEN CAST(cumulative_recovery AS FLOAT) / cumulative_gross_co * 100
        ELSE NULL
    END                                                       AS cumulative_recovery_rate_pct,
    -- Monthly recovery rate
    CASE
        WHEN gross_co > 0
        THEN CAST(gross_recovery AS FLOAT) / gross_co * 100
        ELSE NULL
    END                                                       AS monthly_recovery_rate_pct
FROM with_cumulative
ORDER BY
    FIC_MIS_DATE,
    PROD_CODE;


/* ─────────────────────────────────────────────────────────────────────────────
   Q12  PAYMENT STRESS SEGMENTATION — HIGH-RISK FLAG TABLE
        Combines payment compression + delinquency history + utilisation
        into a composite early-warning score for account-level alerting.
        Power BI use: account-level table with conditional formatting,
                      drill-through from portfolio-level visuals
   ───────────────────────────────────────────────────────────────────────────── */
WITH compression AS (
    SELECT
        FIC_MIS_DATE,
        ACCOUNT_NUMBER,
        PROD_CODE,
        BEHAVIOUR_SCORE,
        ACCT_RISK_SCORE,
        EOP_BAL,
        CURRENT_CREDIT_LIMIT,
        CYC_PMT_AMT,
        ACCT_CYC_MIN_DUE_BAL,
        ACCT_DELQ_DAYS,
        ACCT_DELQ_HISTORY,
        DELQ_LIFE_TIMES,
        DELQ_YEAR_TIMES,
        CYC_WRITE_OFF_BAL,
        EOP_PMT_BOUNCED_AMT,
        OVERDUE_PRINCIPAL,
        OVERDUE_INT,
        HIGH_BAL,
        PD_PERCENT,
        EXPECTED_LOSS_PERCENT,
        -- PCR
        CASE
            WHEN ACCT_CYC_MIN_DUE_BAL > 0
            THEN CAST(CYC_PMT_AMT AS FLOAT) / ACCT_CYC_MIN_DUE_BAL
            ELSE NULL
        END                              AS pcr,
        -- Utilisation
        CASE
            WHEN CURRENT_CREDIT_LIMIT > 0
            THEN CAST(EOP_BAL AS FLOAT) / CURRENT_CREDIT_LIMIT
            ELSE NULL
        END                              AS util_ratio,
        -- Prior month PCR
        LAG(CASE WHEN ACCT_CYC_MIN_DUE_BAL > 0
                 THEN CAST(CYC_PMT_AMT AS FLOAT) / ACCT_CYC_MIN_DUE_BAL
                 ELSE NULL END)
            OVER (PARTITION BY ACCOUNT_NUMBER ORDER BY FIC_MIS_DATE) AS pcr_prior,
        -- Prior month utilisation
        LAG(CASE WHEN CURRENT_CREDIT_LIMIT > 0
                 THEN CAST(EOP_BAL AS FLOAT) / CURRENT_CREDIT_LIMIT
                 ELSE NULL END)
            OVER (PARTITION BY ACCOUNT_NUMBER ORDER BY FIC_MIS_DATE) AS util_prior
    FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
    WHERE CYC_CARD_STATUS NOT IN ('C','W','X')
)
SELECT
    FIC_MIS_DATE                                              AS report_date,
    ACCOUNT_NUMBER,
    PROD_CODE,
    BEHAVIOUR_SCORE,
    ACCT_RISK_SCORE,
    EOP_BAL,
    CURRENT_CREDIT_LIMIT,
    util_ratio * 100                                          AS utilisation_pct,
    pcr,
    pcr_prior,
    CYC_PMT_AMT,
    ACCT_CYC_MIN_DUE_BAL,
    ACCT_DELQ_DAYS,
    DELQ_YEAR_TIMES,
    DELQ_LIFE_TIMES,
    EOP_PMT_BOUNCED_AMT,
    PD_PERCENT,
    EXPECTED_LOSS_PERCENT,
    -- ── STRESS FLAGS ──────────────────────────────────────────────────────────
    -- Flag 1: Payment compressed this cycle
    CASE WHEN pcr BETWEEN 0.95 AND 1.05 THEN 1 ELSE 0 END    AS flag_compressed,
    -- Flag 2: PCR declined month-on-month (compression trending)
    CASE WHEN pcr < pcr_prior AND pcr_prior IS NOT NULL
         THEN 1 ELSE 0 END                                    AS flag_pcr_declining,
    -- Flag 3: Utilisation > 90%
    CASE WHEN util_ratio > 0.90 THEN 1 ELSE 0 END            AS flag_high_util,
    -- Flag 4: Utilisation rising (trending toward limit)
    CASE WHEN util_ratio > util_prior AND util_prior IS NOT NULL
         THEN 1 ELSE 0 END                                    AS flag_util_rising,
    -- Flag 5: Currently past due
    CASE WHEN ACCT_DELQ_DAYS > 0 THEN 1 ELSE 0 END           AS flag_past_due,
    -- Flag 6: Missed payment this cycle (bounced or zero)
    CASE WHEN EOP_PMT_BOUNCED_AMT > 0 THEN 1 ELSE 0 END      AS flag_bounced_payment,
    -- Flag 7: Delinquent 2+ times this year (chronic)
    CASE WHEN DELQ_YEAR_TIMES >= 2 THEN 1 ELSE 0 END          AS flag_chronic_delq,
    -- Flag 8: Overdue principal outstanding
    CASE WHEN OVERDUE_PRINCIPAL > 0 THEN 1 ELSE 0 END         AS flag_overdue_principal,
    -- ── COMPOSITE STRESS SCORE (0–8) ──────────────────────────────────────────
    (CASE WHEN pcr BETWEEN 0.95 AND 1.05 THEN 1 ELSE 0 END
     + CASE WHEN pcr < pcr_prior AND pcr_prior IS NOT NULL THEN 1 ELSE 0 END
     + CASE WHEN util_ratio > 0.90 THEN 1 ELSE 0 END
     + CASE WHEN util_ratio > util_prior AND util_prior IS NOT NULL THEN 1 ELSE 0 END
     + CASE WHEN ACCT_DELQ_DAYS > 0 THEN 1 ELSE 0 END
     + CASE WHEN EOP_PMT_BOUNCED_AMT > 0 THEN 1 ELSE 0 END
     + CASE WHEN DELQ_YEAR_TIMES >= 2 THEN 1 ELSE 0 END
     + CASE WHEN OVERDUE_PRINCIPAL > 0 THEN 1 ELSE 0 END
    )                                                         AS composite_stress_score,
    -- Stress tier
    CASE
        WHEN (CASE WHEN pcr BETWEEN 0.95 AND 1.05 THEN 1 ELSE 0 END
              + CASE WHEN pcr < pcr_prior AND pcr_prior IS NOT NULL THEN 1 ELSE 0 END
              + CASE WHEN util_ratio > 0.90 THEN 1 ELSE 0 END
              + CASE WHEN util_ratio > util_prior AND util_prior IS NOT NULL THEN 1 ELSE 0 END
              + CASE WHEN ACCT_DELQ_DAYS > 0 THEN 1 ELSE 0 END
              + CASE WHEN EOP_PMT_BOUNCED_AMT > 0 THEN 1 ELSE 0 END
              + CASE WHEN DELQ_YEAR_TIMES >= 2 THEN 1 ELSE 0 END
              + CASE WHEN OVERDUE_PRINCIPAL > 0 THEN 1 ELSE 0 END
             ) >= 5 THEN 'RED-Critical'
        WHEN (CASE WHEN pcr BETWEEN 0.95 AND 1.05 THEN 1 ELSE 0 END
              + CASE WHEN pcr < pcr_prior AND pcr_prior IS NOT NULL THEN 1 ELSE 0 END
              + CASE WHEN util_ratio > 0.90 THEN 1 ELSE 0 END
              + CASE WHEN util_ratio > util_prior AND util_prior IS NOT NULL THEN 1 ELSE 0 END
              + CASE WHEN ACCT_DELQ_DAYS > 0 THEN 1 ELSE 0 END
              + CASE WHEN EOP_PMT_BOUNCED_AMT > 0 THEN 1 ELSE 0 END
              + CASE WHEN DELQ_YEAR_TIMES >= 2 THEN 1 ELSE 0 END
              + CASE WHEN OVERDUE_PRINCIPAL > 0 THEN 1 ELSE 0 END
             ) >= 3 THEN 'AMBER-Watch'
        WHEN (CASE WHEN pcr BETWEEN 0.95 AND 1.05 THEN 1 ELSE 0 END
              + CASE WHEN pcr < pcr_prior AND pcr_prior IS NOT NULL THEN 1 ELSE 0 END
              + CASE WHEN util_ratio > 0.90 THEN 1 ELSE 0 END
              + CASE WHEN util_ratio > util_prior AND util_prior IS NOT NULL THEN 1 ELSE 0 END
              + CASE WHEN ACCT_DELQ_DAYS > 0 THEN 1 ELSE 0 END
              + CASE WHEN EOP_PMT_BOUNCED_AMT > 0 THEN 1 ELSE 0 END
              + CASE WHEN DELQ_YEAR_TIMES >= 2 THEN 1 ELSE 0 END
              + CASE WHEN OVERDUE_PRINCIPAL > 0 THEN 1 ELSE 0 END
             ) >= 1 THEN 'YELLOW-Monitor'
        ELSE                                                       'GREEN-Normal'
    END                                                       AS stress_tier
FROM compression
ORDER BY
    FIC_MIS_DATE,
    composite_stress_score DESC;


/* ─────────────────────────────────────────────────────────────────────────────
   Q13  PROVISION VS EXPECTED LOSS
        Compares modelled PD×LGD×EAD expected loss to provision already made.
        Highlights under/over-provisioned accounts.
        Power BI use: scatter plot (provision vs EL), bar chart by product
   ───────────────────────────────────────────────────────────────────────────── */
SELECT
    FIC_MIS_DATE                                              AS report_date,
    PROD_CODE                                                 AS product,
    LOB_CODE                                                  AS lob,
    SUM(EOP_BAL)                                              AS total_balance,
    SUM(UNDRAWN_AMOUNT)                                       AS total_undrawn,
    -- Provision (balance sheet)
    SUM(PROVISION_MADE_BAL)                                   AS total_provision,
    SUM(EOP_PRIN_PROVISION_MADE)                              AS total_prin_provision,
    SUM(EOP_INT_PROVISION_MADE)                               AS total_int_provision,
    -- Expected loss from PD/LGD model
    SUM(PROVISION_AMOUNT)                                     AS total_model_el,
    SUM(EXPECTED_LOSS)                                        AS total_expected_loss_field,
    -- Provision ratio
    CASE
        WHEN SUM(EOP_BAL) > 0
        THEN CAST(SUM(PROVISION_MADE_BAL) AS FLOAT) / SUM(EOP_BAL) * 100
        ELSE NULL
    END                                                       AS provision_coverage_pct,
    -- EL ratio
    CASE
        WHEN SUM(EOP_BAL) > 0
        THEN CAST(SUM(PROVISION_AMOUNT) AS FLOAT) / SUM(EOP_BAL) * 100
        ELSE NULL
    END                                                       AS el_rate_pct,
    -- Over / (under) provision
    SUM(PROVISION_MADE_BAL) - SUM(PROVISION_AMOUNT)          AS provision_surplus_deficit,
    -- Average PD
    AVG(CAST(PD_PERCENT AS FLOAT))                            AS avg_pd_pct,
    -- Average LGD
    AVG(CAST(LGD_PERCENT AS FLOAT))                           AS avg_lgd_pct,
    -- Average expected loss %
    AVG(CAST(EXPECTED_LOSS_PERCENT AS FLOAT))                 AS avg_el_pct
FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
WHERE CYC_CARD_STATUS NOT IN ('W','X')
GROUP BY
    FIC_MIS_DATE,
    PROD_CODE,
    LOB_CODE
ORDER BY
    FIC_MIS_DATE,
    PROD_CODE;


/* ─────────────────────────────────────────────────────────────────────────────
   Q14  CREDIT UTILISATION DISTRIBUTION
        Segments accounts by utilisation band.
        High utilisation (>90%) is the key risk appetite trigger (Boston Fed).
        Power BI use: stacked bar chart, slice by score band and product
   ───────────────────────────────────────────────────────────────────────────── */
SELECT
    FIC_MIS_DATE                                              AS report_date,
    PROD_CODE                                                 AS product,
    CASE
        WHEN BEHAVIOUR_SCORE <  580 THEN '1-Sub580'
        WHEN BEHAVIOUR_SCORE <  650 THEN '2-580-650'
        WHEN BEHAVIOUR_SCORE <  720 THEN '3-650-720'
        ELSE                             '4-720+'
    END                                                       AS score_band,
    -- Utilisation bucket
    CASE
        WHEN CURRENT_CREDIT_LIMIT <= 0                         THEN '0-NoLimit'
        WHEN CAST(EOP_BAL AS FLOAT) / CURRENT_CREDIT_LIMIT < 0.25  THEN '1-0-25pct'
        WHEN CAST(EOP_BAL AS FLOAT) / CURRENT_CREDIT_LIMIT < 0.50  THEN '2-25-50pct'
        WHEN CAST(EOP_BAL AS FLOAT) / CURRENT_CREDIT_LIMIT < 0.75  THEN '3-50-75pct'
        WHEN CAST(EOP_BAL AS FLOAT) / CURRENT_CREDIT_LIMIT < 0.90  THEN '4-75-90pct'
        WHEN CAST(EOP_BAL AS FLOAT) / CURRENT_CREDIT_LIMIT < 1.00  THEN '5-90-100pct'
        ELSE                                                        '6-Over100pct'
    END                                                       AS util_bucket,
    COUNT(DISTINCT ACCOUNT_NUMBER)                            AS account_count,
    SUM(EOP_BAL)                                              AS balance,
    SUM(CURRENT_CREDIT_LIMIT)                                 AS total_limit,
    AVG(CAST(ACCT_DELQ_DAYS AS FLOAT))                        AS avg_delq_days,
    -- Forward delinquency proxy: accounts in bucket currently past due
    SUM(CASE WHEN ACCT_DELQ_DAYS > 0 THEN 1 ELSE 0 END)      AS past_due_accounts,
    CAST(SUM(CASE WHEN ACCT_DELQ_DAYS > 0 THEN 1 ELSE 0 END) AS FLOAT)
        / NULLIF(COUNT(DISTINCT ACCOUNT_NUMBER), 0) * 100    AS past_due_rate_pct,
    -- Min payers in this util band
    SUM(CASE WHEN ACCT_CYC_MIN_DUE_BAL > 0
              AND CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 1.05
             THEN 1 ELSE 0 END)                               AS min_payers_in_band,
    SUM(CASE WHEN OVER_LIMIT_BAL > 0 THEN 1 ELSE 0 END)      AS over_limit_accounts
FROM [OFS].[MONTHLY].[STG_CREDIT_CARD]
WHERE CYC_CARD_STATUS NOT IN ('C','W','X')
GROUP BY
    FIC_MIS_DATE,
    PROD_CODE,
    CASE
        WHEN BEHAVIOUR_SCORE <  580 THEN '1-Sub580'
        WHEN BEHAVIOUR_SCORE <  650 THEN '2-580-650'
        WHEN BEHAVIOUR_SCORE <  720 THEN '3-650-720'
        ELSE                             '4-720+'
    END,
    CASE
        WHEN CURRENT_CREDIT_LIMIT <= 0                         THEN '0-NoLimit'
        WHEN CAST(EOP_BAL AS FLOAT) / CURRENT_CREDIT_LIMIT < 0.25  THEN '1-0-25pct'
        WHEN CAST(EOP_BAL AS FLOAT) / CURRENT_CREDIT_LIMIT < 0.50  THEN '2-25-50pct'
        WHEN CAST(EOP_BAL AS FLOAT) / CURRENT_CREDIT_LIMIT < 0.75  THEN '3-50-75pct'
        WHEN CAST(EOP_BAL AS FLOAT) / CURRENT_CREDIT_LIMIT < 0.90  THEN '4-75-90pct'
        WHEN CAST(EOP_BAL AS FLOAT) / CURRENT_CREDIT_LIMIT < 1.00  THEN '5-90-100pct'
        ELSE                                                        '6-Over100pct'
    END
ORDER BY
    FIC_MIS_DATE,
    util_bucket,
    score_band;
