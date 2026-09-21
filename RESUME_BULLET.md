# Resume Bullets — structured-extract

Form: **action → technical specifics → measured outcome.** Numbers or it doesn't go on the resume.

---

## Bullets

**Primary (lead with this one):**

- Built an LLM extraction benchmark scored against an exact, zero-labelling
  oracle (DuckDB's own `duckdb_settings()`, 274 settings), running 5 hosted
  models × 2 prompts × 120 real documentation sections — 1,200 calls for $2.05 —
  and found **100% evidence-grounding alongside 32% scope accuracy**, showing
  that verbatim citation validates provenance but not correctness.

**Supporting:**

- Designed a Pydantic v2 contract whose `model_json_schema()` generates the
  provider `response_format`, so validator and wire schema cannot drift, with a
  document-grounding rule enforced in a validator because no JSON Schema can
  express it; **88% of 1,200 responses were valid on the first pass** and one
  bounded repair recovered **75%** of the rest.

- Measured a precision/recall tradeoff from a single prompt change across five
  models: hallucinated records fell to **zero on four of five arms**, while
  recall on the strongest arm dropped from **50/51 to 33/51** — quantifying a
  tradeoff usually argued qualitatively.

- Caught a **1.85× discrepancy** between advertised catalogue pricing and billed
  cost by recording both per call: reasoning tokens are billed but excluded from
  `completion_tokens` (2.92× understated on one arm), while the routed provider
  charged 0.27× the listed rate on another.

- Made every published figure reproducible offline — SHA-256 request-keyed
  response cache committed to the repo, so a clean clone with an empty API key
  regenerates all 1,200 rows with a **field-by-field diff of zero**; 245 tests,
  CI, no network required.

- Audited the documentation against the shipped binary as a by-product: **0**
  invented settings and **0** type or scope contradictions across 169 documented
  rows, but **17** core settings undocumented and **32** reference rows that
  require an unstated extension.

## Which roles this supports

- [x] Data Scientist / ML
- [x] AI Engineer (LLM/NLP/CV)
- [ ] Data Engineer
- [x] Data Analyst / Python Developer

Strongest for **AI Engineer** — this is an LLM evaluation project first. It
carries DS/ML on experimental design (stratified sampling, stated limitations,
refusing to claim effects the n doesn't support) and Python on the engineering
(typed contracts, caching, retry/repair separation, 245 tests).

## Keywords this project earns

LLM evaluation · structured outputs / constrained decoding · JSON Schema ·
Pydantic v2 · hallucination measurement · grounding & evidence spans ·
precision/recall tradeoff · prompt ablation · OpenRouter · multi-model
benchmarking · cost & latency instrumentation · stratified sampling ·
reproducible pipelines / response caching · pytest · ruff · CI · DuckDB · uv

Not claimed: fine-tuning, RAG retrieval, vector databases, distributed training,
agents. None of those are in here.

## What I can be questioned on, and want to be

- Why `name` is a free string and not an enum of the 274 known settings.
- Why constrained decoding turns "I don't know" into a confident wrong answer.
- Why the machine-dependent `duckdb_settings().value` is not ground truth for
  defaults.
- Why 40 of 120 documents are excluded from headline recall, and why the proxy
  they use can invert rather than merely under-count.
- Why a 429 is retried but a `ValidationError` is repaired, and why merging the
  two counters would flatter a flaky provider.
