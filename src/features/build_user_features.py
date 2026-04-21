"""Build the segmentation feature mart at the ``(user_id, game_id)`` grain.

Chosen grain: one row per observed ``(user_id, game_id)`` install from ``users.csv``.

Reasoning:
- The data audit confirmed that users can appear in multiple games, so ``user_id``
  alone is not a safe segmentation entity for this project.
- ``(user_id, game_id)`` is the natural install grain available in the users table.
- Activity tables only expose ``user_id``. Because they do not contain ``game_id``,
  behavioral features below are computed at the portfolio ``user_id`` level and then
  attached to each observed user-game row without attempting unsupported attribution.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.data.load_data import load_all_datasets
from src.utils.config import PROCESSED_DATA_DIR, ensure_output_dirs

FEATURE_GRAIN = ("user_id", "game_id")
ROLLING_WINDOW_DAYS = 30
USER_FEATURES_PATH = PROCESSED_DATA_DIR / "user_features.parquet"

SKEWED_FEATURES = [
    "games_installed_count",
    "days_since_game_install",
    "sessions_total",
    "active_days",
    "total_session_duration_hours",
    "levels_completed_total",
    "levels_failed_total",
    "transaction_count",
    "total_revenue_usd",
    "ad_watched_count",
    "offer_shown_count",
]

INTEGER_FEATURES = [
    "games_installed_count",
    "multi_game_user_flag",
    "install_rank_for_user",
    "is_first_game_install_flag",
    "days_since_game_install",
    "days_since_first_portfolio_install",
    "days_since_last_session",
    "days_since_last_purchase",
    "rfm_recency_days",
    "rfm_frequency_sessions",
    "sessions_total",
    "active_days",
    "sessions_last_30d",
    "sessions_prev_30d",
    "levels_completed_total",
    "levels_failed_total",
    "payer_flag",
    "transaction_count",
    "positive_revenue_transaction_count",
    "trial_started_flag",
    "trial_transaction_count",
    "trial_converted_flag",
    "subscription_payer_flag",
    "subscription_transaction_count",
    "ad_watched_count",
    "offer_shown_count",
    "offer_purchased_event_count",
]


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator = numerator.astype(float)
    denominator = denominator.astype(float)
    values = np.divide(
        numerator.to_numpy(),
        denominator.to_numpy(),
        out=np.zeros(len(numerator), dtype=float),
        where=denominator.to_numpy() != 0,
    )
    return pd.Series(values, index=numerator.index, dtype="float64")


def _normalize_to_utc_day(series: pd.Series) -> pd.Series:
    if getattr(series.dt, "tz", None) is None:
        return series.dt.normalize()
    return series.dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()


def _days_between(later: pd.Timestamp, earlier: pd.Series) -> pd.Series:
    return (later - earlier).dt.days.astype("Int64")


def _get_snapshot_day(
    users: pd.DataFrame,
    sessions: pd.DataFrame,
    transactions: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.Timestamp:
    candidates = [
        pd.Timestamp(users["install_date"].max()).normalize(),
        _normalize_to_utc_day(sessions["session_end"]).max(),
        _normalize_to_utc_day(transactions["transaction_date"]).max(),
        _normalize_to_utc_day(events["event_timestamp"]).max(),
    ]
    return max(candidates)


def clean_sessions(sessions: pd.DataFrame) -> pd.DataFrame:
    cleaned = sessions.copy()
    cleaned["session_duration_seconds"] = (
        cleaned["session_end"] - cleaned["session_start"]
    ).dt.total_seconds()
    cleaned = cleaned.loc[cleaned["session_duration_seconds"] >= 0].copy()
    cleaned["session_day"] = _normalize_to_utc_day(cleaned["session_start"])
    cleaned["session_duration_minutes"] = cleaned["session_duration_seconds"] / 60.0
    cleaned["session_duration_hours"] = cleaned["session_duration_seconds"] / 3600.0
    cleaned["levels_completed"] = cleaned["levels_completed"].fillna(0)
    cleaned["levels_failed"] = cleaned["levels_failed"].fillna(0)
    return cleaned


def clean_transactions(transactions: pd.DataFrame) -> pd.DataFrame:
    cleaned = transactions.drop_duplicates(
        subset=["user_id", "transaction_date", "product_type", "revenue_usd", "is_trial"]
    ).copy()
    cleaned["positive_revenue_flag"] = cleaned["revenue_usd"] > 0
    cleaned["subscription_flag"] = cleaned["product_type"].str.startswith("subscription")
    cleaned["trial_flag"] = cleaned["is_trial"].fillna(False).astype(bool)
    cleaned["transaction_day"] = _normalize_to_utc_day(cleaned["transaction_date"])
    return cleaned


def clean_events(events: pd.DataFrame) -> pd.DataFrame:
    cleaned = events.drop_duplicates(
        subset=["user_id", "event_timestamp", "event_name", "event_params"]
    ).copy()
    cleaned["event_day"] = _normalize_to_utc_day(cleaned["event_timestamp"])
    return cleaned


def build_user_game_base(users: pd.DataFrame, snapshot_day: pd.Timestamp) -> pd.DataFrame:
    users_clean = users.copy()
    users_clean["country"] = users_clean["country"].fillna("Unknown")
    users_clean["install_source"] = users_clean["install_source"].fillna("Unknown")
    users_clean["device_os"] = users_clean["device_os"].fillna("Unknown")

    base = (
        users_clean.sort_values(["user_id", "install_date", "game_id"])
        .drop_duplicates(["user_id", "game_id"], keep="first")
        .copy()
    )

    user_rollup = (
        base.groupby("user_id", as_index=False)
        .agg(
            first_portfolio_install_date=("install_date", "min"),
            games_installed_count=("game_id", "nunique"),
        )
    )

    base = base.merge(user_rollup, on="user_id", how="left")
    base["multi_game_user_flag"] = (base["games_installed_count"] > 1).astype("int8")
    base["install_rank_for_user"] = (
        base.groupby("user_id")["install_date"].rank(method="dense").astype("Int64")
    )
    base["is_first_game_install_flag"] = (base["install_rank_for_user"] == 1).astype("int8")
    base["days_since_game_install"] = _days_between(snapshot_day, base["install_date"])
    base["days_since_first_portfolio_install"] = _days_between(
        snapshot_day, base["first_portfolio_install_date"]
    )
    return base


def build_session_features(sessions: pd.DataFrame, snapshot_day: pd.Timestamp) -> pd.DataFrame:
    recent_window_start = snapshot_day - pd.Timedelta(days=ROLLING_WINDOW_DAYS)
    prior_window_start = snapshot_day - pd.Timedelta(days=2 * ROLLING_WINDOW_DAYS)

    recent_mask = sessions["session_day"] >= recent_window_start
    prior_mask = (sessions["session_day"] >= prior_window_start) & (sessions["session_day"] < recent_window_start)

    summary = sessions.groupby("user_id").agg(
        sessions_total=("session_id", "nunique"),
        active_days=("session_day", "nunique"),
        last_session_day=("session_day", "max"),
        total_session_duration_hours=("session_duration_hours", "sum"),
        avg_session_duration_min=("session_duration_minutes", "mean"),
        levels_completed_total=("levels_completed", "sum"),
        levels_failed_total=("levels_failed", "sum"),
    )

    recent_activity = sessions.loc[recent_mask].groupby("user_id").agg(
        sessions_last_30d=("session_id", "nunique"),
        session_duration_hours_last_30d=("session_duration_hours", "sum"),
    )
    prior_activity = sessions.loc[prior_mask].groupby("user_id").agg(
        sessions_prev_30d=("session_id", "nunique"),
        session_duration_hours_prev_30d=("session_duration_hours", "sum"),
    )

    features = summary.join(recent_activity, how="left").join(prior_activity, how="left").fillna(0)
    features["days_since_last_session"] = _days_between(snapshot_day, features["last_session_day"])
    features["sessions_per_active_day"] = _safe_divide(features["sessions_total"], features["active_days"])
    features["levels_attempted_total"] = features["levels_completed_total"] + features["levels_failed_total"]
    features["fail_rate"] = _safe_divide(features["levels_failed_total"], features["levels_attempted_total"])
    features["levels_completed_per_session"] = _safe_divide(
        features["levels_completed_total"], features["sessions_total"]
    )
    features["progression_velocity_levels_per_active_day"] = _safe_divide(
        features["levels_completed_total"], features["active_days"]
    )
    features["recent_session_share_60d"] = _safe_divide(
        features["sessions_last_30d"],
        features["sessions_last_30d"] + features["sessions_prev_30d"],
    )
    features["recent_playtime_share_60d"] = _safe_divide(
        features["session_duration_hours_last_30d"],
        features["session_duration_hours_last_30d"] + features["session_duration_hours_prev_30d"],
    )
    features["session_momentum_ratio_30d"] = _safe_divide(
        features["sessions_last_30d"], features["sessions_prev_30d"] + 1
    )
    features["rfm_recency_days"] = features["days_since_last_session"]
    features["rfm_frequency_sessions"] = features["sessions_total"]
    return features.drop(columns=["last_session_day", "levels_attempted_total"]).reset_index()


def _trial_conversion_flag(user_transactions: pd.DataFrame) -> int:
    trial_rows = user_transactions.loc[user_transactions["trial_flag"]]
    if trial_rows.empty:
        return 0

    first_trial_ts = trial_rows["transaction_date"].min()
    converted = (
        (user_transactions["transaction_date"] > first_trial_ts)
        & (user_transactions["positive_revenue_flag"])
        & (~user_transactions["trial_flag"])
    ).any()
    return int(converted)


def build_transaction_features(transactions: pd.DataFrame, snapshot_day: pd.Timestamp) -> pd.DataFrame:
    summary = transactions.groupby("user_id").agg(
        transaction_count=("transaction_date", "size"),
        positive_revenue_transaction_count=("positive_revenue_flag", "sum"),
        total_revenue_usd=("revenue_usd", "sum"),
        avg_revenue_per_transaction_usd=("revenue_usd", "mean"),
        last_purchase_day=("transaction_day", "max"),
        trial_transaction_count=("trial_flag", "sum"),
        subscription_transaction_count=("subscription_flag", "sum"),
        subscription_revenue_usd=("revenue_usd", lambda s: s[transactions.loc[s.index, "subscription_flag"]].sum()),
    )

    trial_conversion = (
        transactions.groupby("user_id")[["transaction_date", "positive_revenue_flag", "trial_flag"]]
        .apply(_trial_conversion_flag)
        .rename("trial_converted_flag")
        .astype("int8")
    )

    features = summary.join(trial_conversion, how="left")
    features["payer_flag"] = (features["total_revenue_usd"] > 0).astype("int8")
    features["trial_started_flag"] = (features["trial_transaction_count"] > 0).astype("int8")
    features["subscription_payer_flag"] = (features["subscription_revenue_usd"] > 0).astype("int8")
    features["days_since_last_purchase"] = _days_between(snapshot_day, features["last_purchase_day"])
    features["subscription_revenue_share"] = _safe_divide(
        features["subscription_revenue_usd"], features["total_revenue_usd"]
    )
    features["rfm_monetary_total_revenue_usd"] = features["total_revenue_usd"]
    return features.drop(columns=["last_purchase_day", "subscription_revenue_usd"]).reset_index()


def build_event_features(events: pd.DataFrame) -> pd.DataFrame:
    tracked_events = ["ad_watched", "offer_shown", "offer_purchased"]

    event_counts = (
        events.loc[events["event_name"].isin(tracked_events)]
        .groupby(["user_id", "event_name"])
        .size()
        .unstack(fill_value=0)
    )

    for event_name in tracked_events:
        if event_name not in event_counts.columns:
            event_counts[event_name] = 0

    return (
        event_counts.rename(
            columns={
                "ad_watched": "ad_watched_count",
                "offer_shown": "offer_shown_count",
                "offer_purchased": "offer_purchased_event_count",
            }
        )
        .reset_index()
    )


def apply_missing_value_strategy(features: pd.DataFrame) -> pd.DataFrame:
    result = features.copy()

    key_columns = {"user_id", "game_id", "install_date", "first_portfolio_install_date"}
    zero_fill_columns = [column for column in result.columns if column not in key_columns]
    result[zero_fill_columns] = result[zero_fill_columns].fillna(0)

    result["days_since_last_session"] = result["days_since_last_session"].where(
        result["sessions_total"] > 0,
        result["days_since_game_install"] + 1,
    )
    result["days_since_last_purchase"] = result["days_since_last_purchase"].where(
        result["transaction_count"] > 0,
        result["days_since_game_install"] + 1,
    )

    for column in INTEGER_FEATURES:
        if column in result.columns:
            result[column] = result[column].round().astype("Int64")

    return result


def apply_robustness_transforms(features: pd.DataFrame) -> pd.DataFrame:
    result = features.copy()
    for column in SKEWED_FEATURES:
        result[f"log1p_{column}"] = np.log1p(result[column].clip(lower=0))
    return result


def build_user_feature_mart() -> pd.DataFrame:
    datasets = load_all_datasets()
    users = datasets["users"]
    sessions = clean_sessions(datasets["sessions"])
    transactions = clean_transactions(datasets["transactions"])
    events = clean_events(datasets["events"])

    snapshot_day = _get_snapshot_day(users=users, sessions=sessions, transactions=transactions, events=events)

    user_game_base = build_user_game_base(users=users, snapshot_day=snapshot_day)
    session_features = build_session_features(sessions=sessions, snapshot_day=snapshot_day)
    transaction_features = build_transaction_features(transactions=transactions, snapshot_day=snapshot_day)
    event_features = build_event_features(events=events)

    features = (
        user_game_base.merge(session_features, on="user_id", how="left")
        .merge(transaction_features, on="user_id", how="left")
        .merge(event_features, on="user_id", how="left")
    )
    features = apply_missing_value_strategy(features)

    features["ad_watched_per_session"] = _safe_divide(features["ad_watched_count"], features["sessions_total"])
    features["offer_purchase_event_rate"] = _safe_divide(
        features["offer_purchased_event_count"], features["offer_shown_count"]
    )
    features = apply_robustness_transforms(features)

    ordered_columns = [
        "user_id",
        "game_id",
        "install_date",
        "install_source",
        "device_os",
        "country",
        "games_installed_count",
        "multi_game_user_flag",
        "install_rank_for_user",
        "is_first_game_install_flag",
        "days_since_game_install",
        "days_since_first_portfolio_install",
        "days_since_last_session",
        "days_since_last_purchase",
        "rfm_recency_days",
        "rfm_frequency_sessions",
        "rfm_monetary_total_revenue_usd",
        "sessions_total",
        "active_days",
        "sessions_per_active_day",
        "total_session_duration_hours",
        "avg_session_duration_min",
        "sessions_last_30d",
        "sessions_prev_30d",
        "session_duration_hours_last_30d",
        "session_duration_hours_prev_30d",
        "recent_session_share_60d",
        "recent_playtime_share_60d",
        "session_momentum_ratio_30d",
        "levels_completed_total",
        "levels_failed_total",
        "fail_rate",
        "progression_velocity_levels_per_active_day",
        "levels_completed_per_session",
        "payer_flag",
        "transaction_count",
        "positive_revenue_transaction_count",
        "total_revenue_usd",
        "avg_revenue_per_transaction_usd",
        "trial_started_flag",
        "trial_transaction_count",
        "trial_converted_flag",
        "subscription_payer_flag",
        "subscription_transaction_count",
        "subscription_revenue_share",
        "ad_watched_count",
        "ad_watched_per_session",
        "offer_shown_count",
        "offer_purchased_event_count",
        "offer_purchase_event_rate",
    ] + [f"log1p_{column}" for column in SKEWED_FEATURES]

    return features.loc[:, ordered_columns].sort_values(["user_id", "game_id"]).reset_index(drop=True)


def save_user_feature_mart(features: pd.DataFrame, output_path: Path = USER_FEATURES_PATH) -> Path:
    ensure_output_dirs()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(output_path, index=False)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the user-game segmentation feature mart.")
    parser.add_argument(
        "--output-path",
        type=Path,
        default=USER_FEATURES_PATH,
        help="Where to write the parquet feature table.",
    )
    args = parser.parse_args()

    feature_mart = build_user_feature_mart()
    save_user_feature_mart(feature_mart, output_path=args.output_path)
    print(f"Saved {len(feature_mart):,} rows and {feature_mart.shape[1]:,} columns to {args.output_path}")


if __name__ == "__main__":
    main()
