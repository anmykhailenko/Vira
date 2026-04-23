# Vira Games Portfolio Segmentation Summary

## Objective

Build a practical user segmentation from 180 days of portfolio activity to support retention, CRM, and monetization decisions for five casual mobile games.

## Final approach

The final segmentation is built at the **portfolio user level** rather than the raw install-row level. This is important because some users appear in multiple games in `users.csv`, while behavioral and revenue tables only expose `user_id`. A user-level grain avoids duplicating engagement and revenue across installs.

The final model uses **K-Means with 5 segments** after comparing it with a Gaussian Mixture benchmark across multiple cluster counts. The chosen solution offered the best business-usable balance of:

- cluster separation
- segment size sanity
- interpretability

## Final segments

### 1. VIP Spenders

- 4.6% of users
- 97.2% of revenue

Highly engaged, high-value users with strong progression and repeat spend. They are the portfolio’s main revenue engine and should receive premium retention treatment, personalized bundles, and early access style benefits.

### 2. Subscription Loyalists

- 4.4% of users
- 2.7% of revenue

Consistent users whose monetization is overwhelmingly subscription-led. They are lower-value than VIP spenders on a per-user basis, but operationally important because they represent stable recurring value. Focus on renewal support, subscription perk visibility, and churn prevention.

### 3. Engaged Free Players

- 6.4% of users
- near-zero revenue

Very active users with strong session depth but no real monetization. They are the clearest upsell opportunity. The best actions are value-first starter bundles or subscription trials triggered after proven engagement, not at install.

### 4. Steady Core Players

- 39.4% of users
- 0.1% of revenue

Moderately engaged repeat users who still show some current activity but little monetization. They are a development cohort: nurture routine play, progression momentum, and first-purchase conversion.

### 5. Lapsing Casuals

- 45.2% of users
- near-zero revenue

Low-frequency, long-recency users with limited commitment and high churn risk. They should be targeted with lightweight win-back campaigns, short return missions, and low-friction reward loops rather than hard-sell monetization.

## What matters most for the business

1. Revenue is extremely concentrated.
   The top-value payer cohort is small but economically dominant, so protecting that segment matters more than broad monetization experiments.

2. There is a clear monetization bridge segment.
   Engaged Free Players are active enough to justify value-first conversion campaigns.

3. Most of the portfolio is low-value or fading.
   Lapsing Casuals and much of the Steady Core group need retention and habit-building tactics before aggressive monetization.

## Recommended first actions

1. Protect VIP Spenders with premium CRM and bundle personalization.
2. Reduce subscription churn risk by reinforcing value for Subscription Loyalists.
3. Test post-engagement starter offers and trial upsells on Engaged Free Players.
4. Run short, reward-led return journeys for Lapsing Casuals.
5. Use milestones and routine nudges to grow Steady Core Players into higher-value states.

## Caveats

- This is a portfolio-level segmentation, not a game-specific one.
- `event_params` was intentionally not expanded to keep the project compact and reproducible.
- A next iteration should test stability across time windows and consider light segment response modeling.
