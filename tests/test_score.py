"""Scoring: the four outcomes, alias resolution, and the COPY false positive.

Every test here is offline and free. The fixtures are hand-built rows rather
than replayed responses, so a failure points at the scorer and not at a model.
"""

from __future__ import annotations

import pytest

from structured_extract import jsonl, paths
from structured_extract import score as SC
from structured_extract.extract import Outcome

DOCUMENT = """\
## Memory Limit

The `memory_limit` setting caps how much memory DuckDB may use for
intermediate results. It is a VARCHAR and applies to the whole instance.
"""

#: A trimmed stand-in for narrative-0001: a table of `COPY ... TO` options,
#: which look exactly like configuration settings and are not.
COPY_DOCUMENT = """\
### `COPY ... TO` Options

| Name | Description | Type | Default |
|------|-------------|------|---------|
| `FORMAT` | Specifies the copy function to use. | `VARCHAR` | auto |
| `USE_TMP_FILE` | Whether or not to write to a temporary file first. | `BOOL` | auto |
| `PRESERVE_ORDER` | Whether or not to preserve order. Defaults to the value of
the `preserve_insertion_order` configuration option. | `BOOL` | (*) |
"""


@pytest.fixture(scope="module")
def oracle() -> SC.Oracle:
    return SC.load_oracle()


def record(name: str, input_type="VARCHAR", scope="GLOBAL", evidence=None) -> dict:
    return {
        "name": name,
        "input_type": input_type,
        "scope": scope,
        "evidence": evidence or "caps how much memory DuckDB may use",
    }


def result_row(doc_id="narrative-0001", arm="H3", prompt="v2-specified", **kw) -> dict:
    row = {
        "doc_id": doc_id,
        "arm": arm,
        "prompt": prompt,
        "outcome": Outcome.VALID_FIRST_PASS.value,
        "settings": [],
        "cost_reported": 0.001,
    }
    row.update(kw)
    return row


def score_one(row: dict, doc_id: str, text: str, stratum: str, mentioned: list[str], oracle):
    row = {**row, "doc_id": doc_id}
    corpus = {doc_id: {"stratum": stratum, "mentioned_names": mentioned}}
    return SC.score_row(row, corpus, {doc_id: text}, oracle)


# ------------------------------------------------------ 1. alias resolution


def test_a_real_setting_resolves_to_itself(oracle):
    assert oracle.resolve("memory_limit") is not None
    assert oracle.resolve("access_mode") == "access_mode"


def test_an_alias_resolves_to_its_canonical_name(oracle):
    """`memory_limit` and `max_memory` are one setting; scoring must agree."""
    assert oracle.resolve("memory_limit") == oracle.resolve("max_memory")
    assert oracle.resolve("null_order") == oracle.resolve("default_null_order")
    assert oracle.resolve("wal_autocheckpoint") == oracle.resolve("checkpoint_threshold")


def test_matching_is_case_insensitive_because_duckdb_is(oracle):
    """Only `Calendar` and `TimeZone` are not lowercase; a case difference is a
    spelling complaint, not a hallucination."""
    assert oracle.resolve("timezone") == oracle.resolve("TimeZone") == "TimeZone"
    assert oracle.resolve("CALENDAR") == "Calendar"
    assert oracle.resolve("  Access_Mode  ") == "access_mode"


def test_an_invented_name_resolves_to_nothing(oracle):
    assert oracle.resolve("frobnicate_cache") is None
    assert oracle.resolve("FORMAT") is None


# ------------------------------------------- 2, 3. type and scope accuracy


def test_a_correct_record_scores_correct_on_every_field(oracle):
    canonical = oracle.resolve("memory_limit")
    truth = oracle.settings[canonical]
    scored = SC.score_record(
        record("memory_limit", truth["input_type"], truth["scope"]), DOCUMENT, oracle
    )
    assert scored.hallucinated is False
    assert scored.canonical == canonical
    assert scored.input_type_correct is True
    assert scored.scope_correct is True
    assert scored.evidence_grounded is True


def test_a_wrong_type_is_caught_without_affecting_scope(oracle):
    """H1 answered DOUBLE for a boolean whose evidence said 'to `true`'."""
    scored = SC.score_record(record("access_mode", "DOUBLE", "GLOBAL"), DOCUMENT, oracle)
    assert scored.hallucinated is False
    assert scored.input_type_correct is False
    assert scored.scope_correct is True


def test_a_wrong_scope_is_caught_without_affecting_type(oracle):
    """H2 answered LOCAL for GLOBAL settings on three of four records."""
    truth = oracle.settings["access_mode"]
    scored = SC.score_record(record("access_mode", truth["input_type"], "LOCAL"), DOCUMENT, oracle)
    assert scored.input_type_correct is True
    assert scored.scope_correct is False


def test_type_and_scope_are_unscorable_for_a_hallucination(oracle):
    """There is no truth to compare against, and None is not False."""
    scored = SC.score_record(record("frobnicate_cache"), DOCUMENT, oracle)
    assert scored.hallucinated is True
    assert scored.input_type_correct is None
    assert scored.scope_correct is None


# --------------------------------------- 5, 6. hallucination and faithfulness


def test_the_copy_to_false_positive_scores_as_fourteen_hallucinations(oracle):
    """The case the whole benchmark exists for.

    Every record is schema-valid, every quote is verbatim, and not one of the
    names is a DuckDB setting. Schema validity and grounding both pass; only
    the oracle says no.
    """
    names = ["FORMAT", "USE_TMP_FILE", "PRESERVE_ORDER"]
    quotes = {
        "FORMAT": "Specifies the copy function to use.",
        "USE_TMP_FILE": "Whether or not to write to a temporary file first.",
        "PRESERVE_ORDER": "Whether or not to preserve order.",
    }
    row = result_row(settings=[record(n, evidence=quotes[n]) for n in names])
    scored = score_one(
        row, "narrative-0001", COPY_DOCUMENT, "narrative", ["preserve_insertion_order"], oracle
    )

    assert scored.status == SC.Status.ANSWERED
    assert scored.n_returned == 3
    assert scored.n_hallucinated == 3, "COPY options are not configuration settings"
    assert scored.n_real == 0
    assert all(r.evidence_grounded for r in scored.records), "grounded, and still wrong"

    (summary,) = SC.summarise([scored])
    assert summary.hallucination_rate == 1.0
    assert summary.grounding_rate == 1.0
    # The real setting the document only cross-references was not returned.
    assert summary.mentioned_expected == 1
    assert summary.mentioned_found == 0


def test_an_ungrounded_quote_is_flagged_even_on_a_real_setting(oracle):
    scored = SC.score_record(
        record("memory_limit", evidence="a sentence the document never contains"), DOCUMENT, oracle
    )
    assert scored.hallucinated is False
    assert scored.evidence_grounded is False


def test_grounding_tolerates_a_rewrapped_quote(oracle):
    quote = "caps how much memory DuckDB may use for intermediate results."
    assert "\n" in DOCUMENT[DOCUMENT.index("caps") : DOCUMENT.index("results.")]
    assert SC.score_record(
        record("memory_limit", evidence=quote), DOCUMENT, oracle
    ).evidence_grounded


# ------------------------------- 8, 9. empty answers vs failures vs no answer


@pytest.mark.parametrize(
    "outcome",
    [Outcome.PROVIDER_ERROR.value, Outcome.PROVIDER_UNAVAILABLE.value],
)
def test_a_provider_failure_is_no_answer_and_leaves_every_denominator(outcome, oracle):
    row = result_row(outcome=outcome, settings=[])
    scored = score_one(row, "d", DOCUMENT, "narrative", ["memory_limit"], oracle)
    assert scored.status == SC.Status.NO_ANSWER
    assert scored.empty_was_correct is None, "a dead provider is not a wrong answer"

    (summary,) = SC.summarise([scored])
    assert summary.no_answer == 1
    assert summary.answered_empty == 0
    assert summary.availability == 0.0


@pytest.mark.parametrize(
    "outcome",
    [
        Outcome.INVALID_AFTER_REPAIR.value,
        Outcome.UNPARSEABLE.value,
        Outcome.LENGTH_TRUNCATED.value,
    ],
)
def test_a_model_failure_is_its_own_category_not_an_empty_answer(outcome, oracle):
    row = result_row(outcome=outcome, settings=[])
    scored = score_one(row, "d", DOCUMENT, "narrative", ["memory_limit"], oracle)
    assert scored.status == SC.Status.FAILED_EXTRACTION
    assert scored.empty_was_correct is None

    (summary,) = SC.summarise([scored])
    assert summary.failed_extraction == 1
    assert summary.no_answer == 0, "the model's fault, not the provider's"


def test_an_empty_answer_on_a_distractor_document_is_correct(oracle):
    """The 16 distractor documents exist to make this case measurable."""
    row = result_row(settings=[])
    scored = score_one(row, "d", DOCUMENT, "narrative", ["schema", "user"], oracle)
    assert scored.status == SC.Status.ANSWERED_EMPTY
    assert scored.mentioned == [], "distractor names are not things to find"
    assert scored.empty_was_correct is True

    (summary,) = SC.summarise([scored])
    assert summary.empty_correct == 1
    assert summary.empty_wrong == 0
    assert summary.availability == 1.0


def test_an_empty_answer_on_a_document_with_a_real_mention_is_a_miss(oracle):
    row = result_row(settings=[])
    scored = score_one(row, "d", DOCUMENT, "narrative", ["memory_limit"], oracle)
    assert scored.empty_was_correct is False
    assert SC.summarise([scored])[0].empty_wrong == 1


def test_the_four_statuses_are_mutually_exclusive(oracle):
    """The distinction the pilot proved was missing from n_settings alone."""
    cases = [
        (result_row(outcome=Outcome.PROVIDER_ERROR.value), SC.Status.NO_ANSWER),
        (result_row(outcome=Outcome.UNPARSEABLE.value), SC.Status.FAILED_EXTRACTION),
        (result_row(settings=[]), SC.Status.ANSWERED_EMPTY),
        (result_row(settings=[record("memory_limit")]), SC.Status.ANSWERED),
    ]
    got = [score_one(r, "d", DOCUMENT, "narrative", [], oracle).status for r, _ in cases]
    assert got == [want.value for _, want in cases]
    assert len(set(got)) == 4


# --------------------------------------------- reference stratum: real recall


def test_a_reference_document_yields_exact_ground_truth():
    text = (
        "## Global configuration options\n\n"
        "| Name | Description | Type | Default |\n"
        "|--|--|--|--|\n"
        "| `access_mode` | Access mode of the database | `VARCHAR` | `automatic` |"
    )
    assert SC.reference_target(text) == "access_mode"


def test_the_table_separator_is_not_mistaken_for_a_setting():
    text = "## Options\n\n| Name | Type |\n|------|------|\n| `threads` | `UBIGINT` |"
    assert SC.reference_target(text) == "threads"


def test_finding_the_reference_target_counts_as_real_recall(oracle):
    text = (
        "## Global configuration options\n\n"
        "| Name | Description | Type | Default |\n"
        "|--|--|--|--|\n"
        "| `access_mode` | Access mode of the database | `VARCHAR` | `automatic` |"
    )
    row = result_row(settings=[record("access_mode", evidence="Access mode of the database")])
    scored = score_one(row, "reference-0001", text, "reference", ["access_mode"], oracle)
    assert scored.expected == ["access_mode"]

    (summary,) = SC.summarise([scored])
    assert summary.reference_expected == 1
    assert summary.reference_found == 1
    assert summary.reference_recall == 1.0


def test_an_empty_answer_on_a_reference_row_is_always_wrong(oracle):
    """Every reference document documents exactly one setting by construction."""
    text = "## Global configuration options\n\n| Name |\n|--|\n| `access_mode` |"
    scored = score_one(result_row(settings=[]), "r", text, "reference", ["access_mode"], oracle)
    assert scored.empty_was_correct is False


def test_an_alias_answer_still_counts_as_finding_the_reference_target(oracle):
    """Answering `memory_limit` where the table says `max_memory` is correct."""
    text = (
        "## Global configuration options\n\n"
        "| Name | Description |\n|--|--|\n"
        "| `max_memory` | The maximum memory of the system |"
    )
    row = result_row(settings=[record("memory_limit", evidence="The maximum memory of the system")])
    scored = score_one(row, "r", text, "reference", ["max_memory"], oracle)
    assert scored.expected == [scored.records[0].canonical] == ["max_memory"]
    assert scored.records[0].name == "memory_limit", "the model's spelling is preserved"
    assert SC.summarise([scored])[0].reference_found == 1


# ------------------------------------- 7. machine-dependent default handling


def test_the_machine_dependent_settings_are_the_ones_the_docs_describe_as_rules(oracle):
    """`threads` is '# CPU cores', `max_memory` is '80% of RAM'. No extracted
    literal can be scored against a rule, so these are excluded from default
    accuracy rather than counted wrong."""
    for name in SC.MACHINE_DEPENDENT:
        canonical = oracle.resolve(name)
        assert canonical is not None, f"{name} is not a real setting"
        assert oracle.is_machine_dependent(canonical) or oracle.is_machine_dependent(name)


def test_settings_with_a_fixed_default_are_not_excluded(oracle):
    """`custom_profiling_settings` has a 1.3 kB JSON default that a regex over
    the default column mistakes for machine-dependent. It is perfectly fixed."""
    assert not oracle.is_machine_dependent("custom_profiling_settings")
    assert not oracle.is_machine_dependent("access_mode")


def test_every_machine_dependent_default_really_is_a_rule_in_the_docs(oracle):
    """Guards the curated list against the reference table changing under it."""
    rules = 0
    for name in SC.MACHINE_DEPENDENT:
        row = oracle.documented.get(oracle.resolve(name) or "")
        if row is None:
            continue
        rules += 1
        assert not row["default_value"].strip("`").isidentifier() or any(
            word in row["default_value"].lower() for word in ("system", "cpu", "ram", "disk")
        ), f"{name} default {row['default_value']!r} looks like a literal, not a rule"
    assert rules >= 4


# ------------------------------------------ 10. per-arm and per-prompt scoring


def test_summaries_are_one_row_per_arm_and_prompt(oracle):
    rows = [
        result_row(arm=a, prompt=p, settings=[record("memory_limit")])
        for a in ("H1", "H2")
        for p in ("v1-unspecified", "v2-specified")
    ]
    scored = [score_one(r, "d", DOCUMENT, "narrative", [], oracle) for r in rows]
    summaries = SC.summarise(scored)
    assert len(summaries) == 4
    assert {(s.arm, s.prompt) for s in summaries} == {
        (a, p) for a in ("H1", "H2") for p in ("v1-unspecified", "v2-specified")
    }


def test_an_arms_failures_do_not_leak_into_another_arms_rates(oracle):
    good = result_row(arm="H1", settings=[record("memory_limit")])
    bad = result_row(arm="H2", settings=[record("frobnicate_cache")])
    scored = [score_one(r, "d", DOCUMENT, "narrative", [], oracle) for r in (good, bad)]
    by_arm = {s.arm: s for s in SC.summarise(scored)}
    assert by_arm["H1"].hallucination_rate == 0.0
    assert by_arm["H2"].hallucination_rate == 1.0


def test_cost_carried_into_the_summary_is_the_billed_one(oracle):
    row = result_row(cost_reported=0.0123, settings=[])
    (summary,) = SC.summarise([score_one(row, "d", DOCUMENT, "narrative", [], oracle)])
    assert summary.cost_reported == pytest.approx(0.0123)


def test_rates_are_zero_not_an_error_when_a_denominator_is_empty(oracle):
    """An arm that never answered must not crash the report."""
    row = result_row(outcome=Outcome.PROVIDER_ERROR.value)
    (summary,) = SC.summarise([score_one(row, "d", DOCUMENT, "narrative", [], oracle)])
    for rate in (
        summary.hallucination_rate,
        summary.type_accuracy,
        summary.scope_accuracy,
        summary.grounding_rate,
        summary.reference_recall,
        summary.recall_vs_mentioned,
        summary.availability,
    ):
        assert rate == 0.0


# ------------------------------------------- 12. the committed pilot, offline


@pytest.mark.skipif(
    not paths.RESULTS_JSONL.with_name("pilot.jsonl").exists(),
    reason="no pilot results committed yet",
)
def test_the_committed_pilot_scores_without_network_or_key():
    results = jsonl.read_list(paths.RESULTS_JSONL.with_name("pilot.jsonl"))
    scores = SC.score_all(results)
    assert len(scores) == len(results)

    summaries = SC.summarise(scores)
    assert summaries, "the pilot produced no scoreable cells"
    for s in summaries:
        assert 0.0 <= s.hallucination_rate <= 1.0
        assert 0.0 <= s.grounding_rate <= 1.0
        assert s.records_real + s.records_hallucinated == s.records_returned
        assert s.no_answer + s.failed_extraction + s.answered_empty + s.answered == s.n_documents, (
            "every document must land in exactly one status"
        )
