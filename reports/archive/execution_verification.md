# Execution Verification

Verification date: `2026-04-23`

## Commands executed

1. `python3 src/features/build_user_features.py`
2. `MPLCONFIGDIR=./.mplconfig LOKY_MAX_CPU_COUNT=4 python3 src/models/segmentation.py`
3. `MPLCONFIGDIR=./.mplconfig python3 src/analysis/profile_segments.py`
4. `python3 scripts/build_final_notebook.py`
5. `JUPYTER_DATA_DIR=./.jupyter JUPYTER_CONFIG_DIR=./.jupyter MPLBACKEND=Agg MPLCONFIGDIR=./.mplconfig python3 -m nbconvert --to notebook --execute --inplace notebooks/vira_games_segmentation_final.ipynb`

## Results

| Step | Status | Outputs produced | Notes |
| --- | --- | --- | --- |
| Data loading and raw access | `pass` | raw files resolved through `src.data.load_data` | Verified indirectly through feature build, EDA, segmentation, and notebook execution. |
| Feature build | `pass` | `data/processed/user_features.parquet` | Completed with 50,000 user-level rows and 77 columns. |
| Segmentation comparison | `pass` | `data/processed/user_segments.parquet`, `data/processed/segmentation_model_metrics.csv`, segmentation figures, comparison report | Final model selected: `KMeans`, `k=5`. |
| Segment profiling | `pass` | segment profile report, business recommendation report, heatmap, size/revenue chart, impact/ease matrix | Segment IDs remapped to stable business-facing labels. |
| Notebook generation | `pass` | `notebooks/vira_games_segmentation_final.ipynb` | Notebook contains 22 cells and executed outputs. |
| Notebook execution | `pass` | executed notebook with outputs embedded | Required running outside the sandbox because Jupyter kernel startup needs local port binding. |

## Key sanity checks

- `user_features.parquet` is null-free.
- `user_features.parquet` has exactly one row per unique `user_id`.
- final segment mix is:
  - `Lapsing Casuals`: 45.2%
  - `Steady Core Players`: 39.4%
  - `Engaged Free Players`: 6.4%
  - `VIP Spenders`: 4.6%
  - `Subscription Loyalists`: 4.4%
- final model comparison metrics confirm the chosen solution:
  - silhouette: `0.319`
  - smallest segment share: `4.4%`
  - largest segment share: `45.2%`

## Caveats

- Several local verification commands emit harmless environment warnings from `pyarrow` CPU detection on macOS sandboxed runs.
- Notebook execution is reproducible, but in this environment it required an escalated run because sandboxed Jupyter kernel startup could not bind local ports.
