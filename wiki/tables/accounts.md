---
type: SQLite Table
title: accounts
description: One row per customer organisation. The top of the hierarchy.
resource: sqlite:///rawdata/saas.db#accounts
tags: [schema, saas, accounts]
timestamp: 2026-07-19T17:48:32+00:00
---

# accounts

One row per customer organisation. The top of the hierarchy.

# Schema

| Column | Type | Description |
| --- | --- | --- |
| `id` | INTEGER | Primary key. |
| `name` | TEXT | Display name of the account. |
| `segment` | TEXT | Sales segment: smb \| midmarket \| enterprise. |
| `region` | TEXT | Deployment region of the account. |
| `signup_date` | TEXT | Date the account was created (ISO 8601). |

# Joins

- No declared foreign keys.
