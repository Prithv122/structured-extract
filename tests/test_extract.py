"""The repair ladder, the outcome taxonomy, and the invariants that guard them.

No network: ``_post`` is replaced by a scripted fake, so every branch is
exercised offline and for free.
"""

from __future__ import annotations

import json

import pytest

from structured_extract import corpus as corpus_mod
from structured_extract import extract as E
from structured_extract import jsonl, paths
from structured_extract.arms import BY_KEY, Arm

DOCUMENT = """\
## Memory Limit

The `memory_limit` setting caps how much memory DuckDB may use for
intermediate results. It is a VARCHAR and applies to the whole instance.
"""

GOOD = json.dumps(
    {
        "settings": [
            {
                "name": "memory_limit",
                "input_type": "VARCHAR",
                "scope": "GLOBAL",
                "evidence": "caps how much memory DuckDB may use",
            }
        ]
    }
)

BACKTICKED = GOOD.replace('"memory_limit"', '"`memory_limit`"', 1)
UNGROUNDED = json.dumps(
    {
        "settings": [
            {
                "name": "memory_limit",
                "input_type": "VARCHAR",
                "scope": "GLOBAL",
                "evidence": "a sentence that appears nowhere in the document",
            }
        ]
    }
)
NOT_JSON = "Sure! Here is the extraction you asked for:"

ARM = BY_KEY["H3"]


def body(content: str, finish_reason: str = "stop", model: str = "openai/gpt-4.1-nano") -> dict:
    return {
        "model": model,
        "choices": [{"finish_reason": finish_reason, "message": {"content": content}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20},
    }


@pytest.fixture
def transport(monkeypatch):
    """Scripted ``_post``. ``calls`` records every payload that went out."""

    class Transport:
        def __init__(self):
            self.script: list[tuple] = []
            self.calls: list[dict] = []

        def returns(self, *results):
            self.script = list(results)
            return self

        def __call__(self, payload, api_key):
            self.calls.append(payload)
            if not self.script:
                raise AssertionError(f"unscripted call #{len(self.calls)}")
            return self.script.pop(0)

    fake = Transport()
    monkeypatch.setattr(E, "_post", fake)
    monkeypatch.setattr(E.time, "sleep", lambda _s: None)
    return fake


def run(cache, transport, document: str = DOCUMENT, arm: Arm = ARM):
    return E.extract_document(arm, "doc-1", document, cache_dir=cache, api_key="test-key")


# ------------------------------------------------------------- the happy path


def test_valid_first_pass_never_makes_a_second_call(tmp_path, transport):
    transport.returns((body(GOOD), None, False))
    row, extraction = run(tmp_path, transport)

    assert row.outcome == E.Outcome.VALID_FIRST_PASS
    assert row.repair_used is False
    assert len(transport.calls) == 1
    assert extraction is not None
    assert extraction.settings[0].name == "memory_limit"
    assert row.n_settings == 1
    assert row.cost_usd == pytest.approx((100 * 0.10 + 20 * 0.40) / 1e6)


def test_an_empty_extraction_is_a_valid_first_pass(tmp_path, transport):
    """Distractor documents must be able to succeed by returning nothing."""
    transport.returns((body(json.dumps({"settings": []})), None, False))
    row, extraction = run(tmp_path, transport)
    assert row.outcome == E.Outcome.VALID_FIRST_PASS
    assert row.n_settings == 0
    assert extraction.settings == []


# ----------------------------------------------------------------- the repair


def test_one_repair_fixes_a_schema_violation(tmp_path, transport):
    transport.returns((body(BACKTICKED), None, False), (body(GOOD), None, False))
    row, extraction = run(tmp_path, transport)

    assert row.outcome == E.Outcome.VALID_AFTER_REPAIR
    assert row.repair_used is True
    assert len(transport.calls) == 2
    assert extraction.settings[0].name == "memory_limit"
    # Both calls are billed, and the row carries the total.
    assert row.prompt_tokens == 200
    assert row.completion_tokens == 40


def test_one_repair_fixes_an_ungrounded_quote(tmp_path, transport):
    transport.returns((body(UNGROUNDED), None, False), (body(GOOD), None, False))
    row, _ = run(tmp_path, transport)
    assert row.outcome == E.Outcome.VALID_AFTER_REPAIR


def test_the_repair_is_bounded_at_exactly_one(tmp_path, transport):
    """Two bad answers end the ladder. There is no third call."""
    transport.returns((body(BACKTICKED), None, False), (body(BACKTICKED), None, False))
    row, extraction = run(tmp_path, transport)

    assert row.outcome == E.Outcome.INVALID_AFTER_REPAIR
    assert len(transport.calls) == 2
    assert extraction is None
    assert row.validation_errors, "the final errors must survive for the failure analysis"


def test_the_repair_prompt_carries_the_document_the_raw_output_and_the_errors(tmp_path, transport):
    transport.returns((body(BACKTICKED), None, False), (body(GOOD), None, False))
    run(tmp_path, transport)

    repair = transport.calls[1]["messages"]
    contents = [m["content"] for m in repair]
    joined = "\n".join(contents)
    assert DOCUMENT in contents, "the document must be in the repair prompt"
    assert BACKTICKED in joined, "the raw output must be in the repair prompt"
    assert "string_pattern_mismatch" in joined, "the validation errors must be in the repair prompt"


def test_the_repair_prompt_never_contains_the_oracle(tmp_path, transport):
    """The one invariant that would silently invalidate every published number.

    If the repair could see the answer key, the hallucination rate would measure
    the repair prompt. This walks the real 274-name oracle and asserts that no
    setting name reaches the model except the ones the document itself contains.

    It has already earned its place: the first draft of ``SYSTEM_PROMPT`` said
    "words like schema, user, password and threads appear constantly in ordinary
    prose", which is the exact contents of ``corpus.DISTRACTOR_NAMES``. That
    would have told every arm which words the benchmark planted as traps, and
    the 16 distractor documents measure precisely that false-positive case.
    """
    transport.returns((body(BACKTICKED), None, False), (body(GOOD), None, False))
    run(tmp_path, transport)

    prompt = "\n".join(m["content"] for m in transport.calls[1]["messages"]).lower()
    oracle_names = {row["name"] for row in jsonl.read_list(paths.SETTINGS_JSONL)}
    in_document = {name for name in oracle_names if name.lower() in DOCUMENT.lower()}

    # Two setting names cannot be kept out of any English instruction that
    # mentions a JSON schema, and the request envelope needs a "user" role.
    # Both are real setting names, which is the joke, and both are already
    # DISTRACTOR_NAMES -- so a document that merely contains them is meant to
    # be hard. Nothing else may appear, and this set may not grow beyond the
    # words the corpus already treats as ambiguous.
    INCIDENTAL = {"schema", "user"}
    assert INCIDENTAL <= corpus_mod.DISTRACTOR_NAMES

    leaked = sorted(
        name
        for name in oracle_names - in_document
        if name.lower() not in INCIDENTAL and name.lower() in prompt
    )
    assert not leaked, f"oracle names reached the model: {leaked}"

    # The incidental words must be prose, never a list of candidate names.
    for word in INCIDENTAL:
        assert f"{word}," not in prompt, f"{word!r} is being enumerated, not used incidentally"


# ------------------------------------------------------------------- outcomes


def test_output_that_is_not_json_after_the_repair_is_unparseable(tmp_path, transport):
    transport.returns((body(NOT_JSON), None, False), (body(NOT_JSON), None, False))
    row, _ = run(tmp_path, transport)
    assert row.outcome == E.Outcome.UNPARSEABLE
    assert row.validation_errors[0]["type"] == "not_json"


def test_truncation_outranks_unparseable_because_the_cause_is_the_budget(tmp_path, transport):
    """Truncated JSON does not parse, but 'ran out of tokens' is the real reason."""
    half = GOOD[: len(GOOD) // 2]
    transport.returns(
        (body(half, finish_reason="length"), None, False),
        (body(half, finish_reason="length"), None, False),
    )
    row, _ = run(tmp_path, transport)
    assert row.outcome == E.Outcome.LENGTH_TRUNCATED
    assert row.finish_reason == "length"
    assert row.first_finish_reason == "length"


def test_a_truncated_first_pass_can_still_be_repaired(tmp_path, transport):
    transport.returns(
        (body(GOOD[: len(GOOD) // 2], finish_reason="length"), None, False),
        (body(GOOD), None, False),
    )
    row, _ = run(tmp_path, transport)
    assert row.outcome == E.Outcome.VALID_AFTER_REPAIR
    assert row.first_finish_reason == "length"
    assert row.finish_reason == "stop"


def test_no_credit_is_provider_unavailable_and_is_neither_retried_nor_repaired(tmp_path, transport):
    transport.returns((None, "HTTP 402: insufficient credits", True))
    row, extraction = run(tmp_path, transport)

    assert row.outcome == E.Outcome.PROVIDER_UNAVAILABLE
    assert row.repair_used is False
    assert len(transport.calls) == 1, "402 must not be retried and must not burn the repair"
    assert extraction is None
    assert "402" in row.error


def test_an_unknown_model_id_is_provider_unavailable(tmp_path, transport):
    transport.returns((None, "HTTP 404: no endpoints found", True))
    row, _ = run(tmp_path, transport)
    assert row.outcome == E.Outcome.PROVIDER_UNAVAILABLE


def test_a_transport_failure_is_retried_and_does_not_consume_the_repair(tmp_path, transport):
    transport.returns(
        (None, "HTTP 502: bad gateway", False),
        (None, "HTTP 502: bad gateway", False),
        (body(GOOD), None, False),
    )
    row, _ = run(tmp_path, transport)

    assert row.outcome == E.Outcome.VALID_FIRST_PASS
    assert row.repair_used is False, "a 502 is not a bad answer; there was no answer"
    assert len(transport.calls) == 3


def test_transport_failures_that_never_recover_are_provider_error(tmp_path, transport):
    transport.returns(*[(None, "HTTP 500: upstream", False)] * E.MAX_TRANSPORT_RETRIES)
    row, _ = run(tmp_path, transport)
    assert row.outcome == E.Outcome.PROVIDER_ERROR
    assert len(transport.calls) == E.MAX_TRANSPORT_RETRIES


def test_an_error_body_with_a_200_status_is_still_an_error(tmp_path, transport):
    """OpenRouter returns some provider failures inside a 200 body."""
    transport.returns(({"error": {"code": 502, "message": "upstream timed out"}}, None, False))
    row, _ = run(tmp_path, transport)
    assert row.outcome == E.Outcome.PROVIDER_ERROR
    assert "upstream timed out" in row.error


# --------------------------------------------------------- routing and replay


def test_the_answering_model_is_recorded_separately_from_the_requested_one(tmp_path, transport):
    """Project 24's lesson: the row must be able to say a stranger did the work."""
    transport.returns((body(GOOD, model="openai/gpt-4.1-nano-2025-04-14"), None, False))
    row, _ = run(tmp_path, transport)
    assert row.requested_model == "openai/gpt-4.1-nano"
    assert row.answering_model == "openai/gpt-4.1-nano-2025-04-14"


def test_fallbacks_are_off_so_another_model_cannot_answer_silently(tmp_path, transport):
    transport.returns((body(GOOD), None, False))
    run(tmp_path, transport)
    assert transport.calls[0]["provider"]["allow_fallbacks"] is False


def test_only_the_knobs_an_arm_advertises_are_sent(tmp_path, transport):
    transport.returns((body(GOOD), None, False), (body(GOOD), None, False))

    run(tmp_path, transport, arm=BY_KEY["H3"])
    assert transport.calls[0]["temperature"] == 0
    assert transport.calls[0]["seed"] == 0

    run(tmp_path, transport, arm=BY_KEY["H1"])
    sonnet = transport.calls[1]
    assert "temperature" not in sonnet, "Sonnet 5 does not advertise temperature"
    assert "seed" not in sonnet, "Sonnet 5 does not advertise seed"


def test_reasoning_is_disabled_where_the_arm_supports_thinking(tmp_path, transport):
    transport.returns((body(GOOD), None, False))
    run(tmp_path, transport, arm=BY_KEY["H2"])
    assert transport.calls[0]["reasoning"] == {"enabled": False}


def test_a_second_identical_run_replays_from_cache_and_issues_no_http(tmp_path, transport):
    transport.returns((body(GOOD), None, False))
    first, _ = run(tmp_path, transport)
    assert len(transport.calls) == 1

    second, extraction = E.extract_document(
        ARM, "doc-1", DOCUMENT, cache_dir=tmp_path, api_key="", allow_live=False
    )
    assert len(transport.calls) == 1, "the replay must not touch the network"
    assert second.outcome == first.outcome
    assert second.n_settings == first.n_settings
    assert extraction is not None


def test_replay_of_an_uncached_request_fails_loudly_rather_than_silently(tmp_path):
    with pytest.raises(E.MissingAPIKey, match="no cached response"):
        E.extract_document(ARM, "doc-1", DOCUMENT, cache_dir=tmp_path, api_key="", allow_live=False)


def test_a_changed_prompt_is_a_different_cache_entry(tmp_path, transport):
    """Otherwise a prompt edit would silently republish the old run's numbers."""
    transport.returns((body(GOOD), None, False), (body(GOOD), None, False))
    run(tmp_path, transport, document=DOCUMENT)
    run(tmp_path, transport, document=DOCUMENT + "\nAn extra sentence.\n")
    assert len(transport.calls) == 2
    assert len(list((tmp_path / ARM.key).glob("*.json"))) == 2
