# Final Execution Check

Verification date: `2026-04-23`

## Exact commands executed

1. `python3 src/features/build_user_features.py`
2. `MPLCONFIGDIR=./.mplconfig LOKY_MAX_CPU_COUNT=4 python3 src/models/segmentation.py`
3. `MPLCONFIGDIR=./.mplconfig python3 src/analysis/profile_segments.py`
4. `python3 scripts/build_final_notebook.py`
5. `JUPYTER_DATA_DIR=./.jupyter JUPYTER_CONFIG_DIR=./.jupyter MPLBACKEND=Agg MPLCONFIGDIR=./.mplconfig python3 -m nbconvert --to notebook --execute --inplace notebooks/vira_games_segmentation_final.ipynb`

## Command results

| Command | Pass/fail | Produced outputs | Notes |
| --- | --- | --- | --- |
| `python3 src/features/build_user_features.py` | `pass` | `data/processed/user_features.parquet` | Saved 50,000 rows and 77 columns. |
| `MPLCONFIGDIR=./.mplconfig LOKY_MAX_CPU_COUNT=4 python3 src/models/segmentation.py` | `pass` | `data/processed/user_segments.parquet`, `data/processed/segmentation_model_metrics.csv`, `outputs/figures/segmentation/model_comparison_metrics.png`, `outputs/figures/segmentation/final_segments_pca.png`, `reports/segmentation_model_comparison.md` | Final model confirmed as `KMeans`, `k=5`. |
| `MPLCONFIGDIR=./.mplconfig python3 src/analysis/profile_segments.py` | `pass` | `reports/segment_profiles.md`, `reports/business_recommendations.md`, `outputs/figures/segments/segment_comparison_heatmap.png`, `outputs/figures/segments/segment_size_revenue_share.png`, `outputs/figures/business/impact_effort_matrix.png` | Segment names and business recommendations regenerated successfully. |
| `python3 scripts/build_final_notebook.py` | `pass` | `notebooks/vira_games_segmentation_final.ipynb` | Notebook source rebuilt cleanly from the scripted template. |
| `JUPYTER_DATA_DIR=./.jupyter JUPYTER_CONFIG_DIR=./.jupyter MPLBACKEND=Agg MPLCONFIGDIR=./.mplconfig python3 -m nbconvert --to notebook --execute --inplace notebooks/vira_games_segmentation_final.ipynb` | `pass` | Executed `notebooks/vira_games_segmentation_final.ipynb` with embedded outputs | Sandbox run stalled on kernel startup; successful verification was completed outside the sandbox. |

## Output readability checks

- `data/processed/user_features.parquet` loads successfully and contains one row per unique `user_id`.
- `data/processed/user_segments.parquet` loads successfully and contains five named final segments.
- Final notebook contains 22 cells, 13 executed code cells, and embedded outputs.
- Generated figures are present and readable in the expected folders.

## Remaining warnings or caveats

- Parquet-related commands emit harmless `pyarrow` CPU-info warnings in the macOS sandbox.
- Notebook execution reproducibility is confirmed, but in this environment it required an out-of-sandbox run because Jupyter kernel startup needed local port binding.
