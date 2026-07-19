---
type: Index
title: SaaS subscription analytics wiki
description: Compiled knowledge for the SaaS subscription analytics database.
okf_version: "0.1"
timestamp: 2026-07-19T17:48:32+00:00
---

# SaaS subscription analytics wiki

## Tables

* [accounts](tables/accounts.md) - One row per customer organisation. The top of the hierarchy.
* [invoices](tables/invoices.md) - One row per issued bill against a subscription.
* [subscriptions](tables/subscriptions.md) - One row per plan a customer holds. Carries state and price.

## Metrics

* [MRR](metrics/mrr.md) - Monthly Recurring Revenue: active subscriptions only, annual prices normalised to a month.
* [Account churn](metrics/account_churn.md) - Account churn: an account whose most recent subscription has reached state 'churned'.

## References

* [Analyst notes](references/analyst_notes.md) - Verbatim analyst notes. Source of every warning in the metric pages.
