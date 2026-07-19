# Tokenomics for Agents

**Stop feeding your database to the model. Feed it a compiled wiki instead.**

Most agents answer a question by pulling rows out of a database and stuffing
them into the prompt. That works until it doesn't: every question costs more as
your data grows, and the model still has to guess at the things your data
doesn't say out loud.

This demo does it the other way. It reads a SQLite database and a messy
analyst-notes file **once**, and compiles them into a small set of plain
markdown pages. Every question after that is answered from those pages.

## What you get

**1. Questions get ~60x cheaper.** Measured on 8,100 rows of SaaS subscription
data:

| | Tokens to answer one question |
|---|---|
| Compiled wiki | **1,901** |
| Dumping the raw rows | **112,547** |
| | **59x less** |

**2. That cost stops growing with your data.** The raw-dump approach gets more
expensive every time someone signs up. The wiki doesn't — it describes *the
concepts*, and you don't add a new concept every time you add a row.

| Rows in the database | Raw dump | Compiled wiki |
|---|---|---|
| 8,100 (today) | 112,547 tokens | 1,901 tokens |
| 81,000 | 1,125,470 | 1,901 |
| 810,000 | 11,254,700 | 1,901 |

Past roughly 72,000 rows the raw dump no longer fits in a 1M-token context
window at all. The wiki still fits at any size.

**3. The agent stops getting the answer wrong.** This is the part that isn't
about money. In this dataset, a column named `monthly_usd` holds the *annual*
price for annual plans, and trial subscriptions carry a price they never pay.
An agent reading the raw rows has no way to know either — so it sums the column
and reports revenue that is **6x too high**. The wiki says so in plain language,
on the page about revenue, because a human wrote it down in a notes file and the
compile step lifted it out.

**4. No infrastructure.** The output is markdown files in a folder. No vector
database, no embeddings, no index to keep in sync, no server. You can read it,
`grep` it, diff it in a pull request, or hand it to any model. It conforms to
[Open Knowledge Format v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md),
and the whole demo runs on the Python standard library.

The trade: you pay the compile cost once, up front, and you have to re-run it
when the schema or the domain knowledge changes.

Domain: SaaS subscription analytics — accounts, subscriptions, invoices, with
MRR and account churn as the metrics.

## Run it

```bash
python3 seed.py            # build rawdata/saas.db  (8,100 rows)
python3 generate_wiki.py   # compile wiki/          (runs once)
python3 ask.py "how do I calculate MRR?"
```

Python 3 stdlib only. No pip installs, no API keys, no config.

### Optional: compile with a real LLM

The semantic pass is templated by default so the demo needs no key. To run it
against a real model instead:

```bash
pip install -U google-genai
cp .env.example .env        # then put your key in it
python3 generate_wiki.py --llm
```

Uses Gemini 3.5 Flash, reading `GEMINI_API_KEY`. `.env` is gitignored.

This changes **one function** (`describe_llm()`); the OKF output is the same
shape either way. The flag defaults to off and the `google-genai` import lives
inside that function, so the zero-dependency property above still holds for
everything else.

## Sample output

```
Question: how do I calculate MRR?

[1] Read wiki/index.md only  (230 tokens)
[2] Picked 2 concepts by keyword overlap: metrics/mrr.md, tables/accounts.md
[3] Followed cross-links one hop. Opened:
      wiki/metrics/mrr.md
      wiki/tables/accounts.md
      wiki/tables/subscriptions.md
      wiki/tables/invoices.md
      wiki/references/analyst_notes.md

[4] Token comparison
      wiki context :     1679 tokens (5 pages)
      raw dump     :   112547 tokens (every row of every table + notes)
      ratio        :       67.0x cheaper

    The wiki stays this size as the DB grows — it scales with CONCEPTS,
    not with data volume.
    And the raw dump, at 67x the cost, still would not contain the
    warnings below as explicit statements — they were synthesized at
    compile time, not retrieved.

--- assembled context (first ~900 chars) -----------------------------
...
# Warnings

- **Exclude trials.** `state = 'trial'` rows carry a real price but the
  customer pays nothing. Including them inflates MRR. [1]
- **Divide annual by 12.** For `billing_cycle = 'annual'`, `monthly_usd` is the
  annual amount. Summing the column straight is what made the March board deck
  overstate MRR by 14%.
```

## The three layers

| File | Layer | Property |
| --- | --- | --- |
| `rawdata/saas.db` | Raw source | Immutable. Read at compile time, never after. |
| `rawdata/analyst_notes.txt` | Raw source | Tribal knowledge. Hand-written, messy, not in any schema. |
| `generate_wiki.py` | **The compiler** | Expensive, runs once. Extracts structure deterministically; synthesizes meaning. |
| `wiki/` | The compiled artifact | Cheap to read, forever. Plain markdown + YAML. |
| `ask.py` | Consumer | Reads `index.md` first, then only the pages it needs. So does a human. So does any LLM. |

## The four OKF ideas, made visible

1. **One required field.** Every concept page's frontmatter has `type:` — and
   that is the only field OKF requires. `SQLite Table`, `Metric`, `Reference`
   here; types are descriptive strings, registered nowhere.
2. **File path = concept identity.** `/metrics/mrr.md` *is* the identifier for
   MRR. No database of IDs, no registry to keep in sync.
3. **Markdown links = the knowledge graph.** `[subscriptions](/tables/subscriptions.md)`
   is an edge. `generate_wiki.py` builds them from `PRAGMA foreign_key_list`;
   `ask.py` traverses them with one regex. That's the whole graph layer.
4. **`index.md` = progressive disclosure.** A consumer reads ~230 tokens of
   index, decides what's relevant, and opens only that. It never loads the
   bundle whole.


## Where the LLM plugs in

Two functions, both marked in the source:

- `describe()` in `generate_wiki.py` — the entire semantic pass. Its docstring
  reads: *"In production, replace this body with a single LLM call. Nothing
  else in the pipeline changes."* It takes a table and its columns, returns
  descriptions. That swap is already written: `describe_llm()` sits directly
  above it and runs behind `--llm` (see above). Both satisfy the same
  `(description, {column: description})` contract, and the OKF output is the
  same shape either way — which is the producer/consumer independence the
  format buys you.
- `score()` in `ask.py` — keyword overlap standing in for an LLM reading
  `index.md` and choosing which links to follow. Replace it with a model call
  and the traversal is unchanged.

Producer and consumer never negotiate. That independence is the point of having
a format at all.

## One honest warning

Everything above argues that agents should trust the compiled wiki over the raw
data. That only holds if the wiki is right — and a generated page gives you no
way to tell.

A page is a flat markdown file. Nothing in it distinguishes "a human verified
this" from "a model asserted it at 3am." A wrong page is worse than a wrong
row, because a wrong row is one bad fact while a wrong page becomes a cited
source for every agent that reads it afterward. The failure is silent and it
compounds.

Two mitigations, neither exotic:

- **Gate wiki writes behind pull requests**, so a human reviews the diff before
  the bundle changes. Plain markdown makes this work — you can actually read a
  wiki diff, which is not true of an embedding index.
- **Put `verified: false` in the frontmatter of every machine-generated page**
  until a human checks it. Consumers can then weight or refuse unverified pages
  instead of trusting the whole bundle equally.

(The second is described here but not yet implemented in this demo — the
compiler does not emit the flag and there is no `verify.py`.)

