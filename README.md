# Tokenomics for Agents

**An agent that queries raw data pays O(rows) per question, forever. One that
reads a compiled wiki pays O(concepts) — and that number stays flat as the
database grows.**

This is a small, runnable demonstration of that difference. It compiles a
SQLite database and a messy analyst-notes file into a knowledge bundle **once**,
then answers questions from the bundle instead of the data. The bundle is plain
markdown with YAML frontmatter, conformant to
[Open Knowledge Format v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
— no database, no index, no tooling required to read it.

Measured on 8,100 rows of SaaS subscription data:

| | Tokens per question |
|---|---|
| Compiled wiki context | **1,901** |
| Dumping the raw rows | **112,547** |
| | **59x cheaper** |

At 10x the data the gap is 592x, and the raw dump stops fitting in a 1M-token
context window entirely at ~72,000 rows. The wiki column never moves.

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

Uses Gemini 3.5 Flash. `.env` is gitignored. The key is read from `GEMINI_API_KEY` —
an already-exported env var wins over the file, so CI needs no `.env` at all.

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

Generated pages look authoritative. A page is a flat markdown file with no
signal distinguishing "a human verified this" from "a model asserted it at
3am." A wrong page misleads every agent that reads it afterward, silently, and
it will be cited as a source — which is worse than a wrong row, because a wrong
row is one fact and a wrong page is a policy.

Mitigation: gate wiki writes behind pull requests so a human reviews the diff,
and put `verified: false` in the frontmatter of every machine-generated page
until someone checks it. Consumers can then weight or refuse unverified pages
instead of trusting everything in the bundle equally.
