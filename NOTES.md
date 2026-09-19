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

## Open questions for session 3

- **Seed sensitivity is unmeasured.** The corpus is seeded at `20260919` and
  reproducible, but nothing yet says how much a different seed moves a score.
  Project 24's lesson was that the sampling band was wider than most of the gaps
  in the table; budget a re-draw before publishing arm ordering.
- **`narrative-distractor` at 10 documents** is enough to notice a
  false-positive problem, not enough to quantify one. State it as an
  observation, not a rate.
