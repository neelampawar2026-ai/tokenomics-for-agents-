"""THE CONSUMER. Answers a question by reading wiki/, never rawdata/.

    python3 ask.py "how do I calculate MRR?"

Four steps, printed as they happen, so the terminal narrates the pattern.
"""

import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WIKI = os.path.join(HERE, "wiki")
DB = os.path.join(HERE, "rawdata", "saas.db")
NOTES = os.path.join(HERE, "rawdata", "analyst_notes.txt")

INDEX_ENTRY = re.compile(r"^\* \[(.+?)\]\((.+?)\) - (.*)$", re.M)
LINK = re.compile(r"\]\((/[^)]+\.md)\)")
STOP = {"how", "do", "i", "the", "a", "an", "is", "this", "what", "for", "to", "of", "and", "in"}


def tokens(text):
    # Crude on purpose: ~4 chars per token is close enough for a comparison.
    return len(text) // 4


def read(relpath):
    with open(os.path.join(WIKI, relpath.lstrip("/"))) as f:
        return f.read()


def score(question, text):
    """Keyword overlap. In a real agent, the LLM itself reads the index and
    chooses which links to follow — this stands in for that."""
    q = {w for w in re.findall(r"[a-z_]+", question.lower()) if w not in STOP}
    t = set(re.findall(r"[a-z_]+", text.lower()))
    return len(q & t)


def naive_dump():
    """The alternative: every row of every table, plus the notes. Real walk,
    real number — nothing here is estimated."""
    parts = []
    con = sqlite3.connect(DB)
    for (t,) in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall():
        cur = con.execute("SELECT * FROM %s" % t)
        cols = [d[0] for d in cur.description]
        parts.append("TABLE %s (%s)" % (t, ", ".join(cols)))
        parts.extend(" | ".join(str(v) for v in row) for row in cur)
    con.close()
    with open(NOTES) as f:
        parts.append(f.read())
    return "\n".join(parts)


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else "how do I calculate MRR?"
    print("Question: %s\n" % question)

    # 1 --------------------------------------------------------------------
    index = read("index.md")
    print("[1] Read wiki/index.md only  (%d tokens)" % tokens(index))

    # 2 --------------------------------------------------------------------
    entries = INDEX_ENTRY.findall(index)
    ranked = sorted(entries, key=lambda e: score(question, e[0] + " " + e[2]), reverse=True)
    picked = [e[1] for e in ranked[:2]]
    print("[2] Picked %d concepts by keyword overlap: %s" % (len(picked), ", ".join(picked)))

    # 3 --------------------------------------------------------------------
    opened, context = [], []
    queue = list(picked)
    for path in queue:
        norm = path.lstrip("/")
        if norm in opened:
            continue
        opened.append(norm)
        text = read(norm)
        context.append(text)
        if len(opened) <= len(picked):  # one hop only
            queue.extend(LINK.findall(text))
    print("[3] Followed cross-links one hop. Opened:")
    for p in opened:
        print("      wiki/" + p)

    # 4 --------------------------------------------------------------------
    assembled = "\n\n".join(context)
    wiki_tokens = tokens(assembled)
    dump_tokens = tokens(naive_dump())
    print("\n[4] Token comparison")
    print("      wiki context : %8d tokens (%d pages)" % (wiki_tokens, len(opened)))
    print("      raw dump     : %8d tokens (every row of every table + notes)" % dump_tokens)
    print("      ratio        : %8.1fx cheaper" % (dump_tokens / max(wiki_tokens, 1)))
    print("\n    The wiki stays this size as the DB grows — it scales with CONCEPTS,")
    print("    not with data volume.")
    print("    And the raw dump, at %.0fx the cost, still would not contain the" % (dump_tokens / max(wiki_tokens, 1)))
    print("    warnings below as explicit statements — they were synthesized at")
    print("    compile time, not retrieved.\n")

    print("--- assembled context (first ~900 chars) " + "-" * 29)
    print(assembled[:900])
    print("-" * 70)


if __name__ == "__main__":
    main()
