---
type: Metric
title: MRR
description: Monthly Recurring Revenue: active subscriptions only, annual prices normalised to a month.
tags: [revenue, metric, mrr]
timestamp: 2026-07-19T17:48:32+00:00
---

# Definition

MRR is the sum of normalised monthly prices across **active** subscriptions in
[subscriptions](/tables/subscriptions.md). Billing evidence lives in
[invoices](/tables/invoices.md), but invoices are not the basis of MRR.

Normalisation: `monthly_usd` holds the ANNUAL price when
`billing_cycle = 'annual'` (legacy column naming), so it must be divided by 12.

# Warnings

- **Exclude trials.** `state = 'trial'` rows carry a real price but the
  customer pays nothing. Including them inflates MRR. [1]
- **Divide annual by 12.** For `billing_cycle = 'annual'`, `monthly_usd` is the
  annual amount. Summing the column straight is what made the March board deck
  overstate MRR by 14%. [1]
- **Never sum `invoices.total_usd` directly** as revenue — an annual invoice
  lands 12 months of value in a single row. [1]
- **`invoices.paid` is only reliable from 2025-03-01** (billing vendor
  migration; the pre-March backfill was partial). Any collections view must
  start there. [1]

# Examples

```sql
SELECT ROUND(SUM(
         CASE billing_cycle
           WHEN 'annual' THEN monthly_usd / 12.0
           ELSE monthly_usd
         END), 2) AS mrr_usd
FROM subscriptions
WHERE state = 'active';   -- trials excluded on purpose
```

# Citations

1. [Analyst notes](/references/analyst_notes.md) — MRR and data-quality sections.
