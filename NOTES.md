# Notes

Working notes: what broke, what was tried, why one option over another.

---

## Session 2 — the oracle and the corpus

Zero LLM calls this session, on purpose. If the ground truth is wrong, every
number in the README is wrong and no model comparison would reveal it.

### The planned reference-table count (163) was itself a parser bug

The design note said the configuration reference page held 163 rows. The strict
parser finds **169**. The gap is not a change upstream — it is that 163 came from
a lenient regex.

Reproduced it directly. A four-group row pattern over the real page finds 159 of
169 and drops these ten with no error:

```
allowed_configs  allowed_directories  allowed_paths  checkpoint_threshold
default_null_order  extension_directories  max_memory  profile_output
threads  user
```

Six of the ten are rows whose Name cell lists an alias (`max_memory, memory_limit`),
so the comma breaks the pattern. That is exactly the failure the design note
recorded during session 1 — it noticed `threads` and `memory_limit` going missing
and correctly diagnosed the mechanism, but the row count it carried forward was
still the buggy one.

So `docs_table.py` asserts rather than matches: heading present, header labels as
expected, every row splits into exactly four cells, and the record count equals
the table's data-line count. A `TableParseError` is a build failure, never a
shorter file. The lenient version survives as the `B0` baseline arm, because
"do you even need an LLM for this?" is a fair question and hiding B0's bug would
have made the answer a lie.

### `value` is not in the oracle

`duckdb_settings()` returns a `value` column, and it is tempting to treat it as
the default. It is not. On this machine:

| setting | `value` here | documented default |
|---|---|---|
| `threads` | `12` | `# CPU cores` |
| `max_memory` | `50.0 GiB` | `80% of RAM` |
| `Calendar` | `gregorian` | System (locale) calendar |
| `TimeZone` | `Asia/Calcutta` | System (locale) timezone |

Committing `value` would have done two bad things: made `settings.jsonl`
non-reproducible on any other machine (CI would fail on core count alone), and
scored extraction models against one laptop's RAM. It goes to
`observed_values.jsonl`, stamped with `host_platform`, and the docs reference
table is the ground truth for defaults.

Two oracles, and where they disagree that is a finding rather than a bug.

### 280 rows are 274 settings

`duckdb_settings()` emits **both** spellings of an alias pair as full rows: one
carries the `aliases` list, the twin is bare. Discovered by asserting that every
alias also resolves as a name and getting 280 rather than 286.

One directional disagreement fell out of it: the docs table lists
`user, username` (primary first), while the binary makes `username` canonical
with `user` as its alias. Every other pair agrees. Too small to be worth a
section in the README, recorded here so it is not rediscovered.

### The corpus does not contain the benchmark that was planned

The design note specified 120 documents as 55 narrative / 35 extension /
30 reference. Building it and then *measuring* it found two problems.

**1. The extension stratum does not have 35 documents in it.** Across all 58
extension pages there are 31 sections that name a setting other than a
distractor word, and they live on **19 pages**. The sampler takes at most one
section per page so a long page cannot dominate a bucket, which caps the honest
extension sample at 19. Taking 35 would have meant sampling the same pages three
and four times over and calling it a stratum.

So `extension-signal` takes all 19 and `corpus build` prints
`<- census: every eligible page is taken`. It is a census of that part of the
documentation, not a sample, and it should be described that way — the sampling
band does not apply to it.

**2. Distractors were about to eat the benchmark.** `schema`, `user`,
`username`, `password`, `threads` and `secret` are real DuckDB setting names and
also ordinary English words and Postgres/MySQL connection parameters. The design
note flagged them as a deliberate distractor set. What it did not know is the
density: **60% of prose sections that mention any known setting mention only
these.** The first build came out at 54 of 90 prose documents distractor-only —
a corpus where most of the work is "correctly extract nothing from a page about
`CREATE SCHEMA`".

That is a real and worth-measuring failure mode, but not at 60%. Buckets now
split on `has_signal` and distractor-only documents are sampled at a fixed
**16 of 120**. Distinct settings appearing anywhere in the corpus went
**75 → 111**.

Both changes are one command to revert (`corpus build` with different quotas) and
the quota block carries the measurements that motivated it.

### `has_signal` is a sampling flag, not a label

`reference-0010` documents the real `password` setting and scores
`has_signal: false`, because `password` is in the distractor list. That is
correct behaviour for a *sampling balance* heuristic and would be wrong as a
truth label. There is a test pinning that exact row so nobody later reads the
flag as "this document documents a setting".

Only the hand-labelled recall set can answer that question. `extension-0001`
makes the same point from the other side: it says "will count towards the memory
limit" in passing, which no oracle can distinguish from a page that actually
specifies `max_memory`.

### Corpus fetch is pinned, and the pin is checked

`scripts/fetch_source_docs.py` clones `duckdb-web` at `6f6cd16` and refuses to
continue unless the checkout's `_config.yml` still says
`current_duckdb_version: "1.5.5"` — exactly the `duckdb` pinned in
`pyproject.toml`. Docs and oracle have to describe the same release; a later
commit would silently reintroduce the confound the pin exists to remove.

The checkout is ~2 minutes and is *not* committed (`data/source/` is ignored).
The 120 sampled documents are committed instead, so extraction and scoring run
from a clean clone with no network.

### `.gitattributes` marks `data/**` as non-text

The manifest commits a sha256 of every document. Without `-text`, a Windows
clone gets CRLF on checkout and is quietly a different benchmark from the one
the README reports.

---

## Open questions raised in session 2 (answered or carried forward in session 3)

- **Seed sensitivity is unmeasured.** The corpus is seeded at `20260919` and
  reproducible, but nothing yet says how much a different seed moves a score.
  Project 24's lesson was that the sampling band was wider than most of the gaps
  in the table; budget a re-draw before publishing arm ordering.
- **`narrative-distractor` at 10 documents** is enough to notice a
  false-positive problem, not enough to quantify one. State it as an
  observation, not a rate.

---

## Session 2 addendum — CI caught `ruff format` editing the corpus

First CI run after committing the data failed on `ruff format --check`. Not a
style nit: **ruff formats fenced code blocks inside markdown**, and it wanted to
rewrap a pandas snippet in `data/corpus/documents/narrative-0013.md`.

That document is a verbatim excerpt of a DuckDB docs page whose sha256 is
committed in the manifest. A `ruff format .` would have rewritten the corpus and
broken `corpus verify` — and it would have looked like a formatting commit.
Missed locally because I had only ever run `ruff format` on `src/ tests/ scripts/`.

`extend-exclude = ["data"]` in `pyproject.toml`. The corpus is evidence, not
source.

---

## Session 3 — verifying before spending

The rule for this session was: nothing is billed until every id, price and
capability has been checked against something authoritative. That turned out to
matter for a reason that had nothing to do with OpenRouter.

### One document was 83% of the corpus

Building the cost model was the first thing that touched the corpus in anger,
and the size distribution was absurd: 120 documents, 710,288 characters, and a
single document holding 588,774 of them.

`narrative-0036` was `clients/python/reference/index.md` — the Sphinx-generated
Python API reference. It contains **no markdown heading at all**, so
`split_sections` did the only thing it could and emitted the entire file as one
"section". It was eligible for sampling because three setting names appear
somewhere inside 589 kB of `<dl class="py class">`.

Had it gone to the grid it would have been ~147 k tokens per arm per run: past
the context window of most candidate models, and more expensive on its own than
the other 119 documents put together. Those calls would have failed as
`provider_error` and looked like model failures.

`clients/c/api.md` is the same artefact at 441 kB. It was not drawn at this
seed — but seed sensitivity is an open question and the corpus is *due* to be
resampled, so it was a landmine, not a near miss.

Two filters, chosen after measuring rather than guessing:

- **Block-HTML density > 5 tags/1000 chars excludes the page.** The two
  families do not overlap at all: the 14 generated pages score 10–24, every one
  of the 420 prose pages scores <= 1.6. Any threshold in 2..10 selects exactly
  the same pages, which is what makes this a separator rather than a tuned knob.
  `docs/current/index.md` goes too — it is a grid of `box-link` divs with no
  prose in it.
- **`MAX_SECTION_CHARS = 8000`.** Sections are median 255 chars, p95 1.5 kB,
  p99 3.8 kB, and then a tail of generated list dumps: the time-zone reference
  list at 46 kB, the encodings table at 26 kB, the spatial function index at
  17 kB. None of those is prose a reader consumes. The `reference` stratum is
  exempt — its documents are single table rows by construction.

Resampled at the same seed, same quotas. The composition held exactly
(50/10/19/6/35), max document is now 6,142 chars, and the corpus went from
710,288 to 114,783 characters — **6.2x cheaper per arm**.

**The cost:** distinct settings mentioned anywhere fell from 111 to 103. Eight
settings only ever appeared inside the dumps. That is a real reduction in
coverage and it is recorded rather than absorbed.

One test broke, and it was the right kind of break:
`test_has_signal_is_a_sampling_heuristic_not_a_truth_label` asserted the exact
seeded draw, `[["password"]]`. Resampling drew the `threads` reference row too.
The test's *claim* was still true; it had just been written against the sample
instead of the invariant. It now asserts that an unsignalled reference row
exists and names only distractors, which a re-seed cannot break spuriously.

### The arms

`GET /api/v1/models` is public — no key, no spend — so the whole of steps 2–4
happened for free. 447 models in the catalogue, 362 advertising
`structured_outputs`.

Pinned H1 `anthropic/claude-sonnet-5`, H2 `google/gemini-2.5-flash`,
H3 `openai/gpt-4.1-nano`, H4 `openai/gpt-oss-120b`. Roughly an order of
magnitude in price between each step, all four with native structured outputs
so the *mechanism* is held constant and only capability varies. No `:free` ids
(that is the 50/day account-wide cap that killed 24's hosted comparison) and no
`:batch` ids (cheaper, but asynchronous, so they cannot measure latency).

`arms verify` refuses to pass if an id stops resolving, if structured-output
support disappears, if a determinism knob appears or vanishes, or if the price
drifts more than 0.1% from the pin. Project 24 shipped a table with an arm that
had never executed once, because a wrong model id just 404s quietly.

**`temperature=0` is not available across the frontier any more.** Sonnet 5
advertises neither `temperature` nor `seed`; the GPT-5 reasoning family takes
`seed` but not `temperature`. Three options: drop the frontier from the
comparison, pretend the knob was set, or record per arm what the provider
actually accepts and send only those. Took the third. Reproducibility comes
from the committed response cache, not from the sampler.

### The schema, and the two holes left in it on purpose

`name` is **not** an enum of the 274 known settings. It is one line of code to
paste the oracle in, and it would make a hallucinated name impossible to emit —
along with the benchmark's primary measurement. There is a test asserting the
schema happily accepts `frobnicate_cache`.

Grounding is not in the JSON Schema either, because no JSON Schema can say "this
string must be a substring of that document". A Pydantic validator reads the
document from the validation context and enforces it. So the decoder enforces
shape and the validator enforces grounding, and an arm can be perfectly
schema-valid and still fail for quoting something the document does not say.
Two separate columns, because they are two separate failures.

Whitespace runs are normalised on both sides before comparing — markdown
hard-wraps mid-sentence and a model that joins two lines with a space has quoted
the same text. Nothing else is normalised.

`name` is pattern-constrained to a bare SQL identifier, so a name arriving with
its markdown backticks still attached **fails**. Stripping them silently would
have inflated `valid_first_pass` for every arm.

The wire schema inlines every `$ref` and drops `$defs`. Pydantic factors enums
out and refers to them with a `$ref` sitting next to a sibling `description`;
providers disagree about that — some merge, some ignore, some reject the
request. A rejected request is an arm that quietly produces no data, which is
the failure `arms verify` exists to prevent, so it is not worth risking.

### The oracle-leak test caught me writing the leak

`test_the_repair_prompt_never_contains_the_oracle` walks all 274 oracle names
against the outgoing prompt. It failed on its first run, on the system prompt I
had just written:

> Words like schema, user, password and threads appear constantly in ordinary
> prose and in connection strings for other databases

That is *verbatim* `corpus.DISTRACTOR_NAMES`. It would have handed every arm the
list of planted traps, and the 16 distractor documents exist precisely to
measure that false-positive case. Rewritten to describe the phenomenon without
naming any of them.

Two names cannot be kept out: `schema` (any English instruction mentioning a
JSON schema) and `user` (the request envelope's role). Both are real settings
and both are already `DISTRACTOR_NAMES`. The test allows exactly those two,
asserts the allow-list is a subset of `DISTRACTOR_NAMES` so it cannot quietly
grow, and additionally asserts neither is ever followed by a comma — so they can
be used as prose but never enumerated as a list of candidate names.

### Repair is not retry

A `ValidationError` consumes the one bounded repair. A 429 or 502 does not,
because there was no answer to repair — it is retried with backoff instead.
Merging the two counters would let a flaky provider look like a model that
needed fewer repairs.

`length_truncated` outranks `unparseable` in the outcome ladder: truncated JSON
does not parse, but the cause is the token budget, not the model's formatting.
402/403/404 become `provider_unavailable` and are neither retried nor repaired —
retrying "no credit" is just a slower way to fail.

### Nothing has been spent

Total OpenRouter charges after three sessions: **$0.00**. The estimate for the
full 120 x 4 grid is **$1.06**, and the 8-document pilot is about **$0.07**.
Before the corpus fix the same grid would have cost roughly six times that, for
a benchmark that would have been 83% one HTML dump.

## Open questions for session 4

- **The pilot has not been run.** Everything up to it is built and tested
  offline; the pilot is the first billed call and it needs a key.
- **Seed sensitivity is still unmeasured**, and the corpus has now been
  resampled once, which makes the re-draw more interesting rather than less.
- **The 40-section hand-label recall set is not started.**
- **The repair rate is a guess.** `arms cost` assumes 20%. The pilot's job is to
  replace that with a measurement before the full grid is authorised.
- **L1 (local Ollama), B0 (table parser) and B1 (null) are not built.** B0 is
  the `docs_table` parser already in the repo and should be cheap.
