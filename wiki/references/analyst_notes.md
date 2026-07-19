---
type: Reference
title: Analyst notes
description: Verbatim analyst notes. Source of every warning in the metric pages.
resource: file:///rawdata/analyst_notes.txt
tags: [notes, tribal-knowledge]
timestamp: 2026-07-19T17:48:32+00:00
---

# Analyst notes (verbatim)

```
saas analytics — running notes
(nobody has cleaned these up, don't judge)

--- MRR ---

Reminder for whoever picks up the revenue dashboard next: you CANNOT just
SUM(monthly_usd) off subscriptions. Two separate traps.

1. trials. state='trial' rows carry a real price in monthly_usd because the
   plan is already attached, but the customer is paying nothing. They must be
   excluded. Filter state='active'.
2. annual. billing_cycle='annual' rows store the ANNUAL amount in the column
   called monthly_usd. Yes. Legacy naming from the 2022 schema, we never
   renamed it because three downstream jobs read the column by name. Divide by
   12 for annual, use as-is for monthly.

This actually bit us — the March board deck overstated MRR by 14% because the
query summed the column straight. Finance caught it a week later. Do not
repeat.

Same warning applies on the invoice side: never sum invoices.total_usd
directly as "revenue" either, an annual invoice is 12 months of value landing
in one row.

--- churn ---

account churn = an account whose LAST subscription (most recent started_on)
has reached state='churned'. Account level, not subscription level — an
account that swapped plans looks like a churned sub plus a new one, and it is
NOT churned.

Careful: sales counts any downgrade as churn in their own deck. So their churn
number is always higher than ours and neither of us is wrong, we're just
answering different questions. If someone quotes a churn % ask which
definition.

--- data quality ---

invoices.paid is only trustworthy from 2025-03-01 onward. We migrated billing
vendors end of Feb 2025 and the backfill of the paid flag before that date was
partial — a lot of pre-March rows say paid=0 when the invoice was in fact
collected. Any collections/AR analysis should start at March 2025.

--- states ---

subscriptions.state is only ever one of: active, trial, churned. That's the
whole set, closed world.

People will ask about 'paused'. Pause exists as a concept but it only lives in
the billing vendor's system and has never synced into this DB. There is no
paused row here and there never was. A paused customer shows up as 'active'
with no invoices.
```
