---
type: Metric
title: Account churn
description: Account churn: an account whose most recent subscription has reached state 'churned'.
tags: [retention, metric, churn]
timestamp: 2026-07-19T17:48:32+00:00
---

# Definition

An account in [accounts](/tables/accounts.md) is churned when its **most recent**
subscription (highest `started_on`) in [subscriptions](/tables/subscriptions.md)
has `state = 'churned'`.

This is deliberately account-level. An account that swapped plans shows up as a
churned subscription plus a new one and is **not** churned.

# Warnings

- **Sales uses a different definition.** Their deck counts any downgrade as
  churn, so their number is always higher than this one. Neither is wrong —
  they answer different questions. Always ask which definition a quoted churn
  percentage uses. [1]
- **There is no 'paused' state.** `subscriptions.state` is a closed set:
  `active | trial | churned`. Pause exists in the billing vendor's system and
  has never synced into this database. A paused customer appears as `active`
  with no invoices — do not read that as churn. [1]

# Examples

```sql
WITH latest AS (
  SELECT account_id, state,
         ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY started_on DESC) AS rn
  FROM subscriptions
)
SELECT COUNT(*) AS churned_accounts
FROM latest WHERE rn = 1 AND state = 'churned';
```

# Citations

1. [Analyst notes](/references/analyst_notes.md) — churn and states sections.
