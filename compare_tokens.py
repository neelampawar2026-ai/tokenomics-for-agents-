"""Side-by-side token cost: wiki context vs raw-data dump, and how each scales.

Run from okf-demo/:  python3 compare_tokens.py

The single-question comparison in ask.py shows ONE data point. The point of the
pattern is the SLOPE: the wiki is O(concepts), the dump is O(rows). This shows
both, and projects the dump forward as the database grows.
"""

import os
import re
import sqlite3

WIKI = "wiki"
DB = "rawdata/saas.db"
NOTES = "rawdata/analyst_notes.txt"
CONTEXT_WINDOW = 1_000_000  # gemini-3.5-flash

# Crude on purpose: ~4 chars per token. Same estimator ask.py uses.
tokens = lambda text: len(text) // 4


def read(path):
    with open(path) as f:
        return f.read()


def dump_rows(con, limit=None):
    """Every row of every table as text — the naive alternative, really walked."""
    parts = []
    for (t,) in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall():
        q = "SELECT * FROM %s" % t + (" LIMIT %d" % limit if limit else "")
        cur = con.execute(q)
        parts.append("TABLE %s (%s)" % (t, ", ".join(d[0] for d in cur.description)))
        parts.extend(" | ".join(str(v) for v in row) for row in cur)
    return "\n".join(parts)


def main():
    con = sqlite3.connect(DB)
    n_rows = sum(
        con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        for (t,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    )

    # --- what each path actually costs -----------------------------------
    pages = {
        os.path.relpath(os.path.join(r, f), WIKI): read(os.path.join(r, f))
        for r, _, fs in os.walk(WIKI)
        for f in fs
        if f.endswith(".md")
    }
    bundle = sum(tokens(t) for t in pages.values())
    index_only = tokens(pages["index.md"])
    # What ask.py actually loads for the MRR question: index + 5 opened pages.
    typical = index_only + sum(
        tokens(pages[p])
        for p in (
            "metrics/mrr.md",
            "tables/accounts.md",
            "tables/subscriptions.md",
            "tables/invoices.md",
            "references/analyst_notes.md",
        )
    )
    dump = tokens(dump_rows(con) + read(NOTES))

    print("\nPER-PAGE COST OF THE WIKI")
    print("-" * 58)
    for name in sorted(pages):
        print("  %-34s %6d tokens" % (name, tokens(pages[name])))
    print("  %-34s %6d tokens" % ("ENTIRE BUNDLE (all 8 pages)", bundle))

    print("\nONE QUESTION: 'how do I calculate MRR?'")
    print("-" * 58)
    print("  %-34s %6d tokens" % ("1. index.md only", index_only))
    print("  %-34s %6d tokens" % ("2. + 5 pages it links to", typical))
    print("  %-34s %6d tokens" % ("vs. dumping all %d rows" % n_rows, dump))
    print("  %-34s %5.0fx cheaper" % ("", dump / typical))
    print("  Even loading the WHOLE wiki is %.0fx cheaper than one dump." % (dump / bundle))

    # --- the actual punchline: the slope ---------------------------------
    per_row = dump / n_rows
    print("\nHOW EACH SIDE SCALES AS THE DATABASE GROWS")
    print("-" * 58)
    print("  %-14s %14s %14s %10s" % ("rows in DB", "raw dump", "wiki context", "ratio"))
    for mult, label in ((1, ""), (10, ""), (100, ""), (1000, "")):
        rows = n_rows * mult
        projected = int(per_row * rows)
        flag = "  <- measured" if mult == 1 else "  (projected)"
        print("  %-14s %14s %14s %9.0fx%s"
              % ("{:,}".format(rows), "{:,}".format(projected),
                 "{:,}".format(typical), projected / typical, flag))

    print("\n  The wiki column never moves. That is the whole argument.")

    # --- make it concrete ------------------------------------------------
    print("\nAGAINST A 1M-TOKEN CONTEXT WINDOW")
    print("-" * 58)
    print("  wiki context : %5.1f%% of the window" % (100 * typical / CONTEXT_WINDOW))
    print("  raw dump     : %5.1f%% of the window" % (100 * dump / CONTEXT_WINDOW))
    breaks_at = int(CONTEXT_WINDOW / per_row)
    print("  The dump stops fitting at ~%s rows (~%.0fx today's data)."
          % ("{:,}".format(breaks_at), breaks_at / n_rows))
    print("  The wiki still fits at any size — it scales with CONCEPTS.\n")

    con.close()


if __name__ == "__main__":
    main()
