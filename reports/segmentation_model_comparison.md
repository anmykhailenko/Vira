# Segmentation Model Comparison

## Final decision

- Final method: **KMEANS**
- Final segment count: **5**
- Rationale: this option combined the strongest or near-strongest silhouette with acceptable segment balance and the best overall interpretability among viable candidates. K-Means was preferred when quality was effectively tied because it gives cleaner centroids and simpler stakeholder communication.

## Features used

The modeling step used the compact numeric feature set below after missing-value filling and standard scaling.

- `log1p_days_since_first_install`
- `log1p_days_since_latest_install`
- `log1p_days_since_last_session`
- `log1p_days_since_last_purchase`
- `log1p_sessions_total`
- `log1p_active_days`
- `sessions_per_active_day`
- `avg_session_duration_min`
- `sessions_last_30d`
- `sessions_prev_30d`
- `recent_session_share_60d`
- `recent_playtime_share_60d`
- `session_momentum_ratio_30d`
- `levels_completed_per_session`
- `progression_velocity_levels_per_active_day`
- `fail_rate`
- `payer_flag`
- `log1p_transaction_count`
- `log1p_total_revenue_usd`
- `avg_revenue_per_transaction_usd`
- `trial_started_flag`
- `trial_converted_flag`
- `subscription_payer_flag`
- `subscription_revenue_share`
- `consumable_revenue_share`
- `ad_watched_per_session`
- `offer_purchase_event_rate`
- `push_clicks_per_session`
- `log1p_ad_watched_count`
- `log1p_offer_shown_count`
- `log1p_push_notification_click_count`
- `games_installed_count`

## Preprocessing

- Input source: `data/processed/user_features.parquet`
- Missing values: already resolved in the feature mart
- Scaling: `StandardScaler`
- Seed: `42`
- Candidate cluster counts: `3` to `6`

## Comparison table

| Model | k | Silhouette | Inertia | BIC | AIC | Min share | Max share | Interpretability |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `gmm` | 3 | 0.236 | n/a | -4,039,499.1 | -4,041,210.1 | 0.159 | 0.600 | 1.462 |
| `gmm` | 4 | 0.270 | n/a | -4,554,750.6 | -4,557,034.9 | 0.068 | 0.600 | 2.155 |
| `gmm` | 5 | 0.282 | n/a | -4,640,716.9 | -4,643,574.5 | 0.045 | 0.600 | 2.407 |
| `gmm` | 6 | 0.221 | n/a | -4,749,597.6 | -4,753,028.5 | 0.046 | 0.594 | 2.382 |
| `kmeans` | 3 | 0.295 | 891,772.5 | n/a | n/a | 0.090 | 0.481 | 1.557 |
| `kmeans` | 4 | 0.307 | 758,428.7 | n/a | n/a | 0.064 | 0.452 | 2.241 |
| `kmeans` | 5 | 0.319 | 679,242.8 | n/a | n/a | 0.044 | 0.452 | 2.486 |
| `kmeans` | 6 | 0.269 | 619,382.5 | n/a | n/a | 0.044 | 0.446 | 2.504 |


## Final model notes

- Final silhouette: `0.319`
- Smallest segment share: `4.4%`
- Largest segment share: `45.2%`
- Interpretability score: `2.486`

## Why the other candidates were not selected

- Higher-`k` options produced smaller, harder-to-explain segments without a meaningful lift in separation.
- Lower-`k` options blended distinct monetization and lifecycle behaviors that are useful for CRM and monetization actions.
- GMM remained a valid benchmark, but the chosen final model gave a cleaner business story for the same feature space.

## Outputs produced

- `data/processed/user_segments.parquet`
- `data/processed/segmentation_model_metrics.csv`
- `outputs/figures/segmentation/model_comparison_metrics.png`
- `outputs/figures/segmentation/final_segments_pca.png`
