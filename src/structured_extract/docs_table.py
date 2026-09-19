"""Strict parser for the DuckDB configuration reference tables.

The upstream page ``docs/current/configuration/overview.md`` carries two
generated markdown tables (``### Global Configuration Options`` and
``### Local Configuration Options``). They are the *documented* ground truth for
a setting's default value -- unlike ``duckdb_settings().value``, which reports
what this machine happens to be running (see :mod:`structured_extract.oracle`).

Why a hand-written parser and not a regex
-----------------------------------------
The obvious ``re.findall`` over a four-group row pattern silently drops any row
whose cells contain characters the pattern did not anticipate, and a dropped row
is invisible: you get a shorter table and no error. That failure mode produced a
benchmark with a hole in its own ground truth during design.

So every step here is *asserted* rather than assumed: the section must be found,
the header must carry the expected labels, every data row must split into
exactly four cells, and the number of records emitted must equal the number of
table lines minus the header and separator. A :class:`TableParseError` is a build
failure, never a shorter file.

The lenient regex version survives as baseline ``B0`` -- it is the honest
"do you even need an LLM?" comparison, and hiding its bug would have made that
comparison a lie.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

#: Cell labels the upstream generator emits, lowercased. Checked, not assumed.
EXPECTED_HEADER = ("name", "description", "type", "default value")

#: ``{% link docs/current/sql/statements/set.md %}`` -> ``docs/current/sql/statements/set.md``
JEKYLL_LINK = re.compile(r"\{%\s*link\s+(.+?)\s*%\}")

#: A markdown table separator row, e.g. ``|----|--------|--|---|``
SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")

#: Setting names are SQL identifiers; anything else means the cell was misread.
SETTING_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

SECTIONS = {
    "GLOBAL": "### Global Configuration Options",
    "LOCAL": "### Local Configuration Options",
}


class TableParseError(RuntimeError):
    """Raised when the reference page does not look the way the parser expects."""


@dataclass(frozen=True)
class DocsSetting:
    """One documented configuration option, exactly as the reference table states it."""

    name: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    type: str = ""
    default_value: str | None = None
    #: ``True`` when the Default value cell was present but empty. The upstream
    #: generator writes an empty cell for "defaults to the empty string" and the
    #: literal ``NULL`` for "no default". Conflating the two would invent a
    #: disagreement with the binary that the docs never made.
    default_is_empty_cell: bool = False
    scope: str = "GLOBAL"
    source_line: int = 0

    def to_json(self) -> dict:
        return asdict(self)


def _split_row(line: str, lineno: int) -> list[str]:
    """Split one markdown table row into exactly four stripped cells."""
    stripped = line.rstrip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        raise TableParseError(f"line {lineno}: table row is not pipe-delimited: {line[:80]!r}")
    cells = [c.strip() for c in stripped[1:-1].split("|")]
    if len(cells) != 4:
        raise TableParseError(
            f"line {lineno}: expected 4 cells, got {len(cells)}. "
            "An embedded '|' would need escaping upstream; refusing to guess."
        )
    return cells


def _parse_name_cell(cell: str, lineno: int) -> tuple[str, list[str]]:
    """Return ``(primary_name, aliases)`` from a Name cell.

    Several options are documented as a single row listing every alias, e.g.
    ``profile_output, profiling_output``. Splitting on the comma and keeping the
    first as primary matches how ``duckdb_settings()`` reports them: a canonical
    ``name`` plus an ``aliases`` list.
    """
    names = [part.strip().strip("`").strip() for part in cell.split(",")]
    names = [n for n in names if n]
    if not names:
        raise TableParseError(f"line {lineno}: empty Name cell")
    for n in names:
        if not SETTING_NAME.fullmatch(n):
            raise TableParseError(f"line {lineno}: implausible setting name {n!r}")
    return names[0], names[1:]


def _clean_description(cell: str) -> str:
    """Resolve Jekyll ``{% link %}`` tags to the bare path they point at.

    The tags are build-time markup, not prose. Leaving them in would put text no
    reader ever sees into a document an extraction model is asked to read.
    """
    return JEKYLL_LINK.sub(lambda m: m.group(1), cell).strip()


def find_table(lines: list[str], heading: str) -> tuple[int, int]:
    """Return ``(first_data_lineno, last_data_lineno)``, 1-based and inclusive."""
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == heading)
    except StopIteration as exc:
        raise TableParseError(f"heading not found: {heading!r}") from exc

    header_idx = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("|")), None)
    if header_idx is None:
        raise TableParseError(f"no table found under {heading!r}")

    header = _split_row(lines[header_idx], header_idx + 1)
    got = tuple(c.strip("`").lower() for c in header)
    if got != EXPECTED_HEADER:
        raise TableParseError(
            f"under {heading!r}: unexpected header {got!r}, expected {EXPECTED_HEADER!r}. "
            "The upstream generator changed shape; re-read the page before trusting this file."
        )
    if header_idx + 1 >= len(lines) or not SEPARATOR.match(lines[header_idx + 1]):
        raise TableParseError(f"line {header_idx + 2}: expected a table separator row")

    end = header_idx + 2
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    if end == header_idx + 2:
        raise TableParseError(f"under {heading!r}: table has a header but no rows")
    return header_idx + 3, end


def parse_reference_page(path: Path) -> list[DocsSetting]:
    """Parse both reference tables, asserting completeness at every step."""
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[DocsSetting] = []

    for scope, heading in SECTIONS.items():
        first, last = find_table(lines, heading)
        expected = last - first + 1
        before = len(out)

        for lineno in range(first, last + 1):
            name_cell, desc_cell, type_cell, default_cell = _split_row(lines[lineno - 1], lineno)
            name, aliases = _parse_name_cell(name_cell, lineno)
            default = default_cell.strip().strip("`")
            out.append(
                DocsSetting(
                    name=name,
                    aliases=aliases,
                    description=_clean_description(desc_cell),
                    type=type_cell.strip("`").strip(),
                    default_value=None if default in ("", "NULL") else default,
                    default_is_empty_cell=default == "",
                    scope=scope,
                    source_line=lineno,
                )
            )

        produced = len(out) - before
        if produced != expected:
            raise TableParseError(
                f"{heading!r}: table spans {expected} data lines but produced {produced} "
                "records. A silently dropped row is exactly the bug this check exists for."
            )

    _assert_no_duplicate_names(out)
    return out


def _assert_no_duplicate_names(rows: list[DocsSetting]) -> None:
    """Every name and alias must be unique across both tables."""
    seen: dict[str, int] = {}
    for row in rows:
        for label in [row.name, *row.aliases]:
            if label in seen:
                raise TableParseError(
                    f"{label!r} documented twice (line {seen[label]} and line {row.source_line})"
                )
            seen[label] = row.source_line
