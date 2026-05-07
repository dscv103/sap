#!/usr/bin/env -S uv run –script

# /// script

# requires-python = “>=3.13”

# dependencies = [

# “polars>=1.0”,

# “connectorx>=0.3”,

# “pyarrow>=16”,

# ]

# ///

“””
payment_stress_extract.py
─────────────────────────
Extracts all payment compression / cure rate queries from SQL Server 2016
into Polars DataFrames, then writes Parquet files that Power BI can consume
directly (via DirectQuery on Parquet or by importing into a semantic model).

Usage:
uv run payment_stress_extract.py                    # all queries
uv run payment_stress_extract.py –query q1 q7      # specific queries

Connection:
Set env var MSSQL_URI or pass –uri flag.
Format: mssql://user:password@host:1433/database

SQL Server 2016 (v13 RTM) constraints respected:

- No named WINDOW clause (SQL Server 2022+)
- LAG/LEAD/ROW_NUMBER/running SUM OVER available
- READ ONLY — no temp tables, no SET statements that require write access
  “””

from **future** import annotations

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

import polars as pl

# ── Connection ────────────────────────────────────────────────────────────────

def get_uri() -> str:
uri = os.getenv(“MSSQL_URI”)
if not uri:
raise RuntimeError(
“Set MSSQL_URI env var. “
“Format: mssql://user:password@host:1433/database”
)
return uri

# ── Query definitions ─────────────────────────────────────────────────────────

# Each entry: (key, label, sql_text)

# SQL is identical to payment_stress_queries.sql — define inline here so this

# script is self-contained and can be run without reading the .sql file.

TABLE = “[OFS].[MONTHLY].[STG_CREDIT_CARD]”

Q1_MPR = f”””
SELECT
FIC_MIS_DATE                                              AS report_date,
PROD_CODE                                                 AS product,
COUNT(DISTINCT ACCOUNT_NUMBER)                            AS total_accounts,
SUM(CASE WHEN EOP_BAL > 0 THEN 1 ELSE 0 END)             AS accounts_with_balance,
SUM(CYC_PMT_AMT)                                          AS total_payments,
SUM(ACCT_CYC_BALANCE)                                     AS total_beginning_balance,
SUM(EOP_BAL)                                              AS total_eop_balance,
CASE
WHEN SUM(ACCT_CYC_BALANCE) > 0
THEN CAST(SUM(CYC_PMT_AMT) AS FLOAT) / SUM(ACCT_CYC_BALANCE) * 100
ELSE NULL
END                                                       AS mpr_pct,
SUM(CASE WHEN CYC_PMT_AMT > ACCT_CYC_MIN_DUE_BAL
THEN CYC_PMT_AMT - ACCT_CYC_MIN_DUE_BAL
ELSE 0 END)                                      AS aggregate_excess_payment,
SUM(ACCT_CYC_MIN_DUE_BAL)                                AS total_min_due
FROM {TABLE}
WHERE ACCT_CYC_BALANCE > 0
AND CYC_CARD_STATUS NOT IN (‘C’,‘W’,‘X’)
GROUP BY FIC_MIS_DATE, PROD_CODE
ORDER BY FIC_MIS_DATE, PROD_CODE
“””

Q2_MMPR = f”””
SELECT
FIC_MIS_DATE                                              AS report_date,
PROD_CODE                                                 AS product,
COUNT(DISTINCT ACCOUNT_NUMBER)                            AS active_accounts,
SUM(CASE
WHEN ACCT_CYC_MIN_DUE_BAL > 0
AND CYC_PMT_AMT > 0
AND CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 1.02
THEN 1 ELSE 0
END)                                                  AS min_pmt_accounts,
SUM(CASE WHEN CYC_PMT_AMT = 0 AND ACCT_CYC_MIN_DUE_BAL > 0
THEN 1 ELSE 0 END)                               AS zero_pmt_accounts,
SUM(CASE
WHEN CYC_PMT_AMT > ACCT_CYC_MIN_DUE_BAL * 1.02
AND CYC_PMT_AMT < EOP_PRIN_BAL
THEN 1 ELSE 0
END)                                                  AS partial_excess_accounts,
SUM(CASE WHEN CYC_PMT_AMT >= EOP_PRIN_BAL AND EOP_PRIN_BAL > 0
THEN 1 ELSE 0 END)                               AS full_pay_accounts,
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
FROM {TABLE}
WHERE CYC_CARD_STATUS NOT IN (‘C’,‘W’,‘X’)
AND ACCT_CYC_MIN_DUE_BAL > 0
GROUP BY FIC_MIS_DATE, PROD_CODE
ORDER BY FIC_MIS_DATE, PROD_CODE
“””

Q4_PCR_DIST = f”””
SELECT
FIC_MIS_DATE                                              AS report_date,
PROD_CODE                                                 AS product,
CASE
WHEN BEHAVIOUR_SCORE <  500 THEN ‘1-Sub500’
WHEN BEHAVIOUR_SCORE <  620 THEN ‘2-500-620’
WHEN BEHAVIOUR_SCORE <  680 THEN ‘3-620-680’
WHEN BEHAVIOUR_SCORE <  720 THEN ‘4-680-720’
ELSE                             ‘5-720+’
END                                                       AS score_band,
CASE
WHEN ACCT_CYC_MIN_DUE_BAL <= 0                                    THEN ‘0-NoMinDue’
WHEN CYC_PMT_AMT = 0                                               THEN ‘1-ZeroPay’
WHEN CYC_PMT_AMT < ACCT_CYC_MIN_DUE_BAL * 0.50                   THEN ‘2-Below50pct’
WHEN CYC_PMT_AMT < ACCT_CYC_MIN_DUE_BAL * 0.98                   THEN ‘3-50-98pct’
WHEN CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 1.05                  THEN ‘4-AtMin’
WHEN CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 1.50                  THEN ‘5-105-150pct’
WHEN CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 3.00                  THEN ‘6-150-300pct’
WHEN CYC_PMT_AMT < EOP_PRIN_BAL                                    THEN ‘7-Above300pct’
ELSE                                                                    ‘8-FullPay’
END                                                       AS pcr_bucket,
COUNT(DISTINCT ACCOUNT_NUMBER)                            AS account_count,
SUM(EOP_BAL)                                              AS balance_in_bucket,
AVG(CAST(ACCT_DELQ_DAYS AS FLOAT))                        AS avg_delq_days,
AVG(CAST(BEHAVIOUR_SCORE AS FLOAT))                       AS avg_behaviour_score
FROM {TABLE}
WHERE CYC_CARD_STATUS NOT IN (‘C’,‘W’,‘X’)
GROUP BY
FIC_MIS_DATE, PROD_CODE,
CASE WHEN BEHAVIOUR_SCORE < 500 THEN ‘1-Sub500’
WHEN BEHAVIOUR_SCORE < 620 THEN ‘2-500-620’
WHEN BEHAVIOUR_SCORE < 680 THEN ‘3-620-680’
WHEN BEHAVIOUR_SCORE < 720 THEN ‘4-680-720’
ELSE ‘5-720+’ END,
CASE WHEN ACCT_CYC_MIN_DUE_BAL <= 0 THEN ‘0-NoMinDue’
WHEN CYC_PMT_AMT = 0 THEN ‘1-ZeroPay’
WHEN CYC_PMT_AMT < ACCT_CYC_MIN_DUE_BAL * 0.50 THEN ‘2-Below50pct’
WHEN CYC_PMT_AMT < ACCT_CYC_MIN_DUE_BAL * 0.98 THEN ‘3-50-98pct’
WHEN CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 1.05 THEN ‘4-AtMin’
WHEN CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 1.50 THEN ‘5-105-150pct’
WHEN CYC_PMT_AMT <= ACCT_CYC_MIN_DUE_BAL * 3.00 THEN ‘6-150-300pct’
WHEN CYC_PMT_AMT < EOP_PRIN_BAL THEN ‘7-Above300pct’
ELSE ‘8-FullPay’ END
“””

Q6_ROLLRATE = f”””
WITH state_current AS (
SELECT
FIC_MIS_DATE, ACCOUNT_NUMBER, PROD_CODE, EOP_BAL,
CASE
WHEN CYC_WRITE_OFF_BAL > 0  THEN ‘7-ChargeOff’
WHEN DUE_181DPD_UP_BAL > 0  THEN ‘6-180+DPD’
WHEN DUE_150DPD_BAL    > 0  THEN ‘5-150DPD’
WHEN DUE_121DPD_UP_BAL > 0  THEN ‘4-120DPD’
WHEN DUE_90DPD_BAL     > 0  THEN ‘3-90DPD’
WHEN DUE_60DPD_BAL     > 0  THEN ‘2-60DPD’
WHEN DUE_30DPD_BAL     > 0  THEN ‘1-30DPD’
ELSE                            ‘0-Current’
END AS dpd_state
FROM {TABLE}
),
with_prior AS (
SELECT
FIC_MIS_DATE, ACCOUNT_NUMBER, PROD_CODE, EOP_BAL,
dpd_state AS state_now,
LAG(dpd_state) OVER (PARTITION BY ACCOUNT_NUMBER ORDER BY FIC_MIS_DATE) AS state_prior
FROM state_current
)
SELECT
FIC_MIS_DATE AS report_date,
PROD_CODE    AS product,
state_prior,
state_now,
COUNT(DISTINCT ACCOUNT_NUMBER) AS account_count,
SUM(EOP_BAL)                   AS balance_transitioned
FROM with_prior
WHERE state_prior IS NOT NULL
GROUP BY FIC_MIS_DATE, PROD_CODE, state_prior, state_now
“””

Q7_CURE = f”””
WITH dpd_states AS (
SELECT
FIC_MIS_DATE, ACCOUNT_NUMBER, PROD_CODE, BEHAVIOUR_SCORE, EOP_BAL,
CYC_PMT_AMT, ACCT_CYC_MIN_DUE_BAL,
CASE
WHEN CYC_WRITE_OFF_BAL > 0 THEN ‘7-ChargeOff’
WHEN DUE_181DPD_UP_BAL > 0 THEN ‘6-180+DPD’
WHEN DUE_150DPD_BAL    > 0 THEN ‘5-150DPD’
WHEN DUE_121DPD_UP_BAL > 0 THEN ‘4-120DPD’
WHEN DUE_90DPD_BAL     > 0 THEN ‘3-90DPD’
WHEN DUE_60DPD_BAL     > 0 THEN ‘2-60DPD’
WHEN DUE_30DPD_BAL     > 0 THEN ‘1-30DPD’
ELSE                           ‘0-Current’
END AS dpd_state
FROM {TABLE}
),
with_next AS (
SELECT
FIC_MIS_DATE, ACCOUNT_NUMBER, PROD_CODE, BEHAVIOUR_SCORE, EOP_BAL,
dpd_state,
LEAD(dpd_state) OVER (PARTITION BY ACCOUNT_NUMBER ORDER BY FIC_MIS_DATE) AS next_dpd_state
FROM dpd_states
)
SELECT
FIC_MIS_DATE  AS cohort_date,
PROD_CODE     AS product,
dpd_state     AS entry_state,
CASE WHEN BEHAVIOUR_SCORE < 580 THEN ‘1-Sub580’
WHEN BEHAVIOUR_SCORE < 650 THEN ‘2-580-650’
WHEN BEHAVIOUR_SCORE < 720 THEN ‘3-650-720’
ELSE ‘4-720+’ END                                    AS score_band,
COUNT(DISTINCT ACCOUNT_NUMBER)                            AS cohort_count,
SUM(EOP_BAL)                                              AS cohort_balance,
SUM(CASE WHEN next_dpd_state = ‘0-Current’ THEN 1 ELSE 0 END) AS cured_count,
SUM(CASE WHEN next_dpd_state = ‘0-Current’ THEN EOP_BAL ELSE 0 END) AS cured_balance,
SUM(CASE WHEN next_dpd_state > dpd_state   THEN 1 ELSE 0 END) AS worsened_count,
SUM(CASE WHEN next_dpd_state = ‘7-ChargeOff’ THEN 1 ELSE 0 END) AS chargeoff_count,
CASE WHEN COUNT(DISTINCT ACCOUNT_NUMBER) > 0
THEN CAST(SUM(CASE WHEN next_dpd_state = ‘0-Current’ THEN 1 ELSE 0 END) AS FLOAT)
/ COUNT(DISTINCT ACCOUNT_NUMBER) * 100
ELSE NULL END                                        AS cure_rate_pct,
CASE WHEN SUM(EOP_BAL) > 0
THEN CAST(SUM(CASE WHEN next_dpd_state = ‘0-Current’ THEN EOP_BAL ELSE 0 END) AS FLOAT)
/ SUM(EOP_BAL) * 100
ELSE NULL END                                        AS cure_rate_bal_pct
FROM with_next
WHERE dpd_state IN (‘1-30DPD’,‘2-60DPD’,‘3-90DPD’,‘4-120DPD’)
AND next_dpd_state IS NOT NULL
GROUP BY
FIC_MIS_DATE, PROD_CODE, dpd_state,
CASE WHEN BEHAVIOUR_SCORE < 580 THEN ‘1-Sub580’
WHEN BEHAVIOUR_SCORE < 650 THEN ‘2-580-650’
WHEN BEHAVIOUR_SCORE < 720 THEN ‘3-650-720’
ELSE ‘4-720+’ END
“””

Q9_WATERFALL = f”””
SELECT
FIC_MIS_DATE AS report_date,
PROD_CODE    AS product,
SUM(CASE WHEN DUE_30DPD_BAL = 0 AND DUE_60DPD_BAL = 0
AND DUE_90DPD_BAL = 0 AND CYC_WRITE_OFF_BAL = 0
THEN EOP_BAL ELSE 0 END)  AS current_balance,
SUM(DUE_30DPD_BAL)                 AS bal_30dpd,
SUM(DUE_60DPD_BAL)                 AS bal_60dpd,
SUM(DUE_90DPD_BAL)                 AS bal_90dpd,
SUM(DUE_120DPD_BAL)                AS bal_120dpd,
SUM(DUE_150DPD_BAL)                AS bal_150dpd,
SUM(DUE_181DPD_UP_BAL)             AS bal_180plus,
SUM(CYC_WRITE_OFF_BAL)             AS bal_chargeoff,
SUM(EOP_BAL)                        AS total_balance,
CASE WHEN SUM(EOP_BAL) > 0
THEN CAST(SUM(DUE_30DPD_BAL + DUE_60DPD_BAL + DUE_90DPD_BAL
+ DUE_120DPD_BAL + DUE_150DPD_BAL + DUE_181DPD_UP_BAL) AS FLOAT)
/ SUM(EOP_BAL) * 100
ELSE NULL END                  AS delinquency_rate_pct,
SUM(CASE WHEN DUE_30DPD_BAL > 0 THEN 1 ELSE 0 END) AS accts_30dpd,
SUM(CASE WHEN DUE_60DPD_BAL > 0 THEN 1 ELSE 0 END) AS accts_60dpd,
SUM(CASE WHEN DUE_90DPD_BAL > 0 THEN 1 ELSE 0 END) AS accts_90dpd
FROM {TABLE}
GROUP BY FIC_MIS_DATE, PROD_CODE
ORDER BY FIC_MIS_DATE, PROD_CODE
“””

Q10_NCO = f”””
SELECT
FIC_MIS_DATE AS report_date,
PROD_CODE    AS product,
SUM(CYC_WRITE_OFF_BAL)              AS gross_chargeoff,
SUM(PRIN_WRITE_OFF_BAL)             AS principal_chargeoff,
SUM(CYC_RECOVERY_BAL)               AS gross_recovery,
SUM(CYC_WRITE_OFF_BAL)
- SUM(CYC_RECOVERY_BAL)         AS net_chargeoff,
SUM(COALESCE(EOP_AVG_BAL, EOP_BAL)) AS avg_balance,
CASE WHEN SUM(COALESCE(EOP_AVG_BAL, EOP_BAL)) > 0
THEN CAST(SUM(CYC_WRITE_OFF_BAL) - SUM(CYC_RECOVERY_BAL) AS FLOAT)
/ SUM(COALESCE(EOP_AVG_BAL, EOP_BAL)) * 100
ELSE NULL END                   AS nco_rate_monthly_pct,
CASE WHEN SUM(COALESCE(EOP_AVG_BAL, EOP_BAL)) > 0
THEN CAST(SUM(CYC_WRITE_OFF_BAL) - SUM(CYC_RECOVERY_BAL) AS FLOAT)
/ SUM(COALESCE(EOP_AVG_BAL, EOP_BAL)) * 100 * 12
ELSE NULL END                   AS nco_rate_annualised_pct
FROM {TABLE}
GROUP BY FIC_MIS_DATE, PROD_CODE
ORDER BY FIC_MIS_DATE, PROD_CODE
“””

# ── Query registry ────────────────────────────────────────────────────────────

QUERIES: dict[str, tuple[str, str]] = {
“q1”:  (“mpr_trend”,          Q1_MPR),
“q2”:  (“mmpr_trend”,         Q2_MMPR),
“q4”:  (“pcr_distribution”,   Q4_PCR_DIST),
“q6”:  (“roll_rate_matrix”,   Q6_ROLLRATE),
“q7”:  (“cure_rate”,          Q7_CURE),
“q9”:  (“dpd_waterfall”,      Q9_WATERFALL),
“q10”: (“nco_rate”,           Q10_NCO),
}

# ── Extraction ────────────────────────────────────────────────────────────────

def extract(uri: str, key: str, label: str, sql: str, out_dir: Path) -> None:
print(f”  [{key}] {label} — querying…”)
df: pl.DataFrame = pl.read_database_uri(
query=sql,
uri=uri,
engine=“connectorx”,
)
# Ensure report_date is Date type for Power BI
if “report_date” in df.columns:
df = df.with_columns(pl.col(“report_date”).cast(pl.Date))
if “cohort_date” in df.columns:
df = df.with_columns(pl.col(“cohort_date”).cast(pl.Date))

```
out_path = out_dir / f"{label}.parquet"
df.write_parquet(out_path, compression="snappy")
print(f"  [{key}] → {out_path}  ({len(df):,} rows)")
```

def main() -> None:
parser = argparse.ArgumentParser(
description=“Extract payment stress queries → Parquet for Power BI”
)
parser.add_argument(
“–uri”,
default=None,
help=“mssql://user:password@host:1433/database  (overrides MSSQL_URI env var)”,
)
parser.add_argument(
“–query”,
nargs=”*”,
choices=list(QUERIES.keys()),
default=None,
help=“Which queries to run (default: all)”,
)
parser.add_argument(
“–out”,
default=”./parquet_output”,
help=“Output directory for Parquet files (default: ./parquet_output)”,
)
args = parser.parse_args()

```
uri = args.uri or get_uri()
out_dir = Path(args.out)
out_dir.mkdir(parents=True, exist_ok=True)

keys_to_run = args.query or list(QUERIES.keys())
print(f"\nPayment Stress Extract — {datetime.now():%Y-%m-%d %H:%M}")
print(f"Output: {out_dir.resolve()}")
print(f"Queries: {keys_to_run}\n")

for key in keys_to_run:
    label, sql = QUERIES[key]
    extract(uri, key, label, sql, out_dir)

print("\nDone. Load Parquet files into Power BI Desktop via:")
print("  Get Data → Parquet → point to the output directory.")
print("  Each file becomes one table in the semantic model.")
```

if **name** == “**main**”:
main()
