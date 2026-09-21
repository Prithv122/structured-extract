# Interview Prep — structured-extract

**Five questions, five answers.** An unanswered question means this project is not shipped.

---

### Q1. Walk me through the architecture in 90 seconds.

_A:_ It's a benchmark for structured extraction where the ground truth is free
and exact, and it has three layers.

**Ground truth, built with no LLM.** DuckDB ships a function, `duckdb_settings()`,
that returns every configuration setting the binary actually has — 280 rows,
274 distinct settings after alias pairs — with its type and scope. That's an
oracle: it adjudicates whether a setting exists and what its type is, for free,
with zero human labelling. Separately I parse DuckDB's published configuration
reference page into 169 documented rows, which is the truth source for
*defaults*, because the binary's `value` column is machine-dependent — `threads`
is my core count, `max_memory` is a fraction of my RAM. Two oracles, and where
they disagree that's a finding, not a bug.

**Corpus.** 434 real documentation pages, 420 of them prose, split into 4,793
heading sections, stratified-sampled down to 120 documents at a fixed seed.
Verbatim text, committed with a sha256 the CLI re-checks.

**Extraction and scoring.** A Pydantic model defines seven fields per record;
`model_json_schema()` generates the `response_format` sent to the provider, so
the contract and the validator cannot drift apart. Five hosted models × two
prompt variants × 120 documents = 1,200 calls. Each response is parsed and
validated; a validation failure gets exactly one bounded repair, which sees the
document, the raw output and `ValidationError.errors()` — never the oracle.
Then every field is scored against the oracle, and every response is cached by
a hash of the full request, so the published numbers replay offline with no API
key.

The one-line version: **the hard part of extraction isn't extracting, it's
knowing whether the output is right — so I picked a domain where a machine can
tell me.**

---

### Q2. Why did you choose an exact oracle over hand-labelled data?

_A:_ Because hand labels measure agreement with the afternoon somebody spent
writing them, and they don't scale. `duckdb_settings()` gives me 274 settings
with type and scope for free, and it grows when DuckDB grows. A hallucinated
setting name becomes a hard count instead of a judgement call.

The more interesting part is where the oracle **can't** reach, because that
tells you what an oracle is actually for. The oracle can tell me a returned
record is wrong. It cannot tell me what a document *should* have produced —
"this page documents `max_memory`" versus "this page says the word memory" is a
judgement, and no binary has an opinion about it. So recall needs a human.

I spent the scarce human effort exactly there: 40 hand-labelled sections, plus
35 reference rows whose answer is exact by construction, giving 80 of 120
documents real ground truth. The other 40 fall back to a proxy — "does the
document mention a known setting name" — and that proxy is not just biased low,
**it can invert**. On `narrative-0001` the correct answer is the empty set, and
every arm that answered correctly was scored as having missed. So the proxy is
excluded from the headline *by construction* — the `recall` property physically
cannot include it — and printed beside it so the reader can see what's estimated
and what's measured.

The design rule I'd take anywhere: **let the machine score what it can score
exactly, and spend humans only on what it can't.**

---

### Q3. What's the weakest part of this, and what would break first under load?

_A:_ The weakest part is **n**, and I'd say that before an interviewer got to it.

The prompt effect — the most interesting result in the project — rests on 45
hand-labelled documents and 51 expected settings, at one seed. I never measured
seed sensitivity. Project 24 taught me that the sampling band can be wider than
the gaps in the table, and nothing here rules that out for the smaller gaps. The
big effects are safe: H2 going from 20 hallucinated records to 0 isn't a
sampling artefact. "H5 beats H4 by three records" might be, and I don't report
it as if it isn't.

Second weakest: three of eight planned arms were never run — the local model,
the null baseline, and the plain table parser. The parser one stings, because
it answers "do you even need an LLM for this?" and the code already exists.

What breaks first under load is **the sequential loop**. 1,200 calls took ten
hours, 8.6 of them pure provider latency. 100× is a thousand hours in a
straight line. The fix is bounded concurrency behind a per-provider token
bucket — bounded, because this run already produced 20 HTTP 429s from
outrunning a provider. The cache is already the checkpoint, so workers can die
and resume for free.

Second under load is cost shape, not cost: H1 was 85% of a $2 bill. At 100×
that's $175 of a $205 run on one arm. The fix isn't to drop the ceiling arm,
it's to sample it — run it on 1–2% to detect that the cheap arm has drifted,
instead of sweeping it.

---

### Q4. How do you know it works? What did you measure, and against what baseline?

_A:_ 1,200 calls, $2.0528, and the headline is the one number I did **not**
expect:

**Grounding was 100.0% in all ten cells, across 1,891 records.** Every record
has an `evidence` field that must be a verbatim span of its document, and not
one record failed it. In the same table, Gemini 2.5 Flash scores **32–36% on
scope** and DeepSeek V4 Pro **56–63% on type**.

That's the result. The models are reliably quoting the document and reliably
mislabelling what they quoted. **A citation is a check on provenance, not on
correctness** — and a pipeline that ships "every claim is sourced" as its safety
story has measured the easy half. I could only see that because the oracle gave
me a correctness signal independent of the grounding signal.

Second result: a stricter prompt trades recall for precision, and it's a real
trade. Four of five arms went to **zero** hallucinated records. Four of five
also lost recall, and Gemini lost a third of it — 50 settings found became 33.
One prompt change moved it from "finds nearly everything, invents a quarter of
it" to "invents nothing, misses a third". Which is better depends on whether a
false record or a missed record costs more downstream, and this benchmark can
price both.

Baselines: there's no prior number for this task, so the baselines are internal
— the two prompt variants against each other, the five arms against each other,
and the docs-vs-binary audit that needed no model at all (which found DuckDB's
docs never invent a setting and never contradict the binary, but omit 17 core
settings and describe a build with `httpfs` loaded without saying so).

And every number replays: clean tree, `OPENROUTER_API_KEY` empty, 1,200 rows
from the committed cache, field-by-field diff against the published results
empty.

---

### Q5. Your `name` field is a free string. Why didn't you constrain it to the 274 known settings — you'd get zero hallucinations for free?

_A:_ Because that would delete the measurement, not fix the problem.

It's one line to paste the oracle into the schema as an enum. The decoder would
then make a hallucinated name literally unemittable, hallucination rate would
read 0% for every arm, and I'd have learned nothing — I'd have measured the
constraint, not the model. There's a test in the repo asserting the schema
happily accepts `frobnicate_cache`, precisely so nobody "improves" this later.

There's a sharper version of the same trap that the results actually
demonstrate. `input_type` and `scope` **are** closed enums, and constrained
decoding guarantees the value is valid. It does not guarantee it's correct — and
the model has no way to say "I don't know". So "I don't know" comes out as a
confidently wrong enum member. That's exactly what H2's 32% scope accuracy is:
it never emitted an invalid scope, it just guessed, and it guessed wrong about
two-thirds of the time.

**Constrained decoding converts a formatting failure into a semantic one.** It
doesn't remove the failure, it moves it somewhere your JSON parser can't see —
which is worse, because you stop noticing.

The general principle: **never put the answer key in the schema.** Structure the
output, validate the structure, and keep the thing you're measuring outside the
constraint. Scoring is the oracle's job, afterwards.

---

## 30-second pitch

Structured extraction is the most commercially applied LLM pattern there is, and
the hard part isn't extracting — it's knowing whether the output is right. So I
built a benchmark where the ground truth is free and exact: DuckDB's own binary
reports every real configuration setting, which makes a hallucinated setting a
hard count instead of a judgement call. I ran five models across two prompts over
120 real documentation sections — 1,200 calls, $2.05, every response committed so
the numbers replay offline. The finding I didn't expect: grounding was 100% in
every cell — not one record quoted text its document didn't contain — while scope
accuracy on one model sat at 32%. Perfect provenance, wrong answers. A citation
checks where a claim came from, not whether it's true, and you only see the gap
if you have a correctness signal that doesn't come from the model.
