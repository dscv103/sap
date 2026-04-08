#!/usr/bin/env python3
"""
affirm_segmenter.py

Segment Affirm-like transaction histories into 5 actionable groups:
  1) Occasional small-ticket users
  2) Stable installment users
  3) High-ticket financers
  4) Stackers / complex obligation users
  5) Rising-stress / irregular users

Python: 3.13+

Example:
    python affirm_segmenter.py             --input AffirmTXN.csv             --output affirm_segments.csv             --feature-output affirm_segment_features.csv
"""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(slots=True)
class Config:
    small_ticket_threshold: float = 50.0
    high_ticket_threshold: float = 250.0
    very_high_ticket_threshold: float = 500.0
    recurring_min_occurrences: int = 3
    recurring_min_gap_days: int = 20
    recurring_max_gap_days: int = 40
    recurring_gap_success_ratio: float = 0.67
    active_plan_recent_days: int = 45
    same_day_stack_threshold: int = 5
    code_diversity_stack_threshold: int = 8
    active_plan_stack_threshold: int = 3
    recent_window_days: int = 60
    prior_window_days: int = 60
    rising_txn_ratio: float = 1.75
    irregular_gap_cv_threshold: float = 1.50
    irregular_amount_cv_threshold: float = 1.20
    min_txns_for_irregular: int = 6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Segment Affirm transaction histories into 5 actionable groups."
    )
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--output", default="affirm_segments.csv", help="Output CSV path for per-card segments")
    parser.add_argument(
        "--feature-output",
        default="affirm_segment_features.csv",
        help="Output CSV path for detailed engineered features",
    )
    parser.add_argument(
        "--date-col", default="As of Date", help="Transaction date column name"
    )
    parser.add_argument(
        "--card-col", default="CardKey", help="Account / customer key column name"
    )
    parser.add_argument(
        "--merchant-col", default="Merchant Name", help="Merchant / descriptor column name"
    )
    parser.add_argument(
        "--amount-col", default="Card Transaction Amount", help="Transaction amount column name"
    )
    return parser.parse_args()


def normalize_merchant_name(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = re.sub(r"\s+", " ", text).strip().upper()
    return text


def classify_txn_type(merchant: str) -> str:
    if merchant.startswith("AFFIRM.COM PAYM"):
        return "AFFIRM.COM PAYM"
    if merchant.startswith("AFFIRM * PAY"):
        return "AFFIRM * PAY"
    if merchant.startswith("AFFIRM PAY"):
        return "AFFIRM PAY"
    if merchant.startswith("AFFIRM P"):
        return "AFFIRM P"
    return "OTHER"


def extract_code(merchant: str) -> str | None:
    patterns = [
        r"^AFFIRM PAY\s+(.+)$",
        r"^AFFIRM \* PAY\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, merchant)
        if match:
            return match.group(1).strip()
    return None


def safe_cv(values: Iterable[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        return 0.0
    mean = float(np.mean(arr))
    std = float(np.std(arr))
    if math.isclose(mean, 0.0, abs_tol=1e-12):
        return 0.0
    return std / mean


def get_recurring_amount_groups(
    history: pd.DataFrame,
    as_of_date: pd.Timestamp,
    cfg: Config,
) -> list[dict]:
    """
    Identify recurring exact-amount series that look like installment plans.

    A group qualifies when:
    - the exact rounded amount appears at least cfg.recurring_min_occurrences times, and
    - most inter-payment gaps sit in [cfg.recurring_min_gap_days, cfg.recurring_max_gap_days].
    """
    groups: list[dict] = []
    if history.empty:
        return groups

    work = history.copy()
    work["amount_round"] = work["amount"].round(2)

    for amount, g in work.groupby("amount_round", sort=False):
        g = g.sort_values("date")
        if len(g) < cfg.recurring_min_occurrences:
            continue

        gaps = g["date"].diff().dt.days.dropna().to_numpy(dtype=float)
        if gaps.size == 0:
            continue

        in_band_ratio = float(np.mean((gaps >= cfg.recurring_min_gap_days) & (gaps <= cfg.recurring_max_gap_days)))
        if in_band_ratio < cfg.recurring_gap_success_ratio:
            continue

        last_date = g["date"].max()
        active = (as_of_date - last_date).days <= cfg.active_plan_recent_days
        groups.append(
            {
                "amount": float(amount),
                "occurrences": int(len(g)),
                "start_date": g["date"].min(),
                "end_date": last_date,
                "avg_gap_days": float(np.mean(gaps)),
                "gap_cv": safe_cv(gaps),
                "active": bool(active),
                "in_band_ratio": in_band_ratio,
            }
        )

    return groups


def engineer_features(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    df = df.sort_values(["card_key", "date", "amount", "merchant_norm"]).copy()
    dataset_as_of = df["date"].max()
    recent_cutoff = dataset_as_of - pd.Timedelta(days=cfg.recent_window_days)
    prior_cutoff = recent_cutoff - pd.Timedelta(days=cfg.prior_window_days)

    records: list[dict] = []

    for card_key, g in df.groupby("card_key", sort=False):
        g = g.sort_values("date").copy()
        txns = int(len(g))
        total_amt = float(g["amount"].sum())
        avg_amt = float(g["amount"].mean())
        median_amt = float(g["amount"].median())
        max_amt = float(g["amount"].max())
        min_amt = float(g["amount"].min())
        unique_dates = int(g["date"].dt.date.nunique())
        first_date = g["date"].min()
        last_date = g["date"].max()
        span_days = int((last_date - first_date).days)

        gaps = g["date"].diff().dt.days.dropna().tolist()
        avg_gap_days = float(np.mean(gaps)) if gaps else 0.0
        gap_cv = safe_cv(gaps)
        amount_cv = safe_cv(g["amount"].tolist())

        high_ticket_count = int((g["amount"] >= cfg.high_ticket_threshold).sum())
        very_high_ticket_count = int((g["amount"] >= cfg.very_high_ticket_threshold).sum())
        small_ticket_count = int((g["amount"] <= cfg.small_ticket_threshold).sum())
        small_ticket_share = float(small_ticket_count / txns) if txns else 0.0

        same_day_counts = g.groupby(g["date"].dt.date).size()
        max_same_day_txns = int(same_day_counts.max()) if not same_day_counts.empty else 0
        same_day_4plus_days = int((same_day_counts >= 4).sum()) if not same_day_counts.empty else 0
        same_day_5plus_days = int((same_day_counts >= 5).sum()) if not same_day_counts.empty else 0

        recurring_groups = get_recurring_amount_groups(g[["date", "amount"]], dataset_as_of, cfg)
        recurring_plan_count = len(recurring_groups)
        active_plan_count = sum(int(x["active"]) for x in recurring_groups)
        recurring_amount_total = float(sum(x["amount"] for x in recurring_groups if x["active"]))
        recurring_gap_cv = float(np.mean([x["gap_cv"] for x in recurring_groups])) if recurring_groups else 0.0
        recurring_avg_gap = float(np.mean([x["avg_gap_days"] for x in recurring_groups])) if recurring_groups else 0.0
        recurring_max_occurrences = max((x["occurrences"] for x in recurring_groups), default=0)

        recent = g[g["date"] > recent_cutoff]
        prior = g[(g["date"] > prior_cutoff) & (g["date"] <= recent_cutoff)]

        recent_txns = int(len(recent))
        prior_txns = int(len(prior))
        recent_amt = float(recent["amount"].sum())
        prior_amt = float(prior["amount"].sum())
        recent_high_ticket_count = int((recent["amount"] >= cfg.high_ticket_threshold).sum())
        recent_distinct_codes = int(recent["code"].dropna().nunique())
        total_distinct_codes = int(g["code"].dropna().nunique())
        txn_type_diversity = int(g["txn_type"].nunique())

        txn_growth_ratio = float((recent_txns + 1) / (prior_txns + 1))
        amt_growth_ratio = float((recent_amt + 1.0) / (prior_amt + 1.0))
        dormant_then_surge = int(prior_txns <= 1 and recent_txns >= 4)
        recent_new_high_ticket = int(recent_high_ticket_count >= 1 and prior_txns >= 0)

        records.append(
            {
                "card_key": card_key,
                "txn_count": txns,
                "unique_dates": unique_dates,
                "first_date": first_date,
                "last_date": last_date,
                "span_days": span_days,
                "days_since_last_txn": int((dataset_as_of - last_date).days),
                "total_amount": round(total_amt, 2),
                "avg_amount": round(avg_amt, 2),
                "median_amount": round(median_amt, 2),
                "max_amount": round(max_amt, 2),
                "min_amount": round(min_amt, 2),
                "amount_cv": round(amount_cv, 4),
                "avg_gap_days": round(avg_gap_days, 2),
                "gap_cv": round(gap_cv, 4),
                "small_ticket_count": small_ticket_count,
                "small_ticket_share": round(small_ticket_share, 4),
                "high_ticket_count": high_ticket_count,
                "very_high_ticket_count": very_high_ticket_count,
                "max_same_day_txns": max_same_day_txns,
                "same_day_4plus_days": same_day_4plus_days,
                "same_day_5plus_days": same_day_5plus_days,
                "recurring_plan_count": recurring_plan_count,
                "active_plan_count": active_plan_count,
                "recurring_amount_total": round(recurring_amount_total, 2),
                "recurring_gap_cv": round(recurring_gap_cv, 4),
                "recurring_avg_gap": round(recurring_avg_gap, 2),
                "recurring_max_occurrences": recurring_max_occurrences,
                "recent_txns": recent_txns,
                "prior_txns": prior_txns,
                "recent_amount": round(recent_amt, 2),
                "prior_amount": round(prior_amt, 2),
                "recent_high_ticket_count": recent_high_ticket_count,
                "recent_distinct_codes": recent_distinct_codes,
                "distinct_codes": total_distinct_codes,
                "txn_type_diversity": txn_type_diversity,
                "txn_growth_ratio": round(txn_growth_ratio, 4),
                "amt_growth_ratio": round(amt_growth_ratio, 4),
                "dormant_then_surge": dormant_then_surge,
                "recent_new_high_ticket": recent_new_high_ticket,
            }
        )

    return pd.DataFrame.from_records(records)


def assign_segment(row: pd.Series, cfg: Config) -> tuple[str, str]:
    reasons: list[str] = []

    rising_stress = (
        row["txn_count"] >= cfg.min_txns_for_irregular
        and (
            row["txn_growth_ratio"] >= cfg.rising_txn_ratio
            or row["amt_growth_ratio"] >= cfg.rising_txn_ratio
            or row["dormant_then_surge"] == 1
        )
        and (
            row["gap_cv"] >= cfg.irregular_gap_cv_threshold
            or row["amount_cv"] >= cfg.irregular_amount_cv_threshold
            or row["recent_high_ticket_count"] >= 1
        )
    )

    if rising_stress:
        if row["txn_growth_ratio"] >= cfg.rising_txn_ratio:
            reasons.append(f"recent txns up {row['txn_growth_ratio']:.2f}x vs prior window")
        if row["amt_growth_ratio"] >= cfg.rising_txn_ratio:
            reasons.append(f"recent dollars up {row['amt_growth_ratio']:.2f}x")
        if row["gap_cv"] >= cfg.irregular_gap_cv_threshold:
            reasons.append(f"gap CV {row['gap_cv']:.2f} indicates irregular cadence")
        if row["amount_cv"] >= cfg.irregular_amount_cv_threshold:
            reasons.append(f"amount CV {row['amount_cv']:.2f} indicates volatile payment sizes")
        if row["recent_high_ticket_count"] >= 1:
            reasons.append("recent high-ticket activity present")
        return "Rising-stress / irregular users", "; ".join(reasons)

    stacker = (
        row["active_plan_count"] >= cfg.active_plan_stack_threshold
        or row["max_same_day_txns"] >= cfg.same_day_stack_threshold
        or (row["distinct_codes"] >= cfg.code_diversity_stack_threshold and row["txn_count"] >= 12)
    )
    if stacker:
        if row["active_plan_count"] >= cfg.active_plan_stack_threshold:
            reasons.append(f"{int(row['active_plan_count'])} active recurring plans inferred")
        if row["max_same_day_txns"] >= cfg.same_day_stack_threshold:
            reasons.append(f"up to {int(row['max_same_day_txns'])} same-day txns")
        if row["distinct_codes"] >= cfg.code_diversity_stack_threshold:
            reasons.append(f"high code diversity ({int(row['distinct_codes'])})")
        return "Stackers / complex obligation users", "; ".join(reasons)

    high_ticket = (
        row["very_high_ticket_count"] >= 1
        or row["high_ticket_count"] >= 2
        or (row["max_amount"] >= cfg.high_ticket_threshold and row["total_amount"] >= 500.0)
    )
    if high_ticket:
        if row["very_high_ticket_count"] >= 1:
            reasons.append(f"very high-ticket txn observed (max ${row['max_amount']:.2f})")
        elif row["high_ticket_count"] >= 2:
            reasons.append(f"{int(row['high_ticket_count'])} txns >= ${cfg.high_ticket_threshold:.0f}")
        else:
            reasons.append(f"max txn ${row['max_amount']:.2f} with substantial total financed dollars")
        return "High-ticket financers", "; ".join(reasons)

    stable_installment = (
        row["active_plan_count"] >= 1
        and row["recurring_max_occurrences"] >= cfg.recurring_min_occurrences
        and row["gap_cv"] < cfg.irregular_gap_cv_threshold
        and row["amount_cv"] < cfg.irregular_amount_cv_threshold
        and row["txn_growth_ratio"] < cfg.rising_txn_ratio
        and row["max_same_day_txns"] < cfg.same_day_stack_threshold
    )
    if stable_installment:
        reasons.append(f"{int(row['active_plan_count'])} active recurring plan(s)")
        reasons.append(f"recurring cadence avg gap {row['recurring_avg_gap']:.1f} days")
        reasons.append("payment sizes and cadence look relatively stable")
        return "Stable installment users", "; ".join(reasons)

    occasional_small = (
        row["txn_count"] <= 4
        and row["median_amount"] <= cfg.small_ticket_threshold
        and row["high_ticket_count"] == 0
        and row["active_plan_count"] == 0
    ) or (
        row["txn_count"] <= 6
        and row["small_ticket_share"] >= 0.75
        and row["high_ticket_count"] == 0
        and row["active_plan_count"] == 0
    )
    if occasional_small:
        reasons.append(f"low frequency ({int(row['txn_count'])} txns)")
        reasons.append(f"mostly small-ticket behavior (median ${row['median_amount']:.2f})")
        return "Occasional small-ticket users", "; ".join(reasons)

    # Default / catch-all:
    # If not clearly occasional and not clearly stable, err toward the more operationally useful label.
    if row["active_plan_count"] >= 1:
        reasons.append("some recurring-plan evidence, but not stable enough for stable-installment")
        reasons.append("monitor for complexity or irregularity")
        return "Rising-stress / irregular users", "; ".join(reasons)

    reasons.append("moderate activity that does not fit cleaner installment or small-ticket patterns")
    return "Occasional small-ticket users", "; ".join(reasons)


def load_and_prepare(input_path: str, args: argparse.Namespace) -> pd.DataFrame:
    df = pd.read_csv(input_path)

    required = [args.card_col, args.date_col, args.merchant_col, args.amount_col]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Available columns: {list(df.columns)}")

    work = df[[args.card_col, args.date_col, args.merchant_col, args.amount_col]].copy()
    work.columns = ["card_key", "date", "merchant_name", "amount"]

    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["amount"] = pd.to_numeric(work["amount"], errors="coerce")
    work["merchant_norm"] = work["merchant_name"].map(normalize_merchant_name)
    work["txn_type"] = work["merchant_norm"].map(classify_txn_type)
    work["code"] = work["merchant_norm"].map(extract_code)

    work = work.dropna(subset=["card_key", "date", "amount"]).copy()
    work = work[work["amount"] >= 0].copy()

    return work


def main() -> None:
    args = parse_args()
    cfg = Config()

    input_path = Path(args.input)
    output_path = Path(args.output)
    feature_output_path = Path(args.feature_output)

    df = load_and_prepare(str(input_path), args)
    features = engineer_features(df, cfg)

    segs = features.apply(lambda row: assign_segment(row, cfg), axis=1, result_type="expand")
    segs.columns = ["segment", "segment_reason"]
    result = pd.concat([features, segs], axis=1)

    # Friendly ordering
    segment_order = {
        "Occasional small-ticket users": 1,
        "Stable installment users": 2,
        "High-ticket financers": 3,
        "Stackers / complex obligation users": 4,
        "Rising-stress / irregular users": 5,
    }
    result["segment_sort"] = result["segment"].map(segment_order).fillna(99)
    result = result.sort_values(["segment_sort", "card_key"]).drop(columns=["segment_sort"])

    # Compact output + detailed feature file
    segment_cols = [
        "card_key",
        "segment",
        "segment_reason",
        "txn_count",
        "total_amount",
        "avg_amount",
        "median_amount",
        "max_amount",
        "active_plan_count",
        "high_ticket_count",
        "max_same_day_txns",
        "distinct_codes",
        "txn_growth_ratio",
        "amt_growth_ratio",
        "first_date",
        "last_date",
    ]
    result[segment_cols].to_csv(output_path, index=False)
    result.to_csv(feature_output_path, index=False)

    summary = result["segment"].value_counts(dropna=False).rename_axis("segment").reset_index(name="card_keys")
    print("Segmentation complete.")
    print(f"Input:   {input_path}")
    print(f"Output:  {output_path}")
    print(f"Details: {feature_output_path}")
    print("\nSegment distribution:")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
