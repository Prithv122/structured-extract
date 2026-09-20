"""Score extractions against the oracle. This is where counts become results.

The pilot made the case for this module better than any argument could. On
``narrative-0001`` -- a table headed ``COPY ... TO`` Options -- four of five
arms returned 14 records that were schema-valid and verbatim-grounded, and not
one of the 14 is a setting DuckDB has. ``n_settings=14`` and ``n_settings=14``
looked identical in the run summary whether the model had found fourteen real
settings or invented fourteen. Only the oracle separates them.

Four outcomes that must never be conflated
------------------------------------------
``no_answer``
    The provider errored. Nothing was produced, so the row appears in no
    accuracy denominator at all. Counting it as a zero would punish an arm for
    its host being down.
``failed_extraction``
    The model answered, and the answer never validated -- unparseable,
    schema-violating, ungrounded, or truncated. Also excluded from accuracy,
    but it is the arm's own fault and is reported separately.
``answered_empty``
    A validated empty list. On a document that documents nothing this is the
    **correct** answer and scores as such; on one that does, it is a miss.
``answered``
    Records to score, one by one.

What can and cannot be measured yet
-----------------------------------
Everything on the precision side is exact and needs no human: a returned name
either resolves to something ``duckdb_settings()`` knows or it does not, and
its type and scope either match the binary or they do not.

**Recall does not exist yet** for the prose strata, and this module does not
pretend otherwise. The corpus manifest's ``mentioned_names`` says a name
*appears* in the text, which is not the same as the section documenting it --
that distinction is the whole reason the 40-section hand-label set is on the
plan. Anything computed against it is named ``*_vs_mentioned`` and is a proxy
with a known bias: it cannot go above the truth, so it understates recall.

The ``reference`` stratum is the exception. Each of those 35 documents is a
single row of the generated configuration reference table, so the set of
settings it documents is exactly one, and it is recoverable from the row
itself. Those documents are scored for real precision *and* real recall.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import StrEnum

from structured_extract import jsonl, paths
from structured_extract import schema as S
from structured_extract.corpus import DISTRACTOR_NAMES
from structured_extract.extract import NO_ANSWER, Outcome

#: Outcomes where the model answered but nothing validated. Its own failure,
#: unlike NO_ANSWER, and kept apart from it in every report.
FAILED = frozenset({Outcome.INVALID_AFTER_REPAIR, Outcome.UNPARSEABLE, Outcome.LENGTH_TRUNCATED})

#: Settings whose documented default is a property of the machine, not of
#: DuckDB. ``threads`` is the host's core count, ``max_memory`` a fraction of
#: its RAM, ``TimeZone`` and ``Calendar`` the host locale. The reference table
#: documents the *rule* ("80% of RAM"), so no extracted literal can be scored
#: against it and these are excluded from default accuracy rather than counted
#: wrong. Curated deliberately: a regex over the default column also matches
#: ``custom_profiling_settings``, whose default merely contains the word
#: SYSTEM_PEAK_BUFFER_MEMORY, and that one is a perfectly fixed JSON blob.
MACHINE_DEPENDENT = frozenset(
    {
        "Calendar",
        "TimeZone",
        "max_memory",
        "memory_limit",
        "max_temp_directory_size",
        "threads",
    }
)

#: First cell of a markdown table row: ``| `access_mode` | ...``.
_FIRST_CELL = re.compile(r"^\|\s*`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\|")


class Status(StrEnum):
    """Which of the four outcomes this (document, arm, prompt) had."""

    NO_ANSWER = "no_answer"
    FAILED_EXTRACTION = "failed_extraction"
    ANSWERED_EMPTY = "answered_empty"
    ANSWERED = "answered"


@dataclass(frozen=True)
class Oracle:
    """``duckdb_settings()`` and the reference table, indexed for scoring."""

    #: lowercased label (name or alias) -> canonical setting name
    canonical: dict[str, str]
    #: canonical name -> the binary's row
    settings: dict[str, dict]
    #: canonical name -> the reference table's row, where one exists
    documented: dict[str, dict]

    def resolve(self, name: str) -> str | None:
        """Canonical name for an extracted label, or ``None`` if the binary has none.

        Matching is case-insensitive because DuckDB itself is: ``SET timezone``
        and ``SET TimeZone`` are the same setting, and only two of the 274 names
        (``Calendar``, ``TimeZone``) are not already lowercase. Treating a case
        difference as a hallucination would be a spelling complaint dressed up
        as a correctness measurement.
        """
        return self.canonical.get(name.strip().lower())

    def is_machine_dependent(self, canonical: str) -> bool:
        return canonical in MACHINE_DEPENDENT


def load_oracle() -> Oracle:
    settings = {row["name"]: row for row in jsonl.read_list(paths.SETTINGS_JSONL)}
    canonical: dict[str, str] = {}
    for name, row in settings.items():
        canonical.setdefault(name.lower(), name)
        for alias in row["aliases"]:
            canonical.setdefault(alias.lower(), name)

    documented: dict[str, dict] = {}
    for row in jsonl.read_list(paths.DOCS_REFERENCE_JSONL):
        target = canonical.get(row["name"].lower())
        if target is not None:
            documented.setdefault(target, row)
    return Oracle(canonical=canonical, settings=settings, documented=documented)


@dataclass
class RecordScore:
    """One extracted record, judged."""

    name: str
    canonical: str | None
    #: The binary has no setting by this name or any alias of it.
    hallucinated: bool
    #: ``None`` when hallucinated -- there is nothing to compare against.
    input_type_correct: bool | None
    scope_correct: bool | None
    #: Re-checked here rather than trusted: a row can reach the scorer having
    #: failed validation, and the failure analysis wants to know which part.
    evidence_grounded: bool

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class DocumentScore:
    """One (document, arm, prompt) cell."""

    doc_id: str
    arm: str
    prompt: str
    stratum: str
    status: str
    outcome: str
    records: list[RecordScore] = field(default_factory=list)
    #: Exact ground truth, available only for the reference stratum.
    expected: list[str] = field(default_factory=list)
    #: Proxy ground truth for the prose strata: non-distractor names that appear
    #: in the text. An upper bound on what the section might document.
    mentioned: list[str] = field(default_factory=list)
    #: ``True``/``False`` only for an empty answer; ``None`` otherwise.
    empty_was_correct: bool | None = None
    cost_reported: float = 0.0

    @property
    def scored(self) -> bool:
        return self.status in (Status.ANSWERED, Status.ANSWERED_EMPTY)

    @property
    def n_returned(self) -> int:
        return len(self.records)

    @property
    def n_hallucinated(self) -> int:
        return sum(r.hallucinated for r in self.records)

    @property
    def n_real(self) -> int:
        return sum(not r.hallucinated for r in self.records)

    def to_json(self) -> dict:
        row = asdict(self)
        row["records"] = [r.to_json() for r in self.records]
        row["n_returned"] = self.n_returned
        row["n_hallucinated"] = self.n_hallucinated
        row["n_real"] = self.n_real
        return row


def reference_target(text: str) -> str | None:
    """The single setting a ``reference`` document documents.

    Those documents are a heading, the table header, the separator and exactly
    one data row copied verbatim, so the documented setting is the row's first
    cell. This is real ground truth, not a proxy: 35 of the 120 documents can
    be scored for recall today, without waiting for the hand labels.
    """
    for line in reversed(text.strip().splitlines()):
        match = _FIRST_CELL.match(line.strip())
        if match and not set(line.replace("|", "").strip()) <= {"-", ":", " "}:
            return match.group(1)
    return None


def score_record(record: dict, document: str, oracle: Oracle) -> RecordScore:
    canonical = oracle.resolve(record["name"])
    truth = oracle.settings.get(canonical) if canonical else None
    grounded = S.normalise_whitespace(record["evidence"]) in S.normalise_whitespace(document)
    return RecordScore(
        name=record["name"],
        canonical=canonical,
        hallucinated=canonical is None,
        input_type_correct=None if truth is None else record["input_type"] == truth["input_type"],
        scope_correct=None if truth is None else record["scope"] == truth["scope"],
        evidence_grounded=grounded,
    )


def score_row(row: dict, corpus: dict[str, dict], documents: dict[str, str], oracle: Oracle):
    """Score one results row. ``corpus`` and ``documents`` are keyed by doc_id."""
    meta = corpus[row["doc_id"]]
    text = documents[row["doc_id"]]
    outcome = row["outcome"]

    if outcome in {o.value for o in NO_ANSWER}:
        status = Status.NO_ANSWER
    elif outcome in {o.value for o in FAILED}:
        status = Status.FAILED_EXTRACTION
    elif not row["settings"]:
        status = Status.ANSWERED_EMPTY
    else:
        status = Status.ANSWERED

    expected: list[str] = []
    if meta["stratum"] == "reference":
        target = reference_target(text)
        resolved = oracle.resolve(target) if target else None
        if resolved:
            expected = [resolved]

    # Distractors are excluded: a document whose only "known" name is `schema`
    # is exactly the case where an empty answer is right, and counting those as
    # things to find would invert the distractor strata's purpose.
    mentioned = sorted(
        {
            c
            for name in meta["mentioned_names"]
            if name not in DISTRACTOR_NAMES and (c := oracle.resolve(name))
        }
    )

    score = DocumentScore(
        doc_id=row["doc_id"],
        arm=row["arm"],
        prompt=row["prompt"],
        stratum=meta["stratum"],
        status=status.value,
        outcome=outcome,
        records=[score_record(r, text, oracle) for r in row["settings"]],
        expected=expected,
        mentioned=mentioned,
        cost_reported=row["cost_reported"],
    )
    if status is Status.ANSWERED_EMPTY:
        # Empty is right when there was nothing to find. For a reference
        # document that is never true; for prose, the proxy is the best
        # available answer until the hand labels exist.
        target_set = expected if meta["stratum"] == "reference" else mentioned
        score.empty_was_correct = not target_set
    return score


def score_all(results: list[dict]) -> list[DocumentScore]:
    oracle = load_oracle()
    corpus = {row["doc_id"]: row for row in jsonl.read_list(paths.CORPUS_JSONL)}
    documents = {
        doc_id: (paths.CORPUS_DOCUMENTS / f"{doc_id}.md").read_text(encoding="utf-8")
        for doc_id in {row["doc_id"] for row in results}
    }
    return [score_row(row, corpus, documents, oracle) for row in results]


@dataclass
class Summary:
    """Aggregate for one (arm, prompt) cell. Every rate names its denominator."""

    arm: str
    prompt: str
    n_documents: int
    no_answer: int
    failed_extraction: int
    answered_empty: int
    answered: int
    records_returned: int
    records_hallucinated: int
    records_grounded: int
    type_correct: int
    scope_correct: int
    #: Denominator for type/scope: records that resolved to a real setting.
    records_real: int
    empty_correct: int
    empty_wrong: int
    #: Reference stratum only, where ground truth is exact.
    reference_expected: int
    reference_found: int
    #: Prose strata, proxy only.
    mentioned_expected: int
    mentioned_found: int
    cost_reported: float

    @property
    def availability(self) -> float:
        """Share of documents that produced a validated answer of any kind."""
        return (self.answered + self.answered_empty) / self.n_documents if self.n_documents else 0.0

    @property
    def hallucination_rate(self) -> float:
        """Share of returned records the binary has never heard of."""
        return self.records_hallucinated / self.records_returned if self.records_returned else 0.0

    @property
    def type_accuracy(self) -> float:
        return self.type_correct / self.records_real if self.records_real else 0.0

    @property
    def scope_accuracy(self) -> float:
        return self.scope_correct / self.records_real if self.records_real else 0.0

    @property
    def grounding_rate(self) -> float:
        return self.records_grounded / self.records_returned if self.records_returned else 0.0

    @property
    def reference_recall(self) -> float:
        """Real recall. 35 documents, exact ground truth, no human needed."""
        return self.reference_found / self.reference_expected if self.reference_expected else 0.0

    @property
    def recall_vs_mentioned(self) -> float:
        """A proxy, and biased low. See the module docstring before quoting it."""
        return self.mentioned_found / self.mentioned_expected if self.mentioned_expected else 0.0

    def to_json(self) -> dict:
        row = asdict(self)
        row.update(
            availability=round(self.availability, 4),
            hallucination_rate=round(self.hallucination_rate, 4),
            type_accuracy=round(self.type_accuracy, 4),
            scope_accuracy=round(self.scope_accuracy, 4),
            grounding_rate=round(self.grounding_rate, 4),
            reference_recall=round(self.reference_recall, 4),
            recall_vs_mentioned=round(self.recall_vs_mentioned, 4),
        )
        return row


def summarise(scores: list[DocumentScore]) -> list[Summary]:
    """One row per (arm, prompt), in the order the arms were run."""
    out: list[Summary] = []
    for arm, prompt in dict.fromkeys((s.arm, s.prompt) for s in scores):
        cell = [s for s in scores if s.arm == arm and s.prompt == prompt]
        counts = Counter(s.status for s in cell)
        records = [r for s in cell for r in s.records]
        real = [r for r in records if not r.hallucinated]

        found_reference = sum(
            1
            for s in cell
            if s.stratum == "reference"
            and s.expected
            and s.expected[0] in {r.canonical for r in s.records}
        )
        expected_reference = sum(1 for s in cell if s.stratum == "reference" and s.expected)

        prose = [s for s in cell if s.stratum != "reference"]
        mentioned_expected = sum(len(s.mentioned) for s in prose)
        mentioned_found = sum(
            len(set(s.mentioned) & {r.canonical for r in s.records if r.canonical}) for s in prose
        )

        out.append(
            Summary(
                arm=arm,
                prompt=prompt,
                n_documents=len(cell),
                no_answer=counts.get(Status.NO_ANSWER.value, 0),
                failed_extraction=counts.get(Status.FAILED_EXTRACTION.value, 0),
                answered_empty=counts.get(Status.ANSWERED_EMPTY.value, 0),
                answered=counts.get(Status.ANSWERED.value, 0),
                records_returned=len(records),
                records_hallucinated=sum(r.hallucinated for r in records),
                records_grounded=sum(r.evidence_grounded for r in records),
                type_correct=sum(bool(r.input_type_correct) for r in real),
                scope_correct=sum(bool(r.scope_correct) for r in real),
                records_real=len(real),
                empty_correct=sum(1 for s in cell if s.empty_was_correct is True),
                empty_wrong=sum(1 for s in cell if s.empty_was_correct is False),
                reference_expected=expected_reference,
                reference_found=found_reference,
                mentioned_expected=mentioned_expected,
                mentioned_found=mentioned_found,
                cost_reported=round(sum(s.cost_reported for s in cell), 6),
            )
        )
    return out
