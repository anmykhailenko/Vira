"""Business-facing segment profiling and recommendation outputs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.utils.config import FIGURES_DIR, PROCESSED_DATA_DIR, REPORTS_DIR, ensure_output_dirs

FEATURES_PATH = PROCESSED_DATA_DIR / "user_features.parquet"
SEGMENTS_PATH = PROCESSED_DATA_DIR / "user_segments.parquet"
SEGMENT_FIGURES_DIR = FIGURES_DIR / "segments"
BUSINESS_FIGURES_DIR = FIGURES_DIR / "business"
PROFILE_REPORT_PATH = REPORTS_DIR / "segment_profiles.md"
RECOMMENDATIONS_REPORT_PATH = REPORTS_DIR / "business_recommendations.md"

HEATMAP_METRICS = {
    "sessions_total": "Session volume",
    "sessions_last_30d": "Recent sessions",
    "rfm_recency_days": "Days since last session",
    "total_revenue_usd": "Revenue",
    "payer_flag": "Payer rate",
    "subscription_payer_flag": "Subscription payer rate",
    "fail_rate": "Fail rate",
    "ad_watched_per_session": "Ads per session",
    "offer_purchase_event_rate": "Offer purchase rate",
    "push_clicks_per_session": "Push clicks per session",
}


@dataclass
class ProfilingArtifacts:
    merged: pd.DataFrame
    summary: pd.DataFrame
    recommendation_table: pd.DataFrame


def load_inputs(
    features_path: Path = FEATURES_PATH,
    segments_path: Path = SEGMENTS_PATH,
) -> pd.DataFrame:
    features = pd.read_parquet(features_path)
    segments = pd.read_parquet(segments_path)
    return features.merge(segments, on="user_id", how="inner")


def _stable_segment_order(merged: pd.DataFrame) -> dict[int, int]:
    ranking_frame = merged.groupby("segment_id").agg(
        sessions_total=("sessions_total", "median"),
        total_revenue_usd=("total_revenue_usd", "median"),
        rfm_recency_days=("rfm_recency_days", "median"),
        payer_flag=("payer_flag", "mean"),
    )
    ranking_frame["priority_score"] = (
        ranking_frame["sessions_total"].rank(pct=True)
        + ranking_frame["total_revenue_usd"].rank(pct=True)
        + ranking_frame["payer_flag"].rank(pct=True)
        - ranking_frame["rfm_recency_days"].rank(pct=True)
    )
    ranking_frame = ranking_frame.sort_values("priority_score", ascending=False)
    return {old_id: new_id for new_id, old_id in enumerate(ranking_frame.index)}


def _segment_name(row: pd.Series) -> str:
    revenue = row["revenue_share_pct"]
    payer_rate = row["payer_rate_pct"]
    recency = row["median_recency_days"]
    sessions = row["median_sessions"]
    ads = row["ad_intensity"]
    offer_rate = row["offer_response_rate"]
    subscription_rate = row["subscription_payer_rate_pct"]

    if revenue >= 35 or (payer_rate >= 55 and row["median_revenue_usd"] >= 80):
        return "VIP Spenders"
    if recency >= 60 and sessions <= 12:
        return "Lapsing Casuals"
    if sessions >= 45 and payer_rate < 20:
        return "Engaged Free Players"
    if subscription_rate >= 12:
        return "Subscription Loyalists"
    if offer_rate >= 0.12 or (ads >= 0.6 and payer_rate >= 20):
        return "Offer-Responsive Regulars"
    if ads >= 0.9 and payer_rate < 15:
        return "Ad-Funded Routine Players"
    return "Steady Core Players"


def _interpretation(row: pd.Series) -> str:
    if row["segment_name"] == "VIP Spenders":
        return "High-value players with strong repeat engagement and outsized revenue contribution. They are likely motivated by progression momentum, premium content, and convenience."
    if row["segment_name"] == "Lapsing Casuals":
        return "Low-intensity users with long recency and limited spend. They appear motivated by lightweight, low-friction play and need a clear reason to return."
    if row["segment_name"] == "Engaged Free Players":
        return "Frequent users who spend time but not money. They likely value content, mastery, and fair progression more than aggressive monetization."
    if row["segment_name"] == "Subscription Loyalists":
        return "Consistent users with subscription-heavy monetization. Their behavior suggests they value uninterrupted access, routine rewards, and reliable long-term value."
    if row["segment_name"] == "Offer-Responsive Regulars":
        return "Mid-core users who react to offers and commercial prompts. They are likely motivated by perceived value, timely bundles, and event-based nudges."
    if row["segment_name"] == "Ad-Funded Routine Players":
        return "Habitual users willing to watch ads rather than pay directly. They are likely motivated by free progression support and low-commitment rewards."
    return "Stable repeat users with moderate engagement and monetization. They are likely motivated by a balanced mix of progression, routine play, and occasional rewards."


def build_segment_summary(merged: pd.DataFrame) -> pd.DataFrame:
    total_users = len(merged)
    total_revenue = merged["total_revenue_usd"].sum()
    summary = merged.groupby("segment_id").agg(
        users=("user_id", "nunique"),
        median_sessions=("sessions_total", "median"),
        median_recent_sessions=("sessions_last_30d", "median"),
        median_recency_days=("rfm_recency_days", "median"),
        median_revenue_usd=("total_revenue_usd", "median"),
        mean_revenue_usd=("total_revenue_usd", "mean"),
        total_revenue_usd=("total_revenue_usd", "sum"),
        payer_rate_pct=("payer_flag", lambda s: 100 * s.mean()),
        subscription_payer_rate_pct=("subscription_payer_flag", lambda s: 100 * s.mean()),
        ad_intensity=("ad_watched_per_session", "median"),
        offer_response_rate=("offer_purchase_event_rate", "median"),
        mean_fail_rate=("fail_rate", "mean"),
        multi_game_rate_pct=("multi_game_user_flag", lambda s: 100 * s.mean()),
    ).reset_index()
    summary["user_share_pct"] = 100 * summary["users"] / total_users
    summary["revenue_share_pct"] = np.where(
        total_revenue > 0,
        100 * summary["total_revenue_usd"] / total_revenue,
        0.0,
    )
    summary["segment_name"] = summary.apply(_segment_name, axis=1)

    duplicates = summary["segment_name"].duplicated(keep=False)
    if duplicates.any():
        for index, (_, row) in enumerate(summary.loc[duplicates].iterrows(), start=1):
            summary.loc[row.name, "segment_name"] = f"{row['segment_name']} {index}"

    summary["behavioral_interpretation"] = summary.apply(_interpretation, axis=1)
    return summary.sort_values("segment_id").reset_index(drop=True)


def _recommendation_for_segment(row: pd.Series) -> tuple[str, str, int, int]:
    name = row["segment_name"]
    if "VIP Spenders" in name:
        return (
            "Protect with VIP retention treatment",
            "Use premium support, early access, and personalized bundles to defend the small cohort that drives a disproportionate share of revenue.",
            5,
            3,
        )
    if "Lapsing Casuals" in name:
        return (
            "Run low-friction win-back journeys",
            "Send return-triggered push and inbox campaigns tied to easy rewards or short comeback missions rather than hard-sell offers.",
            3,
            5,
        )
    if "Engaged Free Players" in name:
        return (
            "Upsell with value-first starter offers",
            "Target high-engagement non-payers with limited starter bundles or subscription trials after strong play streaks, not immediately after install.",
            4,
            4,
        )
    if "Subscription Loyalists" in name:
        return (
            "Reinforce subscription value",
            "Highlight streak benefits, renewal reminders, and exclusive perks to reduce churn and preserve recurring revenue.",
            4,
            4,
        )
    if "Offer-Responsive" in name:
        return (
            "Optimize offer timing and price ladders",
            "Personalize offers around active play windows and test progression-linked bundles because this segment already shows commercial responsiveness.",
            4,
            3,
        )
    if "Ad-Funded" in name:
        return (
            "Tune ad load without hurting retention",
            "Use rewarded ads and ad-frequency caps to grow ad ARPDAU while protecting session depth in users who prefer free value exchange.",
            3,
            4,
        )
    return (
        "Develop toward higher-value routines",
        "Use milestone nudges, events, and light personalization to move these users toward steadier engagement or first purchase.",
        3,
        4,
    )


def build_recommendation_table(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in summary.itertuples(index=False):
        title, recommendation, impact, ease = _recommendation_for_segment(pd.Series(row._asdict()))
        rows.append(
            {
                "segment_id": row.segment_id,
                "segment_name": row.segment_name,
                "recommendation_title": title,
                "recommendation": recommendation,
                "impact_score": impact,
                "ease_score": ease,
                "priority_score": impact * ease,
            }
        )
    return pd.DataFrame(rows).sort_values(["priority_score", "impact_score"], ascending=False).reset_index(drop=True)


def plot_segment_heatmap(merged: pd.DataFrame, summary: pd.DataFrame) -> Path:
    SEGMENT_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    metric_frame = merged.groupby("segment_id")[list(HEATMAP_METRICS)].mean()
    standardized = metric_frame.apply(lambda column: (column - column.mean()) / (column.std(ddof=0) or 1), axis=0)
    standardized.index = summary.set_index("segment_id")["segment_name"]
    standardized = standardized.rename(columns=HEATMAP_METRICS)
    standardized = standardized.astype(float)

    fig, ax = plt.subplots(figsize=(11, 5.5))
    image = ax.imshow(standardized.to_numpy(), cmap="RdYlBu_r", aspect="auto")
    ax.set_xticks(np.arange(len(standardized.columns)))
    ax.set_xticklabels(standardized.columns, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(standardized.index)))
    ax.set_yticklabels(standardized.index)
    for i in range(standardized.shape[0]):
        for j in range(standardized.shape[1]):
            ax.text(j, i, f"{standardized.iloc[i, j]:.1f}", ha="center", va="center", fontsize=8)
    ax.set_title("Segment Comparison Heatmap (relative to portfolio average)")
    ax.set_xlabel("Key dimensions")
    ax.set_ylabel("")
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    path = SEGMENT_FIGURES_DIR / "segment_comparison_heatmap.png"
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return path


def plot_segment_value(summary: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(summary))
    ax.bar(x - 0.18, summary["user_share_pct"], width=0.36, label="% users", color="#4C78A8")
    ax.bar(x + 0.18, summary["revenue_share_pct"], width=0.36, label="% revenue", color="#F58518")
    ax.set_xticks(x)
    ax.set_xticklabels(summary["segment_name"], rotation=20, ha="right")
    ax.set_ylabel("Share (%)")
    ax.set_title("Segment Size and Revenue Contribution")
    ax.legend(frameon=False)
    fig.tight_layout()
    path = SEGMENT_FIGURES_DIR / "segment_size_revenue_share.png"
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return path


def plot_impact_effort_matrix(recommendation_table: pd.DataFrame) -> Path:
    BUSINESS_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6))
    palette = plt.get_cmap("tab10", len(recommendation_table))
    for idx, row in enumerate(recommendation_table.itertuples(index=False)):
        ax.scatter(row.ease_score, row.impact_score, s=220, color=palette(idx), label=row.segment_name)
        ax.text(row.ease_score + 0.05, row.impact_score + 0.05, row.segment_name, fontsize=9)
    ax.axhline(3.5, color="#999999", linestyle="--", linewidth=1)
    ax.axvline(3.5, color="#999999", linestyle="--", linewidth=1)
    ax.set_xlim(1, 5.4)
    ax.set_ylim(1, 5.4)
    ax.set_xlabel("Implementation ease")
    ax.set_ylabel("Expected impact")
    ax.set_title("Recommended Actions: Impact vs Ease")
    ax.legend(frameon=False, bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    path = BUSINESS_FIGURES_DIR / "impact_effort_matrix.png"
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return path


def write_profile_report(summary: pd.DataFrame) -> Path:
    report = """# Segment Profiles

The final segmentation is profiled at the portfolio user level. Sizes are reported as a share of users and share of total revenue.

"""
    for row in summary.itertuples(index=False):
        report += f"""## Segment {row.segment_id}: {row.segment_name}

- Share of users: **{row.user_share_pct:.1f}%**
- Share of revenue: **{row.revenue_share_pct:.1f}%**
- Median sessions: `{row.median_sessions:.1f}`
- Median sessions in last 30 days: `{row.median_recent_sessions:.1f}`
- Median days since last session: `{row.median_recency_days:.1f}`
- Payer rate: `{row.payer_rate_pct:.1f}%`
- Subscription payer rate: `{row.subscription_payer_rate_pct:.1f}%`
- Median revenue per user: `${row.median_revenue_usd:,.2f}`
- Mean fail rate: `{row.mean_fail_rate:.2%}`
- Multi-game share: `{row.multi_game_rate_pct:.1f}%`
- Interpretation: {row.behavioral_interpretation}

"""

    report += """## Visual outputs

- `outputs/figures/segments/segment_comparison_heatmap.png`
- `outputs/figures/segments/segment_size_revenue_share.png`
"""
    PROFILE_REPORT_PATH.write_text(report)
    return PROFILE_REPORT_PATH


def write_recommendations_report(recommendation_table: pd.DataFrame) -> Path:
    report = """# Business Recommendations

Recommendations are ranked by expected impact and implementation ease for a practical first version of the portfolio segmentation.

| Priority | Segment | Recommended action | Impact | Ease |
| --- | --- | --- | ---: | ---: |
"""
    for priority, row in enumerate(recommendation_table.itertuples(index=False), start=1):
        report += (
            f"| {priority} | **{row.segment_name}** | {row.recommendation_title}: {row.recommendation} | "
            f"{row.impact_score} | {row.ease_score} |\n"
        )

    report += """

## Supporting figure

- `outputs/figures/business/impact_effort_matrix.png`
"""
    RECOMMENDATIONS_REPORT_PATH.write_text(report)
    return RECOMMENDATIONS_REPORT_PATH


def run_profiling(
    features_path: Path = FEATURES_PATH,
    segments_path: Path = SEGMENTS_PATH,
) -> ProfilingArtifacts:
    ensure_output_dirs()
    merged = load_inputs(features_path=features_path, segments_path=segments_path)

    mapping = _stable_segment_order(merged)
    merged["segment_id"] = merged["segment_id"].map(mapping)
    summary = build_segment_summary(merged)
    name_mapping = summary.set_index("segment_id")["segment_name"]
    merged["segment_name"] = merged["segment_id"].map(name_mapping)

    updated_segments = merged[["user_id", "segment_id", "segment_name", "model_name", "k"]].drop_duplicates()
    updated_segments.to_parquet(segments_path, index=False)

    recommendation_table = build_recommendation_table(summary)

    plot_segment_heatmap(merged, summary)
    plot_segment_value(summary)
    plot_impact_effort_matrix(recommendation_table)
    write_profile_report(summary)
    write_recommendations_report(recommendation_table)

    return ProfilingArtifacts(merged=merged, summary=summary, recommendation_table=recommendation_table)


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile final segments and write business-facing outputs.")
    parser.add_argument("--features-path", type=Path, default=FEATURES_PATH)
    parser.add_argument("--segments-path", type=Path, default=SEGMENTS_PATH)
    args = parser.parse_args()

    artifacts = run_profiling(features_path=args.features_path, segments_path=args.segments_path)
    print(artifacts.summary[["segment_id", "segment_name", "user_share_pct", "revenue_share_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()
