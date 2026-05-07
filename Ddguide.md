# Power BI Dashboard Design Guide

## Payment Compression & Cure Rate — Credit Stress Monitor

-----

## Data Model

Load one Parquet file per query as a table. Relate them all on `report_date` + `product`
via a shared **Date dimension table** (auto-created by Power BI or built manually).

|Parquet file              |Power BI table name|Key columns                        |
|--------------------------|-------------------|-----------------------------------|
|`mpr_trend.parquet`       |`MPR`              |report_date, product               |
|`mmpr_trend.parquet`      |`MMPR`             |report_date, product               |
|`pcr_distribution.parquet`|`PCR_Dist`         |report_date, product, pcr_bucket   |
|`roll_rate_matrix.parquet`|`RollRate`         |report_date, state_prior, state_now|
|`cure_rate.parquet`       |`CureRate`         |cohort_date, entry_state           |
|`dpd_waterfall.parquet`   |`DPD`              |report_date, product               |
|`nco_rate.parquet`        |`NCO`              |report_date, product               |

For Q3 (account-level PCR with LAG), Q5 (TPR by score band), Q8 (vintage curves),
Q11 (recovery rate), Q12 (stress segmentation), Q13 (provision vs EL), Q14 (utilisation):
run directly in Power BI via DirectQuery or import via the .sql file as a query.

-----

## Dashboard Pages

### Page 1 — Executive Summary (single-screen KPIs)

|Visual    |Measure                             |Alert threshold        |
|----------|------------------------------------|-----------------------|
|KPI card  |MMPR % (latest month)               |Red > 10%, Amber 8–10% |
|KPI card  |MPR % (latest month)                |Red < 15%, Amber 15–18%|
|KPI card  |30+ DPD cure rate %                 |Red < 75%, Amber 75–85%|
|KPI card  |Annualised NCO %                    |Red > 5%, Amber 3–5%   |
|KPI card  |90+ DPD serious delinquency %       |Red > 4%, Amber 2.5–4% |
|Line chart|MMPR % and MPR % — 24-month trend   |—                      |
|Line chart|Cure rate by entry state — 24 months|—                      |
|Slicer    |Product / LOB                       |—                      |

-----

### Page 2 — Payment Compression Detail

**Visual 1: MMPR Trend Line**

- X: report_date  |  Y: mmpr_pct
- Reference line at 10.75% (Philadelphia Fed Q3 2024 benchmark)
- Colour split by product

**Visual 2: PCR Distribution Histogram (clustered bar)**

- X: pcr_bucket  |  Y: account_count
- Legend: score_band
- Slicer: report_date (show most recent vs 12 months ago)

**Visual 3: Compression Cascade Table**

- Rows: score_band
- Columns: pcr_bucket
- Values: account_count (conditional format: red = ‘4-AtMin’ and ‘1-ZeroPay’)

**Visual 4: MPR Trend**

- X: report_date  |  Y: mpr_pct
- Secondary Y: aggregate_excess_payment (as area)

-----

### Page 3 — Roll-Rate Matrix

**Visual: Matrix visual (pivot table)**

- Rows: state_prior  |  Columns: state_now  |  Values: Transition Rate %

**DAX measure — Transition Rate:**

```dax
Transition Rate % =
VAR _from = SELECTEDVALUE(RollRate[state_prior])
VAR _total_from =
    CALCULATE(
        SUM(RollRate[account_count]),
        ALLSELECTED(RollRate[state_now]),
        RollRate[state_prior] = _from
    )
RETURN
DIVIDE(SUM(RollRate[account_count]), _total_from, 0) * 100
```

**Visual: Flow sankey or stacked bar**

- Shows monthly flow from Current → 30DPD → 60DPD → 90DPD → CO
- X: report_date  |  Y: balance_transitioned  |  Legend: state_now

-----

### Page 4 — Cure Rate Monitor

**Visual 1: Cure Rate KPI by Entry State**

- Three KPI cards: 30DPD cure %, 60DPD cure %, 90DPD cure %
- Spark line: trailing 12 months
- Conditional format: < 75% = red

**Visual 2: Cure Rate by Score Band (clustered bar)**

- X: score_band  |  Y: cure_rate_pct
- Legend: entry_state
- Tells you whether low-score accounts cure at all — key for collections prioritisation

**Visual 3: Cure Rate vs MMPR Scatter (monthly)**

- X: mmpr_pct (from MMPR table, joined on report_date)
- Y: cure_rate_pct (from CureRate table, filter entry_state = ‘1-30DPD’)
- Each point = one month
- Trend line should show negative correlation (higher MMPR → lower cure rate)

**Visual 4: Vintage Cure Curves (line chart)**

- X: months_on_book  |  Y: pct_current_this_month
- Legend: vintage_quarter
- Shows whether recent vintages cure faster or slower than prior cohorts

-----

### Page 5 — Delinquency & Charge-Off

**Visual 1: DPD Waterfall (stacked bar)**

- X: report_date
- Y layers: current_balance | bal_30dpd | bal_60dpd | bal_90dpd | bal_120dpd | bal_150dpd | bal_180plus | bal_chargeoff
- Toggle between balance $ and account count

**Visual 2: NCO Rate Trend**

- X: report_date  |  Y: nco_rate_annualised_pct
- Reference line: 5% (industry stress threshold)
- Secondary Y: gross_chargeoff (bars), gross_recovery (bars, negative)

**Visual 3: Serious Delinquency Rate**

- X: report_date  |  Y: serious_delinq_rate_pct
- Benchmark line at 4% (Philadelphia Fed signal level)

-----

### Page 6 — Account Stress Monitor (Drill-through)

Source: Q12 stress segmentation query (import as DirectQuery or scheduled refresh).

**Visual 1: Stress Tier Distribution (donut or treemap)**

- GREEN / YELLOW / AMBER / RED tiers
- Size = account_count or EOP_BAL

**Visual 2: Stress Flag Breakdown (stacked bar)**

- X: stress_tier  |  Y: count of each flag
- Legends: flag_compressed, flag_high_util, flag_bounced_payment, etc.

**Visual 3: Account-Level Table (drill-through target)**

- Columns: ACCOUNT_NUMBER, stress_tier, composite_stress_score,
  pcr, utilisation_pct, ACCT_DELQ_DAYS, BEHAVIOUR_SCORE,
  EOP_BAL, flag_* columns
- Conditional format: RED tier rows = red background

-----

## Key DAX Measures

```dax
-- MMPR vs Prior Month
MMPR MoM Change =
CALCULATE([MMPR %], DATEADD(DimDate[Date], -1, MONTH))
- [MMPR %]

-- Cure Rate (calculated in Power BI from CureRate table)
Cure Rate % =
DIVIDE(
    SUM(CureRate[cured_count]),
    SUM(CureRate[cohort_count]),
    0
) * 100

-- 30→60 Roll Rate
30-to-60 Roll Rate =
CALCULATE(
    DIVIDE(
        SUM(RollRate[account_count]),
        CALCULATE(
            SUM(RollRate[account_count]),
            RollRate[state_prior] = "1-30DPD"
        )
    ),
    RollRate[state_prior] = "1-30DPD",
    RollRate[state_now]   = "2-60DPD"
) * 100

-- MPR (from MPR table)
MPR % = DIVIDE(SUM(MPR[total_payments]), SUM(MPR[total_beginning_balance])) * 100

-- NCO Annualised
NCO Annualised % =
DIVIDE(
    (SUM(NCO[gross_chargeoff]) - SUM(NCO[gross_recovery])),
    SUM(NCO[avg_balance])
) * 100 * 12

-- Compression corridor (accounts between 95% and 105% of minimum)
Compression Corridor % =
DIVIDE(
    CALCULATE(
        SUM(PCR_Dist[account_count]),
        PCR_Dist[pcr_bucket] = "4-AtMin"
    ),
    SUM(PCR_Dist[account_count])
) * 100
```

-----

## Running Queries via sqlcmd (read-only, no temp tables)

```bash
# Single query to CSV — example for Q1 MPR
sqlcmd -S your_server -d your_database -E \
  -Q "SET NOCOUNT ON; $(cat payment_stress_queries.sql | sed -n '/Q1/,/Q2/p')" \
  -o mpr_output.csv -s "," -W

# Or pipe full file and capture each labelled block separately.
# Better: use the Python extract script with uv:
export MSSQL_URI="mssql://user:password@host:1433/database"
uv run payment_stress_extract.py --out ./pbi_parquet

# Then in Power BI Desktop:
# Get Data → Parquet → select the ./pbi_parquet folder
```

-----

## Calibration Notes

- **PCR tolerance band (98–105%)**: Adjust to your minimum payment formula.
  If your minimum is a flat dollar amount rather than % of balance, set the
  band to ±$5 rather than ±5%.
- **MMPR benchmark**: The Philadelphia Fed Q3 2024 number (10.75%) is for large
  US banks. Your baseline will differ — establish 12-month trailing average as
  your benchmark before setting alert thresholds.
- **DPD bucket assignment**: This SQL uses the `DUE_xDPD_BAL` columns as
  proxies for DPD state. Cross-check against `ACCT_DELQ_DAYS` for consistency.
  Some systems populate one and not the other.
- **Cure definition**: Q7 defines cure as “next month state = Current.”
  A stricter definition requires the account to remain Current for 3 consecutive
  months — implement as a 3-period LEAD window if your data history supports it.
- **Behaviour score bands**: Replace the thresholds in the CASE statements with
  your institution’s internal score quartile breakpoints. The 580/650/720 bands
  are illustrative US VantageScore proxies.
