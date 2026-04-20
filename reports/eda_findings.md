# EDA Findings

## 1. Dataset profiling summary

- Raw counts: `users` 59,398 rows, `sessions` 2,797,416 rows, `transactions` 265,166 rows.
- Unique portfolio users: 50,000 distinct `user_id` values.
- Data quality flags:
  - 1,262 missing `country` values (handled as `Unknown` in analysis)
  - 13,987 negative-duration sessions removed before any duration-based KPI
  - 6,320 exact duplicate transaction rows removed before revenue aggregation
- Cleaned sessions after invalid-duration removal: 2,783,429 rows.

## 2. Engagement and stickiness

- Average DAU is ~5,490, average WAU is ~15,456, and average MAU is ~23,040.
- Mean DAU/MAU stickiness is ~27%, meaning roughly one in four monthly active users return on a typical day.
- The engagement curve is stable but the end-of-period stickiness drops to ~16%.

## 3. Retention patterns by install source

- D1 retention is around 41–43% across install sources.
- D30 retention is around 20–21% for organic, paid, and cross-promo cohorts.
- D60 retention settles near 12–13%.
- Install-source differences are modest, but organic and Google Ads cohorts are slightly stronger through D30.

## 4. Monetization KPIs

- Payer conversion is low but material: ~9.3% of portfolio users pay.
- ARPPU is high: about $349.70 per paying user.
- Median revenue per paying user is $34.95; the 95th percentile is about $1,606.54.
- The top 5% of paying users account for ~57% of total revenue.

## 5. Session behavior and engagement segmentation signals

- Median user session count is 24 sessions, while the top 1% of users exceed 366 sessions.
- Session frequency is highly skewed, supporting at least a three-bucket segmentation: low-frequency, repeat-active, and super-engaged users.
- Median session duration is ~1,055 seconds (~17.6 minutes); the 99th percentile is ~5,136 seconds (~1.4 hours).
- Long sessions and high session frequency both indicate a strong tail of highly engaged players.

## 6. Business-relevant findings

1. Retention is similar across install sources, so acquisition investment should be paired with stronger onboarding and early engagement rather than relying solely on source-level quality.
2. Revenue is concentrated in a small payer segment, suggesting a priority on premium offer optimization and VIP-focused retention for the top 5% of payers.
3. Engagement is clearly skewed: most users are moderate in frequency, but a smaller group is very active. This supports segmentation into casual, repeat, and power-user cohorts for personalized messaging.

## 7. Generated figures

- `outputs/figures/eda/eda_dau_wau_mau.png`
- `outputs/figures/eda/eda_retention_install_source.png`
- `outputs/figures/eda/eda_revenue_per_user.png`
- `outputs/figures/eda/eda_session_frequency.png`
- `outputs/figures/eda/eda_session_duration.png`
