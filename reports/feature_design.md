# Feature Design

## Final grain choice

Final grain: **one row per `user_id`**.

This is the strongest final grain for the first complete version because:

- the assignment asks for user-level segmentation by default
- `sessions.csv`, `transactions.csv`, and `events.csv` only contain `user_id`
- using `(user_id, game_id)` for the final clustering would duplicate the same behavioral and revenue history across multiple installs for multi-game users
- `users.csv` is still used to preserve portfolio context through first install attributes and multi-game flags

The repository previously had an install-level mart. That was useful for exploration, but not for the final segmentation because commercial value and engagement would be overstated for multi-game users.

## Final feature groups

### Lifecycle

- `days_since_first_install`
- `days_since_latest_install`
- `days_since_last_session`
- `days_since_last_purchase`
- `install_span_days`

These separate new users, mature users, and lapsed users while also capturing whether the player expanded into multiple games over time.

### Portfolio context

- `primary_game_id`
- `primary_install_source`
- `primary_device_os`
- `primary_country`
- `games_installed_count`
- `multi_game_user_flag`

These are kept compact and interpretable. They add business context without forcing high-cardinality encoding into the final clustering.

### RFM

- `rfm_recency_days`
- `rfm_frequency_sessions`
- `rfm_monetary_total_revenue_usd`

RFM remains the cleanest business shorthand for reactivation risk, engagement frequency, and economic value.

### Engagement intensity

- `sessions_total`
- `active_days`
- `active_days_last_30d`
- `sessions_per_active_day`
- `total_session_duration_hours`
- `avg_session_duration_min`

These capture both breadth and depth of play and help separate habitual users from truly low-intensity players.

### Engagement dynamics

- `sessions_last_30d`
- `sessions_prev_30d`
- `session_duration_hours_last_30d`
- `session_duration_hours_prev_30d`
- `recent_session_share_60d`
- `recent_playtime_share_60d`
- `session_momentum_ratio_30d`

These distinguish users who are accelerating, stable, or fading.

### Progression

- `levels_completed_total`
- `levels_failed_total`
- `fail_rate`
- `progression_velocity_levels_per_active_day`
- `levels_completed_per_session`

These reflect progression quality, difficulty friction, and mastery.

### Monetization behavior

- `payer_flag`
- `transaction_count`
- `positive_revenue_transaction_count`
- `purchase_active_days`
- `total_revenue_usd`
- `avg_revenue_per_transaction_usd`
- `trial_started_flag`
- `trial_transaction_count`
- `trial_converted_flag`
- `subscription_payer_flag`
- `subscription_transaction_count`
- `subscription_revenue_share`
- `consumable_revenue_share`

This is compact enough to stay interview-friendly while still separating premium users, subscription-led users, and high-engagement non-payers.

### Ads / offers / push interactions

- `ad_watched_count`
- `ad_watched_last_30d`
- `ad_watched_per_session`
- `offer_shown_count`
- `offer_shown_last_30d`
- `offer_purchased_event_count`
- `offer_purchase_event_rate`
- `push_notification_click_count`
- `push_notification_click_last_30d`
- `push_clicks_per_session`
- `subscription_cancel_count`
- `social_share_count`

These are the highest-value event features for practical actionability. They support monetization, CRM, and retention use cases without expanding raw event JSON.

## Transformations and missing-value handling

### Cleaning rules applied

- negative-duration sessions are removed
- exact duplicate transactions are removed
- exact duplicate events are removed
- missing `country`, `install_source`, and `device_os` are standardized to `"Unknown"`
- zero-revenue transactions are retained but not treated as positive spend

### Skew handling

`log1p_*` companion columns are created for the most skewed count, recency, and revenue features, including:

- install counts and lifecycle recency
- sessions and active days
- playtime and progression totals
- transaction counts and revenue
- ads, offer exposure, and push clicks

The raw variables remain in the parquet for stakeholder readability; the transformed versions are used in clustering where they improve stability.

### Missing values

The final mart is null-free.

Rules:

- count-style features are filled with `0`
- ratio features with no valid denominator are set to `0`
- `days_since_last_session` falls back to `days_since_first_install + 1` for users with no valid session
- `days_since_last_purchase` falls back to `days_since_first_install + 1` for users with no transaction history

This keeps missingness explicit through business flags instead of opaque statistical imputation.

## Deliberate exclusions

- No expansion of `event_params` into a wide sparse table.
- No unsupported per-game allocation of sessions, transactions, or events.
- No one-hot explosion of geography or install metadata inside the clustering input.
- No feature dump of dozens of overlapping quantiles or rolling windows.

## Output

Final artifact:

- `data/processed/user_features.parquet`

This mart is compact, user-level, and directly usable for the notebook, model comparison, and business profiling.
