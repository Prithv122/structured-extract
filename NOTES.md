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

### Session 3 addendum — Sonnet dropped, grid went to five arms

Prithvi pushed back on H1: Claude Sonnet 5 at $2.00/$10.00 was **76% of the grid's
cost**, and asked whether GLM 5.3 Flash or DeepSeek V4 Flash could take its place.

Half of that is right and the half that isn't is worth writing down. The Flash
models are not Sonnet-tier — they sit alongside `gpt-4.1-nano` and `gpt-oss-120b`
at $0.04–$0.09/M in. Swapping Sonnet for one does not buy a cheaper ceiling, it
**deletes the ceiling**, and a grid with no known-strong arm cannot separate "this
task is hard" from "these models are small". That separation is the only thing a
ceiling buys and nothing else supplies it.

But the pushback exposed a real error in my reasoning: I had treated *ceiling* and
*frontier* as the same thing. They are not, and haven't been for a while.

| model | $/M in | $/M out | grid | vs Sonnet | temp+seed |
|---|---:|---:|---:|---:|:-:|
| `anthropic/claude-sonnet-5` | 2.000 | 10.000 | $0.798 | 1× | **no** |
| `z-ai/glm-5.3` | 0.896 | 2.816 | $0.273 | 2.9× | yes |
| `deepseek/deepseek-v4-pro` | 0.4223 | 0.8446 | $0.105 | 7.6× | yes |
| `z-ai/glm-5.3-flash` | 0.090 | 0.300 | $0.028 | 28× | yes |
| `deepseek/deepseek-v4-flash` | 0.037 | 0.074 | $0.009 | 87× | yes |

DeepSeek V4 Pro is flagship-class, costs 7.6× less than Sonnet, and takes both
`temperature` and `seed` — which Sonnet does not. So the swap improved three
things at once, and the determinism one was the one I had been quietly rationalising:
the previous `arms.py` docstring presented "H1 cannot be pinned" as a *finding*
about the state of the market. It was a finding, but it was also a defect I had
chosen, and I had not said so.

**Final grid: H1 `deepseek-v4-pro`, H2 `gemini-2.5-flash`, H3 `gpt-4.1-nano`,
H4 `gpt-oss-120b`, H5 `glm-5.3-flash`.** Five vendors, all on native structured
outputs, **all five accept `temperature=0` and a seed**. Grid $1.06 → **$0.39**,
pilot $0.07 → **$0.026**. Cheaper, wider, and fully pinnable.

`test_every_arm_in_the_current_grid_can_be_pinned` now locks that property, so a
future arm swap cannot quietly reintroduce an unpinnable model.

### `:free` ids are not the same endpoint

Prithvi's first suggestion was `glm-5.2:free`, which OpenRouter does list at $0.
It fails twice:

```
z-ai/glm-5.2:free   structured_outputs=False  response_format=False  ctx=32,768
z-ai/glm-5.2        structured_outputs=True   response_format=True   ctx=1,048,576
```

The free endpoint **cannot accept `response_format` at all**, so it cannot run this
benchmark's schema — it is a reduced endpoint wearing the same model's name, not a
discount on the same thing. And `:free` still carries the 50-requests/day
account-wide cap that killed project 24's hosted comparison, against 120 calls per
arm before any repair.

Worth remembering generally: on OpenRouter, `:free` is a different product and
`supported_parameters` is the only reliable way to tell.

### Prices move faster than expected

`deepseek-v4-flash` went from $0.041 to $0.037 input in the 24 hours between
pinning the arms and revisiting them. Nothing depended on it, but it is the first
live evidence that `arms verify`'s drift check earns its place — and the reason
`deepseek-v4-pro` is pinned at 0.4223/0.8446 rather than the rounded 0.422/0.845,
which sat close enough to the 0.1% tolerance to risk a spurious failure.

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

### Pilot 3 and the retry policy that measured itself

`data/results/pilot-01-short-backoff.jsonl` is kept deliberately. It is the
complete 80-row pilot run under `BACKOFF_SECONDS = (1, 4, 10)`, and six of its
rows are `provider_error` from `HTTP 429 ... z-ai/glm-5.3-flash is temporarily
rate-limited upstream ... engine_overloaded`.

Those six are not a fact about GLM 5.3 Flash. Three retries inside five seconds
is no time for an overloaded upstream to recover, so the availability figure
they produce is a property of this harness. The backoff is now
`(5, 20, 60, 60)` with jitter -- 85 s of patience -- and only those six calls
were re-bought, because the cache is keyed by the request and nothing else had
changed.

The file stays so the two runs can be diffed: nothing about the experiment
changed between them except how long the client was willing to wait.

Pilot 3 also produced two runaway generations, and they are **different
failures that look identical in the outcome column**:

- **H1 / v1 / narrative-0001** -- 16,185 reasoning tokens across two calls, both
  hitting the 8,000 cap, $0.04515, 343 s. The model thought until the budget
  was gone. Reproduced on a fresh repair call, so it is not a stale artefact.
- **H4 / v2 / extension-0001** -- 16,000 completion tokens and only 559
  reasoning. It fell into a whitespace repetition loop and emitted newlines
  until the cap.

Neither is being "fixed". Changing H1's token cap or H4's configuration on the
evidence of one adversarial document each, before either arm's field-level
accuracy has been scored, would be tuning the experiment to its hardest case.

---

## Session 4 — the full grid, and three bugs that only exist at 1,200 rows

**1,200 calls, $2.0528, about ten hours.** 5 arms × 2 prompts × 120 documents,
every response committed. The pilot had already de-risked the API, the schema
and the repair ladder, so nothing about the *calls* went wrong. Everything that
went wrong was in the code that reads the results, and all of it surfaced after
the money was spent.

### The scorer crashed on row ~800 because a default has three states, not two

`score_default` raised `AttributeError: 'NoneType' has no attribute 'strip'` and
the entire paid grid was unscorable until it was fixed.

My first diagnosis was wrong and worth recording as wrong: I read it as an
oracle bug — a reference row that had lost its default. It is not. The oracle
encoding is deliberate and complete, and **I had assumed two states where the
docs have three**:

| documented as | `default_value` | `default_is_empty_cell` |
|---|---|---|
| a literal, e.g. `4` | `"4"` | `false` |
| an empty table cell | `None` | `true` |
| the literal word `NULL` | `None` | **`false`** |

Eight of 169 reference rows are the third case. My scorer read
"not an empty cell" as "therefore there is a literal" and called `.strip()` on
`None`. The fix is to compute the *accepted set* of `default_kind` values per
row rather than a single expected value, and to score the kind but not the
value when the documented default is `NULL` or machine-dependent.

The transferable version: when a field can mean "a value", "nothing was said"
and "explicitly nothing", one variable cannot carry it. Collapsing three states
into two is not a style question, it is the crash.

Two smaller ones, same session, same cause — code paths that only the full grid
exercised:

- **`_group_errors` crashed on dicts.** `extract run` passes `ExtractionRow`
  objects; `report` reads a results file and passes the dicts they serialise to.
  The second path had never run.
- **My own retry epilogue defeated the grouping it fed.** `[gave up after 4
  attempt(s) over 97s]` makes every 429 textually unique, so 18 identical errors
  printed as 16 separate lines. The epilogue is now stripped before grouping and
  kept in the row. A feature added in session 3 broke a feature added in session 2
  and nothing failed — it just printed worse.

All three have regression tests now. The expensive lesson is not any of the
three bugs: it is that **a crash on row 800 of 1,200 costs the whole run when
results are written at the end**. The cache saved this one — every call replayed
free — which is the only reason the fix cost minutes instead of $2.

### The cost model was wrong by 1.85×, in both directions

Two figures were recorded per call: `usage.cost` from the provider, and an
estimate from the pinned per-token price. They were expected to agree, and
keeping both was originally just belt-and-braces. It was the most useful
decision of the session.

| arm | billed | predicted | ratio |
|---|---:|---:|---:|
| H1 | $1.7545 | $0.6015 | 2.92× |
| H2 | $0.1674 | $0.1677 | 1.00× |
| H3 | $0.0378 | $0.0383 | 0.99× |
| H4 | $0.0746 | $0.2814 | 0.27× |
| H5 | $0.0186 | $0.0223 | 0.83× |

Exact for the two non-reasoning arms, and wrong in *opposite directions* for the
two reasoning arms, for two unrelated reasons:

- **Reasoning tokens are billed and are not inside `completion_tokens`.** H1 on
  `narrative-0002`: 1,430 completion, 1,475 reasoning. The second number cannot
  be a subset of the first, so any cost model summing the documented fields
  understates a reasoning arm.
- **The catalogue price is a headline, not a quote.** H4 cost 0.27× its pinned
  rate. Fallbacks are disabled, but the request still lands on *some* provider
  and that provider's rate is what appears on the bill.

`arms verify` pins prices to catch drift, and it does that correctly — the pin
matched the catalogue the whole time. The catalogue simply is not the bill. Both
numbers stay in the results, the published figure is `usage.cost`, and the
report prints the divergence per arm so it can never quietly return.

### The replay claim was false for 20 of 1,200 rows

The acceptance criterion says every published number replays from the committed
cache with an empty key. I tested it properly for the first time this session —
copied the tracked tree to a clean directory, `uv sync`, `OPENROUTER_API_KEY=`
— and it **aborted on the first call**.

The cache stores response *bodies*. A call that exhausted its retries on a 429
has no body, so 20 rows had nothing to cache, and `call()` treated a missing
entry as "you changed the experiment" and refused to run. Both of those are
correct in isolation and wrong together.

Fix: when a call gives up, record the exhausted attempt beside the responses as
`<key>.failed.json` — a deliberately different file, carrying no content, that
can never be scored as an answer. Replay finds it and reproduces the row.

The 20 rows that predate the fix were **backfilled from
`data/results/extractions.jsonl`, not captured from the wire**, because the wire
produced nothing to capture. Every backfilled record carries
`"_backfilled": true` so a reader can tell a reconstructed failure from an
observed one without taking a docstring on trust
(`scripts/backfill_exhausted_cache.py`, idempotent).

Verified afterwards: clean tree, no key, 1,200 rows replayed, and a field-by-field
diff against the committed results is **empty** — outcome, settings, cost, tokens,
error text, all identical. The two `report` outputs are byte-identical.

### Two tests broke, for two different reasons, and only one was a real defect

`test_a_broken_read_writes_nothing_to_the_cache` asserted
`list(tmp_path.rglob("*.json")) == []`. Its *claim* — a partial response must
never be replayable as an answer — is still true; it had been written against
the implementation rather than the invariant. It now asserts no *response body*
is written and that whatever is written is a `_failure` record. Same shape of
mistake as session 3's `has_signal` test.

`test_a_429_is_retried_but_a_402_is_not` broke for a genuinely interesting
reason: it looped over two codes sharing one `tmp_path`, with doc ids `d429` and
`d402`. **`doc_id` is not part of a request**, so both produce the same cache
key — the 402 case replayed the 429's newly recorded failure and never called at
all. Correct production behaviour (same document and prompt *is* the same
request), wrong test fixture. Each code now gets its own cache directory.

### What the experiment is allowed to claim

Prithvi pushed back on the first draft of the results write-up, which said the
project's thesis was "confirmed at scale". That was too loose, and the narrower
statement is the one the data actually supports:

> Models can produce perfectly grounded extraction records while still returning
> incorrect settings and incorrect structured attributes. Stricter prompting can
> substantially reduce hallucinated settings, but may reduce recall.

Both halves are strongly supported. What is **not** supported is any claim that
one model is best: the ten cells vary vendor, architecture, price and serving
provider simultaneously, and the design held the *mechanism* constant rather
than isolating any single model property. H5 looking excellent under v2 is an
observation about one configuration on 45 hand-labelled documents at one seed,
not a ranking. The README says exactly this, in those words, before the table.

Worth keeping as a general rule: the temptation to overclaim is strongest right
after the numbers come in and look good, which is also the moment nobody is
checking.

### Numbers worth remembering

- **Grounding is 100.0% in all ten cells, across 1,519 records.** Not one record
  quoted text its document does not contain. In the same table H2 scores 32–36%
  on scope and H1 56–63% on type. Perfect provenance, wrong answers — which is
  the whole point of the project, and it needed the oracle to be visible at all.
- **88% valid on the first pass**; of the 126 repairs, 75% succeeded. H4 alone
  used 81 of those 126.
- **H1 was 85% of the bill** for recall H5 nearly matches at 1/90th the price.
- **13 truncations are 8% of spend.** H1's three are genuine runaway reasoning;
  H4's ten are a whitespace loop with 559–1,147 reasoning tokens. Same label in
  the outcome column, completely different failures.
- One H4 call ran **896 seconds**, because `REQUEST_TIMEOUT` is a socket
  inactivity timeout and not a deadline. Recorded as a defect in the README.

## Open questions for session 5

- **Seed sensitivity is still unmeasured**, and now it is the largest single
  threat to the arm ordering in the table. A three-seed redraw is ~$6 at this
  mix, or ~$1 with H1 sampled rather than swept.
- **40 prose documents are still on the proxy**, which can invert. Labelling
  them is $0 and about a session.
- **L1 (local Ollama), B0 (table parser) and B1 (null) were never built.** B0
  is the cheapest remaining result in the project: it answers "do you even need
  an LLM for this?" and the parser already exists.
- **`REQUEST_TIMEOUT` is inactivity, not a deadline.** Decide before any re-run.
- **The 429s were all in one hour on one arm.** Re-running H5 on another day
  would say whether 91–93% availability is a property of the provider or of that
  afternoon.
