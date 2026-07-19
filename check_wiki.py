"""Verify the compiled wiki/ is a correct OKF bundle — not just that it exists.

Run from okf-demo/:  python3 check_wiki.py
Exit 0 = every check passed.
"""

import os
import re
import sqlite3
import sys

WIKI = "wiki"
DB = "rawdata/saas.db"
LINK = re.compile(r"\]\((/[^)]+\.md)\)")
FENCE = re.compile(r"```sql\n(.*?)```", re.S)

fails = []


def check(ok, label, detail=""):
    print("  %s %s%s" % ("PASS" if ok else "FAIL", label, "" if ok else "  <- " + detail))
    if not ok:
        fails.append(label)


pages = sorted(
    os.path.join(r, f)
    for r, _, fs in os.walk(WIKI)
    for f in fs
    if f.endswith(".md")
)

print("\n1. Frontmatter (OKF requires a non-empty `type` on every concept doc)")
for p in pages:
    text = open(p).read()
    if os.path.basename(p) == "log.md":
        continue  # reserved: no frontmatter, checked separately
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    ty = re.search(r"^type: *(\S.*)$", m.group(1), re.M) if m else None
    check(bool(ty), p, "missing/empty type")

print("\n2. Reserved files")
idx = open(os.path.join(WIKI, "index.md")).read()
log = open(os.path.join(WIKI, "log.md")).read()
check('okf_version: "0.1"' in idx, "index.md declares okf_version")
check(bool(re.search(r"^## \d{4}-\d{2}-\d{2}$", log, re.M)), "log.md has a ## YYYY-MM-DD heading")
check("**Initialization**:" in log, "log.md uses the Initialization/Creation convention")
reserved = [os.path.basename(p) for p in pages if os.path.basename(p) in ("index.md", "log.md")]
check(sorted(reserved) == ["index.md", "log.md"], "only index.md and log.md are reserved names", str(reserved))

print("\n3. Cross-links resolve (the knowledge graph)")
targets = set()
for p in pages:
    for link in LINK.findall(open(p).read()):
        targets.add(link)
        check(os.path.exists(WIKI + link), "%s -> %s" % (p, link), "broken link")
check("FK to [" in open(os.path.join(WIKI, "tables/subscriptions.md")).read(),
      "FK links present (PRAGMA foreign_key_list survived the compile)")

print("\n4. No orphan pages (every page reachable from index.md)")
entries = re.findall(r"^\* \[.+?\]\((.+?)\) - ", idx, re.M)
reachable = {"/" + e for e in entries} | targets
for p in pages:
    rel = "/" + os.path.relpath(p, WIKI)
    if os.path.basename(p) in ("index.md", "log.md"):
        continue
    check(rel in reachable, "reachable: " + rel, "orphan — no inbound link")

print("\n5. Synthesized warnings survived into the metric page")
mrr = open(os.path.join(WIKI, "metrics/mrr.md")).read()
churn = open(os.path.join(WIKI, "metrics/account_churn.md")).read()
check("Exclude trials" in mrr, "mrr.md carries the trials warning")
check("Divide annual by 12" in mrr, "mrr.md carries the annual-by-12 warning")
check("2025-03-01" in mrr, "mrr.md carries the paid-flag date caveat")
check("no 'paused' state" in churn.lower() or "paused" in churn, "churn page carries the 'paused' warning")
check("/references/analyst_notes.md" in mrr, "mrr.md cites its source (provenance chain)")

print("\n6. The wiki's SQL is actually TRUE against the database")
con = sqlite3.connect(DB)
for page in ("metrics/mrr.md", "metrics/account_churn.md"):
    for i, sql in enumerate(FENCE.findall(open(os.path.join(WIKI, page)).read())):
        try:
            rows = con.execute(sql).fetchall()
            check(bool(rows), "%s snippet %d runs and returns rows" % (page, i), "no rows")
        except Exception as e:
            check(False, "%s snippet %d runs" % (page, i), str(e))

# The load-bearing claim: naive SUM overstates MRR. If it doesn't, the warning is fiction.
naive = con.execute("SELECT SUM(monthly_usd) FROM subscriptions").fetchone()[0]
correct = con.execute(
    "SELECT SUM(CASE billing_cycle WHEN 'annual' THEN monthly_usd/12.0 ELSE monthly_usd END)"
    " FROM subscriptions WHERE state='active'"
).fetchone()[0]
check(naive > correct * 2, "naive SUM really does overstate MRR",
      "naive=%.0f correct=%.0f" % (naive, correct))
print("     naive SUM = $%.0f  vs  correct MRR = $%.0f" % (naive, correct))

states = {r[0] for r in con.execute("SELECT DISTINCT state FROM subscriptions")}
check(states == {"active", "trial", "churned"}, "state really is a closed set of 3",
      str(states))
con.close()

print("\n%s  (%d checks failed)" % ("ALL CHECKS PASSED" if not fails else "FAILURES", len(fails)))
sys.exit(1 if fails else 0)
