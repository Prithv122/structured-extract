"""What the extraction schema accepts, rejects, and deliberately does not check."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from structured_extract import schema as S

DOCUMENT = """\
## Memory Limit

The `memory_limit` setting caps how much memory DuckDB may use for
intermediate results. It is a `VARCHAR` and applies to the whole
instance, so setting it affects every connection.
"""


def valid_record(**overrides) -> dict:
    record = {
        "name": "memory_limit",
        "input_type": "VARCHAR",
        "scope": "GLOBAL",
        "evidence": "caps how much memory DuckDB may use",
    }
    record.update(overrides)
    return record


def parse(payload: dict, document: str | None = DOCUMENT) -> S.DocumentExtraction:
    context = None if document is None else {S.DOCUMENT_KEY: document}
    return S.DocumentExtraction.model_validate(payload, context=context)


# --------------------------------------------------------------------- accepts


def test_a_well_formed_extraction_validates():
    parsed = parse({"settings": [valid_record()]})
    assert parsed.settings[0].name == "memory_limit"
    assert parsed.settings[0].input_type is S.SettingType.VARCHAR


def test_no_settings_documented_is_an_empty_list_not_an_error():
    """The distractor strata depend on this: 'nothing here' must be expressible."""
    assert parse({"settings": []}).settings == []


def test_a_quote_rewrapped_across_a_line_break_still_counts_as_verbatim():
    """The document has a hard break inside this sentence; the model joined it."""
    quote = "caps how much memory DuckDB may use for intermediate results."
    assert "\n" in DOCUMENT[DOCUMENT.index("caps") : DOCUMENT.index("results.")]
    parse({"settings": [valid_record(evidence=quote)]})


# --------------------------------------------------------------------- rejects


def test_backticked_name_is_a_failure_not_something_to_normalise():
    """Silently stripping backticks would inflate valid_first_pass for every arm."""
    with pytest.raises(ValidationError) as exc:
        parse({"settings": [valid_record(name="`memory_limit`")]})
    assert exc.value.error_count() == 1
    assert exc.value.errors()[0]["type"] == "string_pattern_mismatch"


@pytest.mark.parametrize("name", ["memory limit", "duckdb.memory_limit", "1memory", "", "SET x"])
def test_names_that_are_not_sql_identifiers_are_rejected(name):
    with pytest.raises(ValidationError):
        parse({"settings": [valid_record(name=name)]})


@pytest.mark.parametrize("value", ["string", "int", "varchar", "TEXT", "BOOL"])
def test_types_outside_the_binarys_vocabulary_are_rejected(value):
    with pytest.raises(ValidationError):
        parse({"settings": [valid_record(input_type=value)]})


@pytest.mark.parametrize("value", ["SESSION", "global", "CONNECTION"])
def test_scopes_outside_the_binarys_vocabulary_are_rejected(value):
    with pytest.raises(ValidationError):
        parse({"settings": [valid_record(scope=value)]})


def test_paraphrased_evidence_is_rejected():
    """The grounding check: plausible, on-topic, and not in the document."""
    with pytest.raises(ValidationError) as exc:
        parse({"settings": [valid_record(evidence="limits the amount of RAM DuckDB consumes")]})
    assert "verbatim" in str(exc.value)


def test_evidence_must_be_more_than_a_word():
    with pytest.raises(ValidationError) as exc:
        parse({"settings": [valid_record(evidence="memory")]})
    assert "at least" in str(exc.value)


def test_the_same_setting_twice_in_one_document_is_rejected():
    with pytest.raises(ValidationError) as exc:
        parse({"settings": [valid_record(), valid_record(evidence="applies to the whole")]})
    assert "more than once" in str(exc.value)


def test_extra_fields_are_rejected_at_both_levels():
    with pytest.raises(ValidationError):
        parse({"settings": [valid_record(confidence=0.9)]})
    with pytest.raises(ValidationError):
        parse({"settings": [], "notes": "none"})


# ------------------------------------------------- what it deliberately allows


def test_a_hallucinated_name_validates_because_the_oracle_is_not_in_the_schema():
    """The primary measurement would vanish if this raised.

    ``frobnicate_cache`` is not a DuckDB setting. The schema must accept it --
    scoring it wrong is the oracle's job, after the fact. Pasting the 274 known
    names into the schema would make hallucination impossible by construction
    and there would be nothing left to measure.
    """
    quote = "caps how much memory DuckDB may use"
    parsed = parse({"settings": [valid_record(name="frobnicate_cache", evidence=quote)]})
    assert parsed.settings[0].name == "frobnicate_cache"


def test_grounding_is_skipped_when_no_document_is_supplied():
    """Shape and grounding are separable on purpose; B0 validates shape only."""
    parse({"settings": [valid_record(evidence="text from nowhere at all")]}, document=None)


# ------------------------------------------------------------- the wire schema


def test_wire_schema_has_no_refs_left_to_confuse_a_provider():
    raw = json.dumps(S.json_schema())
    assert "$ref" not in raw
    assert "$defs" not in raw


def test_every_object_in_the_wire_schema_is_strict():
    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                walk(value)

    walk(S.json_schema())


def test_wire_schema_enums_match_the_python_enums():
    """One source of truth: the provider and the validator must agree."""
    item = S.json_schema()["properties"]["settings"]["items"]
    assert item["properties"]["input_type"]["enum"] == [t.value for t in S.SettingType]
    assert item["properties"]["scope"]["enum"] == [s.value for s in S.Scope]


def test_response_format_is_the_shape_openrouter_expects():
    block = S.response_format()
    assert block["type"] == "json_schema"
    assert block["json_schema"]["strict"] is True
    assert block["json_schema"]["schema"] == S.json_schema()
