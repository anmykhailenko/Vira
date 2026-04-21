from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, PercentFormatter
from pandas import DataFrame, Series

from src.data.load_data import load_sessions, load_transactions, load_users
from src.utils.config import FIGURES_DIR

FIGURE_DIR = FIGURES_DIR / "eda"
RETENTION_OFFSETS = [1, 7, 14, 30, 60]


def ensure_figure_dir() -> Path:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    return FIGURE_DIR


def load_cleaned_data() -> tuple[DataFrame, DataFrame, DataFrame]:
    users = load_users().assign(country=lambda df: df["country"].fillna("Unknown"))
    sessions = load_sessions().copy()
    sessions = sessions.assign(
        session_duration_sec=(sessions["session_end"] - sessions["session_start"]).dt.total_seconds()
    )
    sessions = sessions[sessions["session_duration_sec"] >= 0].copy()
    transactions = load_transactions().drop_duplicates(
        subset=["user_id", "transaction_date", "product_type", "revenue_usd", "is_trial"]
    )
    return users, sessions, transactions


def build_portfolio_user_profile(users: DataFrame) -> DataFrame:
    earliest = users.sort_values(["user_id", "install_date"]).drop_duplicates("user_id", keep="first")
    earliest = earliest.assign(country=earliest["country"].fillna("Unknown"))
    return earliest


def summarize_dataset_profiles(users: DataFrame, sessions: DataFrame, transactions: DataFrame) -> dict[str, int | str]:
    raw_users = load_users()
    raw_sessions = load_sessions()
    raw_transactions = load_transactions()
    missing_country = int(raw_users["country"].isna().sum())
    duplicate_user_id = int(raw_users["user_id"].duplicated().sum())
    negative_sessions = int((raw_sessions["session_end"] < raw_sessions["session_start"]).sum())
    duplicated_transactions = int(
        raw_transactions.duplicated(
            subset=["user_id", "transaction_date", "product_type", "revenue_usd", "is_trial"]
        ).sum()
    )
    return {
        "raw_users_rows": len(raw_users),
        "raw_sessions_rows": len(raw_sessions),
        "raw_transactions_rows": len(raw_transactions),
        "cleaned_sessions_rows": len(sessions),
        "raw_unique_user_ids": int(raw_users["user_id"].nunique()),
        "duplicate_user_id_rows": duplicate_user_id,
        "missing_country_values": missing_country,
        "negative_session_durations": negative_sessions,
        "exact_duplicate_transactions": duplicated_transactions,
        "install_date_range": f"{raw_users['install_date'].min().date()} to {raw_users['install_date'].max().date()}",
    }


def compute_dau_wau_mau_stickiness(sessions: DataFrame) -> DataFrame:
    activity = (
        sessions.assign(session_date=sessions["session_start"].dt.normalize())
        .groupby("session_date")["user_id"]
        .agg(lambda values: set(values))
        .sort_index()
    )
    daily_active = activity.map(len).rename("dau")
    weekly_active = _rolling_unique_user_count(activity, window=7).rename("wau")
    monthly_active = _rolling_unique_user_count(activity, window=30).rename("mau")
    stickiness = (daily_active / monthly_active).rename("stickiness")
    return pd.concat([daily_active, weekly_active, monthly_active, stickiness], axis=1)


def _rolling_unique_user_count(user_sets: Series, window: int) -> Series:
    result = []
    values = list(user_sets)
    for index in range(len(values)):
        start = max(0, index - window + 1)
        window_union = set().union(*values[start : index + 1])
        result.append(len(window_union))
    return Series(result, index=user_sets.index)


def compute_retention_by_dimension(
    sessions: DataFrame, users: DataFrame, dimension: str = "install_source", offsets: list[int] | None = None
) -> DataFrame:
    offsets = offsets or RETENTION_OFFSETS
    users_portfolio = build_portfolio_user_profile(users)
    users_portfolio = users_portfolio.assign(install_date=lambda df: df["install_date"].dt.tz_localize("UTC"))
    sessions = sessions.merge(
        users_portfolio[["user_id", "install_date", dimension]], on="user_id", how="inner"
    )
    sessions = sessions.assign(
        days_since_install=(
            sessions["session_start"].dt.normalize() - sessions["install_date"].dt.normalize()
        ).dt.days
    )
    sessions = sessions[(sessions["days_since_install"] >= 0) & (sessions["days_since_install"] <= max(offsets))].copy()
    sessions = sessions.drop_duplicates(subset=[dimension, "user_id", "days_since_install"])
    cohort_counts = users_portfolio.groupby(dimension)["user_id"].nunique()
    retention = (
        sessions.groupby([dimension, "days_since_install"])["user_id"]
        .nunique()
        .unstack(fill_value=0)
        .reindex(columns=offsets, fill_value=0)
        .divide(cohort_counts, axis=0)
    )
    retention.columns = [f"D{offset}" for offset in offsets]
    return retention


def compute_revenue_metrics(users: DataFrame, transactions: DataFrame) -> dict[str, float | int]:
    users_portfolio = build_portfolio_user_profile(users)
    revenue_per_user = transactions.groupby("user_id")["revenue_usd"].sum()
    payer_ids = revenue_per_user[revenue_per_user > 0].index
    total_revenue = float(revenue_per_user.sum())
    total_users = int(users_portfolio["user_id"].nunique())
    payers = len(payer_ids)
    return {
        "total_revenue_usd": total_revenue,
        "total_users": total_users,
        "payer_count": payers,
        "payer_conversion_rate": payers / total_users if total_users else 0.0,
        "arppu": total_revenue / payers if payers else 0.0,
        "revenue_median": float(revenue_per_user[revenue_per_user > 0].median()) if payers else 0.0,
        "revenue_95th_pct": float(revenue_per_user[revenue_per_user > 0].quantile(0.95)) if payers else 0.0,
        "revenue_top_5_percent_share": float(
            revenue_per_user[revenue_per_user > 0].sort_values(ascending=False).head(int(max(1, payers * 0.05))).sum()
            / total_revenue
        ) if total_revenue else 0.0,
    }


def compute_session_distributions(sessions: DataFrame) -> dict[str, float | Series]:
    sessions_per_user = sessions.groupby("user_id").size()
    durations = sessions["session_duration_sec"].clip(lower=0)
    return {
        "sessions_per_user": sessions_per_user,
        "session_duration_sec": durations,
        "sessions_per_user_summary": sessions_per_user.describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99]).to_dict(),
        "session_duration_summary": durations.describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99]).to_dict(),
    }


def plot_dau_wau_mau(kpi: DataFrame, figure_path: Path | None = None) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(kpi.index, kpi["dau"], label="DAU", linewidth=1.5)
    ax.plot(kpi.index, kpi["wau"], label="WAU", linewidth=1.5)
    ax.plot(kpi.index, kpi["mau"], label="MAU", linewidth=1.5)
    ax.set_title("Daily, Weekly, and Monthly Active Users")
    ax.set_ylabel("Unique active users")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.35)
    ax2 = ax.twinx()
    ax2.plot(kpi.index, kpi["stickiness"], color="#d62728", linestyle="--", linewidth=1.5, label="DAU / MAU")
    ax2.set_ylabel("Stickiness ratio")
    ax2.set_ylim(0, 1)
    ax2.legend(loc="upper right")
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    path = ensure_figure_dir() / (figure_path.name if figure_path else "eda_dau_wau_mau.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def plot_retention(retention: DataFrame, figure_path: Path | None = None) -> Path:
    checkpoint_labels = list(retention.columns)
    x_positions = np.arange(len(checkpoint_labels))
    retention_for_plot = retention.sort_values("D30", ascending=False)
    y_min = float(retention_for_plot.min().min())
    y_max = float(retention_for_plot.max().max())
    y_padding = max(0.01, (y_max - y_min) * 0.15)
    y_lower = max(0.0, y_min - y_padding)
    y_upper = min(1.0, y_max + y_padding)

    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    colors = plt.get_cmap("tab10")(np.linspace(0, 1, len(retention_for_plot)))
    for color, (install_source, values) in zip(colors, retention_for_plot.iterrows()):
        y_values = values.to_numpy(dtype=float)
        ax.plot(
            x_positions,
            y_values,
            marker="o",
            linewidth=2.2,
            markersize=6.5,
            color=color,
            markerfacecolor=color,
            markeredgecolor="white",
            markeredgewidth=1.2,
            label=install_source,
            zorder=3,
        )
        for x_value, y_value in zip(x_positions, y_values):
            ax.annotate(
                f"{y_value:.1%}",
                (x_value, y_value),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                color=color,
            )

    ax.set_title("Cohort Retention by Install Source")
    ax.set_xlabel("Retention checkpoint")
    ax.set_ylabel("Retention rate")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(checkpoint_labels)
    ax.set_xlim(-0.25, len(checkpoint_labels) - 0.75)
    ax.set_ylim(y_lower, y_upper)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.grid(axis="y", alpha=0.3)
    ax.grid(axis="x", alpha=0.12, linestyle="--")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(title="Install source", loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3, frameon=False)
    fig.tight_layout()
    path = ensure_figure_dir() / (figure_path.name if figure_path else "eda_retention_install_source.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def plot_revenue_distribution(transactions: DataFrame, users: DataFrame, figure_path: Path | None = None) -> Path:
    revenue_per_user = transactions.groupby("user_id")["revenue_usd"].sum()
    payers = revenue_per_user[revenue_per_user > 0]
    fig, (ax_hist, ax_cdf) = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={"width_ratios": [1.4, 1]})

    log_bins = np.geomspace(float(payers.min()), float(payers.max()), 28)
    ax_hist.hist(payers, bins=log_bins, color="#1f77b4", edgecolor="white", alpha=0.9)
    ax_hist.set_xscale("log")
    ax_hist.set_title("Revenue per Paying User")
    ax_hist.set_xlabel("Total revenue per user (USD, log scale)")
    ax_hist.set_ylabel("Number of paying users")
    ax_hist.grid(alpha=0.25, which="both", axis="x")
    ax_hist.grid(alpha=0.18, axis="y")

    sorted_revenue = np.sort(payers.to_numpy(dtype=float))
    cdf = np.arange(1, len(sorted_revenue) + 1) / len(sorted_revenue)
    median_value = float(np.median(sorted_revenue))
    p95_value = float(np.quantile(sorted_revenue, 0.95))
    ax_cdf.plot(sorted_revenue, cdf, color="#ff7f0e", linewidth=2.2)
    ax_cdf.axvline(median_value, color="#555555", linestyle="--", linewidth=1.1, label=f"Median ${median_value:,.0f}")
    ax_cdf.axvline(p95_value, color="#c44e52", linestyle="--", linewidth=1.1, label=f"P95 ${p95_value:,.0f}")
    ax_cdf.set_xscale("log")
    ax_cdf.set_title("Payer Revenue CDF")
    ax_cdf.set_xlabel("Total revenue per user (USD, log scale)")
    ax_cdf.set_ylabel("Cumulative share of payers")
    ax_cdf.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax_cdf.grid(alpha=0.25, which="both", axis="x")
    ax_cdf.grid(alpha=0.18, axis="y")
    ax_cdf.legend(loc="lower right", frameon=False)

    dollar_formatter = FuncFormatter(lambda value, _: f"${value:,.0f}")
    ax_hist.xaxis.set_major_formatter(dollar_formatter)
    ax_cdf.xaxis.set_major_formatter(dollar_formatter)
    for axis in (ax_hist, ax_cdf):
        for spine in ("top", "right"):
            axis.spines[spine].set_visible(False)

    fig.tight_layout()
    path = ensure_figure_dir() / (figure_path.name if figure_path else "eda_revenue_per_user.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def plot_revenue_concentration(transactions: DataFrame, users: DataFrame, figure_path: Path | None = None) -> Path:
    revenue_per_user = transactions.groupby("user_id")["revenue_usd"].sum()
    payers = revenue_per_user[revenue_per_user > 0].sort_values()
    cumulative_share = payers.cumsum() / payers.sum()
    percentiles = np.linspace(0, 100, len(payers), endpoint=False) + 100 / len(payers)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(percentiles, cumulative_share, color="#ff7f0e", linewidth=2)
    ax.set_title("Paying User Revenue Concentration")
    ax.set_xlabel("Paying user percentile")
    ax.set_ylabel("Cumulative share of revenue")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1)
    fig.tight_layout()
    path = ensure_figure_dir() / (figure_path.name if figure_path else "eda_revenue_concentration.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def plot_session_frequency(sessions: DataFrame, figure_path: Path | None = None) -> Path:
    counts = sessions.groupby("user_id").size()
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(counts.clip(upper=counts.quantile(0.99)), bins=40, color="#2ca02c", edgecolor="black")
    ax.set_title("Session Frequency Distribution (Top 99th percentile)")
    ax.set_xlabel("Sessions per user")
    ax.set_ylabel("Number of users")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = ensure_figure_dir() / (figure_path.name if figure_path else "eda_session_frequency.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def plot_session_duration(sessions: DataFrame, figure_path: Path | None = None) -> Path:
    durations = sessions["session_duration_sec"].clip(lower=1)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(durations.clip(upper=durations.quantile(0.99)), bins=40, color="#9467bd", edgecolor="black")
    ax.set_xscale("log")
    ax.set_title("Session Duration Distribution")
    ax.set_xlabel("Session duration (seconds, log scale)")
    ax.set_ylabel("Number of sessions")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    path = ensure_figure_dir() / (figure_path.name if figure_path else "eda_session_duration.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def run_eda() -> dict[str, object]:
    users, sessions, transactions = load_cleaned_data()
    summary = summarize_dataset_profiles(users, sessions, transactions)
    time_kpis = compute_dau_wau_mau_stickiness(sessions)
    retention = compute_retention_by_dimension(sessions, users, dimension="install_source")
    revenue_metrics = compute_revenue_metrics(users, transactions)
    session_stats = compute_session_distributions(sessions)

    figure_paths = {
        "dau_wau_mau": plot_dau_wau_mau(time_kpis),
        "retention": plot_retention(retention),
        "revenue_per_user": plot_revenue_distribution(transactions, users),
        "revenue_concentration": plot_revenue_concentration(transactions, users),
        "session_frequency": plot_session_frequency(sessions),
        "session_duration": plot_session_duration(sessions),
    }

    return {
        "summary": summary,
        "time_kpis": time_kpis,
        "retention": retention,
        "revenue_metrics": revenue_metrics,
        "session_stats": session_stats,
        "figure_paths": figure_paths,
    }


if __name__ == "__main__":
    results = run_eda()
    print("EDA completed. Figures saved to:")
    for name, path in results["figure_paths"].items():
        print(f"  {name}: {path}")
