"""One document in, one validated extraction out -- with exactly one repair.

The ladder
----------
Every document gets at most **two** billed calls per arm:

1. The extraction call, with the JSON Schema in ``response_format``.
2. If and only if that output failed to validate, **one** repair call.

There is no third attempt, no "keep going until it parses", and no silent
coercion of a nearly-right answer. The point of the benchmark is to measure how
often a schema-constrained model gets it right, and a loop that retries until
success measures nothing except patience and budget.

Repair is not retry
-------------------
A 429 or a 502 is a *transport* failure and is retried with backoff without
consuming the repair -- nothing was wrong with the model's answer, there was no
answer. A ``ValidationError`` is a *semantic* failure and consumes the one
repair. Conflating them would let a flaky provider look like a model that needs
fewer repairs.

What the repair is allowed to see
---------------------------------
The document, the raw string the model returned, ``ValidationError.errors()``,
and the schema. That is the whole list. **The oracle is never in the prompt**,
not as names, not as a hint, not as "did you mean". If the repair could see the
answer key the hallucination rate would measure the repair prompt rather than
the model, and every number in the README would be worthless.

Replay
------
Every response body is cached on disk keyed by the exact request. A run with a
warm cache and an empty ``OPENROUTER_API_KEY`` reproduces every published
number and issues no HTTP at all, which is how the results stay checkable by
someone who will never buy an OpenRouter credit.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from pydantic import ValidationError

from structured_extract import schema as S
from structured_extract.arms import COMPLETIONS_URL, Arm

#: Transport retries. Not the repair -- see the module docstring.
MAX_TRANSPORT_RETRIES = 3
BACKOFF_SECONDS = (1.0, 4.0, 10.0)

#: Generous enough that truncation means the model ran away rather than that the
#: budget was stingy. Reasoning tokens count against this on most providers, and
#: reasoning is no longer switched off (see ``build_payload``), so the pilot's
#: observed ~250 answer tokens per call is the wrong number to size against.
#: Raised from 2000 after the first pilot: the smallest ``max_completion_tokens``
#: across the five arms is 32,768, so this stays comfortably inside every one.
MAX_OUTPUT_TOKENS = 8000

REQUEST_TIMEOUT = 120.0


class Outcome(StrEnum):
    """What happened to one (document, arm) pair. Exactly one applies."""

    VALID_FIRST_PASS = "valid_first_pass"
    VALID_AFTER_REPAIR = "valid_after_repair"
    #: Parsed as JSON, still violates the schema or the grounding check.
    INVALID_AFTER_REPAIR = "invalid_after_repair"
    #: Not JSON at all, after the repair.
    UNPARSEABLE = "unparseable"
    #: ``finish_reason == "length"`` on the final attempt.
    LENGTH_TRUNCATED = "length_truncated"
    #: The provider answered with an error, or the transport never got there.
    PROVIDER_ERROR = "provider_error"
    #: No provider would serve this model: unknown id, no credit, all routes down.
    PROVIDER_UNAVAILABLE = "provider_unavailable"


#: Outcomes where no answer was produced, so nothing can be scored against the
#: oracle and the row must not be counted in any accuracy denominator.
NO_ANSWER = frozenset({Outcome.PROVIDER_ERROR, Outcome.PROVIDER_UNAVAILABLE})

#: The prompt the first pilot ran. It names the task and warns about names that
#: are ordinary words, but it never says what *kind of thing* a configuration
#: setting is. On ``narrative-0001`` -- a table headed ``COPY ... TO`` Options,
#: with a name, a type and a default per row, which is exactly the shape of a
#: configuration reference -- all three working arms returned the same 14 COPY
#: options, **none** of which ``duckdb_settings()`` knows, and all three missed
#: the one real setting name in the document. Schema-valid, verbatim-grounded,
#: entirely the wrong kind of entity.
#:
#: Kept as an arm of the experiment rather than deleted: the interesting
#: question is not "which model is best" but "how much of the hallucination was
#: the prompt's fault", and that needs both halves.
PROMPT_UNSPECIFIED = """\
You extract DuckDB configuration settings from a single section of the DuckDB \
documentation.

Return every configuration setting that this section *documents*. A section \
documents a setting when it tells the reader what the setting does, what it \
accepts, or how to set it.

Do not return a setting merely because the section contains a word that happens \
to be a setting name. Some setting names are also ordinary English words, or \
parameters belonging to some other system entirely, and a section that uses one \
of those in passing is not documenting a DuckDB setting. An empty list is the \
correct answer for a section that documents nothing.

For each setting, quote a span of the section verbatim as evidence. Copy the \
characters exactly as they appear. Do not paraphrase, tidy or complete the quote.

Answer only with JSON matching the supplied schema."""

#: The same task with the entity type pinned down. This is a *specification*,
#: not an answer key: it says what category of thing is being asked for, and it
#: names none of the 274 settings, so the hallucination measurement survives.
#: The look-alike list is drawn from what the documentation actually contains,
#: not from what the models got wrong -- COPY options, function arguments and
#: column constraints are all tabulated the same way as settings are.
PROMPT_SPECIFIED = """\
You extract DuckDB configuration settings from a single section of the DuckDB \
documentation.

A configuration setting is one you change with SET, RESET or PRAGMA, and it \
then applies to the whole database instance or to your connection. It is a \
property of the database's configuration, not of any one query.

Several other things in DuckDB's documentation are tabulated exactly like \
configuration settings -- a name, a type, a description and a default, often in \
the same kind of table -- and none of them are configuration settings:

- options and arguments of a SQL statement, such as the parenthesised options \
of COPY, CREATE, ATTACH or EXPORT
- parameters of a table function or a scalar function
- column constraints, storage properties and file-format fields
- settings belonging to some other database system, quoted for comparison

If the section documents those, the correct answer is an empty list, even when \
the section is long and every row looks like a setting.

Do not return a setting merely because the section contains a word that happens \
to be a setting name. Some setting names are also ordinary English words, or \
parameters belonging to some other system entirely, and a section that uses one \
of those in passing is not documenting a DuckDB setting.

For each setting, quote a span of the section verbatim as evidence. Copy the \
characters exactly as they appear. Do not paraphrase, tidy or complete the quote.

Answer only with JSON matching the supplied schema."""

#: Prompt variants under test. The key is part of the experiment's identity: it
#: goes into every results row, and because the prompt text is inside the
#: request, it is already part of the cache key -- so the two variants cannot
#: overwrite each other's cached responses.
PROMPTS: dict[str, str] = {
    "v1-unspecified": PROMPT_UNSPECIFIED,
    "v2-specified": PROMPT_SPECIFIED,
}

DEFAULT_PROMPT = "v2-specified"

#: Back-compatible alias for the single-prompt call path.
SYSTEM_PROMPT = PROMPT_UNSPECIFIED

REPAIR_PROMPT = """\
Your previous answer did not validate against the schema.

The errors are listed below. Fix exactly these problems and return the corrected \
JSON. Do not add settings you did not previously return, and do not remove \
settings that were valid -- change only what the errors point at.

If an error says the evidence is not a verbatim span, find the real text in the \
document and copy it character for character.

Your previous answer:
{raw}

Validation errors:
{errors}"""


@dataclass
class CallResult:
    """One HTTP round trip, cached or live."""

    content: str
    finish_reason: str
    answering_model: str
    prompt_tokens: int
    completion_tokens: int
    #: What the provider says it attributes to thinking. NOT reliably a subset
    #: of completion_tokens: DeepSeek V4 Pro reported 1,493 reasoning tokens
    #: against 1,147 completion tokens in the second pilot. 0 means 'none, or
    #: not reported' -- indistinguishable from the response, and the README
    #: says so rather than implying the model did no thinking.
    reasoning_tokens: int
    #: ``usage.cost`` -- the USD OpenRouter says this call actually cost. This
    #: is the authoritative figure; see ExtractionRow for why.
    cost_reported: float
    latency_s: float
    cached: bool
    error: str | None = None
    #: Set when the provider refused in a way that means "no route", not "bad request".
    unavailable: bool = False


@dataclass
class ExtractionRow:
    """One row of the results table. Written whatever happened."""

    doc_id: str
    arm: str
    #: Which entry of PROMPTS produced this row. Two rows differing only here
    #: are the prompt-sensitivity comparison.
    prompt: str
    requested_model: str
    answering_model: str
    outcome: str
    repair_used: bool
    finish_reason: str
    first_finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    latency_s: float
    #: What OpenRouter billed, summed over the one or two calls. Authoritative.
    cost_reported: float
    #: Pinned catalogue price x reported tokens. Kept as a cross-check, never
    #: published as the cost. The second pilot found the two disagree badly and
    #: in both directions -- 2.94x low on H1, 3.8x high on H4 -- so reconstructing
    #: a bill from advertised per-token prices does not work.
    cost_estimated: float
    n_settings: int
    #: The validated records themselves, so scoring never has to replay the
    #: cache or re-validate. Empty when nothing validated.
    settings: list[dict]
    error: str | None
    #: ``ValidationError.errors()`` from the final attempt, for the failure analysis.
    validation_errors: list[dict]

    def to_json(self) -> dict:
        return asdict(self)


class MissingAPIKey(RuntimeError):
    """Raised only when a live call is actually needed and no key is configured."""


def cache_key(model_id: str, payload: dict) -> str:
    """Hash the exact request. A changed prompt is a different experiment."""
    blob = json.dumps({"model": model_id, "payload": payload}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_payload(arm: Arm, messages: list[dict]) -> dict:
    """The request body, with only the knobs this arm actually advertises.

    ``allow_fallbacks: False`` is not optional. With fallbacks on, OpenRouter
    will happily answer an unavailable model with a different one and the row
    would say H3 while a stranger did the work -- which is why every row also
    records ``answering_model`` next to ``requested_model``.

    **Reasoning is left at each provider's default, and no ``reasoning`` field
    is sent at all.** The first version sent ``{"enabled": False}`` to every arm
    that advertises reasoning, on the theory that thinking bills as completion
    tokens and the grid should compare extraction rather than thinking budget.
    The first pilot killed 16 of 40 calls with
    ``HTTP 400: Reasoning is mandatory for this endpoint and cannot be
    disabled`` -- H4 and H5 both refuse. ``supported_parameters`` cannot predict
    this: it lists ``reasoning`` and ``reasoning_effort`` for both of them, so
    ``arms verify`` passed them and only a live call found it.

    That left three options. Disabling where possible and not elsewhere makes
    the arms differ on something that is not capability, which is a confound.
    Requesting a minimum effort is not uniformly expressible -- H2 advertises
    ``reasoning`` but not ``reasoning_effort``. Sending nothing is the only
    policy that is identical for all five arms, and it also happens to be what
    a user of these models actually gets. Reasoning tokens are billed and are
    reported per row in ``reasoning_tokens``, so the cost of thinking is
    visible rather than suppressed.
    """
    payload: dict = {
        "model": arm.model_id,
        "messages": messages,
        "response_format": S.response_format(),
        "max_tokens": MAX_OUTPUT_TOKENS,
        "provider": {"allow_fallbacks": False, "require_parameters": True},
    }
    if arm.supports_temperature:
        payload["temperature"] = 0
    if arm.supports_seed:
        payload["seed"] = 0
    return payload


def _post(payload: dict, api_key: str) -> tuple[dict | None, str | None, bool]:
    """POST once. Returns ``(body, error, unavailable)``; never raises on HTTP status."""
    request = urllib.request.Request(
        COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8")), None, False
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        # 402 no credit, 404 unknown id, 403 route refused: no provider will
        # ever serve this request, so it is not a model result and not a bug in
        # the prompt. Retrying is pointless and repairing is meaningless.
        unavailable = exc.code in (402, 403, 404)
        return None, f"HTTP {exc.code}: {detail}", unavailable
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}", False


def call(
    arm: Arm,
    messages: list[dict],
    cache_dir: Path,
    api_key: str | None = None,
    allow_live: bool = True,
) -> CallResult:
    """One completion, from cache if possible.

    Transport failures are retried with backoff. That is deliberately *not* the
    semantic repair: a 429 means there was no answer to repair.
    """
    payload = build_payload(arm, messages)
    path = cache_dir / arm.key / f"{cache_key(arm.model_id, payload)}.json"

    if path.exists():
        body = json.loads(path.read_text(encoding="utf-8"))
        return _from_body(body, latency_s=body.get("_latency_s", 0.0), cached=True)

    if not allow_live:
        raise MissingAPIKey(
            f"{arm.key} {arm.model_id}: no cached response for this request and "
            f"live calls are disabled. Run with --live and OPENROUTER_API_KEY set "
            f"to populate the cache."
        )
    key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise MissingAPIKey(
            "OPENROUTER_API_KEY is empty and this request is not cached. "
            "Every published number replays from the committed cache; only a "
            "fresh run needs a key."
        )

    error, unavailable = None, False
    for attempt in range(MAX_TRANSPORT_RETRIES):
        started = time.monotonic()
        body, error, unavailable = _post(payload, key)
        latency = time.monotonic() - started
        if body is not None:
            body["_latency_s"] = latency
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
            )
            return _from_body(body, latency_s=latency, cached=False)
        if unavailable:
            break
        if attempt < MAX_TRANSPORT_RETRIES - 1:
            time.sleep(BACKOFF_SECONDS[attempt])

    return CallResult(
        content="",
        finish_reason="",
        answering_model="",
        prompt_tokens=0,
        completion_tokens=0,
        reasoning_tokens=0,
        cost_reported=0.0,
        latency_s=0.0,
        cached=False,
        error=error,
        unavailable=unavailable,
    )


def _from_body(body: dict, latency_s: float, cached: bool) -> CallResult:
    """Read one OpenRouter response body, tolerating the shapes it actually returns."""
    if "error" in body and not body.get("choices"):
        message = body["error"]
        text = message.get("message", str(message)) if isinstance(message, dict) else str(message)
        code = message.get("code") if isinstance(message, dict) else None
        return CallResult(
            content="",
            finish_reason="",
            answering_model=body.get("model", ""),
            prompt_tokens=0,
            completion_tokens=0,
            reasoning_tokens=0,
            cost_reported=0.0,
            latency_s=latency_s,
            cached=cached,
            error=f"provider error: {text}",
            unavailable=code in (402, 403, 404),
        )

    choice = (body.get("choices") or [{}])[0]
    usage = body.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    return CallResult(
        content=(choice.get("message") or {}).get("content") or "",
        # OpenRouter reports the provider's own reason in native_finish_reason and
        # a normalised one in finish_reason; the normalised one is what the
        # outcome ladder keys on.
        finish_reason=choice.get("finish_reason") or "",
        answering_model=body.get("model", ""),
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        reasoning_tokens=int(details.get("reasoning_tokens") or 0),
        cost_reported=float(usage.get("cost") or 0.0),
        latency_s=latency_s,
        cached=cached,
    )


def validate(content: str, document: str) -> tuple[S.DocumentExtraction | None, list[dict], bool]:
    """Parse and validate one raw response.

    Returns ``(extraction, errors, parseable)``. ``parseable`` separates "not
    JSON" from "JSON that breaks the schema", because those are different
    failures of a structured-output implementation and the results table keeps
    them apart.
    """
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        return None, [{"type": "not_json", "msg": str(exc)}], False
    try:
        extraction = S.DocumentExtraction.model_validate(
            payload, context={S.DOCUMENT_KEY: document}
        )
    except ValidationError as exc:
        return None, json.loads(exc.json()), True
    return extraction, [], True


def extract_document(
    arm: Arm,
    doc_id: str,
    document: str,
    cache_dir: Path,
    api_key: str | None = None,
    allow_live: bool = True,
    prompt: str = DEFAULT_PROMPT,
) -> tuple[ExtractionRow, S.DocumentExtraction | None]:
    """Extract one document with one arm and one prompt variant, repairing once."""
    system = PROMPTS[prompt]
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": document},
    ]
    first = call(arm, messages, cache_dir, api_key, allow_live)

    def row(
        result: CallResult,
        outcome: Outcome,
        repair_used: bool,
        errors: list[dict],
        n_settings: int,
        settings: list[dict],
        prompt_tokens: int,
        completion_tokens: int,
        reasoning_tokens: int,
        cost_reported: float,
        latency: float,
        first_reason: str,
    ) -> ExtractionRow:
        return ExtractionRow(
            doc_id=doc_id,
            arm=arm.key,
            prompt=prompt,
            requested_model=arm.model_id,
            answering_model=result.answering_model,
            outcome=outcome.value,
            repair_used=repair_used,
            finish_reason=result.finish_reason,
            first_finish_reason=first_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens,
            latency_s=round(latency, 3),
            cost_reported=round(cost_reported, 8),
            cost_estimated=arm.cost(prompt_tokens, completion_tokens),
            n_settings=n_settings,
            settings=settings,
            error=result.error,
            validation_errors=errors,
        )

    if first.error is not None:
        outcome = Outcome.PROVIDER_UNAVAILABLE if first.unavailable else Outcome.PROVIDER_ERROR
        failed = row(
            first, outcome, False, [], 0, [], 0, 0, 0, first.cost_reported, first.latency_s, ""
        )
        return failed, None

    extraction, errors, _parseable = validate(first.content, document)
    if extraction is not None:
        return (
            row(
                first,
                Outcome.VALID_FIRST_PASS,
                False,
                [],
                len(extraction.settings),
                [r.model_dump(mode="json") for r in extraction.settings],
                first.prompt_tokens,
                first.completion_tokens,
                first.reasoning_tokens,
                first.cost_reported,
                first.latency_s,
                first.finish_reason,
            ),
            extraction,
        )

    # --- the one repair ---------------------------------------------------
    # It sees the document, the raw output, the errors and the schema. Nothing
    # else, and above all not the oracle.
    repair_messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": document},
        {"role": "assistant", "content": first.content},
        {
            "role": "user",
            "content": REPAIR_PROMPT.format(
                raw=first.content or "(the model returned nothing)",
                errors=json.dumps(errors, indent=1, ensure_ascii=False),
            ),
        },
    ]
    second = call(arm, repair_messages, cache_dir, api_key, allow_live)

    tokens_in = first.prompt_tokens + second.prompt_tokens
    tokens_out = first.completion_tokens + second.completion_tokens
    tokens_think = first.reasoning_tokens + second.reasoning_tokens
    billed = first.cost_reported + second.cost_reported
    latency = first.latency_s + second.latency_s

    if second.error is not None:
        outcome = Outcome.PROVIDER_UNAVAILABLE if second.unavailable else Outcome.PROVIDER_ERROR
        return (
            row(
                second,
                outcome,
                True,
                errors,
                0,
                [],
                tokens_in,
                tokens_out,
                tokens_think,
                billed,
                latency,
                first.finish_reason,
            ),
            None,
        )

    repaired, errors2, parseable2 = validate(second.content, document)
    if repaired is not None:
        outcome = Outcome.VALID_AFTER_REPAIR
    elif second.finish_reason == "length":
        # Checked before "unparseable": truncated JSON does not parse, but the
        # cause is the token budget, not the model's formatting.
        outcome = Outcome.LENGTH_TRUNCATED
    elif not parseable2:
        outcome = Outcome.UNPARSEABLE
    else:
        outcome = Outcome.INVALID_AFTER_REPAIR

    return (
        row(
            second,
            outcome,
            True,
            errors2,
            len(repaired.settings) if repaired else 0,
            [r.model_dump(mode="json") for r in repaired.settings] if repaired else [],
            tokens_in,
            tokens_out,
            tokens_think,
            billed,
            latency,
            first.finish_reason,
        ),
        repaired,
    )
