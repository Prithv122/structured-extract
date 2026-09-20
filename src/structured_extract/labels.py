"""The hand-labelled recall set: the one thing no oracle in this repo can supply.

``duckdb_settings()`` answers "is this a real setting?" exactly and for free.
It cannot answer "does *this section* document it", and that is the question
recall needs. The gap is not academic. ``narrative-0001`` is a table of
``COPY ... TO`` options that mentions ``preserve_insertion_order`` once, inside
another row's description, as a cross-reference. The correct extraction is an
empty list -- and the manifest-based proxy, which treats any mentioned name as
something to find, scores every arm that got it right as having missed it.

So the proxy is not merely biased low. On the most interesting document in the
pilot it is inverted, and no amount of extra model runs will fix that.

What a labeller is and is not asked
-----------------------------------
Only the judgement: **which settings does this section document?** Type, scope
and default are not asked for, because the oracle and the reference table
already know them for any named setting -- asking a human to copy them out
would add transcription errors to the ground truth and slow the job down for
nothing.

Two lists per document, and the distinction between them is the whole point:

``documents``
    Settings this section actually documents. Empty is a real answer and the
    common one; 16 of the 85 prose documents are distractors by construction.
``cross_referenced``
    Names that appear in the text but are *not* documented here -- a link to
    another page, a mention in passing, an ordinary English word that happens
    to be a setting name. Recording these separately is what lets a later
    analysis say *why* an arm returned something, rather than only that it was
    wrong.

Why the reference stratum is excluded
-------------------------------------
Those 35 documents are single rows of the generated configuration reference
table, so the setting each one documents is recoverable from the row itself and
is already exact ground truth. Spending scarce human attention there would buy
nothing. The 40 are drawn from the 85 prose documents, where the oracle cannot
reach.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field

from structured_extract import jsonl, paths
from structured_extract.corpus import DISTRACTOR_NAMES

#: How many prose sections get a human read. Big enough that a stratum-level
#: rate has a usable interval, small enough to actually be done in one sitting:
#: the 40 average about 1,000 characters each.
LABEL_SET_SIZE = 40

#: Separate from the corpus seed on purpose. Re-drawing the corpus and
#: re-drawing the label set are different decisions and should not be forced to
#: happen together.
DEFAULT_LABEL_SEED = 20260920

#: ``documents: null`` means nobody has looked at this section yet. An empty
#: list means a human looked and decided the answer is "nothing", which is a
#: completely different claim and the one the distractor strata depend on.
UNLABELLED = None


def bucket_of(row: dict) -> str:
    if row["stratum"] == "reference":
        return "reference"
    return f"{row['stratum']}-{'signal' if row['has_signal'] else 'distractor'}"


@dataclass
class Label:
    """One human judgement about one document."""

    doc_id: str
    bucket: str
    source_path: str
    heading_path: str
    n_chars: int
    #: Names the mention detector found, as candidates to rule in or out. This
    #: is scaffolding for the labeller, not an answer.
    candidates: list[str] = field(default_factory=list)
    #: The judgement. ``None`` until someone makes it.
    documents: list[str] | None = UNLABELLED
    #: Mentioned but not documented here.
    cross_referenced: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def labelled(self) -> bool:
        return self.documents is not UNLABELLED

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, row: dict) -> Label:
        return cls(**row)


def select(corpus: list[dict], n: int = LABEL_SET_SIZE, seed: int = DEFAULT_LABEL_SEED):
    """A seeded, stratified draw from the prose documents.

    Proportional to each bucket's share of the prose pool, so the distractor
    buckets are represented at roughly the rate they occur rather than being
    crowded out by the much larger narrative-signal bucket. Largest remainder,
    so the parts sum to ``n`` exactly instead of to 39 or 41.
    """
    prose = [row for row in corpus if row["stratum"] != "reference"]
    buckets: dict[str, list[dict]] = {}
    for row in prose:
        buckets.setdefault(bucket_of(row), []).append(row)

    exact = {key: n * len(rows) / len(prose) for key, rows in buckets.items()}
    quota = {key: int(value) for key, value in exact.items()}
    remainder = sorted(buckets, key=lambda key: (exact[key] - quota[key], key), reverse=True)
    for key in remainder[: n - sum(quota.values())]:
        quota[key] += 1

    rng = random.Random(seed)
    picked: list[dict] = []
    for key in sorted(buckets):
        pool = sorted(buckets[key], key=lambda row: row["doc_id"])
        picked.extend(rng.sample(pool, min(quota[key], len(pool))))
    return sorted(picked, key=lambda row: row["doc_id"])


def build(corpus: list[dict], n: int = LABEL_SET_SIZE, seed: int = DEFAULT_LABEL_SEED):
    """Create the empty worksheet. Never overwrites a judgement; see ``merge``."""
    return [
        Label(
            doc_id=row["doc_id"],
            bucket=bucket_of(row),
            source_path=row["source_path"],
            heading_path=row["heading_path"],
            n_chars=row["n_chars"],
            candidates=sorted(row["mentioned_names"]),
        )
        for row in select(corpus, n, seed)
    ]


def merge(fresh: list[Label], existing: list[Label]) -> list[Label]:
    """Carry finished judgements onto a regenerated worksheet.

    Re-running ``labels init`` after the corpus changes must not silently throw
    away work already done. Anything already judged is kept; anything new comes
    in blank.
    """
    done = {label.doc_id: label for label in existing if label.labelled}
    out = []
    for label in fresh:
        prior = done.get(label.doc_id)
        if prior is None:
            out.append(label)
            continue
        out.append(
            Label(
                doc_id=label.doc_id,
                bucket=label.bucket,
                source_path=label.source_path,
                heading_path=label.heading_path,
                n_chars=label.n_chars,
                candidates=label.candidates,
                documents=prior.documents,
                cross_referenced=prior.cross_referenced,
                note=prior.note,
            )
        )
    return out


def load() -> list[Label]:
    if not paths.LABELS_JSONL.exists():
        return []
    return [Label.from_json(row) for row in jsonl.read_list(paths.LABELS_JSONL)]


def save(labels: list[Label]) -> int:
    return jsonl.write(paths.LABELS_JSONL, (label.to_json() for label in labels))


def validate(labels: list[Label], resolve) -> list[str]:
    """Problems a labeller can plausibly introduce. ``resolve`` is the oracle's.

    Deliberately not checked: whether a labelled setting appears in
    ``candidates``. A section can document a setting the mention detector
    missed -- that is a *finding about the detector*, and forbidding it would
    cap the ground truth at whatever the regex happened to catch.
    """
    problems: list[str] = []
    seen: set[str] = set()
    for label in labels:
        if label.doc_id in seen:
            problems.append(f"{label.doc_id}: appears twice")
        seen.add(label.doc_id)
        if not label.labelled:
            continue

        for name in label.documents or []:
            if resolve(name) is None:
                problems.append(
                    f"{label.doc_id}: documents {name!r}, which duckdb_settings() "
                    f"has never heard of -- a typo, or a setting that is not real"
                )
        for name in label.cross_referenced:
            if resolve(name) is None:
                problems.append(f"{label.doc_id}: cross_referenced {name!r} is not a real setting")

        both = {resolve(n) for n in label.documents or []} & {
            resolve(n) for n in label.cross_referenced
        }
        if both - {None}:
            problems.append(
                f"{label.doc_id}: {sorted(both - {None})} is in both documents and "
                f"cross_referenced -- it is one or the other"
            )
    return problems


def coverage(labels: list[Label]) -> dict:
    """How much of the job is done, and what it says so far."""
    done = [label for label in labels if label.labelled]
    non_empty = [label for label in done if label.documents]
    return {
        "total": len(labels),
        "labelled": len(done),
        "documents_something": len(non_empty),
        "correctly_empty": len(done) - len(non_empty),
        "settings_labelled": sum(len(label.documents or []) for label in done),
        "cross_references": sum(len(label.cross_referenced) for label in done),
        "distractor_only_candidates": sum(
            1 for label in done if label.candidates and set(label.candidates) <= DISTRACTOR_NAMES
        ),
    }


def worksheet_markdown(labels: list[Label], documents: dict[str, str]) -> str:
    """A single file with every section's full text, for reading in one pass.

    Forty documents means forty files otherwise. The judgements still go in the
    JSONL -- this is for reading, not for editing, and it says so.
    """
    out = [
        "# Hand-labelling worksheet",
        "",
        f"{len(labels)} prose sections drawn from the 85 in the corpus, seeded and",
        "stratified. The reference stratum is excluded: those 35 documents are single",
        "rows of the generated configuration reference table and already have exact",
        "ground truth.",
        "",
        "**Read here, write in `data/labels/recall_labels.jsonl`.** For each document set",
        "`documents` to the list of settings that section *documents*, and move anything",
        "merely mentioned into `cross_referenced`. `documents: []` is a real answer and",
        "is expected to be common. `documents: null` means not yet judged.",
        "",
        "The question is only *which settings*. Type, scope and default are not asked:",
        "the oracle and the reference table already know them for any name you give.",
        "",
        "---",
        "",
    ]
    for label in labels:
        mark = "x" if label.labelled else " "
        out += [
            f"## [{mark}] `{label.doc_id}`  ·  {label.bucket}",
            "",
            f"- source: `{label.source_path}`",
            f"- heading: {label.heading_path}",
            "- names the detector found: "
            + (", ".join(f"`{c}`" for c in label.candidates) or "_none_"),
            "",
            "```markdown",
            documents.get(label.doc_id, "(missing)").strip(),
            "```",
            "",
        ]
    return "\n".join(out) + "\n"
