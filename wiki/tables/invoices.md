---
type: SQLite Table
title: invoices
description: One row per issued bill against a subscription.
resource: sqlite:///rawdata/saas.db#invoices
tags: [schema, saas, invoices]
timestamp: 2026-07-19T17:48:32+00:00
---

# invoices

One row per issued bill against a subscription.

# Schema

| Column | Type | Description |
| --- | --- | --- |
| `id` | INTEGER | Primary key. |
| `sub_id` | INTEGER | FK to [subscriptions](/tables/subscriptions.md). Subscription this invoice bills. |
| `issued_on` | TEXT | Date the invoice was issued (ISO 8601). |
| `total_usd` | REAL | Invoice total. Never sum directly as revenue: annual invoices carry 12 months in one row. |
| `paid` | INTEGER | 1 if collected. Only reliable from 2025-03-01 onward (billing migration). |
| `currency` | TEXT | ISO currency code. Always USD in this dataset. |

# Joins

- Joined with [subscriptions](/tables/subscriptions.md) on `sub_id`.
