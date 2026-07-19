# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Tokenomics for Agents** — a runnable demo of the *wiki memory* pattern.
Published at https://github.com/neelampawar2026-ai/tokenomics-for-agents- and
written to back a blog post, so the repo is an exhibit as much as a codebase.

The thesis, and the sentence every change should stay true to: an agent
querying raw data pays O(rows) per question forever; an agent reading a
compiled wiki pays O(concepts), and that number stays flat as the data grows.
Compile a SQLite DB plus a messy notes file into an
[Open Knowledge Format v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
bundle once, then answer from the bundle. Domain is SaaS subscription analytics
(accounts / subscriptions / invoices, with MRR and account churn as metrics).

The demo's credibility rests on being small enough to read in one sitting.
Five short scripts, each readable top-to-bottom. Resist adding CLI frameworks,
classes, config files, or logging setup.

`wiki/` is deliberately committed to git (unusual for a build artifact) so the
compiled pages render on GitHub — a visitor arriving from the post should see
the artifact without cloning or running anything. `rawdata/saas.db` stays
ignored; it is binary and regenerable.

## Commands

All commands run from `okf-demo/`.

```bash
python3 seed.py                            # build rawdata/saas.db (8,100 rows)
python3 generate_wiki.py                   # compile wiki/ (stages, then swaps)
python3 ask.py "how do I calculate MRR?"   # query the bundle

python3 check_wiki.py                      # THE TEST — 34 checks, exit 0 = sound
python3 compare_tokens.py                  # the token-scaling numbers for demos

rm -rf wiki rawdata/saas.db                # full clean rebuild starts here
```

`check_wiki.py` is the closest thing to a test suite; there is no pytest, no
linter. It needs `wiki/` and `rawdata/saas.db` to exist, so run `seed.py` and
`generate_wiki.py` first. There are no individual tests to run — it is one file
that either passes fully or names what broke.

Optional LLM path (see Known gaps before trusting it):

```bash
pip install -U google-genai                # only dep in the whole repo
cp .env.example .env                       # then add a real GEMINI_API_KEY
python3 generate_wiki.py --llm             # gemini-3.5-flash writes table pages
```

## Architecture

Four layers. The boundaries are the whole point — a change that blurs them
breaks the demo's argument even if the code still runs.

- **Raw sources** (`rawdata/`) — `saas.db` and `analyst_notes.txt`. Immutable.
  `generate_wiki.py` reads them; nothing else should. `ask.py` and
  `compare_tokens.py` touch the DB only to build the naive dump they exist to
  argue against.
- **The compiler** (`generate_wiki.py`) — runs once. Two passes: a
  *structural* pass (`PRAGMA table_info` / `PRAGMA foreign_key_list`, fully
  deterministic) and a *semantic* pass (natural language).
- **The artifact** (`wiki/`) — generated. Never hand-edit it; edit the compiler
  and re-run. Plain markdown + YAML frontmatter, no tooling required to read.
- **Consumers** (`ask.py`, `check_wiki.py`, humans, any LLM) — read `index.md`
  first, then only the pages they need.

Pages are written to `wiki.partial/` and swapped into `wiki/` only after every
page compiles. A failed run (bad key, missing dep) must leave the previous
bundle intact — the artifact is the durable thing the demo is about, so the
compiler must not delete it before it knows it can rebuild it.

### Load-bearing constraints

Each exists because violating it silently breaks a claim the demo makes. They
are not style preferences.

- **The default path is Python 3 stdlib only.** The thesis is that plain files
  need no tooling, so the demo itself must need none. `google-genai` is imported
  *inside* `describe_llm()` and `--llm` defaults off, which is what keeps this
  true. Never hoist that import to module scope.
- **`REFERENCES` in the DDL.** No declared FKs → `PRAGMA foreign_key_list`
  returns nothing → no `FK to [...]` cross-links → the knowledge-graph layer
  vanishes with no error.
- **Seed volume (600 / 3,500 / 4,000 rows).** A toy DB makes the raw dump
  *smaller* than the wiki and the demo argues against itself. If the ratio drops
  below 20x, add rows — never shrink the wiki.
- **The `index.md` bullet format** — `* [Title](path.md) - description` — is
  parsed by regex in both `ask.py` and `check_wiki.py`. Changing it in the
  compiler breaks both consumers.
- **All natural-language generation lives in `describe()` / `describe_llm()`**,
  plus the two hand-written metric pages in `compile_metrics()`. `describe()`'s
  docstring promises an LLM can replace its body with nothing else changing —
  `describe_llm()` is that promise kept. Scattering prose generation elsewhere
  destroys the producer/consumer independence the demo exists to show.
- **Cross-links are bundle-relative** (`/tables/x.md`, leading slash). OKF
  tolerates broken links; this demo should have none.
- **Escape `|` in table-cell text.** Descriptions land in markdown tables; a
  bare pipe splits the cell and the page renders as garbage while still passing
  every text-level check. The writer escapes it — keep that when editing.

### The synthesis punchline

The four facts in `analyst_notes.txt` (exclude trials from MRR; divide annual
by 12; `invoices.paid` unreliable before 2025-03-01; `state` is a closed set
with no `paused`) are deliberately *not* derivable from the schema or the rows.
They are the payload the compile step lifts into `metrics/*.md` as explicit,
citable statements.

`ask.py` must keep printing enough assembled context that the reader *sees*
those warning sentences on screen. If they only exist inside wiki files and
never reach the terminal, the demo's strongest point is invisible.

## Verification

`python3 check_wiki.py` covers six groups: frontmatter `type` on every concept
doc; reserved-file structure (`index.md` / `log.md`); all cross-links resolve;
no orphan pages; the synthesized warnings survived into `metrics/mrr.md`; and —
the one worth preserving — the SQL in the wiki's fenced blocks **executes
against the DB and its claims are true** (naive `SUM` really does overstate MRR
~6x; `state` really has exactly three values).

That last group is the regression test for any future LLM-generated metric
pages. It is what catches a page that is well-formed but wrong.

Not covered by the checker, so check by hand after touching the compiler:

- `ask.py` exits 0 for both `"how do I calculate MRR?"` and
  `"is this account churned?"`.
- The MRR question opens `metrics/mrr.md` and, via one hop, the `subscriptions`
  and `invoices` table pages.
- Table pages **render** correctly, not just parse — the pipe bug above passed
  all 34 checks while producing visibly broken tables.

Two ratio numbers appear in the repo and both are correct: `ask.py` reports
~67x (pages opened only), `compare_tokens.py` reports ~59x (also counts the
`index.md` you must read to choose them). Prefer 59x when quoting — it is the
conservative one.

**`README.md` hardcodes token counts** (1,901 / 112,547 / 59x) in its header
table and again in the punchlines section. Any change to seed volume, page
content, or the token estimator invalidates them. Re-run `compare_tokens.py`
and update both places — they have drifted apart once already. The pasted
`ask.py` sample output further down the README is real terminal output and
legitimately shows 67x; leave it alone rather than editing it to match.

## Known gaps

- **The `--llm` path has never run end to end.** No `google-genai` and no API
  key were available when it was written; only syntax and flag routing are
  verified. The `client.interactions.create` call shape came from the Gemini
  docs. If it fails, the likeliest culprit is `system_instruction`, which the
  docs list as valid but never demonstrate alongside `response_format`.
- **`--llm` only rewrites table pages.** `compile_metrics()` still emits the two
  hand-authored metric pages, so the warnings — the demo's punchline — are
  template text, not model output. Moving them to the model is the more
  interesting demo but makes `check_wiki.py` group 6 essential rather than
  decorative.
- **`verified: false` is documented but not implemented.** `README.md` presents
  it as the mitigation for machine-generated pages being trusted before review.
  Nothing emits the flag and there is no `verify.py`. Implement both or neither
  — the flag is meaningless without something that flips it.
