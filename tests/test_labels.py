"""The hand-labelled recall set: selection, validation, and what it fixes."""

from __future__ import annotations

import pytest

from structured_extract import jsonl, paths
from structured_extract import labels as L
from structured_extract import score as SC


@pytest.fixture(scope="module")
def corpus() -> list[dict]:
    return jsonl.read_list(paths.CORPUS_JSONL)


@pytest.fixture(scope="module")
def oracle() -> SC.Oracle:
    return SC.load_oracle()


# ------------------------------------------------------------------ selection


def test_the_reference_stratum_is_never_labelled_by_hand(corpus):
    """Those 35 already have exact ground truth. Human attention spent there
    buys nothing that `reference_target` does not already give for free."""
    picked = L.select(corpus)
    assert picked
    assert all(row["stratum"] != "reference" for row in picked)


def test_the_selection_is_stratified_across_every_prose_bucket(corpus):
    buckets = {L.bucket_of(row) for row in L.select(corpus)}
    assert buckets == {
        "narrative-signal",
        "narrative-distractor",
        "extension-signal",
        "extension-distractor",
    }


def test_the_quotas_sum_to_exactly_the_requested_size(corpus):
    """Largest remainder, so it is 40 and not 39 or 41."""
    for n in (10, 40, 41, 85):
        assert len(L.select(corpus, n=n)) == n


def test_asking_for_more_than_exist_yields_every_prose_document(corpus):
    prose = [row for row in corpus if row["stratum"] != "reference"]
    assert len(L.select(corpus, n=10_000)) == len(prose)


def test_the_selection_is_deterministic_and_seed_sensitive(corpus):
    first = [row["doc_id"] for row in L.select(corpus)]
    assert first == [row["doc_id"] for row in L.select(corpus)]
    assert first != [row["doc_id"] for row in L.select(corpus, seed=1)]


def test_a_fresh_worksheet_is_entirely_unlabelled(corpus):
    built = L.build(corpus)
    assert all(not label.labelled for label in built)
    assert all(label.documents is None for label in built)
    assert any(label.candidates for label in built), "candidates should be pre-filled"


# --------------------------------------------------------------------- merge


def test_regenerating_the_worksheet_never_discards_a_judgement(corpus):
    built = L.build(corpus)
    done = built[0]
    done.documents = ["memory_limit"]
    done.cross_referenced = ["threads"]
    done.note = "documented in the first paragraph"

    merged = L.merge(L.build(corpus), [done])
    kept = next(label for label in merged if label.doc_id == done.doc_id)
    assert kept.documents == ["memory_limit"]
    assert kept.cross_referenced == ["threads"]
    assert kept.note == "documented in the first paragraph"
    assert sum(1 for label in merged if label.labelled) == 1


def test_a_judgement_of_empty_survives_a_merge(corpus):
    """`[]` is a decision and `None` is not. Confusing them would silently
    re-open 16 distractor documents that had already been judged."""
    built = L.build(corpus)
    built[0].documents = []
    merged = L.merge(L.build(corpus), [built[0]])
    kept = next(label for label in merged if label.doc_id == built[0].doc_id)
    assert kept.documents == []
    assert kept.labelled is True


def test_a_document_that_left_the_corpus_does_not_come_back(corpus):
    stale = L.Label(
        doc_id="gone-9999", bucket="narrative-signal", source_path="x", heading_path="y", n_chars=1
    )
    stale.documents = ["memory_limit"]
    merged = L.merge(L.build(corpus), [stale])
    assert "gone-9999" not in {label.doc_id for label in merged}


# ----------------------------------------------------------------- validation


def test_a_misspelled_setting_name_is_caught(corpus, oracle):
    label = L.build(corpus)[0]
    label.documents = ["memry_limit"]
    (problem,) = L.validate([label], oracle.resolve)
    assert "duckdb_settings() has never heard of" in problem


def test_a_name_in_both_lists_is_caught(corpus, oracle):
    label = L.build(corpus)[0]
    label.documents = ["memory_limit"]
    label.cross_referenced = ["max_memory"]
    (problem,) = L.validate([label], oracle.resolve)
    assert "one or the other" in problem, "aliases of one setting are one setting"


def test_a_duplicated_document_is_caught(corpus, oracle):
    label = L.build(corpus)[0]
    problems = L.validate([label, label], oracle.resolve)
    assert any("appears twice" in p for p in problems)


def test_labelling_a_setting_the_detector_missed_is_allowed(corpus, oracle):
    """Capping ground truth at whatever the regex caught would make the label
    set unable to find the detector's own misses."""
    label = L.build(corpus)[0]
    label.documents = ["allow_unsigned_extensions"]
    label.candidates = []
    assert L.validate([label], oracle.resolve) == []


def test_an_unlabelled_document_raises_no_complaints(corpus, oracle):
    assert L.validate(L.build(corpus), oracle.resolve) == []


def test_coverage_counts_empty_judgements_as_done(corpus):
    built = L.build(corpus)
    built[0].documents = []
    built[1].documents = ["memory_limit"]
    stats = L.coverage(built)
    assert stats["labelled"] == 2
    assert stats["correctly_empty"] == 1
    assert stats["documents_something"] == 1
    assert stats["settings_labelled"] == 1


# ------------------------------------------------- what the labels actually fix


NARRATIVE_0001_TEXT = (paths.CORPUS_DOCUMENTS / "narrative-0001.md").read_text(encoding="utf-8")


def _row(**kw) -> dict:
    row = {
        "doc_id": "narrative-0001",
        "arm": "H1",
        "prompt": "v2-specified",
        "outcome": "valid_first_pass",
        "settings": [],
        "cost_reported": 0.0,
    }
    row.update(kw)
    return row


def test_the_proxy_marks_a_correct_empty_answer_on_narrative_0001_as_a_miss(corpus, oracle):
    """The concrete failure the label set exists to fix.

    The document is a table of `COPY ... TO` options. It mentions
    `preserve_insertion_order` exactly once, inside another row's description,
    as a cross-reference to the configuration page. The correct extraction is an
    empty list -- and the proxy, which treats any mentioned name as a target,
    calls that a miss.
    """
    meta = {row["doc_id"]: row for row in corpus}
    scored = SC.score_row(
        _row(), meta, {"narrative-0001": NARRATIVE_0001_TEXT}, oracle, hand_labels=None
    )
    assert scored.truth_source == "mentioned-proxy"
    assert scored.mentioned == ["preserve_insertion_order"]
    assert scored.empty_was_correct is False, "the proxy is wrong here, and this pins it"


def test_a_hand_label_turns_that_same_answer_into_a_pass(corpus, oracle):
    meta = {row["doc_id"]: row for row in corpus}
    scored = SC.score_row(
        _row(),
        meta,
        {"narrative-0001": NARRATIVE_0001_TEXT},
        oracle,
        hand_labels={"narrative-0001": []},
    )
    assert scored.truth_source == "hand-label"
    assert scored.expected == []
    assert scored.empty_was_correct is True


def test_a_hand_label_beats_the_proxy_but_not_a_reference_row(corpus, oracle):
    """Reference rows are already exact; a label must not be able to overwrite
    ground truth that was never in doubt."""
    meta = {row["doc_id"]: row for row in corpus}
    text = (paths.CORPUS_DOCUMENTS / "reference-0001.md").read_text(encoding="utf-8")
    scored = SC.score_row(
        _row(doc_id="reference-0001"),
        meta,
        {"reference-0001": text},
        oracle,
        hand_labels={"reference-0001": ["memory_limit"]},
    )
    assert scored.truth_source == "reference-row"
    assert scored.expected != ["max_memory"]


def test_a_hand_label_resolves_aliases_to_canonical_names(corpus, oracle):
    """A labeller writing `memory_limit` must match an arm answering
    `max_memory`, and vice versa."""
    meta = {row["doc_id"]: row for row in corpus}
    scored = SC.score_row(
        _row(),
        meta,
        {"narrative-0001": NARRATIVE_0001_TEXT},
        oracle,
        hand_labels={"narrative-0001": ["memory_limit"]},
    )
    assert scored.expected == ["max_memory"]


def test_scoring_without_labels_still_works_and_says_so(corpus, oracle):
    """The label set is additive. An empty one must not break the pipeline."""
    meta = {row["doc_id"]: row for row in corpus}
    scored = SC.score_row(
        _row(), meta, {"narrative-0001": NARRATIVE_0001_TEXT}, oracle, hand_labels={}
    )
    assert scored.truth_source == "mentioned-proxy"


# ------------------------------------------------------- the committed set


def test_the_committed_worksheet_matches_what_init_would_generate(corpus):
    """Guards against a worksheet edited by hand drifting from the selection."""
    committed = L.load()
    if not committed:
        pytest.skip("no label set committed yet")
    assert [label.doc_id for label in committed] == [
        label.doc_id for label in L.build(corpus, n=len(committed))
    ]


def test_every_committed_judgement_is_consistent_with_the_oracle(oracle):
    committed = L.load()
    if not committed:
        pytest.skip("no label set committed yet")
    assert L.validate(committed, oracle.resolve) == []
