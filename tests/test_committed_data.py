"""Invariants of the committed oracle and corpus.

These run offline: no network, no DuckDB extension downloads, no API key. If one
of them fails on a clean clone, the published numbers rest on a file that is not
what the README says it is.
"""

from __future__ import annotations

import json
from collections import Counter

import duckdb
import pytest

from structured_extract import corpus as corpus_mod
from structured_extract import jsonl, paths
from structured_extract.cli import MAX_SECTION_CHARS, QUOTAS
from structured_extract.oracle import CORE, EXTENSIONS

EXPECTED_DUCKDB_VERSION = "v1.5.5"
EXPECTED_SETTINGS_ROWS = 280
EXPECTED_DISTINCT_SETTINGS = 274
EXPECTED_DOCS_ROWS = 169
EXPECTED_CORPUS_DOCS = 120


@pytest.fixture(scope="module")
def settings() -> list[dict]:
    return jsonl.read_list(paths.SETTINGS_JSONL)


@pytest.fixture(scope="module")
def docs() -> list[dict]:
    return jsonl.read_list(paths.DOCS_REFERENCE_JSONL)


@pytest.fixture(scope="module")
def documents() -> list[dict]:
    return jsonl.read_list(paths.CORPUS_JSONL)


@pytest.fixture(scope="module")
def alias_to_canonical(settings) -> dict[str, str]:
    return {a: s["name"] for s in settings for a in s["aliases"]}


# ------------------------------------------------------------------ the oracle


def test_settings_row_count(settings):
    assert len(settings) == EXPECTED_SETTINGS_ROWS


def test_setting_names_are_unique(settings):
    assert len({s["name"] for s in settings}) == len(settings)


def test_one_duckdb_version_throughout(settings):
    assert {s["duckdb_version"] for s in settings} == {EXPECTED_DUCKDB_VERSION}


def test_installed_duckdb_matches_the_pin():
    """A duckdb bump silently invalidates the oracle; fail here instead."""
    assert duckdb.connect().execute("select version()").fetchone()[0] == EXPECTED_DUCKDB_VERSION


def test_no_machine_dependent_value_column(settings):
    """``value`` is what the build machine was running -- it must not be ground truth."""
    assert all("value" not in s for s in settings)


def test_extension_attribution_is_complete(settings):
    counts = Counter(s["extension"] for s in settings)
    assert set(counts) <= {CORE, *EXTENSIONS}
    assert counts[CORE] == 160
    assert sum(counts[e] for e in EXTENSIONS) == EXPECTED_SETTINGS_ROWS - 160


def test_core_settings_match_a_plain_duckdb(settings):
    """Offline cross-check: no extensions loaded, so CI needs no downloads."""
    live = {
        name: (input_type, scope)
        for name, input_type, scope in duckdb.connect()
        .execute("select name, input_type, scope from duckdb_settings()")
        .fetchall()
    }
    committed = {
        s["name"]: (s["input_type"], s["scope"]) for s in settings if s["extension"] == CORE
    }
    assert committed == live


def test_aliases_resolve_to_exactly_one_setting(settings, alias_to_canonical):
    pairs = [(a, s["name"]) for s in settings for a in s["aliases"]]
    assert len(pairs) == len({a for a, _ in pairs})


def test_every_alias_is_also_a_row_of_its_own(settings, alias_to_canonical):
    """``duckdb_settings()`` emits both spellings; 280 rows are 274 settings."""
    names = {s["name"] for s in settings}
    assert set(alias_to_canonical) <= names
    assert len(names - set(alias_to_canonical)) == EXPECTED_DISTINCT_SETTINGS


def test_observed_values_are_stamped_with_a_host(settings):
    observed = jsonl.read_list(paths.OBSERVED_VALUES_JSONL)
    assert len(observed) == len(settings)
    assert all(row["host_platform"] for row in observed)


# ------------------------------------------------- the docs reference table


def test_docs_reference_row_count(docs):
    assert len(docs) == EXPECTED_DOCS_ROWS


def test_docs_reference_labels_are_unique(docs):
    labels = [label for d in docs for label in [d["name"], *d["aliases"]]]
    assert len(labels) == len(set(labels))


def test_docs_never_name_a_setting_the_binary_rejects(docs, settings, alias_to_canonical):
    accepted = {s["name"] for s in settings} | set(alias_to_canonical)
    labels = {label for d in docs for label in [d["name"], *d["aliases"]]}
    assert labels - accepted == set()


def test_docs_never_contradict_the_binary_on_type_or_scope(docs, settings, alias_to_canonical):
    by_name = {s["name"]: s for s in settings}
    for d in docs:
        binary = by_name[alias_to_canonical.get(d["name"], d["name"])]
        assert (d["type"], d["scope"]) == (binary["input_type"], binary["scope"]), d["name"]


def test_empty_default_cell_is_distinguished_from_null(docs):
    by_name = {d["name"]: d for d in docs}
    assert by_name["search_path"]["default_is_empty_cell"] is True
    assert by_name["enable_profiling"]["default_is_empty_cell"] is False
    assert by_name["enable_profiling"]["default_value"] is None


# ---------------------------------------------------------------- the corpus


def test_corpus_size_and_buckets(documents):
    assert len(documents) == EXPECTED_CORPUS_DOCS
    buckets = Counter(
        d["stratum"]
        if d["stratum"] == "reference"
        else f"{d['stratum']}-{'signal' if d['has_signal'] else 'distractor'}"
        for d in documents
    )
    assert buckets == Counter(QUOTAS)


def test_document_ids_are_unique(documents):
    assert len({d["doc_id"] for d in documents}) == len(documents)


def test_every_document_file_matches_its_manifest_hash(documents):
    for row in documents:
        path = paths.CORPUS_DOCUMENTS / f"{row['doc_id']}.md"
        text = path.read_text(encoding="utf-8").rstrip("\n")
        assert corpus_mod.sha256_of(text) == row["sha256"], row["doc_id"]
        assert len(text) == row["n_chars"], row["doc_id"]


def test_no_orphan_document_files(documents):
    on_disk = {p.stem for p in paths.CORPUS_DOCUMENTS.glob("*.md")}
    assert on_disk == {d["doc_id"] for d in documents}


def test_every_mentioned_name_is_a_real_setting(documents, settings, alias_to_canonical):
    canonical = {s["name"] for s in settings} - set(alias_to_canonical)
    for row in documents:
        assert set(row["mentioned_names"]) <= canonical, row["doc_id"]


def test_has_signal_agrees_with_the_mentions_it_records(documents):
    for row in documents:
        expected = any(not m["distractor"] for m in row["mentions"])
        assert row["has_signal"] is expected, row["doc_id"]


def test_distractor_documents_are_a_minority(documents):
    """Measured, not assumed: 60% of eligible prose sections are distractor-only.

    Sampled at a fixed 16 of 120 across the two prose strata, so the corpus
    measures the false-positive case on purpose rather than drowning in it.
    """
    prose = [d for d in documents if d["stratum"] != "reference"]
    assert sum(1 for d in prose if not d["has_signal"]) == 16


def test_has_signal_is_a_sampling_heuristic_not_a_truth_label(documents):
    """A reference row documents a real setting and can still carry no signal.

    ``has_signal`` asks "does this document name something other than a word that
    is usually not a setting?", which is a question about sampling balance. It is
    not a claim about what the document documents -- only the hand-labelled recall
    set answers that. Every reference row *is* a documented setting by
    construction, so any unsignalled one is a live counterexample, and this test
    exists so a future reader does not mistake the flag for ground truth.

    Which rows get drawn is a property of the seed, not of the claim: the first
    version of this test pinned the exact draw (``[["password"]]``) and broke the
    moment the corpus was resampled, for a reason that had nothing to do with
    what it was testing. The corpus is resampled on purpose to measure seed
    sensitivity, so assert the invariant instead.
    """
    unsignalled = [d for d in documents if d["stratum"] == "reference" and not d["has_signal"]]
    assert unsignalled, "no unsignalled reference row was drawn -- the counterexample is gone"
    for doc in unsignalled:
        assert doc["mentioned_names"], f"{doc['doc_id']} names nothing at all"
        assert all(m["distractor"] for m in doc["mentions"]), (
            f"{doc['doc_id']} has no signal but names a non-distractor"
        )


def test_manifest_is_valid_jsonl_with_no_trailing_junk():
    raw = paths.CORPUS_JSONL.read_text(encoding="utf-8").splitlines()
    assert all(json.loads(line) for line in raw)
    assert len(raw) == EXPECTED_CORPUS_DOCS


def test_no_committed_document_is_a_generated_html_dump(documents):
    """Session 3 found ``clients/python/reference/index.md`` in the corpus.

    It is 589 kB of Sphinx HTML with no markdown heading in it, so the splitter
    emitted the whole file as one "section": 83% of the corpus by volume, about
    147 k tokens, past the context window of most candidate arms and dearer than
    the other 119 documents put together -- and not prose, which is what this
    benchmark claims to extract from. It was eligible only because a setting
    name appears somewhere inside it.
    """
    for doc in documents:
        text = (paths.CORPUS_DOCUMENTS / f"{doc['doc_id']}.md").read_text(encoding="utf-8")
        density = corpus_mod.html_density(text)
        assert density <= corpus_mod.MAX_HTML_DENSITY, (
            f"{doc['doc_id']} ({doc['source_path']}) is generated HTML: {density:.1f} tags/1k"
        )


def test_every_document_fits_the_smallest_arm_context(documents):
    """Bounds the cost model and keeps a document a document.

    A prose document is capped at ``MAX_SECTION_CHARS``; reference documents are
    single table rows and are exempt by construction, so the cap is asserted
    against the whole corpus only as an upper bound.
    """
    oversized = [d for d in documents if d["n_chars"] > MAX_SECTION_CHARS]
    assert not oversized, [(d["doc_id"], d["n_chars"]) for d in oversized]

    total = sum(d["n_chars"] for d in documents)
    assert total < 200_000, f"corpus grew to {total} chars -- re-check the per-arm cost estimate"
