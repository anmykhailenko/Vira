# Vira Games Portfolio Segmentation Summary

## Objective

Build a practical segmentation from 180 days of portfolio activity to support retention, CRM, and monetization decisions across five casual mobile games.

## Final approach

The final analysis is built at the **portfolio user level**, not the raw install-row level. This is the correct grain because `users.csv` can contain multiple installs per user while the behavior and revenue tables are keyed only by `user_id`. Working at install level would overcount engagement and monetization for multi-game users.

Two clustering approaches were compared on the same standardized feature set:

- `KMeans`
- `GaussianMixture`

The final choice is **KMeans with 5 segments** because it delivered the strongest business-usable balance of separation, segment size sanity, and interpretability.

## Segment summary

| Segment | Share of users | Share of revenue | What it means |
| --- | ---: | ---: | --- |
| VIP Spenders | 4.6% | 97.2% | Small, highly engaged payer cohort that drives almost all portfolio revenue. |
| Subscription Loyalists | 4.4% | 2.7% | Consistent recurring-value users whose spend is overwhelmingly subscription-led. |
| Engaged Free Players | 6.4% | <0.1% | Very active non-payers and the clearest conversion opportunity. |
| Steady Core Players | 39.4% | 0.1% | Repeat users with moderate activity but weak monetization. |
| Lapsing Casuals | 45.2% | <0.1% | Low-frequency, long-recency users with high churn risk. |

## Business implications

1. Revenue is extremely concentrated.
   Protecting VIP Spenders matters more than broad monetization experiments because this cohort contributes almost all revenue.

2. There is a clear conversion bridge.
   Engaged Free Players already show strong engagement, so value-first starter bundles or subscription trials are more promising here than install-day monetization pushes.

3. Most users need retention before monetization.
   Steady Core Players and Lapsing Casuals are better suited to habit-building, return missions, and lightweight lifecycle messaging than aggressive commercial pressure.

## Recommended first actions

1. Protect VIP Spenders with premium CRM, personalized bundles, and early-access style benefits.
2. Reduce churn risk for Subscription Loyalists with renewal reminders and clearer subscription perk visibility.
3. Test post-engagement starter offers and trial upsells on Engaged Free Players.
4. Use milestones, routine nudges, and progression prompts to grow Steady Core Players.
5. Run short, reward-led win-back journeys for Lapsing Casuals.

## Caveats

- This is a portfolio-level segmentation, not a game-specific one.
- `event_params` was intentionally not expanded to keep the submission compact and reproducible.
- A next iteration should test segment stability across time windows before using the segmentation as a long-lived production taxonomy.
