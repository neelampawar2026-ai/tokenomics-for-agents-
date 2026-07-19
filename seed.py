"""Creates the raw data source: a SQLite DB of SaaS subscription analytics.

Deterministic (fixed random seed) and idempotent (deletes the DB first).
This is a RAW SOURCE. Nothing else in the demo writes to it.
"""

import os
import random
import sqlite3
from datetime import date, timedelta

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rawdata", "saas.db")

N_ACCOUNTS = 600
N_SUBSCRIPTIONS = 3500
N_INVOICES = 4000

PLANS = ["starter", "team", "business", "enterprise"]
SEGMENTS = ["smb", "midmarket", "enterprise"]
REGIONS = ["us-east", "us-west", "emea", "apac"]

random.seed(20250719)


def iso(d):
    return d.isoformat()


def main():
    if os.path.exists(DB):
        os.remove(DB)

    con = sqlite3.connect(DB)
    c = con.cursor()

    # FKs are declared with REFERENCES so PRAGMA foreign_key_list can find them.
    # The compiler turns those into the wiki's cross-links.
    c.executescript(
        """
        CREATE TABLE accounts (
            id           INTEGER PRIMARY KEY,
            name         TEXT NOT NULL,
            segment      TEXT NOT NULL,
            region       TEXT NOT NULL,
            signup_date  TEXT NOT NULL
        );

        CREATE TABLE subscriptions (
            id            INTEGER PRIMARY KEY,
            account_id    INTEGER NOT NULL REFERENCES accounts(id),
            plan          TEXT NOT NULL,
            state         TEXT NOT NULL,
            billing_cycle TEXT NOT NULL,
            monthly_usd   REAL NOT NULL,
            started_on    TEXT NOT NULL,
            ended_on      TEXT
        );

        CREATE TABLE invoices (
            id          INTEGER PRIMARY KEY,
            sub_id      INTEGER NOT NULL REFERENCES subscriptions(id),
            issued_on   TEXT NOT NULL,
            total_usd   REAL NOT NULL,
            paid        INTEGER NOT NULL,
            currency    TEXT NOT NULL
        );
        """
    )

    start = date(2023, 1, 1)

    accounts = []
    for i in range(1, N_ACCOUNTS + 1):
        accounts.append(
            (
                i,
                "Account %04d %s" % (i, random.choice(["Labs", "Group", "Systems", "Co", "Digital"])),
                random.choice(SEGMENTS),
                random.choice(REGIONS),
                iso(start + timedelta(days=random.randint(0, 700))),
            )
        )
    c.executemany("INSERT INTO accounts VALUES (?,?,?,?,?)", accounts)

    subs = []
    for i in range(1, N_SUBSCRIPTIONS + 1):
        r = random.random()
        state = "active" if r < 0.70 else ("trial" if r < 0.90 else "churned")
        cycle = "monthly" if random.random() < 0.70 else "annual"
        base = {"starter": 49.0, "team": 199.0, "business": 599.0, "enterprise": 2400.0}[
            random.choice(PLANS)
        ]
        # NOTE: for annual cycles this column holds the ANNUAL price. Legacy naming.
        price = base * 12 if cycle == "annual" else base
        began = start + timedelta(days=random.randint(0, 850))
        subs.append(
            (
                i,
                random.randint(1, N_ACCOUNTS),
                random.choice(PLANS),
                state,
                cycle,
                round(price, 2),
                iso(began),
                iso(began + timedelta(days=random.randint(30, 400))) if state == "churned" else None,
            )
        )
    c.executemany("INSERT INTO subscriptions VALUES (?,?,?,?,?,?,?,?)", subs)

    invoices = []
    for i in range(1, N_INVOICES + 1):
        sub = subs[random.randrange(len(subs))]
        issued = start + timedelta(days=random.randint(0, 900))
        invoices.append(
            (
                i,
                sub[0],
                iso(issued),
                round(sub[5] * random.uniform(0.9, 1.1), 2),
                1 if random.random() < 0.85 else 0,
                "USD",
            )
        )
    c.executemany("INSERT INTO invoices VALUES (?,?,?,?,?,?)", invoices)

    con.commit()
    for t in ("accounts", "subscriptions", "invoices"):
        print("%-14s %5d rows" % (t, c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]))
    con.close()
    print("wrote", DB)


if __name__ == "__main__":
    main()
