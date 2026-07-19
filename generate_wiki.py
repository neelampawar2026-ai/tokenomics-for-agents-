"""THE COMPILER. Raw data -> wiki/ (an OKF v0.1 bundle). Runs once.

Two passes:
  1. structural  — PRAGMA table_info / foreign_key_list. Fully deterministic.
  2. semantic    — natural language. Templated here; one LLM call in production.

Everything downstream (ask.py, humans, any LLM) reads only wiki/.
"""

import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "rawdata", "saas.db")
NOTES = os.path.join(HERE, "rawdata", "analyst_notes.txt")
WIKI = os.path.join(HERE, "wiki")
STAGING = WIKI + ".partial"

NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
TODAY = NOW[:10]


def frontmatter(**kv):
    lines = ["---"]
    for k, v in kv.items():
        if v is None:
            continue
        lines.append("%s: %s" % (k, v))
    lines.append("---")
    return "\n".join(lines) + "\n"


def write(relpath, text):
    # Writes land in a staging dir; main() swaps it into place only on success,
    # so a failed compile (bad API key, missing dep) leaves the old wiki intact.
    path = os.path.join(STAGING, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    print("  wrote wiki/" + relpath)


# --------------------------------------------------------------------------
# THE SEMANTIC PASS. This is the only function in the pipeline that produces
# natural language. Everything else is deterministic extraction.
# --------------------------------------------------------------------------

def load_env(path=os.path.join(HERE, ".env")):
    """Read KEY=value lines into os.environ. Existing vars win.

    ponytail: 6-line parser, no quoting/multiline/export support. Swap for
    python-dotenv if the file ever needs more than KEY=value.
    """
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def describe_llm(table, columns, foreign_keys):
    """The `--llm` implementation of describe(). Same contract, real model.

    Imported lazily so the default (templated) path stays stdlib-only —
    that zero-dependency property is the whole point of the demo.
    """
    from google import genai  # requires: pip install -U google-genai
    from pydantic import BaseModel, Field  # ships with google-genai

    class Column(BaseModel):
        name: str = Field(description="Exact column name, copied verbatim.")
        description: str = Field(description="One line describing the column.")

    class TableDoc(BaseModel):
        description: str = Field(description="One line describing the table.")
        columns: list[Column]

    load_env()
    client = genai.Client()  # reads GEMINI_API_KEY from the environment

    fk_note = (
        "\n".join("- %s references table %s" % (c, t) for c, t in foreign_keys.items())
        or "- none"
    )
    with open(NOTES) as f:
        notes = f.read()

    interaction = client.interactions.create(
        model="gemini-3.5-flash",
        system_instruction=(
            "You document database tables for a knowledge base that AI agents read "
            "instead of querying raw data. Write for an analyst who has never seen "
            "this schema. Where the analyst notes reveal a trap in a column, say so "
            "in that column's description — those warnings are the point."
        ),
        input=(
            "Table: %s\nColumns: %s\nForeign keys:\n%s\n\n"
            "Analyst notes (tribal knowledge, not in the schema):\n```\n%s\n```\n\n"
            "Write a one-line table description and a one-line description per column."
        )
        % (table, ", ".join(columns), fk_note, notes),
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": TableDoc.model_json_schema(),
        },
    )

    doc = TableDoc.model_validate_json(interaction.output_text)
    col_desc = {c.name: c.description for c in doc.columns}
    # Any column the model skipped still needs a description — the writer indexes by name.
    return doc.description, {c: col_desc.get(c, "Column %s of %s." % (c, table)) for c in columns}


def describe(table, columns, foreign_keys):
    """In production, replace this body with a single LLM call.
    Nothing else in the pipeline changes.

    Input: a table name, its columns, its foreign keys.
    Output: (one_line_description, {column_name: description}).
    The rest of the compiler consumes only that contract, so swapping the
    template below for an LLM prompt leaves the OKF output format identical.

    `--llm` does exactly that swap — see describe_llm() above. The templated
    body below is the default so the demo needs no API key and no installs.
    """
    if "--llm" in sys.argv:
        return describe_llm(table, columns, foreign_keys)

    blurbs = {
        "accounts": "One row per customer organisation. The top of the hierarchy.",
        "subscriptions": "One row per plan a customer holds. Carries state and price.",
        "invoices": "One row per issued bill against a subscription.",
    }
    cols = {
        "name": "Display name of the account.",
        "segment": "Sales segment: smb | midmarket | enterprise.",
        "region": "Deployment region of the account.",
        "signup_date": "Date the account was created (ISO 8601).",
        "plan": "Plan tier the subscription is on.",
        "account_id": "Owning account.",
        "sub_id": "Subscription this invoice bills.",
        "state": "Lifecycle state. Closed set: active, trial, churned. 'paused' does not exist here.",
        "billing_cycle": "monthly or annual. Changes how monthly_usd must be read.",
        "monthly_usd": "Price. WARNING: for billing_cycle='annual' this holds the ANNUAL amount (legacy naming). Divide by 12 for MRR.",
        "started_on": "Date the subscription began (ISO 8601).",
        "ended_on": "Date the subscription ended, NULL unless state='churned'.",
        "issued_on": "Date the invoice was issued (ISO 8601).",
        "total_usd": "Invoice total. Never sum directly as revenue: annual invoices carry 12 months in one row.",
        "paid": "1 if collected. Only reliable from 2025-03-01 onward (billing migration).",
        "currency": "ISO currency code. Always USD in this dataset.",
    }
    desc = blurbs.get(table, "Table %s." % table)
    return desc, {c: cols.get(c, "Column %s of %s." % (c, table)) for c in columns}


# --------------------------------------------------------------------------
# Structural pass
# --------------------------------------------------------------------------

def compile_tables(con):
    entries = []
    tables = [
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    for t in tables:
        info = con.execute("PRAGMA table_info(%s)" % t).fetchall()
        fks = con.execute("PRAGMA foreign_key_list(%s)" % t).fetchall()
        fk_by_col = {r[3]: r[2] for r in fks}  # from-column -> referenced table

        columns = [r[1] for r in info]
        blurb, col_desc = describe(t, columns, fk_by_col)

        rows = ["| Column | Type | Description |", "| --- | --- | --- |"]
        for _, name, ctype, _nn, _dflt, pk in info:
            if pk:
                d = "Primary key."
            elif name in fk_by_col:
                ref = fk_by_col[name]
                d = "FK to [%s](/tables/%s.md). %s" % (ref, ref, col_desc[name])
            else:
                d = col_desc[name]
            # A bare "|" in a description would split the markdown cell. Matters
            # most on the --llm path, where the text isn't ours to control.
            rows.append("| `%s` | %s | %s |" % (name, ctype or "ANY", d.replace("|", "\\|")))

        joins = (
            "\n".join(
                "- Joined with [%s](/tables/%s.md) on `%s`." % (ref, ref, col)
                for col, ref in fk_by_col.items()
            )
            or "- No declared foreign keys."
        )

        body = frontmatter(
            type="SQLite Table",
            title=t,
            description=blurb,
            resource="sqlite:///rawdata/saas.db#%s" % t,
            tags="[schema, saas, %s]" % t,
            timestamp=NOW,
        )
        body += "\n# %s\n\n%s\n\n# Schema\n\n%s\n\n# Joins\n\n%s\n" % (
            t,
            blurb,
            "\n".join(rows),
            joins,
        )
        write("tables/%s.md" % t, body)
        entries.append((t, "tables/%s.md" % t, blurb))
    return entries


def compile_reference():
    with open(NOTES) as f:
        notes = f.read()
    desc = "Verbatim analyst notes. Source of every warning in the metric pages."
    body = frontmatter(
        type="Reference",
        title="Analyst notes",
        description=desc,
        resource="file:///rawdata/analyst_notes.txt",
        tags="[notes, tribal-knowledge]",
        timestamp=NOW,
    )
    body += "\n# Analyst notes (verbatim)\n\n```\n%s\n```\n" % notes.rstrip()
    write("references/analyst_notes.md", body)
    return [("Analyst notes", "references/analyst_notes.md", desc)]


def compile_metrics():
    """Semantic output derived from the four facts in analyst_notes.txt."""
    entries = []

    desc = "Monthly Recurring Revenue: active subscriptions only, annual prices normalised to a month."
    body = frontmatter(
        type="Metric",
        title="MRR",
        description=desc,
        tags="[revenue, metric, mrr]",
        timestamp=NOW,
    )
    body += """
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
"""
    write("metrics/mrr.md", body)
    entries.append(("MRR", "metrics/mrr.md", desc))

    desc = "Account churn: an account whose most recent subscription has reached state 'churned'."
    body = frontmatter(
        type="Metric",
        title="Account churn",
        description=desc,
        tags="[retention, metric, churn]",
        timestamp=NOW,
    )
    body += """
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
"""
    write("metrics/account_churn.md", body)
    entries.append(("Account churn", "metrics/account_churn.md", desc))
    return entries


def compile_index(tables, metrics, refs):
    body = frontmatter(
        type="Index",
        title="SaaS subscription analytics wiki",
        description="Compiled knowledge for the SaaS subscription analytics database.",
        okf_version='"0.1"',
        timestamp=NOW,
    )
    body += "\n# SaaS subscription analytics wiki\n"
    for heading, entries in (("Tables", tables), ("Metrics", metrics), ("References", refs)):
        body += "\n## %s\n\n" % heading
        # This exact bullet format is the consumer's parse contract.
        for title, path, desc in entries:
            body += "* [%s](%s) - %s\n" % (title, path, desc)
    write("index.md", body)


def compile_log(n_tables, n_metrics):
    body = "# Log\n\n## %s\n\n" % TODAY
    body += "- **Initialization**: Compiled OKF bundle from `rawdata/saas.db` and `rawdata/analyst_notes.txt`.\n"
    body += "- **Creation**: %d table pages from `PRAGMA table_info` / `PRAGMA foreign_key_list`.\n" % n_tables
    body += "- **Creation**: %d metric pages synthesized from the analyst notes.\n" % n_metrics
    body += "- **Creation**: 1 reference page mirroring the raw notes verbatim.\n"
    write("log.md", body)


def main():
    if not os.path.exists(DB):
        raise SystemExit("missing %s — run seed.py first" % DB)
    if os.path.exists(STAGING):
        shutil.rmtree(STAGING)

    print("compiling wiki/ ...")
    con = sqlite3.connect(DB)
    tables = compile_tables(con)
    con.close()
    refs = compile_reference()
    metrics = compile_metrics()
    compile_index(tables, metrics, refs)
    compile_log(len(tables), len(metrics))

    # Everything compiled — now, and only now, replace the previous bundle.
    if os.path.exists(WIKI):
        shutil.rmtree(WIKI)
    os.rename(STAGING, WIKI)
    print("done. The raw data is never read again.")


if __name__ == "__main__":
    main()
