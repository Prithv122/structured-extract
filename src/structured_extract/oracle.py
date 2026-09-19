"""The oracle: what DuckDB's own binary says a configuration setting is.

``duckdb_settings()`` adjudicates name existence, type and scope for every
setting the loaded build knows about. That makes it a free, exact, zero-human
ground truth for the extraction benchmark -- a hallucinated setting name is a
hard count, not a judgement call.

Two deliberate choices
----------------------
**Extension attribution.** Roughly 40% of the settings only exist once an
extension is loaded. Each extension is loaded into its *own fresh connection*
and diffed against the base build, so every setting carries the extension that
introduced it. Loading them all into one connection would still give the right
union but would lose the attribution, and "is this setting real?" is a different
question from "is this setting real *in a plain duckdb*?".

**``value`` is not in this file.** ``duckdb_settings().value`` is what *this
machine* is running: ``threads`` reports the host's core count, ``memory_limit``
a fraction of host RAM, ``Calendar`` and ``TimeZone`` the host locale. The docs
reference table says "System (locale) calendar" for the same setting -- it is
documenting the rule, not a value. Committing ``value`` would make the oracle
non-reproducible across machines and would score models against this laptop.
It is written separately to ``observed_values.jsonl``, stamped with the host it
came from, precisely so the disagreements stay visible instead of silently
becoming ground truth.
"""

from __future__ import annotations

import platform
from dataclasses import asdict, dataclass, field

import duckdb

#: Extensions that contribute settings, in the order they are probed.
#: ``aws`` adds none in 1.5.5 and is kept so the report says so out loud rather
#: than leaving a reader to wonder whether it was forgotten.
EXTENSIONS = ("httpfs", "mysql", "postgres", "azure", "iceberg", "spatial", "delta", "aws")

#: Attribution for settings present in a plain build with no extensions loaded.
CORE = "core"


class OracleError(RuntimeError):
    """Raised when the binary does not report settings the way this module expects."""


@dataclass(frozen=True)
class OracleSetting:
    """One setting as the DuckDB binary reports it. Machine-independent fields only."""

    name: str
    description: str
    input_type: str
    scope: str
    aliases: list[str] = field(default_factory=list)
    #: ``"core"``, or the extension whose load made this setting appear.
    extension: str = CORE
    duckdb_version: str = ""

    def to_json(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ObservedValue:
    """What ``value`` happened to be on the machine that built the oracle."""

    name: str
    value: str | None
    extension: str
    duckdb_version: str
    host_platform: str

    def to_json(self) -> dict:
        return asdict(self)


_QUERY = """
select name, value, description, input_type, scope, aliases
from duckdb_settings()
order by name
"""


def _rows(extension: str | None) -> list[tuple]:
    """Query settings from a fresh connection, optionally with one extension loaded."""
    con = duckdb.connect()
    try:
        if extension is not None:
            con.execute(f"install {extension}")
            con.execute(f"load {extension}")
        return con.execute(_QUERY).fetchall()
    finally:
        con.close()


def duckdb_version() -> str:
    con = duckdb.connect()
    try:
        return str(con.execute("select version()").fetchone()[0])
    finally:
        con.close()


def build_oracle(
    extensions: tuple[str, ...] = EXTENSIONS,
) -> tuple[list[OracleSetting], list[ObservedValue], dict[str, int]]:
    """Return ``(settings, observed_values, per_extension_counts)``.

    Raises :class:`OracleError` if two extensions claim the same setting name, or
    if an extension redefines a core setting's type or scope -- either would make
    ``extension`` ambiguous, and an ambiguous oracle is worse than no oracle.
    """
    version = duckdb_version()
    host = f"{platform.system()} {platform.machine()} python{platform.python_version()}"

    settings: dict[str, OracleSetting] = {}
    observed: dict[str, ObservedValue] = {}
    counts: dict[str, int] = {}

    def absorb(rows: list[tuple], extension: str) -> int:
        added = 0
        for name, value, description, input_type, scope, aliases in rows:
            if name in settings:
                prior = settings[name]
                if (prior.input_type, prior.scope) != (input_type, scope):
                    raise OracleError(
                        f"{name!r} is reported as {prior.input_type}/{prior.scope} by "
                        f"{prior.extension!r} but {input_type}/{scope} by {extension!r}"
                    )
                continue
            settings[name] = OracleSetting(
                name=name,
                description=description or "",
                input_type=input_type,
                scope=scope,
                aliases=sorted(aliases or []),
                extension=extension,
                duckdb_version=version,
            )
            observed[name] = ObservedValue(
                name=name,
                value=value,
                extension=extension,
                duckdb_version=version,
                host_platform=host,
            )
            added += 1
        return added

    counts[CORE] = absorb(_rows(None), CORE)
    for ext in extensions:
        counts[ext] = absorb(_rows(ext), ext)

    ordered = sorted(settings.values(), key=lambda s: s.name)
    return ordered, [observed[s.name] for s in ordered], counts


def alias_map(settings: list[OracleSetting]) -> dict[str, str]:
    """Map every alias to its canonical setting name.

    ``duckdb_settings()`` emits *both* members of an alias pair as full rows: one
    carries the ``aliases`` list, its twin is bare. So the 280 rows describe 274
    distinct settings. The row carrying the list is treated as canonical, which is
    the binary's own view of which spelling is primary.

    Raises :class:`OracleError` on a collision -- an alias resolving to two
    different settings would let a wrong extraction score as correct -- or when
    the twin row disagrees on type or scope.
    """
    by_name = {s.name: s for s in settings}
    out: dict[str, str] = {}
    for s in settings:
        for a in s.aliases:
            if a in out and out[a] != s.name:
                raise OracleError(f"alias {a!r} maps to both {out[a]!r} and {s.name!r}")
            twin = by_name.get(a)
            if twin is not None and (twin.input_type, twin.scope) != (s.input_type, s.scope):
                raise OracleError(
                    f"alias row {a!r} is {twin.input_type}/{twin.scope} but its canonical "
                    f"{s.name!r} is {s.input_type}/{s.scope}"
                )
            out[a] = s.name
    return out


def canonical_name(name: str, aliases: dict[str, str]) -> str:
    """Collapse any accepted spelling onto its canonical one."""
    return aliases.get(name, name)


def known_names(settings: list[OracleSetting]) -> set[str]:
    """Every string the binary accepts as a setting name, canonical or alias."""
    return {s.name for s in settings} | set(alias_map(settings))


def distinct_settings(settings: list[OracleSetting]) -> list[OracleSetting]:
    """The 274 settings behind the 280 rows, with mirror alias rows removed."""
    aliases = alias_map(settings)
    return [s for s in settings if s.name not in aliases]
