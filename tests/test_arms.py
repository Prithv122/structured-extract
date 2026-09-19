"""The guard that makes project 24's silent dead arm impossible to ship again.

``check_arm`` is pure: it takes a catalogue dict, so every branch is tested
offline against a synthetic catalogue. ``test_arms_live.py`` does the one real
network check, and it is skipped when offline.
"""

from __future__ import annotations

import pytest

from structured_extract import arms as A
from structured_extract import jsonl, paths
from structured_extract.cli import QUOTAS, _pilot_documents


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
