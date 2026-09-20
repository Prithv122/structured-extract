"""The guard that makes project 24's silent dead arm impossible to ship again.

``check_arm`` is pure: it takes a catalogue dict, so every branch is tested
offline against a synthetic catalogue. ``test_arms_live.py`` does the one real
network check, and it is skipped when offline.
"""

from __future__ import annotations

import pytest

from structured_extract import arms as A
from structured_extract import jsonl, paths
from structured_extract.cli import QUOTAS, _group_errors, _pilot_documents
from structured_extract.extract import ExtractionRow


def catalogue_entry(arm: A.Arm, **overrides) -> dict:
    entry = {
        "id": arm.model_id,
        "supported_parameters": [
            "response_format",
            "structured_outputs",
            *(["temperature"] if arm.supports_temperature else []),
            *(["seed"] if arm.supports_seed else []),
        ],
        "pricing": {
            "prompt": str(arm.price_in / 1e6),
            "completion": str(arm.price_out / 1e6),
        },
        "context_length": 128_000,
        "top_provider": {"max_completion_tokens": 32_768},
    }
    entry.update(overrides)
    return entry


def catalogue(*arms: A.Arm) -> dict[str, dict]:
    return {arm.model_id: catalogue_entry(arm) for arm in arms}


ARM = A.BY_KEY["H3"]


# ---------------------------------------------------------------- the registry


def test_every_arm_key_and_model_id_is_unique():
    assert len({a.key for a in A.HOSTED}) == len(A.HOSTED)
    assert len({a.model_id for a in A.HOSTED}) == len(A.HOSTED)


def test_no_arm_is_a_free_or_batch_variant():
    """``:free`` is the 50/day account-wide cap that killed project 24's grid.

    ``:batch`` is cheaper but asynchronous, so it cannot measure latency.
    """
    for arm in A.HOSTED:
        assert ":free" not in arm.model_id
        assert ":batch" not in arm.model_id


def test_every_arm_explains_why_it_is_in_the_grid():
    for arm in A.HOSTED:
        assert len(arm.rationale) > 40, f"{arm.key} has no rationale"


def test_cost_is_computed_from_reported_tokens_and_pinned_prices():
    assert ARM.cost(1_000_000, 0) == pytest.approx(ARM.price_in)
    assert ARM.cost(0, 1_000_000) == pytest.approx(ARM.price_out)
    assert ARM.cost(0, 0) == 0.0


# ------------------------------------------------------------------- the check


def test_a_pinned_arm_that_matches_the_catalogue_passes():
    check = A.check_arm(ARM, catalogue(ARM))
    assert check.ok
    assert check.found
    assert check.structured_outputs


def test_a_missing_model_id_fails_loudly():
    """The project 24 failure, reproduced: a typo'd suffix and nothing says so."""
    typo = A.Arm(**{**ARM.__dict__, "model_id": "openai/gpt-4.1-nano-a55b"})
    check = A.check_arm(typo, catalogue(ARM))
    assert not check.ok
    assert not check.found
    assert "does not resolve" in check.problems[0]
    assert "ids from that provider exist" in check.problems[0]


def test_losing_structured_output_support_fails():
    live = catalogue(ARM)
    live[ARM.model_id]["supported_parameters"] = ["response_format", "temperature", "seed"]
    check = A.check_arm(ARM, live)
    assert not check.ok
    assert any("structured_outputs" in p for p in check.problems)


def test_a_price_rise_fails_so_published_cost_cannot_drift_silently():
    live = catalogue(ARM)
    live[ARM.model_id]["pricing"]["prompt"] = str(ARM.price_in * 2 / 1e6)
    check = A.check_arm(ARM, live)
    assert not check.ok
    assert any("input price" in p for p in check.problems)


def test_a_price_change_below_the_tolerance_is_ignored():
    """Providers publish more decimal places than they advertise."""
    live = catalogue(ARM)
    live[ARM.model_id]["pricing"]["prompt"] = "0.00000009999999999"
    assert A.check_arm(ARM, live).ok


def test_gaining_or_losing_a_determinism_knob_fails():
    live = catalogue(ARM)
    live[ARM.model_id]["supported_parameters"].remove("temperature")
    check = A.check_arm(ARM, live)
    assert not check.ok
    assert any("temperature support" in p for p in check.problems)


def test_verify_checks_every_arm():
    checks = A.verify(catalogue=catalogue(*A.HOSTED))
    assert len(checks) == len(A.HOSTED)
    assert all(c.ok for c in checks)


# -------------------------------------------------------------------- the pilot


def test_the_pilot_covers_every_bucket_before_it_repeats_any():
    """A pilot that misses the distractors cannot show the outcomes are distinct."""
    rows = jsonl.read_list(paths.CORPUS_JSONL)
    pilot = _pilot_documents(rows, 8)

    assert len(pilot) == 8
    assert len({d["doc_id"] for d in pilot}) == 8

    def bucket(row: dict) -> str:
        if row["stratum"] == "reference":
            return "reference"
        return f"{row['stratum']}-{'signal' if row['has_signal'] else 'distractor'}"

    assert {bucket(d) for d in pilot} == set(QUOTAS)


def test_the_pilot_is_deterministic():
    rows = jsonl.read_list(paths.CORPUS_JSONL)
    assert [d["doc_id"] for d in _pilot_documents(rows, 8)] == [
        d["doc_id"] for d in _pilot_documents(rows, 8)
    ]


def test_the_pilot_cannot_ask_for_more_documents_than_exist():
    rows = jsonl.read_list(paths.CORPUS_JSONL)
    assert len(_pilot_documents(rows, 10_000)) == len(rows)


# ------------------------------------------------------------- error reporting


REAL_402 = (
    'HTTP 402: {"error":{"message":"Insufficient credits. This account never '
    "purchased credits. Make sure your key is on the correct account or org, and "
    'if so, purchase more at https://openrouter.ai/settings/credits","code":402,'
    '"metadata":{"limit_source":"openrouter_credits"}}}'
)


def row(arm: str, error: str | None):
    return ExtractionRow(
        doc_id="d",
        arm=arm,
        prompt="v2-specified",
        requested_model="m",
        answering_model="",
        outcome="provider_unavailable",
        repair_used=False,
        finish_reason="",
        first_finish_reason="",
        prompt_tokens=0,
        completion_tokens=0,
        reasoning_tokens=0,
        latency_s=0.0,
        cost_usd=0.0,
        n_settings=0,
        error=error,
        validation_errors=[],
    )


def test_identical_provider_errors_collapse_to_one_line():
    """The first live pilot printed 40 rows and not one reason. 40 copies of one
    error is not a report."""
    grouped = _group_errors([row(a, REAL_402) for a in ["H1", "H2", "H3", "H4", "H5"]])
    assert len(grouped) == 1
    assert sum(len(v) for v in grouped.values()) == 5


def test_the_providers_own_wording_survives_the_json_envelope():
    """OpenRouter's 402 body names the remedy and the URL -- reproduce it, do not
    replace it with a guess at what it meant."""
    (message,) = _group_errors([row("H1", REAL_402)])
    assert message.startswith("HTTP 402: ")
    assert "This account never purchased credits" in message
    assert "openrouter.ai/settings/credits" in message
    assert '{"error"' not in message, "the JSON envelope should be unwrapped"


def test_an_error_that_is_not_json_is_passed_through_unchanged():
    (message,) = _group_errors([row("H1", "TimeoutError: timed out")])
    assert message == "TimeoutError: timed out"


def test_different_errors_stay_separate():
    grouped = _group_errors([row("H1", REAL_402), row("H2", "HTTP 500: upstream")])
    assert len(grouped) == 2
