# Data Audit

## 1. Files found and row counts

Raw directory: `data/raw/ds_test_task_dataset`

| File | Rows | Columns |
| --- | ---: | ---: |
| `users.csv` | 59,398 | 6 |
| `sessions.csv` | 2,797,416 | 6 |
| `transactions.csv` | 265,166 | 5 |
| `events.csv` | 2,255,431 | 4 |

Notes:
- The raw dataset path is available under the scaffolded project path and resolves correctly through `src.utils.config.RAW_DATA_DIR`.
- All four expected files were found.

## 2. Column schema per file

### `users.csv`

| Column | Loaded dtype |
| --- | --- |
| `user_id` | `string` |
| `install_date` | `datetime64[ns]` |
| `install_source` | `string` |
| `country` | `string` |
| `device_os` | `string` |
| `game_id` | `string` |

### `sessions.csv`

| Column | Loaded dtype |
| --- | --- |
| `user_id` | `string` |
| `session_id` | `string` |
| `session_start` | `datetime64[ns, UTC]` |
| `session_end` | `datetime64[ns, UTC]` |
| `levels_completed` | `Int64` |
| `levels_failed` | `Int64` |

### `transactions.csv`

| Column | Loaded dtype |
| --- | --- |
| `user_id` | `string` |
| `transaction_date` | `datetime64[ns, UTC]` |
| `product_type` | `string` |
| `revenue_usd` | `float64` |
| `is_trial` | `boolean` |

### `events.csv`

| Column | Loaded dtype |
| --- | --- |
| `user_id` | `string` |
| `event_timestamp` | `datetime64[ns, UTC]` |
| `event_name` | `string` |
| `event_params` | `string` |

## 3. Date fields and parsing notes

- `users.install_date` is parsed explicitly with format `%Y-%m-%d`.
- `sessions.session_start`, `sessions.session_end`, `transactions.transaction_date`, and `events.event_timestamp` are parsed explicitly as UTC timestamps.
- Parsing completed without `NaT` values in any of the known date columns.

Observed date ranges:

| Dataset | Date column | Min | Max |
| --- | --- | --- | --- |
| `users` | `install_date` | `2025-07-01` | `2025-12-27` |
| `sessions` | `session_start` | `2025-07-01 06:27:00+00:00` | `2025-12-27 23:59:00+00:00` |
| `transactions` | `transaction_date` | `2025-07-02 12:00:00+00:00` | `2025-12-27 22:00:00+00:00` |
| `events` | `event_timestamp` | `2025-07-01 06:29:36+00:00` | `2026-01-11 23:36:00+00:00` |

Notes:
- `events` extends beyond the install window, which is plausible because events continue after install.
- `session_end` includes fractional seconds and parses cleanly with pandas UTC datetime parsing.

## 4. Missing values summary

| File | Missing values |
| --- | --- |
| `users.csv` | `country`: 1,262; all other columns: 0 |
| `sessions.csv` | no missing values detected |
| `transactions.csv` | no missing values detected |
| `events.csv` | no missing values detected |

Notes:
- `country` is the only column with missing values observed in the raw data.
- No missing timestamps were found in the session, transaction, or event tables.

## 5. Duplicate checks

### `users.csv`

- Exact duplicate rows: 0
- Duplicate `user_id`: 9,398
- Duplicate `(user_id, game_id)` pairs: 0
- Unique `user_id` count: 50,000

Interpretation:
- `user_id` is **not globally unique** in `users.csv`.
- The duplicates appear to reflect the same user appearing in multiple games rather than duplicate rows for the same game.
- Distribution of games per `user_id`:
  - 42,514 users appear in 1 game
  - 5,574 users appear in 2 games
  - 1,912 users appear in 3 games

### `sessions.csv`

- Exact duplicate rows: 0
- Duplicate `session_id`: 0
- Duplicate `(user_id, session_start)` pairs: 6,617

### `transactions.csv`

- Exact duplicate rows: 6,320
- Duplicate transaction signature on `(user_id, transaction_date, product_type, revenue_usd, is_trial)`: 6,320

### `events.csv`

- Exact duplicate rows: 1
- Duplicate event signature on `(user_id, event_timestamp, event_name, event_params)`: 1

## 6. Basic key integrity notes and risks for downstream analysis

### Foreign-key coverage

All activity tables reference known user IDs:

- `sessions.user_id` missing in `users.user_id`: 0
- `transactions.user_id` missing in `users.user_id`: 0
- `events.user_id` missing in `users.user_id`: 0

### Integrity risks

1. `users.csv` is not one-row-per-user.
   - Joining `sessions`, `transactions`, or `events` to `users` on `user_id` alone will duplicate rows for multi-game users.
   - This is the most important downstream modeling risk in the raw data.

2. Negative session durations exist.
   - 13,987 rows have `session_end < session_start`.
   - These should be flagged before any session-duration based KPI or feature engineering.

3. Duplicate transactions exist.
   - 6,320 transaction rows are duplicated on the full observed transaction signature.
   - Revenue metrics can be overstated if duplicates are not handled deliberately.

4. Zero-revenue transactions exist.
   - 3,981 rows have `revenue_usd == 0`.
   - These may be legitimate trial-related or edge-case transaction records and should not be dropped without checking business meaning.

5. `country` has missing values.
   - Missing geography may affect breakdowns by country or region.

## 7. Notes on `event_params` and whether/how it should be parsed later

- `event_params` is stored as a JSON-like string column.
- A deterministic sample of 10,000 rows parsed successfully as JSON in all 10,000 cases.
- Sampled parameter keys vary by event type and look well-structured:
  - `ad_watched`: `ad_format`, `ad_network`
  - `feature_unlock`: `feature`
  - `level_complete`: `duration_sec`, `level_id`, `score`
  - `level_fail`: `duration_sec`, `level_id`, `score`
  - `level_start`: `level_id`
  - `offer_purchased`: `offer_id`
  - `offer_shown`: `offer_id`, `price_usd`
  - `push_notification_click`: `campaign`
  - `social_share`: `platform`, `share_type`
  - `subscription_cancel`: `reason`
  - `tutorial_complete`: `duration_sec`

Recommendation:
- Do **not** expand `event_params` during raw ingestion.
- Parse it later only for event-specific analyses or feature engineering, and preferably selectively by `event_name` to avoid unnecessary wide sparse tables.

## 8. Recommended canonical load functions for later agents

Use the shared loader module in `src/data/load_data.py`:

- `load_users()`
- `load_sessions()`
- `load_transactions()`
- `load_events()`
- `load_all_datasets()`

Why these should be the defaults:

- Paths come from `src.utils.config`.
- Date parsing is explicit and consistent.
- Column validation is built in.
- File resolution is tolerant to small naming or extension variations.
- Raw files remain unchanged.

## Recommended usage notes for downstream agents

- Treat `users.csv` as an install-level table, not automatically as a unique user dimension.
- Avoid joining activity tables to `users` on `user_id` alone without a deliberate choice about multi-game users.
- Keep duplicate handling explicit and analysis-dependent instead of silently dropping records inside the loader.
- Use the validation module in `src/data/validate_data.py` when a quick raw-data audit is needed again.
