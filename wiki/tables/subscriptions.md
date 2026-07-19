---
type: SQLite Table
title: subscriptions
description: One row per plan a customer holds. Carries state and price.
resource: sqlite:///rawdata/saas.db#subscriptions
tags: [schema, saas, subscriptions]
timestamp: 2026-07-19T17:48:32+00:00
---

# subscriptions

One row per plan a customer holds. Carries state and price.

# Schema

| Column | Type | Description |
| --- | --- | --- |
| `id` | INTEGER | Primary key. |
| `account_id` | INTEGER | FK to [accounts](/tables/accounts.md). Owning account. |
| `plan` | TEXT | Plan tier the subscription is on. |
| `state` | TEXT | Lifecycle state. Closed set: active, trial, churned. 'paused' does not exist here. |
| `billing_cycle` | TEXT | monthly or annual. Changes how monthly_usd must be read. |
| `monthly_usd` | REAL | Price. WARNING: for billing_cycle='annual' this holds the ANNUAL amount (legacy naming). Divide by 12 for MRR. |
| `started_on` | TEXT | Date the subscription began (ISO 8601). |
| `ended_on` | TEXT | Date the subscription ended, NULL unless state='churned'. |

# Joins

- Joined with [accounts](/tables/accounts.md) on `account_id`.
