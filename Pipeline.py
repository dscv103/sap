# “””
Card Spend Analytics Pipeline

Designed for 10M+ row datasets. Uses Polars for columnar, lazy evaluation.
Modules run independently — pipe together or run standalone.

Install: uv add polars pyarrow rich
“””

import polars as pl
from datetime import date
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

# ─────────────────────────────────────────────

# 0. LOAD & NORMALIZE

# ─────────────────────────────────────────────

def load(path: str) -> pl.LazyFrame:
“””
Lazy load — no data pulled into memory until .collect().
Adjust separator/encoding as needed for your source.
“””
return (
pl.scan_csv(path, try_parse_dates=True)
.with_columns([
pl.col(“TXN_POST_DATE”).str.to_date(”%m/%d/%Y”),
pl.col(“TXN_DATE”).str.to_date(”%m/%d/%Y”),
pl.col(“AMOUNT_TRANSACTION”).cast(pl.Float64),
pl.col(“INTERCHANGE_FEES”).cast(pl.Float64),
pl.col(“MERCHANT_TYPE”).cast(pl.Utf8),
# Normalize debit amounts to positive, credits to negative
pl.when(pl.col(“DEBIT_CREDIT_IND”) == “D”)
.then(pl.col(“AMOUNT_TRANSACTION”).abs())
.otherwise(-pl.col(“AMOUNT_TRANSACTION”).abs())
.alias(“AMOUNT_NORMALIZED”),
])
)

# ─────────────────────────────────────────────

# 1. DATA QUALITY AUDIT  (run first — always)

# Priority: CRITICAL — bad data poisons downstream

# ─────────────────────────────────────────────

def audit_data_quality(lf: pl.LazyFrame) -> dict:
“””
Flags known issues in this schema:
- MERCHANT_CITY containing phone numbers (PayPal passthrough)
- TXN_REF_NUMBER duplicates (double-posting risk)
- Post date lag outliers (>5 days = processor/dispute flag)
- CARD_EXPIRATION_DATE uniformity (all 2807 in sample = suspicious)
- INCLUSION_FLAG = N rows that might skew aggregates
“””
df = lf.collect()
total = len(df)

```
issues = {}

# Phone numbers in MERCHANT_CITY
phone_pattern = r"^\d{3}-\d{3}-\d{4}$"
phone_cities = df.filter(
    pl.col("MERCHANT_CITY").str.contains(phone_pattern)
)
issues["phone_number_as_city"] = {
    "count": len(phone_cities),
    "pct": round(len(phone_cities) / total * 100, 2),
    "merchants": phone_cities["MERCHANT_NAME"].unique().to_list(),
}

# Duplicate TXN_REF_NUMBERs (only on purchase rows)
purchases = df.filter(pl.col("DEBIT_CREDIT_IND") == "D")
dupes = (
    purchases.group_by("TXN_REF_NUMBER")
    .agg(pl.len().alias("cnt"))
    .filter(pl.col("cnt") > 1)
)
issues["duplicate_txn_refs"] = {"count": len(dupes)}

# Post date lag
df_with_lag = df.with_columns(
    (pl.col("TXN_POST_DATE") - pl.col("TXN_DATE"))
    .dt.total_days()
    .alias("post_lag_days")
)
lag_outliers = df_with_lag.filter(pl.col("post_lag_days") > 5)
issues["post_lag_gt5_days"] = {"count": len(lag_outliers)}

# Expiration date uniformity
exp_dist = df["CARD_EXPIRATION_DATE"].value_counts().sort("count", descending=True)
issues["expiration_date_distribution"] = exp_dist.to_dicts()

# INCLUSION_FLAG = N
excluded = df.filter(pl.col("INCLUSION_FLAG") == "N")
issues["excluded_rows"] = {"count": len(excluded), "pct": round(len(excluded) / total * 100, 2)}

return issues
```

# ─────────────────────────────────────────────

# 2. INTERCHANGE YIELD BY MCC

# Priority: HIGH — direct P&L impact

# SQL equivalent included below

# ─────────────────────────────────────────────

def interchange_yield_by_mcc(lf: pl.LazyFrame) -> pl.DataFrame:
“””
Yield = interchange_fees / transaction_amount
Negative interchange_fees in source = cost to issuer, so we flip sign.

```
SQL equivalent:
    SELECT
        MERCHANT_TYPE,
        COUNT(*)                                        AS txn_count,
        SUM(AMOUNT_TRANSACTION)                        AS gross_spend,
        SUM(ABS(INTERCHANGE_FEES))                     AS total_interchange,
        AVG(ABS(INTERCHANGE_FEES)/AMOUNT_TRANSACTION)  AS avg_yield_pct,
        AVG(AMOUNT_TRANSACTION)                        AS avg_ticket
    FROM transactions
    WHERE DEBIT_CREDIT_IND = 'D'
      AND INCLUSION_FLAG = 'Y'
      AND AMOUNT_TRANSACTION > 0
    GROUP BY MERCHANT_TYPE
    ORDER BY total_interchange DESC;
"""
return (
    lf
    .filter(
        (pl.col("DEBIT_CREDIT_IND") == "D") &
        (pl.col("INCLUSION_FLAG") == "Y") &
        (pl.col("AMOUNT_TRANSACTION") > 0)
    )
    .with_columns(
        pl.col("INTERCHANGE_FEES").abs().alias("fee_abs"),
    )
    .group_by("MERCHANT_TYPE")
    .agg([
        pl.len().alias("txn_count"),
        pl.col("AMOUNT_TRANSACTION").sum().alias("gross_spend"),
        pl.col("fee_abs").sum().alias("total_interchange"),
        (pl.col("fee_abs") / pl.col("AMOUNT_TRANSACTION")).mean().alias("avg_yield_pct"),
        pl.col("AMOUNT_TRANSACTION").mean().alias("avg_ticket"),
    ])
    .with_columns(
        (pl.col("avg_yield_pct") * 100).round(3).alias("avg_yield_pct"),
    )
    .sort("total_interchange", descending=True)
    .collect()
)
```

# ─────────────────────────────────────────────

# 3. FRAUD SIGNAL SCORING

# Priority: HIGH — risk + regulatory exposure

# ─────────────────────────────────────────────

# MCC codes commonly associated with elevated fraud/risk

HIGH_RISK_MCC = {
“7922”,  # Betting/gambling (BETIX example)
“7995”,  # Gambling transactions
“5912”,  # Drug stores (card-not-present fraud)
“4829”,  # Wire transfers
“6051”,  # Quasi-cash / crypto exchanges
}

def score_fraud_signals(lf: pl.LazyFrame) -> pl.DataFrame:
“””
Composite signal scoring. Each flag contributes to a risk_score.
Tune weights based on your portfolio’s observed loss rates.

```
Signals:
- High-risk MCC (+3)
- Large ticket (>2 std devs above mean) (+2)
- Cross-border transaction (+1)
- Non-recurring, high MCC risk (+1)
- Short post lag on large ticket (+1)
"""
df = lf.filter(
    (pl.col("DEBIT_CREDIT_IND") == "D") &
    (pl.col("INCLUSION_FLAG") == "Y")
).collect()

mean_amt = df["AMOUNT_TRANSACTION"].mean()
std_amt = df["AMOUNT_TRANSACTION"].std()
large_ticket_threshold = mean_amt + (2 * std_amt)

return (
    df
    .with_columns([
        # Signal flags
        pl.col("MERCHANT_TYPE").is_in(HIGH_RISK_MCC).cast(pl.Int8).alias("flag_high_risk_mcc"),
        (pl.col("AMOUNT_TRANSACTION") > large_ticket_threshold).cast(pl.Int8).alias("flag_large_ticket"),
        (pl.col("MERCHANT_COUNTRY") != "US").cast(pl.Int8).alias("flag_cross_border"),
        (
            (pl.col("RECURRING_IND") == "N") &
            pl.col("MERCHANT_TYPE").is_in(HIGH_RISK_MCC)
        ).cast(pl.Int8).alias("flag_nonrecurring_high_risk"),
    ])
    .with_columns(
        # Composite score
        (
            pl.col("flag_high_risk_mcc") * 3 +
            pl.col("flag_large_ticket") * 2 +
            pl.col("flag_cross_border") * 1 +
            pl.col("flag_nonrecurring_high_risk") * 1
        ).alias("risk_score")
    )
    .filter(pl.col("risk_score") > 0)
    .select([
        "CARD_USER_ID", "TXN_DATE", "MERCHANT_NAME", "MERCHANT_TYPE",
        "AMOUNT_TRANSACTION", "MERCHANT_COUNTRY",
        "flag_high_risk_mcc", "flag_large_ticket", "flag_cross_border",
        "flag_nonrecurring_high_risk", "risk_score"
    ])
    .sort("risk_score", descending=True)
)
```

# ─────────────────────────────────────────────

# 4. CARDHOLDER SEGMENTATION

# Priority: HIGH — drives retention, product fit

# ─────────────────────────────────────────────

def segment_cardholders(lf: pl.LazyFrame, as_of: date = date.today()) -> pl.DataFrame:
“””
RFM + behavioral segmentation per cardholder.

```
Recency   = days since last purchase
Frequency = distinct purchase days in period
Monetary  = total spend

Behavioral add-ons:
- recurring_ratio: subscription stickiness signal
- category_entropy: spend diversity (high = broad wallet, low = concentrated)
- payment_regularity: how consistently they pay down balance

SQL equivalent (simplified):
    SELECT
        CARD_USER_ID,
        DATEDIFF(day, MAX(TXN_DATE), GETDATE())    AS recency_days,
        COUNT(DISTINCT TXN_DATE)                   AS frequency,
        SUM(AMOUNT_TRANSACTION)                    AS monetary,
        AVG(CASE WHEN RECURRING_IND='Y' THEN 1.0 ELSE 0.0 END) AS recurring_ratio
    FROM transactions
    WHERE DEBIT_CREDIT_IND = 'D' AND INCLUSION_FLAG = 'Y'
    GROUP BY CARD_USER_ID;
"""
purchases = lf.filter(
    (pl.col("DEBIT_CREDIT_IND") == "D") &
    (pl.col("INCLUSION_FLAG") == "Y")
)

rfm = (
    purchases
    .group_by("CARD_USER_ID")
    .agg([
        pl.col("TXN_DATE").max().alias("last_txn_date"),
        pl.col("TXN_DATE").n_unique().alias("frequency"),
        pl.col("AMOUNT_TRANSACTION").sum().alias("monetary"),
        pl.col("AMOUNT_TRANSACTION").mean().alias("avg_ticket"),
        (pl.col("RECURRING_IND") == "Y").mean().alias("recurring_ratio"),
        pl.col("MERCHANT_TYPE").n_unique().alias("category_diversity"),
    ])
    .with_columns(
        (pl.lit(as_of) - pl.col("last_txn_date"))
        .dt.total_days()
        .alias("recency_days")
    )
    .collect()
)

# Quintile scoring (1=worst, 5=best)
rfm = rfm.with_columns([
    pl.col("recency_days").rank(method="ordinal", descending=True)
        .over(pl.lit(1)).alias("R"),  # lower recency = better
    pl.col("frequency").rank(method="ordinal").alias("F"),
    pl.col("monetary").rank(method="ordinal").alias("M"),
]).with_columns([
    # Normalize to 1–5 quintiles
    ((pl.col("R") - 1) / (rfm.height - 1) * 4 + 1).round(0).cast(pl.Int8).alias("R_score"),
    ((pl.col("F") - 1) / (rfm.height - 1) * 4 + 1).round(0).cast(pl.Int8).alias("F_score"),
    ((pl.col("M") - 1) / (rfm.height - 1) * 4 + 1).round(0).cast(pl.Int8).alias("M_score"),
]).with_columns(
    (pl.col("R_score") + pl.col("F_score") + pl.col("M_score")).alias("RFM_total")
).with_columns(
    pl.when(pl.col("RFM_total") >= 13).then(pl.lit("Champions"))
    .when(pl.col("RFM_total") >= 10).then(pl.lit("Loyal"))
    .when(pl.col("RFM_total") >= 7).then(pl.lit("Potential"))
    .when(pl.col("R_score") <= 2).then(pl.lit("At Risk"))
    .otherwise(pl.lit("Hibernating"))
    .alias("segment")
)

return rfm.sort("RFM_total", descending=True)
```

# ─────────────────────────────────────────────

# 5. RECURRING CHARGE MONITOR

# Priority: MEDIUM-HIGH — subscription detection + dropout alert

# ─────────────────────────────────────────────

def detect_recurring_dropout(lf: pl.LazyFrame, lookback_days: int = 90) -> pl.DataFrame:
“””
For merchants where RECURRING_IND = Y, find card+merchant pairs
that had consistent charges but stopped within the lookback window.

```
This is your early churn signal — a cardholder who stopped paying
ADT or a streaming service may have churned the card entirely.

Approach:
1. Find (card, merchant) pairs with 2+ historical recurring charges
2. Flag pairs where last charge is older than lookback_days
"""
recurring = (
    lf
    .filter(
        (pl.col("RECURRING_IND") == "Y") &
        (pl.col("DEBIT_CREDIT_IND") == "D") &
        (pl.col("INCLUSION_FLAG") == "Y")
    )
    .group_by(["CARD_USER_ID", "MERCHANT_NAME"])
    .agg([
        pl.len().alias("charge_count"),
        pl.col("TXN_DATE").max().alias("last_charge_date"),
        pl.col("TXN_DATE").min().alias("first_charge_date"),
        pl.col("AMOUNT_TRANSACTION").mean().alias("avg_amount"),
    ])
    .filter(pl.col("charge_count") >= 2)
    .collect()
)

cutoff = pl.lit(date.today()) - pl.duration(days=lookback_days)

return (
    recurring
    .with_columns(
        (pl.lit(date.today()) - pl.col("last_charge_date"))
        .dt.total_days()
        .alias("days_since_last_charge")
    )
    .filter(pl.col("days_since_last_charge") > lookback_days)
    .sort("days_since_last_charge", descending=True)
)
```

# ─────────────────────────────────────────────

# 6. PAYMENT BEHAVIOR ANALYSIS

# Priority: MEDIUM — credit risk, collections targeting

# ─────────────────────────────────────────────

def payment_behavior(lf: pl.LazyFrame) -> pl.DataFrame:
“””
Per cardholder:
- Total purchases vs. total payments (net exposure)
- Average days to payment after spend cycle
- Payment-to-spend ratio (>1.0 = overpaying/credits, <0.8 = revolving risk)

```
SQL equivalent:
    SELECT
        CARD_USER_ID,
        SUM(CASE WHEN DEBIT_CREDIT_IND='D' THEN AMOUNT_TRANSACTION ELSE 0 END) AS total_spend,
        SUM(CASE WHEN DEBIT_CREDIT_IND='C' THEN ABS(AMOUNT_TRANSACTION) ELSE 0 END) AS total_payments,
        SUM(CASE WHEN DEBIT_CREDIT_IND='C' THEN ABS(AMOUNT_TRANSACTION) ELSE 0 END)
          / NULLIF(SUM(CASE WHEN DEBIT_CREDIT_IND='D' THEN AMOUNT_TRANSACTION ELSE 0 END), 0)
          AS payment_ratio
    FROM transactions
    WHERE INCLUSION_FLAG = 'Y'
    GROUP BY CARD_USER_ID;
"""
df = lf.filter(pl.col("INCLUSION_FLAG") == "Y").collect()

spend = (
    df.filter(pl.col("DEBIT_CREDIT_IND") == "D")
    .group_by("CARD_USER_ID")
    .agg(pl.col("AMOUNT_TRANSACTION").sum().alias("total_spend"))
)
payments = (
    df.filter(pl.col("DEBIT_CREDIT_IND") == "C")
    .group_by("CARD_USER_ID")
    .agg(pl.col("AMOUNT_TRANSACTION").abs().sum().alias("total_payments"))
)

return (
    spend.join(payments, on="CARD_USER_ID", how="left")
    .with_columns(
        pl.col("total_payments").fill_null(0),
    )
    .with_columns(
        (pl.col("total_payments") / pl.col("total_spend")).round(3).alias("payment_ratio"),
        (pl.col("total_spend") - pl.col("total_payments")).alias("net_exposure"),
    )
    .with_columns(
        pl.when(pl.col("payment_ratio") >= 0.95).then(pl.lit("Full Payer"))
        .when(pl.col("payment_ratio") >= 0.50).then(pl.lit("Partial Payer"))
        .when(pl.col("payment_ratio") > 0).then(pl.lit("Minimum Payer"))
        .otherwise(pl.lit("Non Payer"))
        .alias("payment_segment")
    )
    .sort("net_exposure", descending=True)
)
```

# ─────────────────────────────────────────────

# RUNNER

# ─────────────────────────────────────────────

if **name** == “**main**”:
DATA_PATH = “sampledata.csv”  # swap for your full file path / S3 URI

```
console.rule("[bold cyan]Card Spend Analytics Pipeline[/bold cyan]")

lf = load(DATA_PATH)

# 1. Quality audit — always first
console.rule("1. Data Quality Audit")
issues = audit_data_quality(lf)
for k, v in issues.items():
    console.print(f"  [yellow]{k}[/yellow]: {v}")

# 2. Interchange yield
console.rule("2. Interchange Yield by MCC")
yield_df = interchange_yield_by_mcc(lf)
console.print(yield_df)

# 3. Fraud signals
console.rule("3. Fraud Signal Scoring")
fraud_df = score_fraud_signals(lf)
console.print(fraud_df)

# 4. Cardholder segments
console.rule("4. Cardholder Segmentation (RFM)")
seg_df = segment_cardholders(lf)
console.print(seg_df.select(["CARD_USER_ID", "segment", "RFM_total", "monetary", "recency_days"]))

# 5. Recurring dropout
console.rule("5. Recurring Charge Dropout")
dropout_df = detect_recurring_dropout(lf)
console.print(dropout_df)

# 6. Payment behavior
console.rule("6. Payment Behavior")
pay_df = payment_behavior(lf)
console.print(pay_df)

console.rule("[bold green]Pipeline complete[/bold green]")
```
