# structured-extract

> Extract validated, evidence-grounded records of DuckDB configuration settings from real documentation prose, and score every field against the binary's own `duckdb_settings()` — a free, exact oracle for 280 settings.

[![CI](https://github.com/Prithv122/structured-extract/actions/workflows/ci.yml/badge.svg)](https://github.com/Prithv122/structured-extract/actions/workflows/ci.yml)

**Status:** in progress — ground truth and corpus are built and committed; the
extraction arms are not yet run. Nothing in §5 is measured yet and the section
says so rather than showing placeholders.
**Stack:** Python 3.12 · `uv` · Pydantic v2 · duckdb 1.5.5 · OpenRouter · Ollama · pytest · ruff

---

## 1. The problem

Turning documentation prose into structured records is the most commercially
applied LLM pattern there is, and the hardest part of shipping one is not the
extraction — it is knowing whether the output is right. Most extraction demos
score against labels a human wrote in an afternoon, which measures agreement
with that afternoon rather than correctness.

This project picks a domain where the ground truth already exists and is exact.
DuckDB's own `duckdb_settings()` adjudicates whether a configuration setting
exists, what type it takes and what scope it has, for **280 settings, with zero
human labelling**. A hallucinated setting name becomes a hard count instead of a
judgement call. The by-product is useful in its own right: the same comparison
audits DuckDB's published configuration reference against the shipped binary.

## 2. The data

| | |
|---|---|
| Documentation | [`duckdb/duckdb-web`](https://github.com/duckdb/duckdb-web) @ `6f6cd16` (2026-09-06), 434 pages under `docs/current`, of which **420 are prose** |
| Oracle | `duckdb_settings()` from the `duckdb` Python package, **v1.5.5** |
| Licence | MIT (both) — Copyright 2018-2025 Stichting DuckDB Foundation |
| Corpus | 120 documents sampled from 4,793 heading sections, seed `20260919` |
| Refresh | one-off, pinned |

The 14 excluded pages are generated API reference — the `clients/c/` tree, the
Sphinx dump at `clients/python/reference/index.md`, and the docs landing page,
which is a grid of navigation tiles. They are HTML, not prose, and the two
families do not overlap: every excluded page carries 10–24 block-HTML tags per
1000 characters and every prose page carries ≤ 1.6.

The docs checkout's `_config.yml` sets `current_duckdb_version: "1.5.5"`, exactly
the installed `duckdb`. Documentation and oracle describe the same release, and
`scripts/fetch_source_docs.py` refuses to run if that stops being true — a docs
checkout one release ahead of the binary would produce "hallucinations" that were
really just version skew.

Not synthetic. Every document is a verbatim heading section of a real DuckDB
documentation page, committed with the page and heading it came from and a
sha256 that `corpus verify` re-checks.

## 3. Architecture

```mermaid
flowchart LR
    subgraph truth["ground truth · no LLM"]
        BIN["duckdb_settings()<br/>280 rows / 274 settings"] --> OR["settings.jsonl"]
        REF["configuration reference<br/>169 documented options"] --> DR["docs_reference.jsonl"]
        BIN -.machine-dependent.-> OV["observed_values.jsonl"]
    end
    subgraph corpus["corpus"]
        DOCS["434 pages<br/>420 prose"] --> SEC["4,793 heading sections"]
        SEC --> SAMP["stratified sample<br/>seed 20260919"]
        SAMP --> CD["120 documents"]
    end
    CD --> ARM["extraction arms<br/>H1-H5 · L1 · B0 · B1"]
    ARM --> VAL["Pydantic validate<br/>+ grounding check<br/>+ one bounded repair"]
    VAL --> SCORE["score"]
    OR --> SCORE
    DR --> SCORE
    SCORE --> AUDIT["docs vs binary audit"]

    style truth fill:#eef,stroke:#88a
    style corpus fill:#efe,stroke:#8a8
```

The oracle never reaches the extraction or repair path. The repair prompt sees
the document, the raw output, `ValidationError.errors()` and the schema —
nothing else. Feeding it the oracle would leak ground truth into the pipeline
and make the benchmark measure itself.

## 4. Key decisions & tradeoffs

| Decision | Chose | Over | Why |
|---|---|---|---|
| Ground truth | `duckdb_settings()` + the generated reference table | Hand-labelled records | Exact, free, 280 settings, zero labelling. The scarce human effort goes where no oracle can reach: 40 hand-labelled sections for *recall*, because "mentioned" and "documented" are different and only a person can tell them apart. |
| Defaults | The docs reference table | `duckdb_settings().value` | `value` is what the *build machine* runs — `threads` is its core count, `max_memory` a fraction of its RAM. Committing it would make the oracle non-reproducible and score models against one laptop. Kept separately in `observed_values.jsonl`, host-stamped. |
| Reference-table parser | Hand-written, assert at every step | `re.findall` over a row pattern | Measured on the real page: the regex silently drops **10 of 169 rows**, every one of them invisible. It survives as the `B0` baseline arm so "do you even need an LLM?" gets a fair answer. |
| Corpus unit | Heading sections of real pages | Whole pages, or synthetic paragraphs | Sections are what a reader consumes and fit a context window, so truncation policy does not become a confound. Prose stays exactly as shipped, tables and Jekyll markup included. |
| Stratum sizes | Measured, then rebalanced | The planned 55/35/30 | Only **19** extension pages contain a section naming a non-distractor setting. 35 was not obtainable without sampling the same pages four times; `extension-signal` is a census of all 19 and says so. |
| Distractors | Fixed 16 of 120 | Whatever the corpus produced | 60% of prose sections mentioning a "known setting" mention only `schema`/`user`/`username`/`password`/`threads`/`secret`. Left alone they took 54 of 90 prose documents. They are a real failure mode, sampled on purpose instead of by accident. |
| Pydantic | Yes, here | The `extract_json` + dataclass approach that [project 24](https://github.com/Prithv122/production-rag) chose | Not a reversal — a different layer. 24's payload was one flat field, where Pydantic would have duplicated `extract_json`. This payload is a nested list of records with closed enums, a pattern-constrained identifier and a cross-field uniqueness rule; `model_json_schema()` drives `response_format` so contract and validator cannot drift, and the per-field `ValidationError.errors()` list *is* the repair prompt's input. |
| Hallucination check | Leave `name` a free string | An enum of the 274 known settings | Putting the oracle in the schema would make a hallucinated name impossible to emit — and delete the benchmark's primary measurement. The schema must accept `frobnicate_cache`; scoring it wrong is the oracle's job, afterwards. There is a test asserting exactly this. |
| Grounding check | `evidence` must be a verbatim span of the document | An LLM judge, or trusting the model | Free, exact and unarguable, in the same way the oracle is. JSON Schema cannot express it, so the decoder enforces shape and a Pydantic validator enforces grounding — which means an arm can be perfectly schema-valid and still fail for quoting something the document does not say. Those are separate columns. Whitespace runs are normalised on both sides, because markdown hard-wraps mid-sentence; nothing else is. |
| Arm selection | Five hosted models, all with native structured outputs | A mix of structured and unstructured arms | Holding the mechanism constant means H1–H5 vary by capability alone. "Does constrained decoding help at all?" is a different question and belongs to the B0/B1 baselines. |
| The ceiling | `deepseek-v4-pro` | `claude-sonnet-5` | A grid with no strong arm cannot separate "this task is hard" from "these models are small", so a ceiling is not optional. But Sonnet was 76% of the cost and is the only candidate that accepts neither `temperature` nor `seed`. Decoupling "ceiling" from "frontier" made the grid 2.7× cheaper, one arm wider, and fully pinnable. |
| Determinism | Send only the knobs each provider advertises, and record which | Assume `temperature=0` works | It does not work everywhere — Sonnet 5 takes neither control, the GPT-5 family takes `seed` but not `temperature`. The client sends only what an arm advertises and `arms verify` fails if that changes, so the method section stays re-derivable rather than aspirational. |
| Repair vs retry | A `ValidationError` consumes the one repair; a 429 or 502 does not | One counter for both | A 502 is not a bad answer, it is no answer. Merging them would let a flaky provider look like a model that needs fewer repairs. |

## 5. Results

**Not measured yet.** The extraction arms have not been run; this section will
carry hallucination rate, per-field accuracy, cost and latency per arm, with the
sampling band alongside, once they have.

The arms are pinned, and every id was resolved against OpenRouter's public
catalogue before a line of client code was written against it
(`structured-extract arms verify`):

| Arm | Model | $/M in | $/M out | Role | Structured outputs | `temperature` + `seed` |
|---|---|---:|---:|---|:-:|:-:|
| H1 | `deepseek/deepseek-v4-pro` | 0.4223 | 0.8446 | ceiling | ✓ | ✓ |
| H2 | `google/gemini-2.5-flash` | 0.30 | 2.50 | mid-tier | ✓ | ✓ |
| H3 | `openai/gpt-4.1-nano` | 0.10 | 0.40 | small, non-reasoning | ✓ | ✓ |
| H4 | `openai/gpt-oss-120b` | 0.15 | 0.60 | open weights | ✓ | ✓ |
| H5 | `z-ai/glm-5.3-flash` | 0.090 | 0.300 | floor | ✓ | ✓ |

Five vendors, every arm on native structured outputs so the *mechanism* is held
constant, and **every arm accepts `temperature=0` and a seed** — which took a
deliberate choice, see below.

Estimated cost of the full 120 × 5 grid: **$0.39**
(`structured-extract arms cost`). Published costs will come from the token
counts the providers actually report, not from this estimate.

**Claude Sonnet 5 was the original ceiling and was dropped.** At $2.00/$10.00 it
was 76% of the grid's cost on its own, and it is the only model considered here
that advertises neither `temperature` nor `seed` — so keeping it meant either
pretending the knob was set or publishing a grid with one arm that could not be
held still. The fix was to stop treating "ceiling" as a synonym for "frontier":
DeepSeek V4 Pro is flagship-class, takes both controls, and costs 7.6× less. The
grid got cheaper, wider and more reproducible at the same time.

No `:free` model ids anywhere. They are not the same endpoint —
`z-ai/glm-5.2:free` reports `structured_outputs=False`, `response_format=False`
and a 32 k context against the paid id's 1 M, so it cannot accept this schema at
all — and `:free` carries OpenRouter's 50-requests/day account-wide cap, while a
single arm needs 120 calls before any repair.

What *is* measured is the ground truth itself — the docs-vs-binary audit, which
is a result in its own right and needed no model at all:

| | |
|---|---:|
| Documented names unknown to the binary | **0** |
| Scope disagreements across 169 rows | **0** |
| Type disagreements across 169 rows | **0** |
| Core settings the reference page omits | **17** |
| Reference rows that require an extension | **32** |
| Settings in no reference table at all | **105** |

Reproduce with `uv run structured-extract oracle verify --detail`.

The DuckDB docs never invent a setting and never contradict the binary on type
or scope. They do omit 17 core settings — 11 `debug_*`, 3 `force_*`, and
`pandas_analyze_sample` / `python_enable_replacements` / `python_scan_all_frames`
— which is plausibly deliberate for the debug ones. And the reference page is
generated from a build with `httpfs` loaded without saying so, which is why 32 of
its 169 "global configuration options" do not exist in a plain DuckDB.

## 6. How to run

```bash
git clone https://github.com/Prithv122/structured-extract.git
cd structured-extract
uv sync --all-groups
uv run pytest
```

That works offline, with no API key. 120 tests check the committed oracle, the
corpus, the extraction schema and the repair ladder, including a cross-check of
the committed core settings against a live plain `duckdb`.

```bash
uv run structured-extract oracle verify --detail   # the audit above
uv run structured-extract corpus verify            # re-hash every document
uv run structured-extract corpus stats
```

The arms are pinned by exact model id and price. Checking them costs nothing —
OpenRouter's model catalogue is a public endpoint and needs no key:

```bash
uv run structured-extract arms verify
uv run structured-extract arms cost
```

Running the grid replays from the committed cache by default, so every published
number reproduces with `OPENROUTER_API_KEY` empty and no network:

```bash
uv run structured-extract extract run
uv run structured-extract extract run --pilot 8 --verbose
```

`--live` issues real, billed requests for anything not already cached. It is the
only command in this repo that spends money, and it refuses to start unless
`OPENROUTER_API_KEY` is set in the environment:

```bash
uv run structured-extract extract run --pilot 8 --live --verbose
```

One test reads the live catalogue to confirm the pinned ids still resolve. It is
deselected by default so the suite stays offline:

```bash
uv run pytest -m live
```

To rebuild the ground truth from scratch (needs network once, ~2 min for the
pinned docs checkout, plus DuckDB extension downloads):

```bash
uv run python scripts/fetch_source_docs.py
uv run structured-extract oracle build
uv run structured-extract corpus build --seed 20260919
```

Environment variables are listed in `.env.example`; neither is needed for
anything above.

## 7. What I'd change at 100× scale

Not written yet — it belongs with the results.

---

## References

- DuckDB documentation and `duckdb_settings()`, both MIT — the corpus and the
  oracle. Sampled documents are verbatim excerpts; see `data/README.md`.
- No reference implementation was consulted for the extraction or scoring design.
