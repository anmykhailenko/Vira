"""Generate the final submission notebook."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf


def build_notebook() -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    cells: list[nbf.NotebookNode] = []

    cells.append(
        nbf.v4.new_markdown_cell(
            """# Vira Games User Segmentation

## 1. Problem framing

Goal: build a practical user segmentation for the Vira Games mobile portfolio that supports lifecycle messaging, monetization, and re-engagement decisions.

This notebook is intentionally concise. It focuses on the end-to-end segmentation story:

1. data overview
2. EDA highlights
3. feature engineering rationale
4. segmentation model comparison
5. final segment profiles
6. business recommendations
7. caveats and next steps
"""
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            """from __future__ import annotations

from pathlib import Path
import random
import sys

import numpy as np
import pandas as pd
from IPython.display import Image, Markdown, display

PROJECT_ROOT = Path.cwd()
if not (PROJECT_ROOT / "src").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.analysis.eda_kpis import run_eda
from src.analysis.profile_segments import run_profiling
from src.data.load_data import load_all_datasets
from src.features.build_user_features import build_user_feature_mart, save_user_feature_mart
from src.models.segmentation import run_segmentation
from src.utils.config import DEFAULT_RANDOM_SEED

random.seed(DEFAULT_RANDOM_SEED)
np.random.seed(DEFAULT_RANDOM_SEED)
pd.set_option("display.max_columns", 100)
DEFAULT_RANDOM_SEED"""
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            """## 2. Data overview

The raw project data is provided as four flat files. A key modeling constraint is that `users.csv` contains multiple installs for some users while the behavioral tables only contain `user_id`, so the final segmentation is built at the portfolio user level rather than the install row level.
"""
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            """datasets = load_all_datasets()
overview = pd.DataFrame(
    {
        "dataset": list(datasets.keys()),
        "rows": [len(df) for df in datasets.values()],
        "columns": [len(df.columns) for df in datasets.values()],
        "unique_users": [df["user_id"].nunique() if "user_id" in df.columns else np.nan for df in datasets.values()],
    }
)
overview"""
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            """users = datasets["users"]
user_grain_note = pd.DataFrame(
    {
        "metric": [
            "Raw user rows",
            "Unique user_id",
            "Users in multiple games",
            "Multi-game share",
        ],
        "value": [
            len(users),
            users["user_id"].nunique(),
            int((users.groupby("user_id")["game_id"].nunique() > 1).sum()),
            f"{(users.groupby('user_id')['game_id'].nunique() > 1).mean():.1%}",
        ],
    }
)
user_grain_note"""
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            """## 3. EDA highlights

The optional EDA section is kept lightweight and focused on signals that justify the segmentation design. The reusable `run_eda()` function regenerates the KPI figures used in the written findings.
"""
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            """eda_results = run_eda()

eda_summary = pd.DataFrame(
    [
        ("Average DAU", round(eda_results["time_kpis"]["dau"].mean(), 0)),
        ("Average WAU", round(eda_results["time_kpis"]["wau"].mean(), 0)),
        ("Average MAU", round(eda_results["time_kpis"]["mau"].mean(), 0)),
        ("Mean stickiness", f"{eda_results['time_kpis']['stickiness'].mean():.1%}"),
        ("Payer conversion", f"{eda_results['revenue_metrics']['payer_conversion_rate']:.1%}"),
        ("ARPPU", f"${eda_results['revenue_metrics']['arppu']:,.2f}"),
        ("Top 5% payer revenue share", f"{eda_results['revenue_metrics']['revenue_top_5_percent_share']:.1%}"),
    ],
    columns=["metric", "value"],
)
eda_summary"""
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            """for label in [
    "dau_wau_mau",
    "retention",
    "revenue_per_user",
    "session_frequency",
]:
    display(Markdown(f"**{label.replace('_', ' ').title()}**"))
    display(Image(filename=str(eda_results["figure_paths"][label])))"""
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            """## 4. Feature engineering rationale

The final feature table is deliberately compact and interview-friendly. It keeps stakeholder-readable raw features and adds `log1p_*` companions only where clustering stability benefits from skew reduction.

Feature groups:

- lifecycle and recency
- RFM
- engagement level and momentum
- progression quality
- monetization behavior
- ads, offers, and push interactions
"""
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            """feature_mart = build_user_feature_mart()
save_user_feature_mart(feature_mart)

feature_snapshot = pd.DataFrame(
    [
        ("Rows", len(feature_mart)),
        ("Unique users", feature_mart["user_id"].nunique()),
        ("Payer rate", f"{feature_mart['payer_flag'].mean():.1%}"),
        ("Subscription payer rate", f"{feature_mart['subscription_payer_flag'].mean():.1%}"),
        ("Median sessions", feature_mart["sessions_total"].median()),
        ("Median recency days", feature_mart["rfm_recency_days"].median()),
        ("Multi-game share", f"{feature_mart['multi_game_user_flag'].mean():.1%}"),
    ],
    columns=["metric", "value"],
)
feature_snapshot"""
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            """selected_columns = [
    "user_id",
    "primary_game_id",
    "primary_install_source",
    "games_installed_count",
    "sessions_total",
    "sessions_last_30d",
    "rfm_recency_days",
    "total_revenue_usd",
    "subscription_revenue_share",
    "ad_watched_per_session",
    "offer_purchase_event_rate",
]
feature_mart[selected_columns].head(10)"""
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            """## 5. Segmentation method comparison

Two methods are compared on the same standardized feature set:

- `KMeans`
- `GaussianMixture`

Cluster counts from 3 to 6 are tested. Selection balances separation, segment balance, and interpretability rather than optimizing one metric in isolation.
"""
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            """segmentation_artifacts = run_segmentation()
metrics = segmentation_artifacts.metrics.copy()
metrics"""
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            """display(Image(filename=str(PROJECT_ROOT / "outputs/figures/segmentation/model_comparison_metrics.png")))
display(Image(filename=str(PROJECT_ROOT / "outputs/figures/segmentation/final_segments_pca.png")))"""
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            """The final choice is `KMeans` with **5 segments**. It provides the best silhouette among business-usable candidates and cleanly separates high-value spenders, subscription-led value, engaged free users, steady core players, and lapsing casuals.
"""
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            """## 6. Final segmentation and profiles

The profiling step remaps arbitrary cluster IDs into stable business-facing segment IDs and names.
"""
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            """profiling_artifacts = run_profiling()
profiling_artifacts.summary[
    [
        "segment_id",
        "segment_name",
        "user_share_pct",
        "revenue_share_pct",
        "median_sessions",
        "median_recency_days",
        "payer_rate_pct",
        "subscription_payer_rate_pct",
    ]
]"""
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            """display(Image(filename=str(PROJECT_ROOT / "outputs/figures/segments/segment_comparison_heatmap.png")))
display(Image(filename=str(PROJECT_ROOT / "outputs/figures/segments/segment_size_revenue_share.png")))"""
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            """## 7. Business recommendations

Recommendations are tied directly to the observed segment behaviors instead of generic mobile gaming playbooks.
"""
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            """profiling_artifacts.recommendation_table[
    [
        "segment_name",
        "recommendation_title",
        "impact_score",
        "ease_score",
    ]
]"""
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            """display(Image(filename=str(PROJECT_ROOT / "outputs/figures/business/impact_effort_matrix.png")))"""
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            """## 8. Caveats and next steps

- This is a portfolio-level segmentation because the behavioral tables do not include `game_id`.
- The segmentation is intentionally practical and interpretable rather than overly complex.
- If more time were available, the next improvements would be stability checks across time windows, selective parsing of event parameters, and light experimentation on segment-specific uplift or response propensity.
"""
        )
    )

    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.9"},
    }
    return nb


def main() -> None:
    notebook = build_notebook()
    output_path = Path("notebooks/vira_games_segmentation_final.ipynb")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
