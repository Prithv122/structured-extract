"""Build the extraction corpus from the upstream DuckDB documentation.

A document here is a *heading section* of a real documentation page, not a whole
file and not a synthetic paragraph. Sections are the unit a reader actually
consumes, they are short enough to fit a context window without truncation
policy becoming a confound, and they keep the prose exactly as shipped --
including the tables, code fences and Jekyll link markup a real pipeline has to
survive.

Three strata, because the task is not uniformly hard
----------------------------------------------------
``reference``
    One row of the generated configuration reference table, rendered as a tiny
    document. Name, description, type and default are all present and explicit.
    This is the easy end, and any arm that cannot score near-perfectly here has
    a formatting problem rather than a comprehension problem.
``extension``
    Sections from ``core_extensions/`` and ``extensions/`` pages. Settings are
    introduced in prose mid-page, often alongside SQL examples, and roughly 40%
    of all settings only exist once an extension is loaded.
``narrative``
    Everything else -- guides, SQL reference, operations manual. Settings appear
    in passing, sometimes only as a backticked word in a sentence about
    something else. This is where *mentioned* and *documented* come apart, and
    it is why 40 sections get hand-labelled for recall: no oracle can tell you
    whether a section was trying to document a setting or merely named it.

Deliberate distractors
----------------------
``schema``, ``user``, ``username`` and ``password`` are real DuckDB setting
names that are also ordinary English words and Postgres/MySQL connection
parameters. Sections mentioning them are *kept*, not filtered: they are wrong in
a way ``duckdb_settings()`` alone cannot catch, because the name checks out
while the section was never about the DuckDB setting at all.
"""

from __future__ import annotations

import hashlib
import random
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from structured_extract.docs_table import SECTIONS, find_table

#: YAML front matter delimited by ``---`` at the very top of a page.
FRONT_MATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.S)

#: ATX headings. Setext headings do not occur in this corpus and are not handled.
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")

#: ``title: Reading and Writing Parquet Files`` inside the front matter.
TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.M)

#: Directories whose pages document an extension.
EXTENSION_DIRS = ("core_extensions", "extensions")

#: Setting names that are also ordinary words or connection parameters. Kept on
#: purpose; see the module docstring.
DISTRACTOR_NAMES = frozenset({"schema", "user", "username", "password", "threads", "secret"})

#: Block-level HTML tags. Prose pages use inline `<code>`/`<a>` occasionally;
#: the Sphinx- and Doxygen-generated API pages are built out of these.
BLOCK_HTML = re.compile(r"<(?:div|dl|dt|dd|span|table|tr|td)[ >/]")

#: Block-HTML tags per 1000 characters above which a page is a generated API
#: dump rather than documentation prose. The two families do not overlap: every
#: page under ``clients/c/`` and ``clients/python/reference/`` scores 10-24,
#: every genuine prose page in the 434-page checkout scores <= 1.6. Any
#: threshold in 2..10 selects exactly the same pages, so this is a separator,
#: not a tuned parameter.
MAX_HTML_DENSITY = 5.0

STRATA = ("narrative", "extension", "reference")


@dataclass(frozen=True)
class Mention:
    """A setting name found in a section's text."""

    name: str
    count: int
    #: ``True`` if at least one occurrence was inside backticks. Prose that names
    #: a setting in code formatting is far more likely to be documenting it.
    backticked: bool
    #: ``True`` if this name is in :data:`DISTRACTOR_NAMES`.
    distractor: bool

    def to_json(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Section:
    """One heading section of one documentation page."""

    source_path: str
    page_title: str
    heading: str
    #: ``"Page Title > H2 > H3"`` -- the trail a reader followed to reach it.
    heading_path: str
    text: str
    start_line: int
    stratum: str

    @property
    def n_chars(self) -> int:
        return len(self.text)


@dataclass(frozen=True)
class CorpusDocument:
    """A sampled section, as committed to ``data/corpus/``."""

    doc_id: str
    stratum: str
    source_path: str
    page_title: str
    heading_path: str
    n_chars: int
    sha256: str
    mentions: list[Mention] = field(default_factory=list)
    #: Names mentioned anywhere in the text, canonicalised and deduplicated.
    #: A *mention* is not a claim that the section documents the setting.
    mentioned_names: list[str] = field(default_factory=list)
    #: ``True`` when at least one mention is not in :data:`DISTRACTOR_NAMES`.
    #: Documents where it is ``False`` mention only words like ``schema`` or
    #: ``password`` -- real setting names, but almost always used as something
    #: else. They are sampled at a fixed rate to measure the false-positive rate
    #: on purpose, instead of letting them flood the corpus by accident.
    has_signal: bool = False

    def to_json(self) -> dict:
        row = asdict(self)
        row["mentions"] = [m.to_json() if isinstance(m, Mention) else m for m in self.mentions]
        return row


def strip_front_matter(text: str) -> tuple[str, str]:
    """Return ``(body, page_title)``. Title is ``""`` when there is no front matter."""
    match = FRONT_MATTER.match(text)
    if not match:
        return text, ""
    block = match.group(0)
    title = TITLE.search(block)
    return text[match.end() :], (title.group(1).strip().strip("\"'") if title else "")


def stratum_for(rel_path: str) -> str:
    """Classify a page by where it sits in the docs tree."""
    head = rel_path.split("/", 1)[0]
    return "extension" if head in EXTENSION_DIRS else "narrative"


def split_sections(rel_path: str, text: str) -> list[Section]:
    """Split a page into heading sections, keeping the heading trail.

    Content before the first heading becomes a section headed by the page title,
    so an introduction that introduces a setting is not silently discarded --
    on several DuckDB pages the intro is the only prose about the page's subject.
    """
    body, page_title = strip_front_matter(text)
    stratum = stratum_for(rel_path)
    lines = body.splitlines()

    sections: list[Section] = []
    trail: list[str] = []
    current_heading = page_title or rel_path
    current_level = 0
    buf: list[str] = []
    start_line = 1

    def flush(heading: str, level: int, body_lines: list[str], line_no: int) -> None:
        content = "\n".join(body_lines).strip()
        if not content:
            return
        path_parts = [page_title, *trail[: max(level - 1, 0)], heading] if level else [heading]
        seen: list[str] = []
        for part in path_parts:
            if part and (not seen or seen[-1] != part):
                seen.append(part)
        sections.append(
            Section(
                source_path=rel_path,
                page_title=page_title,
                heading=heading,
                heading_path=" > ".join(seen),
                text=content,
                start_line=line_no,
                stratum=stratum,
            )
        )

    for i, line in enumerate(lines, 1):
        m = HEADING.match(line)
        if not m:
            buf.append(line)
            continue
        flush(current_heading, current_level, buf, start_line)
        level = len(m.group(1))
        heading = m.group(2).strip()
        trail[level - 1 :] = [heading]
        current_heading, current_level, buf, start_line = heading, level, [], i

    flush(current_heading, current_level, buf, start_line)
    return sections


def _name_pattern(names: set[str]) -> re.Pattern[str]:
    """One alternation over every known setting name, longest first.

    Longest-first matters: ``s3_url_style`` must not be reported as ``s3_url``
    plus leftovers, and ``memory_limit`` must not lose to a shorter prefix.
    """
    ordered = sorted(names, key=len, reverse=True)
    return re.compile(
        r"(?<![A-Za-z0-9_])(" + "|".join(map(re.escape, ordered)) + r")(?![A-Za-z0-9_])"
    )


def find_mentions(text: str, names: set[str], aliases: dict[str, str]) -> list[Mention]:
    """Find every known setting name in ``text``, canonicalised.

    Occurrences are counted on the raw text and separately on the text with all
    inline-code spans removed, so ``backticked`` records whether the name ever
    appeared in code formatting rather than only in running prose.
    """
    pattern = _name_pattern(names)
    total = Counter(pattern.findall(text))
    outside_code = Counter(pattern.findall(re.sub(r"`[^`]*`", " ", text)))

    merged: dict[str, dict] = {}
    for raw, count in total.items():
        canon = aliases.get(raw, raw)
        entry = merged.setdefault(canon, {"count": 0, "backticked": False})
        entry["count"] += count
        if count > outside_code.get(raw, 0):
            entry["backticked"] = True

    return [
        Mention(
            name=name,
            count=data["count"],
            backticked=data["backticked"],
            distractor=name in DISTRACTOR_NAMES,
        )
        for name, data in sorted(merged.items())
    ]


def html_density(text: str) -> float:
    """Block-level HTML tags per 1000 characters."""
    return len(BLOCK_HTML.findall(text)) / max(len(text), 1) * 1000


def iter_pages(docs_root: Path) -> list[tuple[str, str]]:
    """Return ``(relative_posix_path, text)`` for every *prose* markdown page, sorted.

    Generated API-reference pages are skipped. ``clients/python/reference/index.md``
    is 589 kB of Sphinx HTML with no markdown heading anywhere in it, so the
    splitter emitted the entire file as a single 589 kB "section" -- 83% of the
    corpus by volume in one document, ~147 k tokens, past the context window of
    most candidate arms and more expensive than the other 119 documents combined.
    ``clients/c/api.md`` is the same thing at 441 kB and would have been drawn by
    some other seed. Neither is prose, which is what this benchmark claims to
    extract from, so they are excluded at the page level rather than capped.
    """
    base = docs_root
    out = []
    for p in sorted(base.rglob("*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        if html_density(text) > MAX_HTML_DENSITY:
            continue
        out.append((p.relative_to(base).as_posix(), text))
    return out


def doc_id_for(stratum: str, index: int) -> str:
    return f"{stratum}-{index:04d}"


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sample_sections(
    buckets: dict[str, list[Section]],
    quotas: dict[str, int],
    seed: int,
) -> list[Section]:
    """Seeded stratified sample, one section per source page where possible.

    Sampling *with* page repetition would let a single long page dominate a
    bucket, so the first pass takes at most one section per page and only falls
    back to a second pass when a quota cannot be met otherwise. When a bucket is
    exhausted the second pass is a real, reportable fact about the corpus -- the
    ``pages_available`` figure in :func:`sampling_report` exists to say so rather
    than let a quota quietly become a census with repeats.
    """
    rng = random.Random(seed)
    chosen: list[Section] = []

    for bucket, quota in quotas.items():
        pool = buckets.get(bucket, [])
        if len(pool) < quota:
            raise ValueError(
                f"bucket {bucket!r}: need {quota} sections, only {len(pool)} available"
            )

        by_page: dict[str, list[Section]] = {}
        for s in pool:
            by_page.setdefault(s.source_path, []).append(s)

        pages = sorted(by_page)
        rng.shuffle(pages)
        picked = [rng.choice(sorted(by_page[p], key=lambda s: s.start_line)) for p in pages]

        if len(picked) < quota:
            already = {(s.source_path, s.start_line) for s in picked}
            remaining = [s for s in pool if (s.source_path, s.start_line) not in already]
            remaining.sort(key=lambda s: (s.source_path, s.start_line))
            rng.shuffle(remaining)
            picked.extend(remaining[: quota - len(picked)])

        chosen.extend(picked[:quota])

    return chosen


def sampling_report(buckets: dict[str, list[Section]], quotas: dict[str, int]) -> list[str]:
    """One line per bucket: quota, sections available, and distinct source pages."""
    lines = []
    for bucket, quota in quotas.items():
        pool = buckets.get(bucket, [])
        pages = len({s.source_path for s in pool})
        # The reference bucket is 169 rows of one generated page by construction,
        # so "one page" is not a shortage there and the note would be noise.
        census = bucket != "reference" and quota >= pages
        note = "  <- census: every eligible page is taken" if census else ""
        lines.append(
            f"  {bucket:<22} quota {quota:>3}  sections {len(pool):>4}  pages {pages:>4}{note}"
        )
    return lines


def reference_sections(page_path: Path, rel_path: str) -> list[Section]:
    """Render each configuration-reference row as its own one-row document.

    The header, separator and data line are copied **verbatim** from the page, so
    a reference document is a byte-exact excerpt rather than a re-rendering. That
    matters: column padding, backticks and the occasional 1.3 kB JSON default are
    part of what the model has to read, and prettifying them would quietly make
    the easy stratum easier than the page it came from.
    """
    lines = page_path.read_text(encoding="utf-8").splitlines()
    out: list[Section] = []

    for scope, heading in SECTIONS.items():
        first, last = find_table(lines, heading)
        header, separator = lines[first - 3], lines[first - 2]
        trail = f"Configuration > Configuration Reference > {heading.lstrip('# ')}"
        for lineno in range(first, last + 1):
            row = lines[lineno - 1]
            text = "\n".join([heading, "", header, separator, row])
            out.append(
                Section(
                    source_path=rel_path,
                    page_title="Configuration",
                    heading=f"{scope} option (line {lineno})",
                    heading_path=trail,
                    text=text,
                    start_line=lineno,
                    stratum="reference",
                )
            )
    return out


def has_signal(mentions: list[Mention]) -> bool:
    """A document has signal when it names at least one non-distractor setting."""
    return any(not m.distractor for m in mentions)


def bucket_for(section: Section, mentions: list[Mention]) -> str:
    """Sampling bucket: the stratum, split by whether the section has signal."""
    if section.stratum == "reference":
        return "reference"
    return f"{section.stratum}-{'signal' if has_signal(mentions) else 'distractor'}"


def build_documents(
    sections: list[Section],
    names: set[str],
    aliases: dict[str, str],
) -> list[CorpusDocument]:
    """Attach mention metadata and a stable id to each sampled section."""
    counters = dict.fromkeys(STRATA, 0)
    docs: list[CorpusDocument] = []
    for section in sections:
        counters[section.stratum] += 1
        mentions = find_mentions(section.text, names, aliases)
        docs.append(
            CorpusDocument(
                doc_id=doc_id_for(section.stratum, counters[section.stratum]),
                stratum=section.stratum,
                source_path=section.source_path,
                page_title=section.page_title,
                heading_path=section.heading_path,
                n_chars=section.n_chars,
                sha256=sha256_of(section.text),
                mentions=mentions,
                mentioned_names=[m.name for m in mentions],
                has_signal=has_signal(mentions),
            )
        )
    return docs
