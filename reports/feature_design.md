# Feature Design

## 1. Chosen Grain

Final grain: **one row per `(user_id, game_id)`**.

This is the right entity for segmentation here because the data audit showed that the same `user_id` can appear in multiple games. Using plain `user_id` would collapse distinct install contexts into one row and blur the segmentation target.

Important modeling constraint:

- `users.csv` contains `game_id`
- `sessions.csv`, `transactions.csv`, and `events.csv` do not

Because the activity tables do not expose `game_id`, the implemented mart keeps the requested `(user_id, game_id)` grain but computes behavior features at the portfolio `user_id` level, then attaches those user-level summaries to each observed user-game row. This preserves the segmentation entity without inventing unsupported per-game behavior attribution.

## 2. Feature Groups

### Lifecycle

- `days_since_game_install`
- `days_since_first_portfolio_install`
- `days_since_last_session`
- `days_since_last_purchase`
- `install_rank_for_user`
- `is_first_game_install_flag`

These separate new installs, mature installs, and lapsed user-game rows.

### Portfolio Context

- `games_installed_count`
- `multi_game_user_flag`

These capture whether a user belongs to a single-game or multi-game portfolio pattern, which is important given the duplicate-user audit finding.

### RFM

- `rfm_recency_days`
- `rfm_frequency_sessions`
- `rfm_monetary_total_revenue_usd`

RFM stays compact and interpretable while covering closeness to churn, usage intensity, and commercial value.

### Engagement

- `sessions_total`
- `active_days`
- `sessions_per_active_day`
- `total_session_duration_hours`
- `avg_session_duration_min`

These describe how often and how deeply a user engages.

### Engagement Dynamics

- `sessions_last_30d`
- `sessions_prev_30d`
- `session_duration_hours_last_30d`
- `session_duration_hours_prev_30d`
- `recent_session_share_60d`
- `recent_playtime_share_60d`
- `session_momentum_ratio_30d`

These measure whether behavior is accelerating, stable, or fading without adding too many rolling-window features.

### Progression

- `levels_completed_total`
- `levels_failed_total`
- `fail_rate`
- `progression_velocity_levels_per_active_day`
- `levels_completed_per_session`

These help separate efficient progressors, struggling players, and low-intensity users.

### Monetization

- `payer_flag`
- `transaction_count`
- `positive_revenue_transaction_count`
- `total_revenue_usd`
- `avg_revenue_per_transaction_usd`
- `trial_started_flag`
- `trial_transaction_count`
- `trial_converted_flag`
- `subscription_payer_flag`
- `subscription_transaction_count`
- `subscription_revenue_share`

These distinguish non-payers, light payers, heavy payers, trial users, and subscription-oriented spenders.

### Ads / Offers

- `ad_watched_count`
- `ad_watched_per_session`
- `offer_shown_count`
- `offer_purchased_event_count`
- `offer_purchase_event_rate`

These are compact and directly actionable for segmentation because they reflect ad tolerance and commercial responsiveness.

## 3. Transformations

### Cleaning

The feature builder follows the agreed cleaning policy:

- negative-duration sessions are removed
- exact duplicate transactions are removed
- exact duplicate events are removed
- missing `country`, `install_source`, and `device_os` values are standardized to `"Unknown"`
- zero-revenue transactions are retained but not treated as positive spend

### Skew Handling

The following high-skew features receive `log1p` companion columns:

- `games_installed_count`
- `days_since_game_install`
- `sessions_total`
- `active_days`
- `total_session_duration_hours`
- `levels_completed_total`
- `levels_failed_total`
- `transaction_count`
- `total_revenue_usd`
- `ad_watched_count`
- `offer_shown_count`

The raw business-readable variables are kept, and `log1p_*` versions are added for clustering stability.

### Missing Values

The final parquet is intentionally null-free for model readiness.

Rules:

- count features are filled with `0`
- rate and share features with no denominator are set to `0`
- `days_since_last_session` falls back to `days_since_game_install + 1` when no session exists
- `days_since_last_purchase` falls back to `days_since_game_install + 1` when no transaction exists

This keeps missingness explicit through flags such as `payer_flag` and `trial_started_flag` rather than via arbitrary mean imputation.

### Leakage Control

This is an unsupervised feature table, so there is no target leakage. Still, temporal leakage is controlled by computing every feature from observed data up to a single shared snapshot date defined as the latest available day across the cleaned tables. No future labels or post-snapshot information are used.

## 4. Exclusions

The feature set intentionally excludes several tempting additions.

### Excluded raw event parameter expansion

`event_params` is not flattened. It would create a sparse, brittle table and is unnecessary for a compact interview-ready segmentation mart.

### Excluded broad event catalog counts

Only ads and offer interaction events are kept from the event stream. Other events were omitted to keep the feature set focused and compact.

### Excluded unsupported per-game behavior attribution

No attempt is made to split sessions, revenue, or events by `game_id`, because the source tables do not contain that key. Any such split would be heuristic leakage of assumptions, not information from the data.

### Excluded high-cardinality geography engineering

Raw `country` is retained as context, but no region or one-hot expansion is built into this mart. That keeps the output compact and leaves encoding choices to downstream modeling.

### Excluded redundant summary statistics

The mart avoids multiple overlapping session-duration quantiles and product-mix variants. The goal is interpretability and segmentation usefulness, not maximum feature count.

## 5. Output Summary

The resulting artifact is:

- `data/processed/user_features.parquet`

It is a clean `(user_id, game_id)` feature table suitable for downstream scaling, encoding, and clustering.
