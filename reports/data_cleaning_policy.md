# Data Cleaning and Handling Policy

## Purpose

This document defines the data cleaning and handling policy to apply before exploratory data analysis (EDA) and feature engineering for the mobile gaming segmentation project.

The goal is to keep downstream work:

- practical
- reproducible
- consistent across notebooks and scripts
- simple enough for an interview-style project

This policy does **not** implement transformations. It records the decisions that later preprocessing, EDA, and feature engineering should follow.

## Guiding Principles

1. Raw files remain unchanged.
2. Cleaning rules should be explicit, deterministic, and easy to explain.
3. We should avoid silent record loss unless rows are clearly invalid or duplicated.
4. We should not assume business meaning that is not supported by the audit.
5. Shared preprocessing utilities should handle issues that affect multiple downstream steps.
6. EDA can surface anomalies, but core cleaning logic should not live only inside notebooks if it affects features or segmentation outputs.

## Intended Downstream Structure

- Treat `users.csv` as an install-level table keyed most safely by `(user_id, game_id)`, not as a universal one-row-per-user dimension.
- Build user-level features only after making an explicit decision about whether aggregation is:
  - across the full portfolio by `user_id`, or
  - within a game context by `(user_id, game_id)`
- Keep canonical cleaning steps in shared preprocessing utilities so EDA and feature engineering use the same filtered inputs.

## Issue Policies

### 1. `users` table duplication / multiple rows per `user_id`

**What the issue is**

`users.csv` contains multiple rows for some `user_id` values. The audit shows no duplicate `(user_id, game_id)` pairs, so the duplication reflects the same user appearing in multiple games rather than exact repeated rows.

**Why it matters**

Joining activity tables to `users` on `user_id` alone will duplicate downstream rows for multi-game users. This can inflate counts, distort aggregates, and produce incorrect user-level features.

**Chosen handling strategy**

- Do not deduplicate `users` down to one row per `user_id`.
- Treat the table as an install-level or user-game table.
- In shared preprocessing, document and enforce that joins to `users` must be deliberate:
  - use `(user_id, game_id)` when a game-level context exists
  - avoid joining on `user_id` alone unless the analysis explicitly wants one-to-many expansion or a separately constructed user-level dimension
- For user-level segmentation across the portfolio, aggregate behavioral tables to `user_id` first, then attach only user attributes that are stable and well-defined at that level.

**Alternative options briefly considered**

- Keep one arbitrary row per `user_id`
- Keep the earliest install row per `user_id`
- Create a single canonical game per user

**Final decision rationale**

Those options discard valid multi-game information and introduce unsupported assumptions about which row best represents the user. The safer policy is to preserve all valid install rows and force explicit join logic.

**Where the fix belongs**

Shared preprocessing utilities.

### 2. Negative session durations

**What the issue is**

Some rows in `sessions.csv` have `session_end < session_start`, which implies a negative duration.

**Why it matters**

Negative durations make session length metrics invalid and can contaminate engagement features such as total play time, average session length, recency windows, and retention-style activity summaries.

**Chosen handling strategy**

- Flag these rows as invalid session-duration records.
- Exclude them from any duration-based calculations.
- Keep them available only if needed for non-duration counts, but default cleaned session datasets used for feature engineering should remove them entirely to avoid accidental leakage into metrics.

**Alternative options briefly considered**

- Take the absolute value of the duration
- Swap start and end timestamps
- Impute duration from neighboring sessions

**Final decision rationale**

Those repairs are speculative and not supported by the audit. Excluding clearly invalid rows is simpler, safer, and easier to defend.

**Where the fix belongs**

Shared preprocessing utilities.

### 3. Duplicate transaction rows

**What the issue is**

`transactions.csv` contains exact duplicate rows on the full observed transaction signature: `(user_id, transaction_date, product_type, revenue_usd, is_trial)`.

**Why it matters**

Duplicate transactions can overstate revenue, payer counts, conversion-related features, and product mix metrics.

**Chosen handling strategy**

- Drop exact duplicate transaction rows in the canonical cleaned transaction dataset.
- Preserve only one copy of each exact duplicate signature.
- Keep the rule limited to exact duplicates only; do not collapse near-duplicates.

**Alternative options briefly considered**

- Keep all rows and only note the risk in EDA
- Deduplicate using a narrower key
- Try to infer a hidden transaction identifier

**Final decision rationale**

Exact duplicates are the clearest low-risk case for removal. Narrower-key deduplication may wrongly remove legitimate repeated purchases, while leaving exact duplicates in place would bias monetization features.

**Where the fix belongs**

Shared preprocessing utilities.

### 4. Missing country values

**What the issue is**

`users.country` has missing values.

**Why it matters**

Missing geography affects country-level breakdowns and any segmentation features that depend on geography or regional grouping.

**Chosen handling strategy**

- Do not impute a guessed country.
- Standardize missing values to an explicit `"Unknown"` category at analysis or feature-use time.
- Keep the raw missingness available so EDA can quantify its prevalence.
- If region-based features are created later, map missing country to an `"Unknown"` region bucket as well.

**Alternative options briefly considered**

- Drop affected users
- Impute from install source, device OS, or activity timing
- Fill with the modal country

**Final decision rationale**

The missing share is material enough to preserve but not large enough to justify speculative imputation. `"Unknown"` is simple, explicit, and stable for both EDA and modeling.

**Where the fix belongs**

Shared preprocessing utilities, with EDA also reporting the missingness rate.

### 5. `event_params` usage strategy

**What the issue is**

`event_params` is a JSON-like string column whose keys vary by `event_name`.

**Why it matters**

Blindly expanding all parameters would create a wide, sparse, and harder-to-maintain dataset. It also increases the risk of inconsistent parsing logic across notebooks and feature scripts.

**Chosen handling strategy**

- Do not parse or expand `event_params` during base ingestion.
- Parse it selectively and only for event types that are directly needed for a specific analysis or feature set.
- Centralize any parsing helpers so the same event-specific logic is reused across EDA and feature engineering.
- Keep the default event table narrow: core event columns plus raw `event_params`.

**Alternative options briefly considered**

- Fully flatten all keys into columns upfront
- Ignore `event_params` entirely
- Parse JSON ad hoc inside each notebook

**Final decision rationale**

Full flattening is unnecessary and brittle, while ignoring the field would waste useful signal. Selective, reusable parsing keeps the project practical and avoids overengineering.

**Where the fix belongs**

Feature engineering, supported by shared preprocessing utilities for reusable parsers. EDA may parse selected event types only when needed.

### 6. Zero-revenue transactions

**What the issue is**

Some transaction rows have `revenue_usd == 0`.

**Why it matters**

These rows can affect payer definitions, revenue summaries, trial conversion logic, and monetization features. However, the audit does not prove they are erroneous.

**Chosen handling strategy**

- Retain zero-revenue transactions in the cleaned dataset.
- Do not count them as positive revenue when building monetization features.
- When defining payers, use a strict positive-revenue rule unless a later business definition explicitly says otherwise.
- Analyze them separately in EDA, especially alongside `is_trial`.

**Alternative options briefly considered**

- Drop all zero-revenue rows
- Convert them to missing revenue
- Treat them as paid transactions by default

**Final decision rationale**

Dropping them would impose an unsupported assumption. Retaining them while using explicit downstream definitions keeps the data intact and prevents accidental revenue inflation.

**Where the fix belongs**

EDA and feature engineering, with optional shared helper flags if reused often.

### 7. Exact duplicate event rows

**What the issue is**

`events.csv` contains at least one exact duplicate row on `(user_id, event_timestamp, event_name, event_params)`.

**Why it matters**

Even a small number of exact duplicates can distort event counts and event-derived features if duplicate handling is inconsistent.

**Chosen handling strategy**

- Drop exact duplicate event rows in the canonical cleaned events dataset.
- Do not attempt broader event deduplication beyond exact matches.

**Alternative options briefly considered**

- Ignore the issue because the count is small
- Deduplicate on a looser event signature

**Final decision rationale**

Removing exact duplicates is low risk and easy to explain. Looser deduplication could remove legitimate repeated actions.

**Where the fix belongs**

Shared preprocessing utilities.

### 8. Duplicate `(user_id, session_start)` pairs

**What the issue is**

`sessions.csv` has duplicate `(user_id, session_start)` pairs, but no duplicate `session_id` values and no exact duplicate rows.

**Why it matters**

This may indicate concurrent sessions, logging granularity limits, or another benign data-generation pattern. If treated incorrectly, valid sessions could be removed.

**Chosen handling strategy**

- Do not deduplicate these rows.
- Treat `session_id` as the session-level identifier.
- Only use these duplicates as an EDA note and monitor whether they affect any session-based feature logic.

**Alternative options briefly considered**

- Collapse rows on `(user_id, session_start)`
- Keep only one session per start timestamp

**Final decision rationale**

There is not enough evidence that these are errors. Since `session_id` is unique, aggressive deduplication would be riskier than keeping them.

**Where the fix belongs**

EDA only, with no cleaning action in shared preprocessing at this stage.

## Summary of Where Logic Should Live

### Shared preprocessing utilities

- enforce safe handling expectations for `users` joins
- drop exact duplicate transaction rows
- drop exact duplicate event rows
- remove invalid negative-duration sessions from canonical cleaned session inputs
- standardize missing country handling for reusable cleaned datasets
- provide reusable selective parsers for `event_params` when needed

### EDA only

- quantify multi-game user prevalence and join-risk implications
- inspect zero-revenue transactions, especially versus `is_trial`
- monitor duplicate `(user_id, session_start)` pairs without removing them
- report missing-country prevalence and impact on geography cuts

### Feature engineering

- define payer logic using explicit positive-revenue rules
- selectively parse `event_params` for only the event types needed by features
- decide whether segmentation is portfolio-level by `user_id` or game-aware by `(user_id, game_id)`

## Final Policy Decisions

1. Preserve raw data and apply cleaning only in reproducible downstream layers.
2. Treat `users` as an install-level table, not a one-row-per-user dimension.
3. Remove clearly invalid or clearly duplicated records only when the evidence is strong:
   - negative-duration sessions: exclude
   - exact duplicate transactions: drop
   - exact duplicate events: drop
4. Keep ambiguous cases unless there is clear evidence they are wrong:
   - zero-revenue transactions: retain
   - duplicate `(user_id, session_start)` session pairs: retain
5. Do not use speculative imputations:
   - missing country becomes explicit `"Unknown"` rather than guessed
   - invalid timestamps are not repaired heuristically
6. Keep `event_params` raw by default and parse only selectively for clear downstream use cases.
