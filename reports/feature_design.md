# Feature Design

## 1. Final Feature Grain

### Decision

Final grain for this submission: **one row per `user_id` across the full portfolio**.

### Why this is the right choice here

The data audit showed that `users.csv` is **not** one-row-per-user. It is an install-level table with multiple rows for some `user_id` values across games, while `(user_id, game_id)` pairs remain unique.

At the same time:

- `sessions.csv` only contains `user_id`
- `transactions.csv` only contains `user_id`
- `events.csv` only contains `user_id`

Because the behavioral tables do **not** contain `game_id`, a `user_id + game_id` segmentation mart would require us to infer which game each session, transaction, or event belongs to. That attribution is unsupported by the raw data and would introduce avoidable noise and arbitrary assumptions.

### Tradeoff considered

Option 1: `user_id` across the portfolio

- Pros:
  - fully supported by all activity tables
  - avoids row duplication from joining `users` on `user_id`
  - produces a clean, defensible user entity for segmentation
  - fits the practical, interview-friendly brief
- Cons:
  - loses game-specific behavioral nuance
  - cannot distinguish whether monetization or engagement came from one game or several

Option 2: `user_id + game_id`

- Pros:
  - more aligned with install-level context
  - potentially better for game-specific segment actions
- Cons:
  - not supported by the activity tables as delivered
  - would require heuristic mapping of portfolio activity back to games
  - high risk of incorrect feature attribution

### Final choice

Use **portfolio-level `user_id`** for this submission. The mart intentionally includes a small amount of portfolio-context information from `users.csv`, especially:

- `games_installed_count`
- `multi_game_user_flag`
- `days_since_install` based on the earliest observed install
- `days_since_latest_install` based on the most recent observed install

This keeps the grain valid while still preserving whether the user behaves like a single-game or multi-game portfolio player.

## 2. Feature Groups

The final mart contains one row per `user_id` and groups features into the following blocks.

### Lifecycle

- `days_since_install`
- `days_since_latest_install`
- `days_since_last_session`
- `days_since_last_purchase`

### Portfolio Context

- `games_installed_count`
- `multi_game_user_flag`

### RFM

- `rfm_recency_days`
- `rfm_frequency_sessions`
- `rfm_monetary_total_revenue_usd`

### Engagement Intensity

- `sessions_total`
- `active_days`
- `sessions_per_active_day`
- `total_session_duration_hours`
- `session_duration_mean_min`
- `session_duration_median_min`
- `session_duration_p90_min`

### Engagement Trajectory

- `sessions_last_30d`
- `sessions_prev_30d`
- `session_duration_hours_last_30d`
- `session_duration_hours_prev_30d`
- `session_activity_recent_share_60d`
- `session_duration_recent_share_60d`

### Progression

- `levels_completed_total`
- `levels_failed_total`
- `fail_rate`
- `progression_velocity_levels_per_active_day`
- `levels_completed_per_session`

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
- `iap_consumable_transaction_count`
- `iap_nonconsumable_transaction_count`
- `consumable_revenue_share`
- `nonconsumable_revenue_share`
- `subscription_revenue_share`

### Ads / Offer / CRM Interaction

- `ad_watched_count`
- `ad_watched_per_session`
- `offer_shown_count`
- `offer_purchased_event_count`
- `offer_purchase_event_rate`
- `push_notification_click_count`
- `push_clicks_per_active_day`
- `social_share_count`
- `tutorial_complete_count`
- `feature_unlock_count`
- `subscription_cancel_event_count`
- `subscription_canceled_flag`

### Robustness Transforms

Added `log1p_...` versions for the most skewed volume metrics:

- `log1p_sessions_total`
- `log1p_active_days`
- `log1p_total_session_duration_hours`
- `log1p_levels_completed_total`
- `log1p_transaction_count`
- `log1p_total_revenue_usd`
- `log1p_ad_watched_count`
- `log1p_offer_shown_count`

## 3. Rationale For Each Group

### Lifecycle

These features separate newly acquired users from mature, aging, or recently lapsed users. They are especially important in gaming segmentation because a low-activity new user and a low-activity veteran are not the same CRM problem.

### Portfolio Context

Since `users.csv` is install-level, portfolio depth is one of the few valid pieces of user metadata we can carry into a portfolio-level mart without forcing arbitrary category rollups. Multi-game users may behave differently in both engagement and monetization.

### RFM

RFM is a strong baseline for practical segmentation:

- recency captures current closeness to churn
- frequency captures play habit strength
- monetary captures commercial value

These are easy to explain in an interview and useful for downstream cluster interpretation.

### Engagement Intensity

Raw activity volume alone is not enough. Pairing total sessions with active days and session-duration summaries helps distinguish:

- frequent short-burst users
- deeper long-session users
- low-frequency but high-intensity users

### Engagement Trajectory

Static totals hide whether a player is ramping up or cooling down. The recent-vs-prior 30-day comparison gives a compact, interpretable momentum signal without introducing too many windowed features.

### Progression

Level completion, failure pressure, and progression velocity help separate:

- casual explorers
- highly efficient progressors
- struggling users who may need difficulty tuning or guided offers

These features are more behaviorally specific than pure activity counts.

### Monetization

Segmentation for mobile games should distinguish:

- non-payers vs payers
- low-value vs high-value payers
- trial users vs converted users
- subscription vs IAP preference

Using both totals and product mix keeps the feature set compact while still useful for pricing and CRM actions.

### Ads / Offer / CRM Interaction

Ad watching, offer exposure, offer purchase behavior, and push interactions give direct signal about monetization receptiveness and marketing responsiveness. These are often highly actionable even when revenue is still low.

### Robustness Transforms

Count and revenue features are strongly right-skewed, especially `total_revenue_usd`. Including `log1p` versions makes the mart easier to use for clustering without throwing away the original business-readable metrics.

## 4. Transformations Applied

Cleaning and transformation rules follow the agreed policy:

- negative-duration sessions are excluded before session-based aggregation
- exact duplicate transactions are dropped
- exact duplicate events are dropped
- zero-revenue transactions are retained
- `event_params` is not fully expanded; only event-name level counts are used here

Additional feature transformations:

- session duration converted to hours and minutes for readable aggregates
- recent-vs-earlier activity summarized over fixed 30-day windows
- rates computed with safe zero-division handling
- share features constrained naturally to `[0, 1]`
- `log1p` transforms added for high-skew count and revenue features

No hard winsorization was applied in this mart. For this submission, preserving true whale behavior is more useful than clipping it away, and the added `log1p` columns already reduce the worst skew for clustering.

## 5. Missing Value Strategy

The final parquet is intentionally null-free.

Rules used:

- count features with no observed activity are set to `0`
- monetary totals with no transactions are set to `0`
- rate features with no denominator are set to `0`
- `days_since_last_purchase` for never-payers is set to `days_since_install + 1`
- `days_since_last_session` would also fall back to `days_since_install + 1` if a user had no sessions

Why this strategy:

- it keeps the dataset model-ready
- it makes missingness explicit through companion flags such as `payer_flag`
- it avoids arbitrary median imputation for behavior that never happened

## 6. Highly Skewed Features Handling

The most skewed raw features are:

- session counts
- active days
- total play time
- levels completed
- transaction count
- total revenue
- ad watch counts
- offer shown counts

Handling choice:

- keep the raw business-readable columns
- add parallel `log1p_...` columns for clustering use

This is a good compromise for an interview-style project because it preserves interpretability while still making the feature matrix more stable for distance-based methods.

## 7. Features Intentionally Excluded And Why

### Raw categorical user attributes

Excluded from the mart:

- `country`
- `install_source`
- `device_os`
- `game_id`

Why:

- `game_id` conflicts with the final portfolio-level grain
- `country`, `install_source`, and `device_os` become ambiguous for multi-game users
- forcing one-hot encoding or arbitrary rollups would add complexity and weakly justified assumptions

### Fully parsed `event_params`

Excluded because a full flatten would create a wide sparse matrix and was not needed to capture the highest-value behavioral signals for this submission.

### Very granular temporal features

Excluded examples:

- day-of-week session distributions
- hourly play patterns
- many rolling windows

Why:

- these can quickly bloat the mart
- they are less interview-friendly
- they add noise before clustering unless carefully curated

### Segment labels or supervised targets

Not created yet because this stage is feature preparation only.

## 8. Risks And Caveats

1. Portfolio-level grain is correct for the delivered tables, but it blends behavior across games.
2. Some monetization and offer signals may come from different games for the same user, which reduces game-specific actionability.
3. Event-derived features are based on event counts, not deep parsing of `event_params`.
4. Using the latest cleaned event date as the shared snapshot date means event recency extends beyond the session observation window.
5. Revenue remains highly skewed even after adding `log1p` columns; downstream scaling will still matter.
6. Some features are naturally correlated, especially RFM and engagement totals, so the clustering stage should still review redundancy before final modeling.

## 9. Output Summary

Generated output:

- `src/features/build_user_features.py`
- `data/processed/user_features.parquet`

Current processed mart:

- one row per `user_id`
- 50,000 users
- 63 columns
- no missing values
