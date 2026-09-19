"""The reference-table parser must fail loudly, never quietly short."""

from __future__ import annotations

import textwrap

import pytest

from structured_extract.docs_table import (
    DocsSetting,
    TableParseError,
    find_table,
    parse_reference_page,
)


def write_page(tmp_path, body: str):
    path = tmp_path / "overview.md"
    path.write_text(textwrap.dedent(body).lstrip("\n"), encoding="utf-8")
    return path


GOOD = """
    ## Configuration Reference

    ### Global Configuration Options

    | Name | Description | Type | Default value |
    |----|--------|--|---|
    | `access_mode` | Access mode of the database | `VARCHAR` | `automatic` |
    | `max_memory`, `memory_limit` | The maximum memory | `VARCHAR` | `80% of RAM` |
    | `search_path` | Catalog search path | `VARCHAR` |  |
    | `enable_profiling` | Enables profiling | `VARCHAR` | NULL |

    ### Local Configuration Options

    | Name | Description | Type | Default value |
    |----|--------|--|---|
    | `schema` | Default schema, see [set]({% link docs/set.md %}) | `VARCHAR` | `main` |
"""


def test_parses_both_tables(tmp_path):
    rows = parse_reference_page(write_page(tmp_path, GOOD))
    assert [r.name for r in rows] == [
        "access_mode",
        "max_memory",
        "search_path",
        "enable_profiling",
        "schema",
    ]
    assert [r.scope for r in rows] == ["GLOBAL"] * 4 + ["LOCAL"]


def test_alias_row_keeps_both_names(tmp_path):
    rows = {r.name: r for r in parse_reference_page(write_page(tmp_path, GOOD))}
    assert rows["max_memory"].aliases == ["memory_limit"]


def test_empty_cell_and_null_are_not_conflated(tmp_path):
    rows = {r.name: r for r in parse_reference_page(write_page(tmp_path, GOOD))}
    empty, null = rows["search_path"], rows["enable_profiling"]
    assert (empty.default_value, empty.default_is_empty_cell) == (None, True)
    assert (null.default_value, null.default_is_empty_cell) == (None, False)


def test_jekyll_link_tags_are_resolved(tmp_path):
    rows = {r.name: r for r in parse_reference_page(write_page(tmp_path, GOOD))}
    assert "{%" not in rows["schema"].description
    assert "docs/set.md" in rows["schema"].description


def test_missing_heading_raises(tmp_path):
    page = write_page(tmp_path, GOOD.replace("### Local Configuration Options", "### Other"))
    with pytest.raises(TableParseError, match="heading not found"):
        parse_reference_page(page)


def test_unexpected_header_raises(tmp_path):
    page = write_page(
        tmp_path,
        GOOD.replace("| Name | Description | Type | Default value |", "| A | B | C | D |", 1),
    )
    with pytest.raises(TableParseError, match="unexpected header"):
        parse_reference_page(page)


def test_embedded_pipe_raises_rather_than_guessing(tmp_path):
    """The failure this module exists for: a row that does not split into 4 cells."""
    page = write_page(
        tmp_path,
        GOOD.replace(
            "| `access_mode` | Access mode of the database | `VARCHAR` | `automatic` |",
            "| `access_mode` | Access mode | of the database | `VARCHAR` | `automatic` |",
        ),
    )
    with pytest.raises(TableParseError, match="expected 4 cells"):
        parse_reference_page(page)


def test_duplicate_name_raises(tmp_path):
    page = write_page(tmp_path, GOOD.replace("`search_path`", "`access_mode`"))
    with pytest.raises(TableParseError, match="documented twice"):
        parse_reference_page(page)


def test_alias_colliding_with_another_row_raises(tmp_path):
    page = write_page(tmp_path, GOOD.replace("`memory_limit`", "`access_mode`"))
    with pytest.raises(TableParseError, match="documented twice"):
        parse_reference_page(page)


def test_find_table_reports_inclusive_data_range(tmp_path):
    lines = write_page(tmp_path, GOOD).read_text(encoding="utf-8").splitlines()
    first, last = find_table(lines, "### Global Configuration Options")
    assert last - first + 1 == 4
    assert lines[first - 1].startswith("| `access_mode`")


def test_docs_setting_round_trips_to_json():
    row = DocsSetting(name="x", aliases=["y"], description="d", type="VARCHAR", scope="LOCAL")
    assert row.to_json()["aliases"] == ["y"]
