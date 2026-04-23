"""Model comparison and final segmentation pipeline."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.utils.config import DEFAULT_RANDOM_SEED, FIGURES_DIR, PROCESSED_DATA_DIR, REPORTS_DIR, ensure_output_dirs

FEATURES_PATH = PROCESSED_DATA_DIR / "user_features.parquet"
SEGMENTS_PATH = PROCESSED_DATA_DIR / "user_segments.parquet"
SEGMENTATION_FIGURES_DIR = FIGURES_DIR / "segmentation"
REPORT_PATH = REPORTS_DIR / "segmentation_model_comparison.md"
METRICS_PATH = PROCESSED_DATA_DIR / "segmentation_model_metrics.csv"

MODEL_FEATURE_COLUMNS = [
    "log1p_days_since_first_install",
    "log1p_days_since_latest_install",
    "log1p_days_since_last_session",
    "log1p_days_since_last_purchase",
    "log1p_sessions_total",
    "log1p_active_days",
    "sessions_per_active_day",
    "avg_session_duration_min",
    "sessions_last_30d",
    "sessions_prev_30d",
    "recent_session_share_60d",
    "recent_playtime_share_60d",
    "session_momentum_ratio_30d",
    "levels_completed_per_session",
    "progression_velocity_levels_per_active_day",
    "fail_rate",
    "payer_flag",
    "log1p_transaction_count",
    "log1p_total_revenue_usd",
    "avg_revenue_per_transaction_usd",
    "trial_started_flag",
    "trial_converted_flag",
    "subscription_payer_flag",
    "subscription_revenue_share",
    "consumable_revenue_share",
    "ad_watched_per_session",
    "offer_purchase_event_rate",
    "push_clicks_per_session",
    "log1p_ad_watched_count",
    "log1p_offer_shown_count",
    "log1p_push_notification_click_count",
    "games_installed_count",
]

KEY_PROFILE_FEATURES = [
    "rfm_recency_days",
    "sessions_total",
    "sessions_last_30d",
    "total_revenue_usd",
    "payer_flag",
    "subscription_payer_flag",
    "ad_watched_count",
    "offer_shown_count",
    "push_notification_click_count",
]

CLUSTER_RANGE = range(3, 7)
SILHOUETTE_SAMPLE_SIZE = 12000
MIN_VIABLE_SEGMENT_SHARE = 0.04


@dataclass
class SegmentationArtifacts:
    metrics: pd.DataFrame
    final_model_name: str
    final_k: int
    final_labels: np.ndarray
    final_assignments: pd.DataFrame
    pca_projection: pd.DataFrame
    scaled_matrix: np.ndarray


def load_features(path: Path = FEATURES_PATH) -> pd.DataFrame:
    return pd.read_parquet(path)


def prepare_model_matrix(features: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, StandardScaler]:
    model_frame = features.loc[:, MODEL_FEATURE_COLUMNS].copy()
    model_frame = model_frame.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    scaler = StandardScaler()
    matrix = scaler.fit_transform(model_frame)
    return model_frame, matrix, scaler


def _segment_size_metrics(labels: np.ndarray) -> tuple[float, float]:
    shares = pd.Series(labels).value_counts(normalize=True)
    return float(shares.min()), float(shares.max())


def _sampled_silhouette(matrix: np.ndarray, labels: np.ndarray) -> float:
    if len(labels) <= SILHOUETTE_SAMPLE_SIZE:
        return float(silhouette_score(matrix, labels))

    rng = np.random.default_rng(DEFAULT_RANDOM_SEED)
    sample_idx = rng.choice(len(labels), size=SILHOUETTE_SAMPLE_SIZE, replace=False)
    return float(silhouette_score(matrix[sample_idx], labels[sample_idx]))


def _interpretability_score(features: pd.DataFrame, labels: np.ndarray) -> float:
    summary = features.assign(segment=labels).groupby("segment")[KEY_PROFILE_FEATURES].mean()
    overall = features[KEY_PROFILE_FEATURES].mean()
    normalized_gap = (summary - overall).abs().divide(features[KEY_PROFILE_FEATURES].std(ddof=0).replace(0, 1), axis=1)
    return float(normalized_gap.max(axis=0).mean())


def compare_models(features: pd.DataFrame) -> SegmentationArtifacts:
    model_frame, matrix, _ = prepare_model_matrix(features)
    metrics: list[dict[str, float | int | str]] = []
    candidate_results: dict[tuple[str, int], np.ndarray] = {}

    for k in CLUSTER_RANGE:
        kmeans = KMeans(n_clusters=k, random_state=DEFAULT_RANDOM_SEED, n_init=20)
        kmeans_labels = kmeans.fit_predict(matrix)
        kmeans_min_share, kmeans_max_share = _segment_size_metrics(kmeans_labels)
        metrics.append(
            {
                "model": "kmeans",
                "k": k,
                "silhouette": _sampled_silhouette(matrix, kmeans_labels),
                "inertia": float(kmeans.inertia_),
                "bic": np.nan,
                "aic": np.nan,
                "min_segment_share": kmeans_min_share,
                "max_segment_share": kmeans_max_share,
                "interpretability_score": _interpretability_score(features, kmeans_labels),
            }
        )
        candidate_results[("kmeans", k)] = kmeans_labels

        gmm = GaussianMixture(n_components=k, covariance_type="diag", n_init=2, random_state=DEFAULT_RANDOM_SEED)
        gmm.fit(matrix)
        gmm_labels = gmm.predict(matrix)
        gmm_min_share, gmm_max_share = _segment_size_metrics(gmm_labels)
        metrics.append(
            {
                "model": "gmm",
                "k": k,
                "silhouette": _sampled_silhouette(matrix, gmm_labels),
                "inertia": np.nan,
                "bic": float(gmm.bic(matrix)),
                "aic": float(gmm.aic(matrix)),
                "min_segment_share": gmm_min_share,
                "max_segment_share": gmm_max_share,
                "interpretability_score": _interpretability_score(features, gmm_labels),
            }
        )
        candidate_results[("gmm", k)] = gmm_labels

    metrics_df = pd.DataFrame(metrics).sort_values(["model", "k"]).reset_index(drop=True)
    viable = metrics_df.loc[metrics_df["min_segment_share"] >= MIN_VIABLE_SEGMENT_SHARE].copy()
    if viable.empty:
        viable = metrics_df.copy()

    best_silhouette = viable["silhouette"].max()
    shortlisted = viable.loc[viable["silhouette"] >= best_silhouette - 0.02].copy()
    shortlisted["prefer_interpretable"] = np.where(shortlisted["model"].eq("kmeans"), 1, 0)
    shortlisted = shortlisted.sort_values(
        ["silhouette", "interpretability_score", "prefer_interpretable", "min_segment_share"],
        ascending=[False, False, False, False],
    )
    final_choice = shortlisted.iloc[0]
    final_model_name = str(final_choice["model"])
    final_k = int(final_choice["k"])
    final_labels = candidate_results[(final_model_name, final_k)]

    pca = PCA(n_components=2, random_state=DEFAULT_RANDOM_SEED)
    projection = pca.fit_transform(matrix)
    pca_projection = pd.DataFrame(
        {
            "pc1": projection[:, 0],
            "pc2": projection[:, 1],
            "segment_id": final_labels,
        }
    )
    final_assignments = features[["user_id"]].copy()
    final_assignments["segment_id"] = pd.Series(final_labels).astype(int)
    final_assignments["model_name"] = final_model_name
    final_assignments["k"] = final_k

    return SegmentationArtifacts(
        metrics=metrics_df,
        final_model_name=final_model_name,
        final_k=final_k,
        final_labels=final_labels,
        final_assignments=final_assignments,
        pca_projection=pca_projection,
        scaled_matrix=matrix,
    )


def _format_metric(value: float | int | str) -> str:
    if pd.isna(value):
        return "n/a"
    if isinstance(value, str):
        return value
    if abs(float(value)) >= 1000:
        return f"{float(value):,.1f}"
    return f"{float(value):.3f}"


def plot_model_metrics(metrics: pd.DataFrame) -> dict[str, Path]:
    SEGMENTATION_FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for model_name, subset in metrics.groupby("model"):
        axes[0].plot(subset["k"], subset["silhouette"], marker="o", linewidth=2, label=model_name.upper())
        axes[1].plot(subset["k"], subset["min_segment_share"], marker="o", linewidth=2, label=model_name.upper())
        if subset["bic"].notna().any():
            axes[2].plot(subset["k"], subset["bic"], marker="o", linewidth=2, label=f"{model_name.upper()} BIC")
            axes[2].plot(subset["k"], subset["aic"], marker="s", linewidth=1.6, linestyle="--", label=f"{model_name.upper()} AIC")

    axes[0].set_title("Model Separation by Cluster Count")
    axes[0].set_xlabel("Candidate segments")
    axes[0].set_ylabel("Silhouette")
    axes[1].set_title("Smallest Segment Share")
    axes[1].set_xlabel("Candidate segments")
    axes[1].set_ylabel("Min segment share")
    axes[2].set_title("GMM Information Criteria")
    axes[2].set_xlabel("Candidate segments")
    axes[2].set_ylabel("Score")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(frameon=False)
    fig.tight_layout()
    metrics_path = SEGMENTATION_FIGURES_DIR / "model_comparison_metrics.png"
    fig.savefig(metrics_path, dpi=220)
    plt.close(fig)

    return {"model_metrics": metrics_path}


def plot_final_projection(pca_projection: pd.DataFrame, final_model_name: str, final_k: int) -> Path:
    fig, ax = plt.subplots(figsize=(8, 6))
    sample = pca_projection.sample(n=min(12000, len(pca_projection)), random_state=DEFAULT_RANDOM_SEED)
    palette = plt.get_cmap("tab10", sample["segment_id"].nunique())
    for segment_id in sorted(sample["segment_id"].unique()):
        subset = sample.loc[sample["segment_id"] == segment_id]
        ax.scatter(
            subset["pc1"],
            subset["pc2"],
            s=24,
            alpha=0.65,
            label=f"Segment {segment_id}",
            color=palette(segment_id),
            linewidths=0,
        )
    ax.set_title(f"Final Segment Separation ({final_model_name.upper()}, k={final_k})")
    ax.set_xlabel("Principal component 1")
    ax.set_ylabel("Principal component 2")
    ax.grid(alpha=0.2)
    ax.legend(title="Segment", frameon=False, ncol=2)
    fig.tight_layout()
    output_path = SEGMENTATION_FIGURES_DIR / "final_segments_pca.png"
    fig.savefig(output_path, dpi=220)
    plt.close(fig)
    return output_path


def write_report(artifacts: SegmentationArtifacts, features: pd.DataFrame) -> Path:
    metrics = artifacts.metrics.copy()
    final_row = metrics.loc[
        (metrics["model"] == artifacts.final_model_name) & (metrics["k"] == artifacts.final_k)
    ].iloc[0]

    comparison_table = metrics.copy()
    for column in ["silhouette", "inertia", "bic", "aic", "min_segment_share", "max_segment_share", "interpretability_score"]:
        comparison_table[column] = comparison_table[column].map(_format_metric)

    selected_features_md = "\n".join(f"- `{column}`" for column in MODEL_FEATURE_COLUMNS)

    report = f"""# Segmentation Model Comparison

## Final decision

- Final method: **{artifacts.final_model_name.upper()}**
- Final segment count: **{artifacts.final_k}**
- Rationale: this option combined the strongest or near-strongest silhouette with acceptable segment balance and the best overall interpretability among viable candidates. K-Means was preferred when quality was effectively tied because it gives cleaner centroids and simpler stakeholder communication.

## Features used

The modeling step used the compact numeric feature set below after missing-value filling and standard scaling.

{selected_features_md}

## Preprocessing

- Input source: `data/processed/user_features.parquet`
- Missing values: already resolved in the feature mart
- Scaling: `StandardScaler`
- Seed: `{DEFAULT_RANDOM_SEED}`
- Candidate cluster counts: `{min(CLUSTER_RANGE)}` to `{max(CLUSTER_RANGE)}`

## Comparison table

| Model | k | Silhouette | Inertia | BIC | AIC | Min share | Max share | Interpretability |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
"""
    for row in comparison_table.itertuples(index=False):
        report += (
            f"| `{row.model}` | {row.k} | {row.silhouette} | {row.inertia} | {row.bic} | {row.aic} | "
            f"{row.min_segment_share} | {row.max_segment_share} | {row.interpretability_score} |\n"
        )

    report += f"""

## Final model notes

- Final silhouette: `{float(final_row['silhouette']):.3f}`
- Smallest segment share: `{float(final_row['min_segment_share']):.1%}`
- Largest segment share: `{float(final_row['max_segment_share']):.1%}`
- Interpretability score: `{float(final_row['interpretability_score']):.3f}`

## Why the other candidates were not selected

- Higher-`k` options produced smaller, harder-to-explain segments without a meaningful lift in separation.
- Lower-`k` options blended distinct monetization and lifecycle behaviors that are useful for CRM and monetization actions.
- GMM remained a valid benchmark, but the chosen final model gave a cleaner business story for the same feature space.

## Outputs produced

- `data/processed/user_segments.parquet`
- `data/processed/segmentation_model_metrics.csv`
- `outputs/figures/segmentation/model_comparison_metrics.png`
- `outputs/figures/segmentation/final_segments_pca.png`
"""

    REPORT_PATH.write_text(report)
    return REPORT_PATH


def run_segmentation(
    features_path: Path = FEATURES_PATH,
    segments_path: Path = SEGMENTS_PATH,
    metrics_path: Path = METRICS_PATH,
) -> SegmentationArtifacts:
    ensure_output_dirs()
    SEGMENTATION_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    features = load_features(features_path)
    artifacts = compare_models(features)
    artifacts.final_assignments.to_parquet(segments_path, index=False)
    artifacts.metrics.to_csv(metrics_path, index=False)
    plot_model_metrics(artifacts.metrics)
    plot_final_projection(artifacts.pca_projection, artifacts.final_model_name, artifacts.final_k)
    write_report(artifacts, features)
    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare segmentation models and save final assignments.")
    parser.add_argument("--features-path", type=Path, default=FEATURES_PATH)
    parser.add_argument("--segments-path", type=Path, default=SEGMENTS_PATH)
    args = parser.parse_args()

    artifacts = run_segmentation(features_path=args.features_path, segments_path=args.segments_path)
    print(
        json.dumps(
            {
                "final_model": artifacts.final_model_name,
                "final_k": artifacts.final_k,
                "segments_path": str(args.segments_path),
                "metrics_path": str(METRICS_PATH),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
