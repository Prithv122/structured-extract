"""Section splitting, mention detection and seeded sampling."""

from __future__ import annotations

import textwrap

import pytest

from structured_extract import corpus

PAGE = textwrap.dedent(
    """
    ---
    layout: docu
    title: Reading and Writing Parquet Files
    ---

    An introduction that names `memory_limit` before any heading.

    ## Examples

    Set the `threads` option to control parallelism.

    ### Nested

    Deeper prose about `preserve_insertion_order`.

    ## Empty
    """
).lstrip("\n")

NAMES = {"memory_limit", "max_memory", "threads", "preserve_insertion_order", "schema"}
ALIASES = {"memory_limit": "max_memory"}


def sections():
    return corpus.split_sections("data/parquet/overview.md", PAGE)


def test_front_matter_is_stripped_and_title_kept():
    body, title = corpus.strip_front_matter(PAGE)
    assert title == "Reading and Writing Parquet Files"
    assert not body.lstrip().startswith("---")
    assert "layout: docu" not in body


def test_intro_before_the_first_heading_becomes_a_section():
    first = sections()[0]
    assert first.heading == "Reading and Writing Parquet Files"
    assert "memory_limit" in first.text


def test_heading_path_records_the_trail():
    nested = next(s for s in sections() if s.heading == "Nested")
    assert nested.heading_path == "Reading and Writing Parquet Files > Examples > Nested"


def test_empty_sections_are_dropped():
    assert "Empty" not in [s.heading for s in sections()]


def test_stratum_follows_the_docs_tree():
    assert corpus.stratum_for("core_extensions/httpfs/s3api.md") == "extension"
    assert corpus.stratum_for("extensions/overview.md") == "extension"
    assert corpus.stratum_for("guides/performance/how_to_tune_workloads.md") == "narrative"


def test_mentions_are_canonicalised_onto_the_oracle_name():
    found = corpus.find_mentions("Set `memory_limit` to 2GB.", NAMES, ALIASES)
    assert [m.name for m in found] == ["max_memory"]
    assert found[0].backticked is True


def test_bare_prose_mention_is_not_marked_backticked():
    found = corpus.find_mentions("The threads option matters.", NAMES, ALIASES)
    assert [(m.name, m.backticked) for m in found] == [("threads", False)]


def test_word_boundaries_are_respected():
    text = "my_threads and threads_count are not the setting"
    assert corpus.find_mentions(text, NAMES, ALIASES) == []


def test_longest_name_wins():
    names = {"s3_url", "s3_url_style"}
    found = corpus.find_mentions("set `s3_url_style` to path", names, {})
    assert [m.name for m in found] == ["s3_url_style"]


def test_distractor_names_are_flagged_not_dropped():
    found = corpus.find_mentions("create a table with the correct schema", NAMES, ALIASES)
    assert [(m.name, m.distractor) for m in found] == [("schema", True)]
    assert corpus.has_signal(found) is False


def test_has_signal_needs_one_non_distractor_name():
    found = corpus.find_mentions("`schema` and `threads` and `max_memory`", NAMES, ALIASES)
    assert corpus.has_signal(found) is True


def make_section(page: str, line: int, stratum: str = "narrative") -> corpus.Section:
    return corpus.Section(
        source_path=page,
        page_title="T",
        heading=f"h{line}",
        heading_path=f"T > h{line}",
        text=f"body of {page}:{line} mentioning `threads`",
        start_line=line,
        stratum=stratum,
    )


def test_sampling_is_deterministic_for_a_seed():
    pool = {"narrative-signal": [make_section(f"p{i}.md", 1) for i in range(30)]}
    a = corpus.sample_sections(pool, {"narrative-signal": 10}, seed=7)
    b = corpus.sample_sections(pool, {"narrative-signal": 10}, seed=7)
    assert [s.source_path for s in a] == [s.source_path for s in b]


def test_a_different_seed_gives_a_different_sample():
    pool = {"narrative-signal": [make_section(f"p{i}.md", 1) for i in range(30)]}
    a = corpus.sample_sections(pool, {"narrative-signal": 10}, seed=7)
    b = corpus.sample_sections(pool, {"narrative-signal": 10}, seed=8)
    assert [s.source_path for s in a] != [s.source_path for s in b]


def test_one_section_per_page_until_the_pages_run_out():
    pool = {"b": [make_section("only.md", line) for line in range(1, 6)]}
    picked = corpus.sample_sections(pool, {"b": 3}, seed=1)
    assert len({(s.source_path, s.start_line) for s in picked}) == 3


def test_prefers_distinct_pages_when_it_can():
    pool = {
        "b": [make_section("a.md", 1), make_section("a.md", 2), make_section("b.md", 1)],
    }
    picked = corpus.sample_sections(pool, {"b": 2}, seed=3)
    assert {s.source_path for s in picked} == {"a.md", "b.md"}


def test_quota_larger_than_the_pool_raises():
    pool = {"b": [make_section("a.md", 1)]}
    with pytest.raises(ValueError, match="only 1 available"):
        corpus.sample_sections(pool, {"b": 5}, seed=1)


def test_sampling_report_flags_a_census():
    pool = {"b": [make_section("a.md", 1), make_section("a.md", 2)]}
    line = corpus.sampling_report(pool, {"b": 2})[0]
    assert "census" in line


def test_build_documents_ids_and_hashes():
    picked = [make_section("a.md", 1), make_section("b.md", 1)]
    docs = corpus.build_documents(picked, NAMES, ALIASES)
    assert [d.doc_id for d in docs] == ["narrative-0001", "narrative-0002"]
    assert docs[0].sha256 == corpus.sha256_of(picked[0].text)
    assert docs[0].n_chars == len(picked[0].text)
