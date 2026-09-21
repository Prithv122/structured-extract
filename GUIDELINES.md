# structured-extract — G7

**Tier:** 3 (flagship) · **Category:** AI Engineering / LLM · **Wave:** 3 - Production tier

Root rules in `../GUIDELINES.md` apply. This file is project-specific only — keep it under 40 lines.

## What this is

Extract validated, evidence-grounded records of DuckDB configuration settings from real
documentation prose, and score every field against the binary's own `duckdb_settings()` —
a free, exact oracle for 280 settings with zero human labelling.

## Stack

Python 3.12 · `uv` · Pydantic v2 (`model_json_schema()` drives `response_format`) ·
duckdb 1.5.5 (the oracle) · OpenRouter (hosted arms) · Ollama (local arm) · pytest · ruff.

## Acceptance criteria

- [x] Oracle committed and verified: `data/oracle/settings.jsonl` + `data/oracle/docs_reference.jsonl`
- [x] Corpus committed: 120 documents, 3 strata, seeded, provenance-pinned
- [x] Pydantic schema + exactly one bounded repair (never fed the oracle)
- [x] Hallucination rate, per-field accuracy and cost measured across arms H1-H5 —
      1,200 calls, $2.0528. **L1, B0 and B1 were not run**; the README says so.
- [x] Hand-labelled recall set (40 sections) — mentioned != documented
- [x] Every published number replays from the committed cache with an empty API key —
      verified on a clean tree, diff against the published rows empty
- [ ] Ship gate passes

## Project-specific notes

- **Source corpus:** `duckdb/duckdb-web` @ `6f6cd1659f0e2ddd1965b1d3f1833e7fc512e7ac`
  (2026-09-06, MIT). Its `_config.yml` pins `current_duckdb_version: "1.5.5"` — **exactly**
  the installed duckdb. Docs and oracle are the same release; do not upgrade either alone.
- **`duckdb_settings().value` is machine-dependent** (`threads`, `memory_limit`, `Calendar`).
  It is NOT ground truth for "default" — the docs reference table is. Two oracles, and their
  disagreements are a finding, not a bug.
- **Never let the oracle into the pipeline.** The repair prompt sees the document, the raw
  output, `ValidationError.errors()` and the schema. Nothing else.
- **Arms are pinned in `arms.py`** with price and capability. `arms verify` resolves
  every id against the *public* catalogue — no key, no spend — and fails on drift.
  Run it before any session that will spend.
- No API key ever enters an agent session. `extract run --live` is the only command
  that costs money, and only the user runs it.
