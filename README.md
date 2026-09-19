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
| Documentation | [`duckdb/duckdb-web`](https://github.com/duckdb/duckdb-web) @ `6f6cd16` (2026-09-06), 434 pages under `docs/current` |
| Oracle | `duckdb_settings()` from the `duckdb` Python package, **v1.5.5** |
| Licence | MIT (both) — Copyright 2018-2025 Stichting DuckDB Foundation |
| Corpus | 120 documents sampled from 7,498 heading sections, seed `20260919` |
| Refresh | one-off, pinned |

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
        DOCS["434 doc pages"] --> SEC["7,498 heading sections"]
        SEC --> SAMP["stratified sample<br/>seed 20260919"]
        SAMP --> CD["120 documents"]
    end
    CD --> ARM["extraction arms<br/>H1-H4 · L1 · B0 · B1"]
    ARM --> VAL["Pydantic validate<br/>+ one bounded repair"]
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
| Pydantic | Yes, here | The `extract_json` + dataclass approach that [project 24](https://github.com/Prithv122/production-rag) chose | Not a reversal — a different layer. 24's payload was one flat field, where Pydantic would have duplicated `extract_json`. This payload is a nested list of 8-field records with enums, optionals and cross-field constraints, `model_json_schema()` drives `response_format` so contract and validator cannot drift, and the per-field `ValidationError.errors()` list *is* the repair prompt's input. `extract_json` still sits underneath as stage one. |

## 5. Results

**Not measured yet.** The extraction arms have not been run; this section will
carry hallucination rate, per-field accuracy, cost and latency per arm, with the
sampling band alongside, once they have.

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

That works offline, with no API key. The committed oracle and corpus are checked
by 53 tests, including a cross-check of the committed core settings against a
live plain `duckdb`.

```bash
uv run structured-extract oracle verify --detail   # the audit above
uv run structured-extract corpus verify            # re-hash every document
uv run structured-extract corpus stats
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
